"""
Liveness Detection Challenge System

This module implements a facial liveness detection system that combines active challenges
(blink, head movements, smile) with passive liveness detection using rPPG (remote
photoplethysmography) from cheek regions. The system uses MediaPipe for facial landmark
detection and OpenCV for video processing.

Passive liveness uses the Sync_rPPG pipeline:
  green channel → detrend (low-pass subtraction) → bandpass (0.7-4.0 Hz)
  → DWT (db4) → quality metrics (SNR, PSD, MAD, STD, PCC)

Features:
- Random sequence of active liveness challenges
- Passive liveness verification using heart rate detection from video
- OTP fallback for failed or timed-out challenges
- Real-time video feedback with status display
"""
import sys
import cv2
import mediapipe as mp
import numpy as np
import random
import time
from collections import deque
from scipy.signal import welch
from otp import OTPService
from rppg import (
    detrend_signal,
    compute_correlation,
    compute_mad,
    compute_psd_and_snr,
    compute_std,
    estimate_fps,
    bandpass_filter,
    has_motion_artifact,
    preprocess_rppg,
    apply_dwt,
)
from inference import predict_features
import matplotlib.pyplot as plt

# Initialize OTP service for fallback authentication
otp_service = OTPService()

# Session configuration
timeout_seconds    = 60   # Challenge timeout in seconds
session_start_time = time.time()

# Challenge state flags
challenge_verified   = False
challenge_invalidated = False
otp_mode    = False
otp_sent    = False
otp_verified = False

# MediaPipe face mesh for landmark detection
mp_face_mesh = mp.solutions.face_mesh

# Facial landmark indices for different features
# Eye landmarks for blink detection
LEFT_EYE  = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]

# Mouth landmarks for smile detection
LEFT_MOUTH   = 61
RIGHT_MOUTH  = 291
TOP_LIP      = 13
BOTTOM_LIP   = 14

# Thresholds for active liveness detection
EAR_THRESHOLD    = 0.22   # Eye aspect ratio threshold for blink detection
EAR_CONSEC_FRAMES = 2     # Consecutive frames below threshold to count as blink

HEAD_X_THRESHOLD      = 0.05   # Head turn threshold (normalized coordinates)
HEAD_Y_THRESHOLD      = 0.04   # Head tilt threshold (normalized coordinates)
SMILE_RATIO_THRESHOLD = 10     # Mouth width/height ratio for smile detection
ACTION_CONFIRM_FRAMES = 5      # Frames action must be held to confirm

# Passive liveness settings using rPPG
RPPG_WINDOW_SECONDS      = 8     # Sliding-window duration for rPPG analysis
PASSIVE_LIVENESS_THRESHOLD = 0.35 # Correlation threshold for passive liveness

# Signal buffers for rPPG analysis
left_cheek_signal  = []   # Green channel values from left cheek ROI
right_cheek_signal = []   # Green channel values from right cheek ROI
signal_times       = []   # Timestamps for signal samples
MIN_SIGNAL_LENGTH  = 60

# ── Passive fake detection: rolling probability smoother ─────────────────────
# Collects per-frame ML fake probabilities and triggers OTP when the rolling
# average stays high enough for long enough — ignores single-frame spikes.
FAKE_PROB_WINDOW    = 15    # rolling window size (frames)
FAKE_PROB_MIN_FILLS = 10    # minimum predictions before a verdict is possible
FAKE_PROB_THRESHOLD = 0.55  # avg fake prob above this → flag as suspected fake
fake_prob_history   = deque(maxlen=FAKE_PROB_WINDOW)   # rolling buffer
passive_fake_triggered = False   # latched once OTP is forced by passive check

# Available random actions for active liveness challenges
ALL_ACTIONS = [
    "blink_twice",
    "turn_left",
    "turn_right",
    "look_up",
    "look_down",
    "smile"
]

# Randomly choose how many actions and their order for this session
num_actions        = random.choice([4, 5, 6])
challenge_sequence = random.sample(ALL_ACTIONS, k=num_actions)

# Blink detection state
blink_counter  = 0   # Consecutive frames with low EAR
blink_total    = 0   # Total blinks detected
blink_baseline = 0   # Baseline blink count for current action

# Challenge progress tracking
current_step       = 0   # Current step in challenge sequence
action_hold_counter = 0  # Frames current action has been held


def euclidean(p1, p2):
    """
    Calculate the Euclidean distance between two points.

    Args:
        p1: First point as (x, y) tuple or array
        p2: Second point as (x, y) tuple or array

    Returns:
        float: Euclidean distance between the points
    """
    return np.linalg.norm(np.array(p1) - np.array(p2))


def eye_aspect_ratio(eye_points):
    """
    Calculate the eye aspect ratio (EAR) for blink detection.

    EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)

    Args:
        eye_points: List of 6 eye landmark points [(x,y), ...]

    Returns:
        float: Eye aspect ratio, 0.0 if denominator is zero
    """
    p1, p2, p3, p4, p5, p6 = eye_points
    A = euclidean(p2, p6)
    B = euclidean(p3, p5)
    C = euclidean(p1, p4)
    if C == 0:
        return 0.0
    return (A + B) / (2.0 * C)


def get_landmark_coords(face_landmarks, w, h, indices):
    """
    Extract pixel coordinates for specified facial landmark indices.

    Args:
        face_landmarks: MediaPipe face landmarks object
        w: Frame width in pixels
        h: Frame height in pixels
        indices: List of landmark indices to extract

    Returns:
        list: List of (x, y) pixel coordinates
    """
    coords = []
    for idx in indices:
        lm = face_landmarks.landmark[idx]
        coords.append((int(lm.x * w), int(lm.y * h)))
    return coords


def get_prompt(action):
    """
    Get the user prompt text for a given action.

    Args:
        action: Action name string

    Returns:
        str: User-friendly prompt text
    """
    prompts = {
        "blink_twice": "Please blink twice",
        "turn_left":   "Turn head left",
        "turn_right":  "Turn head right",
        "look_up":     "Look up",
        "look_down":   "Look down",
        "smile":       "Smile"
    }
    return prompts.get(action, "Show your face")


def get_cheek_rois(face_landmarks, w, h, box_size=40):
    """
    Calculate regions of interest (ROIs) for left and right cheeks for rPPG analysis.

    Uses multiple facial landmarks to compute stable center points for cheek regions,
    then creates square ROIs around these centers for extracting green channel signals.

    Args:
        face_landmarks: MediaPipe face landmarks object
        w: Frame width in pixels
        h: Frame height in pixels
        box_size: Half-size of square ROI in pixels (default: 40)

    Returns:
        tuple: ((left_x1, left_y1, left_x2, left_y2), (right_x1, right_y1, right_x2, right_y2))
               where each tuple represents (x1, y1, x2, y2) bounding box coordinates
    """
    LEFT_CHEEK_CENTER  = [116, 123, 147, 187, 207, 205, 36, 142]
    RIGHT_CHEEK_CENTER = [345, 352, 376, 411, 427, 425, 266, 371]

    left_points  = [(face_landmarks.landmark[i].x * w,
                     face_landmarks.landmark[i].y * h)
                    for i in LEFT_CHEEK_CENTER]
    right_points = [(face_landmarks.landmark[i].x * w,
                     face_landmarks.landmark[i].y * h)
                    for i in RIGHT_CHEEK_CENTER]

    lx = int(np.mean([p[0] for p in left_points]))
    ly = int(np.mean([p[1] for p in left_points]))
    rx = int(np.mean([p[0] for p in right_points]))
    ry = int(np.mean([p[1] for p in right_points]))

    lx -= 10
    rx += 10

    left_roi  = (max(0, lx - box_size), max(0, ly - box_size),
                 min(w, lx + box_size), min(h, ly + box_size))
    right_roi = (max(0, rx - box_size), max(0, ry - box_size),
                 min(w, rx + box_size), min(h, ry + box_size))

    return left_roi, right_roi


# ── Video source ───────────────────────────────────────────────────────────────
video_source = 0
if len(sys.argv) > 1:
    video_source = sys.argv[1]

cap = cv2.VideoCapture(video_source)

# ── Main loop ──────────────────────────────────────────────────────────────────
with mp_face_mesh.FaceMesh(
    static_image_mode=False,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
) as face_mesh:

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame from webcam.")
            break

        if video_source == 0:
            frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]

        rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)

        # Per-frame display defaults
        status_text          = "Show your face"
        passive_corr         = 0.0
        passive_liveness_passed = False

        # Initialise metric variables (safe defaults in case ROI extraction fails)
        left_peak_psd  = 0.0
        right_peak_psd = 0.0
        left_peak_freq = 0.0
        right_peak_freq = 0.0
        left_snr       = 0.0
        right_snr      = 0.0
        left_std       = 0.0
        right_std      = 0.0
        left_mad       = 0.0
        right_mad      = 0.0
        smile_ratio    = 0.0
        freq_diff      = 0.0
        psd_ratio      = 0.0
        std_ratio      = 0.0
        mad_ratio      = 0.0
        snr_ratio      = 0.0

        if challenge_verified:
            status_text = "Challenge passed"

        elif otp_mode:
            status_text = "OTP required. Press V to verify"

        if results.multi_face_landmarks and not challenge_verified and not otp_mode:
            face_landmarks = results.multi_face_landmarks[0]

            # ── Active challenge: eye / head / smile landmarks ─────────────────
            left_eye  = get_landmark_coords(face_landmarks, w, h, LEFT_EYE)
            right_eye = get_landmark_coords(face_landmarks, w, h, RIGHT_EYE)

            left_ear  = eye_aspect_ratio(left_eye)
            right_ear = eye_aspect_ratio(right_eye)
            ear       = (left_ear + right_ear) / 2.0

            nose         = face_landmarks.landmark[1]
            left_face    = face_landmarks.landmark[234]
            right_face   = face_landmarks.landmark[454]
            top_face     = face_landmarks.landmark[10]
            bottom_face  = face_landmarks.landmark[152]

            face_center_x = (left_face.x + right_face.x) / 2.0
            face_center_y = (top_face.y  + bottom_face.y) / 2.0

            offset_x = nose.x - face_center_x
            offset_y = nose.y - face_center_y

            turned_left_now   = offset_x < -HEAD_X_THRESHOLD
            turned_right_now  = offset_x >  HEAD_X_THRESHOLD
            looking_up_now    = offset_y < -HEAD_Y_THRESHOLD
            looking_down_now  = offset_y >  HEAD_Y_THRESHOLD

            mouth_left_lm  = face_landmarks.landmark[LEFT_MOUTH]
            mouth_right_lm = face_landmarks.landmark[RIGHT_MOUTH]
            top_lip_lm     = face_landmarks.landmark[TOP_LIP]
            bottom_lip_lm  = face_landmarks.landmark[BOTTOM_LIP]

            mouth_width  = abs(mouth_right_lm.x - mouth_left_lm.x)
            mouth_height = abs(bottom_lip_lm.y  - top_lip_lm.y)
            smile_ratio  = mouth_width / (mouth_height + 1e-6)
            smiling_now  = smile_ratio < SMILE_RATIO_THRESHOLD

            # ── Passive liveness: Sync_rPPG green-channel accumulation ─────────
            (left_x1, left_y1, left_x2, left_y2), \
            (right_x1, right_y1, right_x2, right_y2) = \
                get_cheek_rois(face_landmarks, w, h)

            left_roi_px  = frame[left_y1:left_y2,  left_x1:left_x2]
            right_roi_px = frame[right_y1:right_y2, right_x1:right_x2]

            if left_roi_px.size > 0 and right_roi_px.size > 0:
                # Sync_rPPG Eq. 1: S_t = (1/N) Σ G_t(i)
                left_green_mean  = float(np.mean(left_roi_px[:, :, 1]))
                right_green_mean = float(np.mean(right_roi_px[:, :, 1]))

                current_time = (time.time()
                                if video_source == 0
                                else cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0)

                left_cheek_signal.append(left_green_mean)
                right_cheek_signal.append(right_green_mean)
                signal_times.append(current_time)

                # Maintain sliding window of RPPG_WINDOW_SECONDS
                while signal_times and (current_time - signal_times[0] > RPPG_WINDOW_SECONDS):
                    signal_times.pop(0)
                    left_cheek_signal.pop(0)
                    right_cheek_signal.pop(0)

                fps_est = estimate_fps(signal_times)

                # Motion artefact check (raw signal, pre-DWT)
                motion_detected = (
                    has_motion_artifact(left_cheek_signal) or
                    has_motion_artifact(right_cheek_signal)
                )

                # ── Sync_rPPG quality metrics ─────────────────────────────────
                # All functions internally apply: detrend → bandpass → DWT (db4)
                passive_corr = compute_correlation(
                    left_cheek_signal, right_cheek_signal, fps_est
                )
                left_std  = compute_std(left_cheek_signal,  fps_est)
                right_std = compute_std(right_cheek_signal, fps_est)
                left_mad  = compute_mad(left_cheek_signal,  fps_est)
                right_mad = compute_mad(right_cheek_signal, fps_est)

                left_peak_freq,  left_peak_psd,  left_snr  = \
                    compute_psd_and_snr(left_cheek_signal,  fps_est)
                right_peak_freq, right_peak_psd, right_snr = \
                    compute_psd_and_snr(right_cheek_signal, fps_est)

                # ── Cross-cheek helper values ─────────────────────────────────
                def _safe_ratio(a, b):
                    a, b = abs(float(a)), abs(float(b))
                    return min(a, b) / (max(a, b) + 1e-9)

                def _safe_diff(a, b):
                    return abs(float(a) - float(b))

                freq_diff = _safe_diff(left_peak_freq,  right_peak_freq)
                psd_ratio = _safe_ratio(left_peak_psd,  right_peak_psd)
                std_ratio = _safe_ratio(left_std,        right_std)
                mad_ratio = _safe_ratio(left_mad,        right_mad)
                snr_ratio = _safe_ratio(left_snr,        right_snr)

                # ── DWT energy features ───────────────────────────────────────
                left_dwt  = preprocess_rppg(left_cheek_signal,  fps_est)
                right_dwt = preprocess_rppg(right_cheek_signal, fps_est)

                dwt_energy_left  = float(np.sum(left_dwt  ** 2))
                dwt_energy_right = float(np.sum(right_dwt ** 2))
                dwt_energy_ratio = _safe_ratio(dwt_energy_left, dwt_energy_right)
                dwt_var_left     = float(np.var(left_dwt))
                dwt_var_right    = float(np.var(right_dwt))

                # ── Feature dict for ML classifier ───────────────────────────
                features = {
                    # Metadata
                    "fps_est"            : fps_est if fps_est else 0.0,
                    "num_signal_samples" : len(left_cheek_signal),

                    # Core synchronisation
                    "corr"               : passive_corr,
                    "corr_squared"       : passive_corr ** 2,

                    # STD / MAD (DWT-based)
                    "left_std"           : left_std,
                    "right_std"          : right_std,
                    "left_mad"           : left_mad,
                    "right_mad"          : right_mad,

                    # Frequency / PSD / SNR
                    "left_peak_freq"     : left_peak_freq,
                    "right_peak_freq"    : right_peak_freq,
                    "left_peak_psd"      : left_peak_psd,
                    "right_peak_psd"     : right_peak_psd,
                    "left_snr"           : left_snr,
                    "right_snr"          : right_snr,

                    # Cross-cheek diffs
                    "freq_diff"          : freq_diff,
                    "psd_diff"           : _safe_diff(left_peak_psd,  right_peak_psd),
                    "std_diff"           : _safe_diff(left_std,        right_std),
                    "mad_diff"           : _safe_diff(left_mad,        right_mad),
                    "snr_diff"           : _safe_diff(left_snr,        right_snr),

                    # Cross-cheek ratios
                    "psd_ratio"          : psd_ratio,
                    "std_ratio"          : std_ratio,
                    "mad_ratio"          : mad_ratio,
                    "snr_ratio"          : snr_ratio,
                    "freq_ratio"         : _safe_ratio(left_peak_freq, right_peak_freq),

                    # DWT energy (wavelet-domain features)
                    "dwt_energy_left"    : dwt_energy_left,
                    "dwt_energy_right"   : dwt_energy_right,
                    "dwt_energy_ratio"   : dwt_energy_ratio,
                    "dwt_energy_diff"    : _safe_diff(dwt_energy_left, dwt_energy_right),
                    "dwt_var_left"       : dwt_var_left,
                    "dwt_var_right"      : dwt_var_right,
                    "dwt_var_ratio"      : _safe_ratio(dwt_var_left,   dwt_var_right),
                    "dwt_var_diff"       : _safe_diff(dwt_var_left,    dwt_var_right),
                }

                # ── ML prediction + rolling smoother ─────────────────────────
                if len(left_cheek_signal) >= 50:
                    pred, fake_prob = predict_features(features)
                    fake_prob_history.append(fake_prob)

                    n_preds  = len(fake_prob_history)
                    avg_prob = float(np.mean(fake_prob_history))

                    # ── Fake detection verdict ────────────────────────────────
                    # Only act once we have enough predictions to be confident,
                    # and only latch once (passive_fake_triggered prevents
                    # repeated OTP sends on the same session).
                    if (
                        not passive_fake_triggered
                        and not otp_mode
                        and n_preds >= FAKE_PROB_MIN_FILLS
                        and avg_prob >= FAKE_PROB_THRESHOLD
                    ):
                        passive_fake_triggered = True
                        otp_mode = True
                        if not otp_sent:
                            otp_service.send_otp()
                            otp_sent = True
                        print(
                            f"\n⚠  Passive liveness FAILED — "
                            f"avg fake prob = {avg_prob:.2f} "
                            f"over {n_preds} frames "
                            f"(threshold {FAKE_PROB_THRESHOLD}). "
                            f"Forcing OTP verification.\n"
                        )

                    # ── HUD: rolling-average bar ──────────────────────────────
                    bar_w  = int(avg_prob * 160)          # 0–160 px bar
                    bar_col = (
                        (0, 60, 255)   if avg_prob >= FAKE_PROB_THRESHOLD
                        else (0, 200, 80)
                    )
                    cv2.rectangle(frame, (20, 338), (180, 352), (60, 60, 60), -1)
                    cv2.rectangle(frame, (20, 338), (20 + bar_w, 352), bar_col, -1)
                    cv2.putText(
                        frame,
                        f"Avg fake ({n_preds}f): {avg_prob:.2f}",
                        (20, 333),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        bar_col, 2,
                    )

                # Draw cheek ROI overlays
                cv2.rectangle(frame,
                               (left_x1,  left_y1),  (left_x2,  left_y2),
                               (255, 0, 0), 2)
                cv2.rectangle(frame,
                               (right_x1, right_y1), (right_x2, right_y2),
                               (0, 255, 0), 2)

            # ── Timeout / active challenge logic ──────────────────────────────
            elapsed = time.time() - session_start_time

            if elapsed > timeout_seconds:
                challenge_invalidated = True
                otp_mode = True
                if not otp_sent:
                    otp_service.send_otp()
                    otp_sent = True
                status_text = "Challenge timed out. OTP sent."

            elif current_step < len(challenge_sequence):
                current_action = challenge_sequence[current_step]
                status_text    = get_prompt(current_action)
                action_detected = False

                if current_action == "blink_twice":
                    if ear < EAR_THRESHOLD:
                        blink_counter += 1
                    else:
                        if blink_counter >= EAR_CONSEC_FRAMES:
                            blink_total += 1
                            print(f"Blink detected. Total blinks: {blink_total}")
                        blink_counter = 0
                    if blink_total - blink_baseline >= 2:
                        action_detected = True

                elif current_action == "turn_left":
                    action_detected = turned_left_now

                elif current_action == "turn_right":
                    action_detected = turned_right_now

                elif current_action == "look_up":
                    action_detected = looking_up_now

                elif current_action == "look_down":
                    action_detected = looking_down_now

                elif current_action == "smile":
                    action_detected = smiling_now

                if current_action == "blink_twice":
                    if action_detected:
                        blink_baseline = blink_total
                        current_step  += 1
                        action_hold_counter = 0
                else:
                    if action_detected:
                        action_hold_counter += 1
                    else:
                        action_hold_counter = 0
                    if action_hold_counter >= ACTION_CONFIRM_FRAMES:
                        current_step += 1
                        action_hold_counter = 0

            else:
                challenge_verified = True
                if passive_liveness_passed:
                    status_text = "Challenge passed + passive liveness OK"
                else:
                    status_text = "Challenge passed"

            # ── HUD overlays ──────────────────────────────────────────────────
            cv2.putText(frame, f"Blinks: {blink_total}", (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            cv2.putText(frame, f"Smile ratio: {smile_ratio:.2f}", (20, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            cv2.putText(frame,
                        f"Step: {min(current_step+1, len(challenge_sequence))}"
                        f"/{len(challenge_sequence)}",
                        (20, 180),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 255, 200), 2)
            cv2.putText(frame, f"L-PSD: {left_peak_psd:.4f}", (20, 200),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
            cv2.putText(frame, f"R-PSD: {right_peak_psd:.4f}", (20, 220),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
            cv2.putText(frame, f"Corr (DWT): {passive_corr:.2f}", (20, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
            cv2.putText(frame,
                        f"Passive: {'OK' if passive_liveness_passed else 'Weak'}",
                        (20, 260),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)

        # ── Status banner ──────────────────────────────────────────────────────
        cv2.putText(frame, status_text, (20, 280),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

        cv2.imshow("Challenge Response Liveness", frame)

        delay = 1 if video_source == 0 else 30
        key   = cv2.waitKey(delay) & 0xFF

        # ── OTP verification ───────────────────────────────────────────────────
        if key == ord("v") and otp_mode and not otp_verified:
            user_otp = input("Enter OTP sent to your email: ").strip()
            if otp_service.verify_otp(user_otp):
                otp_verified       = True
                challenge_verified = True
                otp_mode           = False
                print("Access granted.")
            else:
                print("Invalid OTP.")

        # ── Debug plot (key: d) ────────────────────────────────────────────────
        elif key == ord("d") and len(left_cheek_signal) > 30:
            fps_est = estimate_fps(signal_times)

            l_raw  = np.array(left_cheek_signal)
            r_raw  = np.array(right_cheek_signal)

            # Bandpass-filtered signals (for raw visualisation)
            l_filt = bandpass_filter(detrend_signal(l_raw, fps_est), fps_est)
            r_filt = bandpass_filter(detrend_signal(r_raw, fps_est), fps_est)

            # DWT approximation coefficients (Sync_rPPG representation)
            l_dwt  = preprocess_rppg(l_raw, fps_est)
            r_dwt  = preprocess_rppg(r_raw, fps_est)

            corr_raw = float(np.corrcoef(l_filt, r_filt)[0, 1])
            min_len  = min(len(l_dwt), len(r_dwt))
            corr_dwt = float(np.corrcoef(l_dwt[:min_len], r_dwt[:min_len])[0, 1])

            fig, axes = plt.subplots(4, 1, figsize=(11, 10))

            # Plot 1: raw green-channel signals
            axes[0].plot(l_raw - np.mean(l_raw), label='Left raw',  alpha=0.6)
            axes[0].plot(r_raw - np.mean(r_raw), label='Right raw', alpha=0.6)
            axes[0].set_title('Raw green-channel signals (mean-removed)')
            axes[0].legend()

            # Plot 2: detrended + bandpassed signals
            axes[1].plot(l_filt, label='Left filtered',  alpha=0.7)
            axes[1].plot(r_filt, label='Right filtered', alpha=0.7)
            axes[1].set_title(
                f'Detrended + bandpassed (0.7–4.0 Hz) — corr: {corr_raw:.3f}'
            )
            axes[1].legend()

            # Plot 3: DWT (db4) approximation coefficients
            axes[2].plot(l_dwt, label='Left DWT cA',  alpha=0.8, color='steelblue')
            axes[2].plot(r_dwt, label='Right DWT cA', alpha=0.8, color='darkorange')
            axes[2].set_title(
                f'DWT db4 approximation coefficients — PCC: {corr_dwt:.3f}'
            )
            axes[2].legend()

            # Plot 4: Welch PSD of bandpassed signals
            fl, pl = welch(l_filt, fs=fps_est, nperseg=min(len(l_filt), 64))
            fr, pr = welch(r_filt, fs=fps_est, nperseg=min(len(r_filt), 64))
            axes[3].plot(fl, pl, label='Left PSD',  color='steelblue')
            axes[3].plot(fr, pr, label='Right PSD', color='darkorange')
            axes[3].axvspan(0.7, 4.0, alpha=0.1, color='green',
                            label='HR band (0.7–4.0 Hz)')
            axes[3].set_xlim(0, 5)
            axes[3].set_title('Power Spectral Density (bandpassed signal)')
            axes[3].legend()

            plt.tight_layout()
            plt.savefig('rppg_debug.png')
            plt.show()

            print(f"\n── Sync_rPPG Debug ────────────────────────────────")
            print(f"FPS           : {fps_est:.1f}")
            print(f"Signal length : {len(left_cheek_signal)} samples")
            print(f"Corr (raw bp) : {corr_raw:.3f}")
            print(f"Corr (DWT)    : {corr_dwt:.3f}   (real≈0.72, fake≈0.08)")
            print(f"Left  freq    : {left_peak_freq:.2f} Hz  |  SNR: {left_snr:.1f} dB")
            print(f"Right freq    : {right_peak_freq:.2f} Hz  |  SNR: {right_snr:.1f} dB")
            print(f"Freq diff     : {freq_diff:.3f}")
            print(f"PSD ratio     : {psd_ratio:.3f}")
            print(f"STD ratio     : {std_ratio:.3f}")
            print(f"MAD ratio     : {mad_ratio:.3f}")
            print(f"SNR ratio     : {snr_ratio:.3f}")
            print(f"────────────────────────────────────────────────────\n")

        # ── Reset (key: r) ────────────────────────────────────────────────────
        elif key == ord("r"):
            num_actions        = random.choice([4, 5, 6])
            challenge_sequence = random.sample(ALL_ACTIONS, k=num_actions)

            blink_counter       = 0
            blink_total         = 0
            blink_baseline      = 0
            current_step        = 0
            action_hold_counter = 0

            left_cheek_signal  = []
            right_cheek_signal = []
            signal_times       = []

            fake_prob_history.clear()
            passive_fake_triggered = False

            session_start_time    = time.time()
            challenge_verified    = False
            challenge_invalidated = False
            otp_mode              = False
            otp_sent              = False
            otp_verified          = False

            otp_service.reset()
            print("Challenge reset:", challenge_sequence)

        elif key == ord("q"):
            break

# Clean up resources
cap.release()
cv2.destroyAllWindows()
