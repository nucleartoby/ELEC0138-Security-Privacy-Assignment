"""
Liveness Detection Challenge System

This module implements a facial liveness detection system that combines active challenges
(blink, head movements, smile) with passive liveness detection using rPPG (remote
photoplethysmography) from cheek regions. The system uses MediaPipe for facial landmark
detection and OpenCV for video processing.

Features:
- Random sequence of active liveness challenges
- Passive liveness verification using heart rate detection from video
- OTP fallback for failed or timed-out challenges
- Real-time video feedback with status display
"""

import cv2
import mediapipe as mp
import numpy as np
import random
import time
from scipy.signal import welch
from scipy.stats import median_abs_deviation
from otp import OTPService
from rppg import detrend_signal, compute_correlation, compute_mad, compute_psd_and_snr, compute_std, estimate_fps, bandpass_filter, has_motion_artifact
import matplotlib.pyplot as plt

# Initialize OTP service for fallback authentication
otp_service = OTPService()

# Session configuration
timeout_seconds = 60  # Challenge timeout in seconds
session_start_time = time.time()

# Challenge state flags
challenge_verified = False
challenge_invalidated = False
otp_mode = False
otp_sent = False
otp_verified = False

# MediaPipe face mesh for landmark detection
mp_face_mesh = mp.solutions.face_mesh

# Facial landmark indices for different features
# Eye landmarks for blink detection
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]

# Mouth landmarks for smile detection
LEFT_MOUTH = 61
RIGHT_MOUTH = 291
TOP_LIP = 13
BOTTOM_LIP = 14

# Thresholds for active liveness detection
EAR_THRESHOLD = 0.22  # Eye aspect ratio threshold for blink detection
EAR_CONSEC_FRAMES = 2  # Consecutive frames below threshold to count as blink

HEAD_X_THRESHOLD = 0.05  # Head turn threshold (normalized coordinates)
HEAD_Y_THRESHOLD = 0.04  # Head tilt threshold (normalized coordinates)
SMILE_RATIO_THRESHOLD = 10  # Mouth width/height ratio for smile detection
ACTION_CONFIRM_FRAMES = 5  # Frames action must be held to confirm

# Passive liveness settings using rPPG
RPPG_WINDOW_SECONDS = 8  # Time window for rPPG signal analysis
PASSIVE_LIVENESS_THRESHOLD = 0.35  # Correlation threshold for passive liveness

# Signal buffers for rPPG analysis
left_cheek_signal = []  # Green channel values from left cheek ROI
right_cheek_signal = []  # Green channel values from right cheek ROI
signal_times = []  # Timestamps for signal samples

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
num_actions = random.choice([4, 5, 6])
challenge_sequence = random.sample(ALL_ACTIONS, k=num_actions)

# Blink detection state
blink_counter = 0  # Consecutive frames with low EAR
blink_total = 0    # Total blinks detected
blink_baseline = 0 # Baseline blink count for current action

# Challenge progress tracking
current_step = 0  # Current step in challenge sequence
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
        "turn_left": "Turn head left",
        "turn_right": "Turn head right",
        "look_up": "Look up",
        "look_down": "Look down",
        "smile": "Smile"
    }
    return prompts.get(action, "Show your face")
        "look_down": "Look down",
        "smile": "Smile"
    }
    return prompts.get(action, "Show your face")


def get_cheek_rois(face_landmarks, w, h, box_size=40):  # increased from 30
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
    # More landmarks averaged = more stable center point under head tilt
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

    # Push boxes outward away from nose by 15px
    lx -= 15
    rx += 15

    left_roi  = (max(0, lx-box_size), max(0, ly-box_size),
                 min(w, lx+box_size), min(h, ly+box_size))
    right_roi = (max(0, rx-box_size), max(0, ry-box_size),
                 min(w, rx+box_size), min(h, ry+box_size))

    return left_roi, right_roi








# Initialize video capture from webcam
cap = cv2.VideoCapture(0)

# Initialize MediaPipe FaceMesh for facial landmark detection
with mp_face_mesh.FaceMesh(
    static_image_mode=False,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
) as face_mesh:

    while True:
        # Capture frame from webcam
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame from webcam.")
            break

        # Flip frame horizontally for mirror effect
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]

        # Convert to RGB for MediaPipe processing
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)

        # Initialize status variables
        status_text = "Show your face"
        passive_corr = 0.0
        passive_liveness_passed = False

        # Check if challenge is already completed
        if challenge_verified:
            status_text = "Challenge passed"

        elif otp_mode:
            status_text = "OTP required. Press V to verify"

        # Process facial landmarks if face detected and challenge not complete
        if results.multi_face_landmarks and not challenge_verified and not otp_mode:
            face_landmarks = results.multi_face_landmarks[0]

            # Extract eye landmarks and calculate eye aspect ratio for blink detection
            left_eye = get_landmark_coords(face_landmarks, w, h, LEFT_EYE)
            right_eye = get_landmark_coords(face_landmarks, w, h, RIGHT_EYE)

            left_ear = eye_aspect_ratio(left_eye)
            right_ear = eye_aspect_ratio(right_eye)
            ear = (left_ear + right_ear) / 2.0

            # Calculate head pose offsets for turn/look detection
            nose = face_landmarks.landmark[1]
            left_face = face_landmarks.landmark[234]
            right_face = face_landmarks.landmark[454]
            top_face = face_landmarks.landmark[10]
            bottom_face = face_landmarks.landmark[152]

            face_center_x = (left_face.x + right_face.x) / 2.0
            face_center_y = (top_face.y + bottom_face.y) / 2.0

            offset_x = nose.x - face_center_x
            offset_y = nose.y - face_center_y

            turned_left_now = offset_x < -HEAD_X_THRESHOLD
            turned_right_now = offset_x > HEAD_X_THRESHOLD
            looking_up_now = offset_y < -HEAD_Y_THRESHOLD
            looking_down_now = offset_y > HEAD_Y_THRESHOLD

            # Extract mouth landmarks and calculate smile ratio
            mouth_left = face_landmarks.landmark[LEFT_MOUTH]
            mouth_right = face_landmarks.landmark[RIGHT_MOUTH]
            top_lip = face_landmarks.landmark[TOP_LIP]
            bottom_lip = face_landmarks.landmark[BOTTOM_LIP]

            mouth_width = abs(mouth_right.x - mouth_left.x)
            mouth_height = abs(bottom_lip.y - top_lip.y)
            smile_ratio = mouth_width / (mouth_height + 1e-6)

            # Keep your original logic for now
            smiling_now = smile_ratio < SMILE_RATIO_THRESHOLD

            # Passive liveness: cheek-based rPPG correlation
            (left_x1, left_y1, left_x2, left_y2), (right_x1, right_y1, right_x2, right_y2) = get_cheek_rois(face_landmarks, w, h)

            left_roi = frame[left_y1:left_y2, left_x1:left_x2]
            right_roi = frame[right_y1:right_y2, right_x1:right_x2]

            if left_roi.size > 0 and right_roi.size > 0:
                left_green_mean = np.mean(left_roi[:, :, 1])
                right_green_mean = np.mean(right_roi[:, :, 1])
                current_time = time.time()

                left_cheek_signal.append(left_green_mean)
                right_cheek_signal.append(right_green_mean)
                signal_times.append(current_time)

                # Maintain sliding window of RPPG_WINDOW_SECONDS
                while signal_times and (current_time - signal_times[0] > RPPG_WINDOW_SECONDS):
                    signal_times.pop(0)
                    left_cheek_signal.pop(0)
                    right_cheek_signal.pop(0)

                fps_est = estimate_fps(signal_times)

                # --- MOTION ARTIFACT CHECK GOES HERE ---
                motion_detected = (
                    has_motion_artifact(left_cheek_signal) or
                    has_motion_artifact(right_cheek_signal)
                )

                if motion_detected:
                    # Reset signals on motion — don't compute metrics on corrupt window
                    left_cheek_signal.clear()
                    right_cheek_signal.clear()
                    signal_times.clear()
                    passive_liveness_passed = False
                    passive_corr = 0.0
                    left_peak_freq = right_peak_freq = 0.0
                    left_peak_psd = right_peak_psd = 0.0
                    left_snr = right_snr = 0.0
                    left_std = right_std = 0.0
                    left_mad = right_mad = 0.0
                    cv2.putText(frame, "Motion detected - hold still", (20, 300),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                else:
                    # Only compute metrics on clean windows
                    passive_corr = compute_correlation(left_cheek_signal, right_cheek_signal, fps_est)
                    left_std  = compute_std(left_cheek_signal, fps_est)
                    right_std = compute_std(right_cheek_signal, fps_est)
                    left_mad  = compute_mad(left_cheek_signal, fps_est)
                    right_mad = compute_mad(right_cheek_signal, fps_est)
                    left_peak_freq,  left_peak_psd,  left_snr  = compute_psd_and_snr(left_cheek_signal,  fps_est)
                    right_peak_freq, right_peak_psd, right_snr = compute_psd_and_snr(right_cheek_signal, fps_est)

                    # Helper functions for ratio calculations
                    def safe_ratio(a, b):
                        a, b = abs(float(a)), abs(float(b))
                        return min(a, b) / (max(a, b) + 1e-6)

                    def safe_diff(a, b):
                        return abs(a - b)

                    # Calculate various signal quality metrics
                    freq_diff = safe_diff(left_peak_freq, right_peak_freq)
                    psd_ratio = safe_ratio(left_peak_psd, right_peak_psd)
                    std_ratio = safe_ratio(left_std, right_std)
                    mad_ratio = safe_ratio(left_mad, right_mad)
                    snr_ratio = safe_ratio(left_snr, right_snr)

                    # Thresholds for passive liveness detection
                    CORR_THRESH      = 0.50
                    FREQ_DIFF_THRESH = 0.20
                    PSD_RATIO_THRESH = 0.45
                    STD_RATIO_THRESH = 0.55
                    MAD_RATIO_THRESH = 0.55
                    SNR_RATIO_THRESH = 0.40
                    MIN_SNR          = -10

                    # Check individual metric conditions
                    corr_ok       = passive_corr >= CORR_THRESH
                    left_pulse_ok  = 0.8 <= left_peak_freq  <= 3.5 and left_snr  >= MIN_SNR
                    right_pulse_ok = 0.8 <= right_peak_freq <= 3.5 and right_snr >= MIN_SNR
                    freq_ok       = freq_diff <= FREQ_DIFF_THRESH
                    psd_ok        = psd_ratio >= PSD_RATIO_THRESH
                    std_ok        = std_ratio >= STD_RATIO_THRESH
                    mad_ok        = mad_ratio >= MAD_RATIO_THRESH
                    snr_ok        = snr_ratio >= SNR_RATIO_THRESH

                    # Hard gate — both cheeks must show valid pulse frequency
                    if not (left_pulse_ok and right_pulse_ok):
                        passive_liveness_passed = False
                    else:
                        # Calculate composite score from all metrics
                        score = (
                            (2 if corr_ok else 0) +
                            freq_ok               +
                            psd_ok                +
                            std_ok                +
                            mad_ok                +
                            snr_ok
                        )
                        # Max score = 7, pass at 5
                        passive_liveness_passed = score >= 5

                        passive_liveness_passed = score >= 5

                cv2.rectangle(frame, (left_x1, left_y1), (left_x2, left_y2), (255, 0, 0), 2)
                cv2.rectangle(frame, (right_x1, right_y1), (right_x2, right_y2), (0, 255, 0), 2)

            # Check for challenge timeout
            elapsed = time.time() - session_start_time

            if elapsed > timeout_seconds:
                challenge_invalidated = True
                otp_mode = True
                if not otp_sent:
                    otp_service.send_otp()
                    otp_sent = True
                status_text = "Challenge timed out. OTP sent."

            elif current_step < len(challenge_sequence):
                # Get current challenge action and display prompt
                current_action = challenge_sequence[current_step]
                status_text = get_prompt(current_action)

                action_detected = False

                # Process different action types
                if current_action == "blink_twice":
                    # Blink detection logic
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

                # Update challenge progress based on action detection
                if current_action == "blink_twice":
                    if action_detected:
                        blink_baseline = blink_total
                        current_step += 1
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
                # All challenges completed
                challenge_verified = True
                if passive_liveness_passed:
                    status_text = "Challenge passed + passive liveness OK"
                else:
                    status_text = "Challenge passed"

            # Display real-time metrics on frame
            cv2.putText(frame, f"Blinks: {blink_total}", (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

            cv2.putText(frame, f"Smile ratio: {smile_ratio:.2f}", (20, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)


            cv2.putText(frame, f"Step: {min(current_step + 1, len(challenge_sequence))}/{len(challenge_sequence)}", (20, 180),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 255, 200), 2)
            
            cv2.putText(frame, f"L-PSD: {left_peak_psd:.4f}", (20, 200),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)

            cv2.putText(frame, f"R-PSD: {right_peak_psd:.4f}", (20, 220),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)

            cv2.putText(frame, f"Corr: {passive_corr:.2f}", (20, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)

            cv2.putText(frame, f"Passive: {'OK' if passive_liveness_passed else 'Weak'}", (20, 260),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)

        # Display main status text
        cv2.putText(frame, status_text, (20, 280),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

        # Show processed frame
        cv2.imshow("Challenge Response Liveness", frame)

        # Handle keyboard input
        key = cv2.waitKey(1) & 0xFF

        # Verify OTP only when timed out and user presses V
        if key == ord("v") and otp_mode and not otp_verified:
            user_otp = input("Enter OTP sent to your email: ").strip()
            if otp_service.verify_otp(user_otp):
                otp_verified = True
                challenge_verified = True
                otp_mode = False
                print("Access granted.")
            else:
                print("Invalid OTP.")


        elif key == ord("d") and len(left_cheek_signal) > 30:
            # Debug mode: display rPPG analysis plots and metrics
            fps_est = estimate_fps(signal_times)
            

            
            l_raw = np.array(left_cheek_signal)
            r_raw = np.array(right_cheek_signal)
            l_filt = bandpass_filter(l_raw, fps_est)
            r_filt = bandpass_filter(r_raw, fps_est)
            
            fig, axes = plt.subplots(3, 1, figsize=(10, 8))
            
            # Plot 1: raw vs filtered signals
            axes[0].plot(l_raw - np.mean(l_raw), label='Left raw', alpha=0.5)
            axes[0].plot(r_raw - np.mean(r_raw), label='Right raw', alpha=0.5)
            axes[0].set_title('Raw green channel signals')
            axes[0].legend()
            
            # Plot 2: bandpassed signals + correlation
            corr = np.corrcoef(l_filt, r_filt)[0,1]
            axes[1].plot(l_filt, label='Left filtered', alpha=0.7)
            axes[1].plot(r_filt, label='Right filtered', alpha=0.7)
            axes[1].set_title(f'Bandpassed signals — correlation: {corr:.3f}')
            axes[1].legend()
            
            # Plot 3: PSD of both cheeks
            from scipy.signal import welch
            fl, pl = welch(l_filt, fs=fps_est, nperseg=min(len(l_filt), 64))
            fr, pr = welch(r_filt, fs=fps_est, nperseg=min(len(r_filt), 64))
            axes[2].plot(fl, pl, label='Left PSD')
            axes[2].plot(fr, pr, label='Right PSD')
            axes[2].plot(fl, pl, label='Left PSD')
            axes[2].plot(fr, pr, label='Right PSD')
            axes[2].axvspan(0.7, 4.0, alpha=0.1, color='green', label='Heart rate band')
            axes[2].set_xlim(0, 5)
            axes[2].set_title('Power Spectral Density')
            axes[2].legend()
            
            plt.tight_layout()
            plt.savefig('rppg_debug.png')
            plt.show()
            
            # Print all metric values
            print(f"FPS: {fps_est:.1f}")
            print(f"Correlation: {passive_corr:.3f}  (thresh: 0.30)")
            print(f"Left freq: {left_peak_freq:.2f} Hz, SNR: {left_snr:.1f} dB")
            print(f"Right freq: {right_peak_freq:.2f} Hz, SNR: {right_snr:.1f} dB")
            print(f"Freq diff: {freq_diff:.3f}  (thresh: 0.50)")
            print(f"PSD ratio: {psd_ratio:.3f}  (thresh: 0.45)")
            print(f"STD ratio: {std_ratio:.3f}  (thresh: 0.55)")
            print(f"MAD ratio: {mad_ratio:.3f}  (thresh: 0.55)")
            print(f"SNR ratio: {snr_ratio:.3f}  (thresh: 0.40)")
            print(f"Score: {score}/7")

        elif key == ord("r"):
            # Reset challenge: generate new sequence and clear all state
            num_actions = random.choice([4, 5, 6])
            challenge_sequence = random.sample(ALL_ACTIONS, k=num_actions)

            blink_counter = 0
            blink_total = 0
            blink_baseline = 0
            current_step = 0
            action_hold_counter = 0

            left_cheek_signal = []
            right_cheek_signal = []
            signal_times = []

            session_start_time = time.time()
            challenge_verified = False
            challenge_invalidated = False
            otp_mode = False
            otp_sent = False
            otp_verified = False

            otp_service.reset()

            print("Challenge reset:", challenge_sequence)

        elif key == ord("q"):
            break

# Clean up resources
cap.release()
cv2.destroyAllWindows()