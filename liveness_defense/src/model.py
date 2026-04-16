"""
LivenessNet — PyTorch MLP for rPPG-based passive liveness detection.

Shared by train_classifier.py (training) and inference.py (runtime).
Keeping the architecture in one place means a change here propagates
automatically to both without version skew.

Architecture per hidden layer:  Linear → BatchNorm1d → ReLU → Dropout
Output layer:                   Linear(1) → Sigmoid   (fake probability ∈ [0,1])

BatchNorm stabilises training on small datasets (~600 samples) by normalising
activations between layers, removing dependence on careful weight init.
Dropout adds regularisation without any extra data.
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
