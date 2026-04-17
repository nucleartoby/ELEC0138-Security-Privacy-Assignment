"""
model.py — PyTorch model definitions for rPPG-based passive liveness detection.

Contains three classes:

  LivenessNet       — supervised MLP classifier (fake probability)
  FeatureDenoiser   — ADDM-style MLP autoencoder trained on real features only
  FeatureDiscriminator — adversarial discriminator for ADDM training

LivenessNet shared by train_classifier.py and inference.py.
FeatureDenoiser / FeatureDiscriminator shared by train_denoiser.py and inference.py.

References:
  Yu et al. "Adversarial Denoising Diffusion Model for Anomaly Detection"
  NeurIPS 2023 — https://arxiv.org/abs/2312.04382
"""

import torch
import torch.nn as nn
import numpy as np


class LivenessNet(nn.Module):
    # Default architecture — change here only, both train + inference pick it up
    DEFAULT_HIDDEN  = (128, 64, 32)
    DEFAULT_DROPOUT = (0.3, 0.3, 0.2)

    def __init__(
        self,
        n_features: int,
        hidden_sizes: tuple = DEFAULT_HIDDEN,
        dropouts: tuple     = DEFAULT_DROPOUT,
    ):
        """
        Args:
            n_features   : number of input features (set at training time)
            hidden_sizes : tuple of hidden layer widths
            dropouts     : per-layer dropout probabilities (same length as hidden_sizes)
        """
        super().__init__()

        layers = []
        in_dim = n_features
        for h, d in zip(hidden_sizes, dropouts):
            layers += [
                nn.Linear(in_dim, h),
                nn.BatchNorm1d(h),
                nn.ReLU(inplace=True),
                nn.Dropout(p=d),
            ]
            in_dim = h
        layers += [nn.Linear(in_dim, 1), nn.Sigmoid()]

        self.net = nn.Sequential(*layers)

    # ── Forward ───────────────────────────────────────────────────────────────
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x : (batch, n_features) float32 tensor

        Returns:
            (batch,) fake probability in [0, 1]
        """
        return self.net(x).squeeze(-1)

    # ── Convenience helpers ───────────────────────────────────────────────────
    @torch.no_grad()
    def predict_proba(self, x_np: np.ndarray) -> np.ndarray:
        """
        sklearn-style predict_proba: numpy in, numpy out.

        Returns:
            ndarray of shape (N, 2)  — columns: [P(real), P(fake)]
        """
        self.eval()
        x_t = torch.tensor(x_np, dtype=torch.float32)
        p   = self(x_t).cpu().numpy()                  # shape (N,)
        return np.column_stack([1.0 - p, p])

    @torch.no_grad()
    def predict(self, x_np: np.ndarray, threshold: float = 0.4) -> np.ndarray:
        """Binary prediction at given threshold (0 = real, 1 = fake)."""
        return (self.predict_proba(x_np)[:, 1] >= threshold).astype(int)


# ══════════════════════════════════════════════════════════════════════════════
# ADDM components — trained with train_denoiser.py on REAL samples only.
# At inference time, reconstruction error becomes an anomaly score:
#   fake faces produce high error; real faces stay near the training manifold.
# ══════════════════════════════════════════════════════════════════════════════

class FeatureDenoiser(nn.Module):
    """
    MLP autoencoder that learns to reconstruct clean real-face features from
    noisy versions.  Bottleneck forces learning of the real-data manifold.

    Encoder:  n_features → 64 → 32 → 16  (with BN + LeakyReLU)
    Decoder:  16 → 32 → 64 → n_features  (with BN + LeakyReLU, linear output)

    Training: add Gaussian noise at random σ ∈ [0, σ_max], minimise
              L_recon = MSE(x_clean, Denoiser(x_noisy))
    Anomaly score at inference: MSE(x, Denoiser(x))  — no noise added.
    """

    def __init__(self, n_features: int, hidden: tuple = (64, 32, 16)):
        super().__init__()

        # ── Encoder ──────────────────────────────────────────────────────────
        enc_layers = []
        in_dim = n_features
        for h in hidden:
            enc_layers += [
                nn.Linear(in_dim, h),
                nn.BatchNorm1d(h),
                nn.LeakyReLU(0.1, inplace=True),
            ]
            in_dim = h
        self.encoder = nn.Sequential(*enc_layers)

        # ── Decoder ──────────────────────────────────────────────────────────
        dec_layers = []
        for h in reversed(hidden[:-1]):          # 16→32→64
            dec_layers += [
                nn.Linear(in_dim, h),
                nn.BatchNorm1d(h),
                nn.LeakyReLU(0.1, inplace=True),
            ]
            in_dim = h
        dec_layers.append(nn.Linear(in_dim, n_features))   # linear output
        self.decoder = nn.Sequential(*dec_layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x : (batch, n_features) float32

        Returns:
            x_hat : reconstructed features, same shape as x
        """
        return self.decoder(self.encoder(x))

    @torch.no_grad()
    def reconstruction_error(self, x_np: np.ndarray) -> np.ndarray:
        """
        Per-sample MSE between input and reconstruction.

        Args:
            x_np : (N, n_features) float32 ndarray (already scaled)

        Returns:
            errors : (N,) float32 ndarray
        """
        self.eval()
        x_t   = torch.tensor(x_np, dtype=torch.float32)
        x_hat = self(x_t)
        return ((x_t - x_hat) ** 2).mean(dim=1).cpu().numpy()


class FeatureDiscriminator(nn.Module):
    """
    Adversarial discriminator used during ADDM training.

    Distinguishes:
      • real clean features  (label 1 — "comes from the true data manifold")
      • denoiser reconstructions (label 0 — "generated by the model")

    This adversarial signal pushes the denoiser's output distribution
    to match the real feature distribution, not just minimise pixel MSE.

    Architecture: n_features → 32 → 16 → 1 (sigmoid)
    """

    def __init__(self, n_features: int, hidden: tuple = (32, 16)):
        super().__init__()
        layers = []
        in_dim = n_features
        for h in hidden:
            layers += [
                nn.Linear(in_dim, h),
                nn.LeakyReLU(0.1, inplace=True),
                nn.Dropout(0.2),
            ]
            in_dim = h
        layers += [nn.Linear(in_dim, 1), nn.Sigmoid()]
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Returns (batch,) probability that x is a real (not reconstructed) sample."""
        return self.net(x).squeeze(-1)
