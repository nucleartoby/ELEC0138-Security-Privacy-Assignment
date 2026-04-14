import os
import cv2
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import mediapipe as mp

from rppg import (
    compute_correlation,
    compute_mad,
    compute_psd_and_snr,
    compute_std,
    estimate_fps,
    has_motion_artifact,
)

mp_face_mesh = mp.solutions.face_mesh

LEFT_CHEEK_CENTER = [116, 123, 147, 187, 207, 205, 36, 142]
RIGHT_CHEEK_CENTER = [345, 352, 376, 411, 427, 425, 266, 371]


def get_cheek_rois(face_landmarks, w, h, box_size=40):
    left_points = [
        (face_landmarks.landmark[i].x * w, face_landmarks.landmark[i].y * h)
        for i in LEFT_CHEEK_CENTER
    ]
    right_points = [
        (face_landmarks.landmark[i].x * w, face_landmarks.landmark[i].y * h)
        for i in RIGHT_CHEEK_CENTER
    ]

    lx = int(np.mean([p[0] for p in left_points])) - 10
    ly = int(np.mean([p[1] for p in left_points]))
    rx = int(np.mean([p[0] for p in right_points])) + 10
    ry = int(np.mean([p[1] for p in right_points]))

    left_roi = (
        max(0, lx - box_size),
        max(0, ly - box_size),
        min(w, lx + box_size),
        min(h, ly + box_size),
    )
    right_roi = (
        max(0, rx - box_size),
        max(0, ry - box_size),
        min(w, rx + box_size),
        min(h, ry + box_size),
    )
    return left_roi, right_roi


def safe_ratio(a, b):
    a = abs(float(a))
    b = abs(float(b))
    return min(a, b) / (max(a, b) + 1e-6)


def safe_diff(a, b):
    return abs(float(a) - float(b))


def list_video_files(folder):
    exts = {".mp4", ".avi", ".mov", ".mkv"}
    return sorted([p for p in Path(folder).rglob("*") if p.suffix.lower() in exts])


def sample_first_n(paths, n):
    return paths[:min(n, len(paths))]


def extract_features_from_video(video_path, max_frames=300):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None

    left_cheek_signal = []
    right_cheek_signal = []
    signal_times = []

    frame_count = 0
    face_found_frames = 0

    with mp_face_mesh.FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as face_mesh:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            if frame_count > max_frames:
                break

            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb)

            if not results.multi_face_landmarks:
                continue

            face_landmarks = results.multi_face_landmarks[0]
            face_found_frames += 1

            (lx1, ly1, lx2, ly2), (rx1, ry1, rx2, ry2) = get_cheek_rois(face_landmarks, w, h)

            left_roi = frame[ly1:ly2, lx1:lx2]
            right_roi = frame[ry1:ry2, rx1:rx2]

            if left_roi.size == 0 or right_roi.size == 0:
                continue

            left_green_mean = np.mean(left_roi[:, :, 1])
            right_green_mean = np.mean(right_roi[:, :, 1])

            t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            left_cheek_signal.append(left_green_mean)
            right_cheek_signal.append(right_green_mean)
            signal_times.append(t)

    cap.release()

    if len(left_cheek_signal) < 32 or len(right_cheek_signal) < 32:
        return None

    fps_est = estimate_fps(signal_times)
    if fps_est is None:
        fps_est = 30.0

    motion_left = has_motion_artifact(left_cheek_signal)
    motion_right = has_motion_artifact(right_cheek_signal)

    corr = compute_correlation(left_cheek_signal, right_cheek_signal, fps_est)

    left_std = compute_std(left_cheek_signal, fps_est)
    right_std = compute_std(right_cheek_signal, fps_est)

    left_mad = compute_mad(left_cheek_signal, fps_est)
    right_mad = compute_mad(right_cheek_signal, fps_est)

    left_peak_freq, left_peak_psd, left_snr = compute_psd_and_snr(left_cheek_signal, fps_est)
    right_peak_freq, right_peak_psd, right_snr = compute_psd_and_snr(right_cheek_signal, fps_est)

    features = {
        "fps_est": fps_est,
        "num_signal_samples": len(left_cheek_signal),
        "face_found_frames": face_found_frames,
        "motion_left": int(motion_left),
        "motion_right": int(motion_right),

        # Core correlation
        "corr": corr,
        "corr_squared": corr ** 2,   # NEW (very important)

        # Raw stats
        "left_std": left_std,
        "right_std": right_std,
        "left_mad": left_mad,
        "right_mad": right_mad,

        # Frequencies
        "left_peak_freq": left_peak_freq,
        "right_peak_freq": right_peak_freq,

        # Power / signal strength
        "left_peak_psd": left_peak_psd,
        "right_peak_psd": right_peak_psd,
        "left_snr": left_snr,
        "right_snr": right_snr,

        # Differences (VERY IMPORTANT)
        "freq_diff": safe_diff(left_peak_freq, right_peak_freq),
        "psd_diff": safe_diff(left_peak_psd, right_peak_psd),   # NEW
        "std_diff": safe_diff(left_std, right_std),             # NEW
        "mad_diff": safe_diff(left_mad, right_mad),             # NEW
        "snr_diff": safe_diff(left_snr, right_snr),             # NEW

        # Ratios
        "psd_ratio": safe_ratio(left_peak_psd, right_peak_psd),
        "std_ratio": safe_ratio(left_std, right_std),
        "mad_ratio": safe_ratio(left_mad, right_mad),
        "snr_ratio": safe_ratio(left_snr, right_snr),
        "freq_ratio": safe_ratio(left_peak_freq, right_peak_freq),  # NEW

        # Raw signal stats

    }
    return features


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real_dir", type=str, required=True, help="Folder containing real videos")
    parser.add_argument("--fake_dir", type=str, required=True, help="Folder containing fake videos")
    parser.add_argument("--n_real", type=int, default=300)
    parser.add_argument("--n_fake", type=int, default=300)
    parser.add_argument("--max_frames", type=int, default=300)
    parser.add_argument("--output_csv", type=str, default="celebdf_subset_features.csv")
    args = parser.parse_args()

    real_paths = sample_first_n(list_video_files(args.real_dir), args.n_real)
    fake_paths = sample_first_n(list_video_files(args.fake_dir), args.n_fake)

    print(f"Using {len(real_paths)} real videos")
    print(f"Using {len(fake_paths)} fake videos")

    rows = []

    for label_name, label_value, paths in [
        ("real", 0, real_paths),
        ("fake", 1, fake_paths),
    ]:
        for i, video_path in enumerate(paths, 1):
            print(f"[{label_name}] {i}/{len(paths)} -> {video_path.name}")
            try:
                feats = extract_features_from_video(video_path, max_frames=args.max_frames)
                if feats is None:
                    print("  skipped: insufficient signal")
                    continue

                feats["video_path"] = str(video_path)
                feats["video_name"] = video_path.name
                feats["label"] = label_value
                feats["label_name"] = label_name
                rows.append(feats)

            except Exception as e:
                print(f"  error: {e}")

    df = pd.DataFrame(rows)
    df.to_csv(args.output_csv, index=False)
    print(f"\nSaved features to {args.output_csv}")
    print(f"Final usable samples: {len(df)}")
    print(df["label_name"].value_counts(dropna=False))


if __name__ == "__main__":
    main()