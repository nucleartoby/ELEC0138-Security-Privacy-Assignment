"""
Inference Module — Denoiser → LivenessNet (sequential pipeline)
================================================================

Loads the trained LivenessNet bundle saved by train_classifier.py and
optionally the FeatureDenoiser bundle saved by train_denoiser.py.

Pipeline:
    raw_features → (scaler) → scaled_features
                            → FeatureDenoiser (if loaded)
                            → cleaned_features
                            → LivenessNet
                            → fake probability

The denoiser acts as a learned preprocessor that pulls the feature vector
toward the real-data manifold learned by ADDM training.  When combined with
a classifier retrained on denoised features, this removes noise artefacts
that the classifier would otherwise misinterpret.

If no denoiser bundle is present, raw (scaled) features are passed directly
to the classifier — identical to the original pre-ADDM pipeline.

Exposes two functions used by challenge.py:

  predict_features(feats_dict) -> (pred, fake_prob)
  predict_video(video_path)    -> dict with prediction + features
"""

import os

import numpy as np
import pandas as pd
import torch

from model import LivenessNet, FeatureDenoiser
from extract_features import extract_features_from_video

# ── Paths ──────────────────────────────────────────────────────────────────────
MODEL_PATH    = "liveness_model.pth"
DENOISER_PATH = "denoiser_bundle.pth"   # optional; skipped if absent


# ══════════════════════════════════════════════════════════════════════════════
# Load classifier bundle
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# Load denoiser bundle (optional)
# ══════════════════════════════════════════════════════════════════════════════

_denoiser = None

if os.path.exists(DENOISER_PATH):
    try:
        den_bundle = torch.load(DENOISER_PATH, map_location="cpu", weights_only=False)

        _denoiser = FeatureDenoiser(
            n_features = den_bundle["n_features"],
            hidden     = tuple(den_bundle.get("denoiser_hidden", (64, 32, 16))),
        )
        _denoiser.load_state_dict(den_bundle["denoiser_state_dict"])
        _denoiser.eval()

        print(f"[inference] ADDM denoiser loaded from {DENOISER_PATH} "
              f"— features will be cleaned before classification.")
    except Exception as e:
        print(f"[inference] WARNING: could not load denoiser bundle: {e}")
        _denoiser = None
else:
    print(f"[inference] No denoiser bundle found at {DENOISER_PATH} "
          f"— passing raw features to classifier.")


# ══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ══════════════════════════════════════════════════════════════════════════════

def _preprocess(feats: dict) -> np.ndarray:
    """Convert feature dict → scaled (1, F) float32 ndarray."""
    x = (
        pd.DataFrame([feats])
          .reindex(columns=feature_cols, fill_value=0)
          .values
          .astype(np.float64)
    )
    x = imputer.transform(x)
    return scaler.transform(x).astype(np.float32)


def _denoise(x: np.ndarray) -> np.ndarray:
    """
    Run the FeatureDenoiser on a (1, F) scaled array to obtain cleaned features.

    Returns the input unchanged if the denoiser is not loaded.
    """
    if _denoiser is None:
        return x
    with torch.no_grad():
        x_clean = _denoiser(torch.from_numpy(x)).cpu().numpy().astype(np.float32)
    return x_clean


def _classifier_prob(x: np.ndarray) -> float:
    """Run LivenessNet on a (1, F) scaled array, return fake probability."""
    with torch.no_grad():
        return float(net(torch.from_numpy(x)).item())


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def predict_features(feats: dict):
    """
    Run inference on a pre-computed feature dictionary.

    Pipeline:  scale → denoise (optional) → classify.

    Called every frame by challenge.py once the rPPG buffer is long enough.

    Args:
        feats : dict matching the keys in feature_cols

    Returns:
        (pred, fake_prob)
          pred     : 0 = real, 1 = fake
          fake_prob: classifier output on cleaned features ∈ [0, 1]
    """
    x         = _preprocess(feats)          # (1, F) scaled
    x_clean   = _denoise(x)                 # cleaned by ADDM denoiser (or identity)
    fake_prob = _classifier_prob(x_clean)

    pred = 1 if fake_prob >= threshold else 0
    return pred, fake_prob


def predict_video(video_path, max_frames: int = 150):
    """
    End-to-end prediction from a video file path.

    Args:
        video_path : path to video file
        max_frames : maximum frames to process

    Returns:
        dict with keys:
          prediction        : 0 = real, 1 = fake
          fake_probability  : classifier score on cleaned features ∈ [0, 1]
          classifier_prob_raw : classifier score on RAW (non-denoised) features,
                                for debugging / comparison
          features          : extracted feature dict
        or None if the video yielded insufficient rPPG signal.
    """
    feats = extract_features_from_video(video_path, max_frames=max_frames)
    if feats is None:
        return None

    x       = _preprocess(feats)
    x_clean = _denoise(x)

    fake_prob     = _classifier_prob(x_clean)
    raw_prob      = _classifier_prob(x)     # for comparison only
    pred          = 1 if fake_prob >= threshold else 0

    return {
        "prediction"          : int(pred),
        "fake_probability"    : float(fake_prob),
        "classifier_prob_raw" : float(raw_prob),
        "features"            : feats,
    }


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    video_path = sys.argv[1] if len(sys.argv) > 1 else "test.mp4"
    result = predict_video(video_path)
    if result is None:
        print("Could not extract features from video.")
    else:
        print("\nPrediction        :", "FAKE" if result["prediction"] == 1 else "REAL")
        print("Fake prob (clean) :", f"{result['fake_probability']:.4f}")
        print("Fake prob (raw)   :", f"{result['classifier_prob_raw']:.4f}")
