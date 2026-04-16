"""
Inference Module — PyTorch LivenessNet

Loads the trained LivenessNet bundle saved by train_classifier.py and
exposes two functions used by challenge.py:

  predict_features(feats_dict) -> (pred, fake_prob)
  predict_video(video_path)    -> dict with prediction + features
"""

import numpy as np
import pandas as pd
import torch

from model import LivenessNet
from extract_features import extract_features_from_video

MODEL_PATH = "liveness_model.pth"

# ── Load bundle ────────────────────────────────────────────────────────────────
# weights_only=False is required because the bundle contains sklearn objects
# (SimpleImputer, StandardScaler) serialised alongside the state dict.
bundle = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)

net = LivenessNet(
    n_features   = bundle["n_features"],
    hidden_sizes = bundle["hidden_sizes"],
    dropouts     = bundle["dropouts"],
)
net.load_state_dict(bundle["model_state_dict"])
net.eval()

feature_cols = bundle["feature_cols"]
imputer      = bundle["imputer"]
scaler       = bundle["scaler"]
threshold    = bundle.get("threshold", 0.4)


# ── Public API ─────────────────────────────────────────────────────────────────

def predict_features(feats: dict):
    """
    Run inference on a pre-computed feature dictionary.

    Called every frame by challenge.py once the rPPG buffer is long enough.

    Args:
        feats : dict matching the keys in feature_cols

    Returns:
        (pred, fake_prob)
          pred     : 0 = real, 1 = fake
          fake_prob: raw sigmoid output ∈ [0, 1]
    """
    x = (
        pd.DataFrame([feats])
          .reindex(columns=feature_cols, fill_value=0)
          .values
          .astype(np.float64)
    )
    x = imputer.transform(x)           # fill any remaining NaNs
    x = scaler.transform(x).astype(np.float32)

    with torch.no_grad():
        fake_prob = float(net(torch.from_numpy(x)).item())

    pred = 1 if fake_prob >= threshold else 0
    return pred, fake_prob


def predict_video(video_path, max_frames: int = 150):
    """
    End-to-end prediction from a video file path.

    Args:
        video_path : path to video file
        max_frames : maximum frames to process

    Returns:
        dict with keys: prediction, fake_probability, features
        or None if the video yielded insufficient rPPG signal
    """
    feats = extract_features_from_video(video_path, max_frames=max_frames)
    if feats is None:
        return None

    pred, prob = predict_features(feats)
    return {
        "prediction"      : int(pred),
        "fake_probability": float(prob),
        "features"        : feats,
    }


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    video_path = sys.argv[1] if len(sys.argv) > 1 else "test.mp4"
    result = predict_video(video_path)
    if result is None:
        print("Could not extract features from video.")
    else:
        print("\nPrediction  :", "FAKE" if result["prediction"] == 1 else "REAL")
        print("Fake prob   :", f"{result['fake_probability']:.4f}")
