"""
train_denoiser.py — ADDM-inspired Feature-Space Denoiser Training


Adaptation to feature-space liveness detection

Instead of denoising image patches in pixel space, we denoise the 35-dim
rPPG feature vectors in feature space.  The model is trained on REAL face
features only.

At inference:
  • Real face  → features lie on the learned manifold → LOW  reconstruction error
  • Fake face  → features are off-manifold             → HIGH reconstruction error

The reconstruction error is combined with the LivenessNet classifier score in
inference.py for a two-head anomaly detector.

Training objective (Eq. 1 in ADDM paper, adapted to feature space):
  L_total = L_recon + λ_adv * L_adv

  L_recon = MSE(x_clean, Denoiser(x_noisy))        ← denoiser reconstruction loss
  L_adv   = BCE(D(x_clean), 1) + BCE(D(x̂_clean), 0) ← discriminator loss
                                                       where x̂_clean = Denoiser(x_noisy)

Noise schedule:
  σ ~ Uniform(σ_min, σ_max)   per batch  (multi-scale denoising)
  x_noisy = x_clean + ε * σ   where ε ~ N(0, I)

Usage:
  python train_denoiser.py --csv real_features.csv \\
      --sigma_max 0.5 --lambda_adv 0.05 --epochs 200 \\
      --save denoiser_bundle.pth

  # Use the liveness classifier bundle for scaler/imputer:
  python train_denoiser.py --csv real_features.csv \\
      --classifier_bundle liveness_model.pth
"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from model import FeatureDenoiser, FeatureDiscriminator

# ── Reproducibility ────────────────────────────────────────────────────────────
SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)

def load_real_features(csv_path: str, classifier_bundle_path: str | None = None):
    """
    Load real-class feature rows from a CSV, apply the same imputer+scaler
    that was fit during classifier training.

    Args:
        csv_path               : path to features CSV (must have 'label' column, 0=real)
        classifier_bundle_path : optional path to liveness_model.pth to reuse preprocessing

    Returns:
        X_real  : (N_real, F) float32 ndarray — scaled features
        feature_cols : list of feature column names
        imputer, scaler : preprocessing objects (for saving into bundle)
    """
    df = pd.read_csv(csv_path)

    # Filter to real samples only
    if "label" not in df.columns:
        raise ValueError("CSV must have a 'label' column (0=real, 1=fake)")
    df_real = df[df["label"] == 0].copy()
    if len(df_real) == 0:
        raise ValueError("No real-labelled rows found in CSV.")
    print(f"  Loaded {len(df_real)} real samples from {csv_path}")

    # ── Preprocessing ─────────────────────────────────────────────────────────
    if classifier_bundle_path and os.path.exists(classifier_bundle_path):
        bundle      = torch.load(classifier_bundle_path, map_location="cpu", weights_only=False)
        feature_cols = bundle["feature_cols"]
        imputer      = bundle["imputer"]
        scaler       = bundle["scaler"]
        print(f"  Reusing imputer+scaler from {classifier_bundle_path}")
    else:
        from sklearn.impute import SimpleImputer
        from sklearn.preprocessing import StandardScaler

        non_feature = {"label", "video", "filename", "path", "split"}
        feature_cols = [c for c in df.columns if c not in non_feature]

        imputer = SimpleImputer(strategy="median")
        scaler  = StandardScaler()
        print("  Fitting fresh imputer+scaler on real data only")
        imputer.fit(df_real[feature_cols].values.astype(np.float64))
        scaler.fit(
            imputer.transform(df_real[feature_cols].values.astype(np.float64))
        )

    X = (
        df_real
        .reindex(columns=feature_cols, fill_value=0)
        .values
        .astype(np.float64)
    )
    X = imputer.transform(X)
    X = scaler.transform(X).astype(np.float32)

    return X, feature_cols, imputer, scaler




def add_noise(x: torch.Tensor, sigma_min: float, sigma_max: float) -> torch.Tensor:
    """
    Multi-scale Gaussian corruption.
    σ is sampled once per batch from Uniform[σ_min, σ_max].
    This trains the denoiser to handle a range of noise levels,
    mimicking the multi-step diffusion noising schedule in the ADDM paper.
    """
    sigma = sigma_min + (sigma_max - sigma_min) * torch.rand(1).item()
    return x + sigma * torch.randn_like(x)


def train_addm(
    X_real     : np.ndarray,
    n_features : int,
    *,
    sigma_min  : float = 0.05,
    sigma_max  : float = 0.5,
    lambda_adv : float = 0.05,
    epochs     : int   = 200,
    batch_size : int   = 64,
    lr_denoiser: float = 1e-3,
    lr_disc    : float = 1e-4,
    val_split  : float = 0.15,
    patience   : int   = 30,
    device     : str   = "cpu",
) -> tuple:
    """
    ADDM training loop.

    Args:
        X_real     : (N, F) scaled real-only feature matrix
        n_features : feature dimensionality F
        sigma_min/max : noise level range
        lambda_adv : weight for adversarial loss (λ in paper, default 0.05)
        epochs     : maximum training epochs
        batch_size : mini-batch size
        lr_denoiser/lr_disc : learning rates
        val_split  : fraction held out for early-stopping validation
        patience   : early-stopping patience (epochs without val improvement)
        device     : torch device string

    Returns:
        (denoiser, discriminator, train_stats)
        train_stats: dict with loss curves + calibration statistics
    """

    idx      = np.random.permutation(len(X_real))
    n_val    = max(1, int(len(X_real) * val_split))
    val_idx  = idx[:n_val]
    trn_idx  = idx[n_val:]

    X_trn = torch.tensor(X_real[trn_idx], dtype=torch.float32).to(device)
    X_val = torch.tensor(X_real[val_idx], dtype=torch.float32).to(device)

    loader = DataLoader(
        TensorDataset(X_trn),
        batch_size=batch_size,
        shuffle=True,
        drop_last=(len(X_trn) > batch_size),
    )

  
    denoiser = FeatureDenoiser(n_features).to(device)
    disc     = FeatureDiscriminator(n_features).to(device)

    opt_D  = torch.optim.Adam(denoiser.parameters(), lr=lr_denoiser, weight_decay=1e-5)
    opt_G  = torch.optim.Adam(disc.parameters(),     lr=lr_disc,     weight_decay=1e-5)

    sched_D = torch.optim.lr_scheduler.ReduceLROnPlateau(opt_D, patience=10, factor=0.5)

    bce  = nn.BCELoss()
    mse  = nn.MSELoss()

    real_label = lambda n: torch.ones(n,  device=device)
    fake_label = lambda n: torch.zeros(n, device=device)


    history     = {"recon": [], "adv_d": [], "adv_g": [], "val_recon": []}
    best_val    = float("inf")
    best_state  = None
    no_improve  = 0

    print(f"\n  Training ADDM on {len(X_trn)} real samples | val={len(X_val)}")
    print(f"  σ ∈ [{sigma_min}, {sigma_max}]  λ_adv={lambda_adv}  epochs={epochs}\n")

    for epoch in range(1, epochs + 1):
        denoiser.train()
        disc.train()

        ep_recon = ep_adv_d = ep_adv_g = 0.0
        n_batches = 0

        for (x_clean,) in loader:
            n = x_clean.size(0)
            x_noisy = add_noise(x_clean, sigma_min, sigma_max)

            # ── Step 1: Update Discriminator ─────────────────────────────────
            # D should output 1 for real clean, 0 for denoiser output
            opt_G.zero_grad()
            with torch.no_grad():
                x_hat = denoiser(x_noisy)

            loss_d = 0.5 * (
                bce(disc(x_clean), real_label(n)) +
                bce(disc(x_hat.detach()), fake_label(n))
            )
            loss_d.backward()
            opt_G.step()

            # ── Step 2: Update Denoiser (reconstruction + adversarial) ───────
            opt_D.zero_grad()
            x_hat     = denoiser(x_noisy)
            l_recon   = mse(x_hat, x_clean)
            # Generator loss: fool discriminator into thinking x_hat is real
            l_adv_g   = bce(disc(x_hat), real_label(n))
            loss_den  = l_recon + lambda_adv * l_adv_g
            loss_den.backward()
            opt_D.step()

            ep_recon  += l_recon.item()
            ep_adv_d  += loss_d.item()
            ep_adv_g  += l_adv_g.item()
            n_batches += 1

        # ── Validation ────────────────────────────────────────────────────────
        denoiser.eval()
        with torch.no_grad():
            val_recon = mse(denoiser(X_val), X_val).item()   # no noise at val time

        sched_D.step(val_recon)

        history["recon"].append(ep_recon / n_batches)
        history["adv_d"].append(ep_adv_d / n_batches)
        history["adv_g"].append(ep_adv_g / n_batches)
        history["val_recon"].append(val_recon)

        if epoch % 20 == 0 or epoch == 1:
            print(
                f"  Epoch {epoch:4d}/{epochs} | "
                f"recon={ep_recon/n_batches:.5f}  adv_d={ep_adv_d/n_batches:.5f}  "
                f"adv_g={ep_adv_g/n_batches:.5f} | val_recon={val_recon:.5f}"
            )

        # ── Early stopping ────────────────────────────────────────────────────
        if val_recon < best_val - 1e-6:
            best_val   = val_recon
            best_state = {
                "denoiser": {k: v.cpu().clone() for k, v in denoiser.state_dict().items()},
                "disc"    : {k: v.cpu().clone() for k, v in disc.state_dict().items()},
            }
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                print(f"  Early stop at epoch {epoch} (no val improvement for {patience} epochs)")
                break

    # ── Restore best weights ──────────────────────────────────────────────────
    if best_state:
        denoiser.load_state_dict(best_state["denoiser"])
        disc.load_state_dict(best_state["disc"])

    # ── Calibration: compute reconstruction-error statistics on all real data ─
    # These statistics are used at inference time to normalise the anomaly score:
    #   z_score = (error - mean_err) / std_err
    # A high z_score → likely fake.
    denoiser.eval()
    with torch.no_grad():
        X_all = torch.tensor(X_real, dtype=torch.float32).to(device)
        errors = ((denoiser(X_all) - X_all) ** 2).mean(dim=1).cpu().numpy()

    calib = {
        "mean_recon_error" : float(errors.mean()),
        "std_recon_error"  : float(errors.std() + 1e-8),
        "p95_recon_error"  : float(np.percentile(errors, 95)),
        "p99_recon_error"  : float(np.percentile(errors, 99)),
    }
    print(f"\n  Calibration on {len(X_real)} real samples:")
    print(f"    mean recon error = {calib['mean_recon_error']:.6f}")
    print(f"    std  recon error = {calib['std_recon_error']:.6f}")
    print(f"    p95  recon error = {calib['p95_recon_error']:.6f}")
    print(f"    p99  recon error = {calib['p99_recon_error']:.6f}")

    train_stats = {"history": history, "calibration": calib, "best_val_recon": best_val}
    return denoiser, disc, train_stats


# ══════════════════════════════════════════════════════════════════════════════
# Evaluation helper
# ══════════════════════════════════════════════════════════════════════════════

def evaluate_denoiser(denoiser, X_real, X_fake, calib, device="cpu"):
    """
    Print a quick anomaly-score separation report.

    Uses normalised reconstruction error:
      z = (error - mean) / std

    Ideally z_fake >> z_real ≈ 0.
    """
    denoiser.eval()
    def recon_errors(X):
        with torch.no_grad():
            t  = torch.tensor(X, dtype=torch.float32).to(device)
            return ((denoiser(t) - t) ** 2).mean(dim=1).cpu().numpy()

    e_real = recon_errors(X_real)
    e_fake = recon_errors(X_fake)

    mean_r, std_r = calib["mean_recon_error"], calib["std_recon_error"]
    z_real = (e_real - mean_r) / std_r
    z_fake = (e_fake - mean_r) / std_r

    print("\n  ── Anomaly score (z-score) separation ─────────────")
    print(f"  Real  | mean={z_real.mean():.3f}  std={z_real.std():.3f}  "
          f"p95={np.percentile(z_real, 95):.3f}")
    print(f"  Fake  | mean={z_fake.mean():.3f}  std={z_fake.std():.3f}  "
          f"p5={np.percentile(z_fake,  5):.3f}")

    # AUROC with sklearn if available
    try:
        from sklearn.metrics import roc_auc_score
        y_true  = np.array([0]*len(z_real) + [1]*len(z_fake))
        z_score = np.concatenate([z_real, z_fake])
        auc     = roc_auc_score(y_true, z_score)
        print(f"  AUROC (recon error alone) = {auc:.4f}")
    except ImportError:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def build_parser():
    p = argparse.ArgumentParser(
        description="Train ADDM-inspired feature-space denoiser for liveness detection"
    )
    p.add_argument("--csv",                required=True,
                   help="Path to features CSV (label col: 0=real, 1=fake)")
    p.add_argument("--classifier_bundle",  default="liveness_model.pth",
                   help="Existing classifier bundle to reuse imputer+scaler (default: liveness_model.pth)")
    p.add_argument("--save",               default="denoiser_bundle.pth",
                   help="Output path for denoiser bundle (default: denoiser_bundle.pth)")
    p.add_argument("--sigma_min",  type=float, default=0.05,
                   help="Minimum noise level σ (default: 0.05)")
    p.add_argument("--sigma_max",  type=float, default=0.50,
                   help="Maximum noise level σ (default: 0.50)")
    p.add_argument("--lambda_adv", type=float, default=0.05,
                   help="Adversarial loss weight λ (default: 0.05 per ADDM paper)")
    p.add_argument("--epochs",     type=int,   default=200,
                   help="Max training epochs (default: 200)")
    p.add_argument("--batch_size", type=int,   default=64)
    p.add_argument("--lr",         type=float, default=1e-3,
                   help="Denoiser learning rate (default: 1e-3)")
    p.add_argument("--lr_disc",    type=float, default=1e-4,
                   help="Discriminator learning rate (default: 1e-4)")
    p.add_argument("--patience",   type=int,   default=30,
                   help="Early-stopping patience in epochs (default: 30)")
    p.add_argument("--evaluate",   action="store_true",
                   help="After training, report anomaly-score separation on real vs fake rows")
    p.add_argument("--device",     default="cpu",
                   help="Torch device (default: cpu)")
    return p


def main():
    args = build_parser().parse_args()

    print("=" * 60)
    print("  ADDM Feature-Space Denoiser Training")
    print("=" * 60)

    # ── Load data ─────────────────────────────────────────────────────────────
    X_real, feature_cols, imputer, scaler = load_real_features(
        args.csv, args.classifier_bundle
    )
    n_features = X_real.shape[1]

    # ── Train ─────────────────────────────────────────────────────────────────
    denoiser, disc, stats = train_addm(
        X_real,
        n_features,
        sigma_min   = args.sigma_min,
        sigma_max   = args.sigma_max,
        lambda_adv  = args.lambda_adv,
        epochs      = args.epochs,
        batch_size  = args.batch_size,
        lr_denoiser = args.lr,
        lr_disc     = args.lr_disc,
        patience    = args.patience,
        device      = args.device,
    )

    # ── Optional evaluation on fake class ────────────────────────────────────
    if args.evaluate:
        df = pd.read_csv(args.csv)
        df_fake = df[df["label"] == 1]
        if len(df_fake) > 0:
            X_fake = (
                df_fake
                .reindex(columns=feature_cols, fill_value=0)
                .values
                .astype(np.float64)
            )
            X_fake = imputer.transform(X_fake)
            X_fake = scaler.transform(X_fake).astype(np.float32)
            evaluate_denoiser(denoiser, X_real, X_fake, stats["calibration"], args.device)
        else:
            print("  No fake rows in CSV — skipping evaluation.")

    # ── Save bundle ───────────────────────────────────────────────────────────
    bundle = {
        # Model weights
        "denoiser_state_dict"      : denoiser.state_dict(),
        "discriminator_state_dict" : disc.state_dict(),

        # Architecture params (needed to rebuild models in inference.py)
        "n_features"   : n_features,
        "denoiser_hidden"  : (64, 32, 16),
        "disc_hidden"      : (32, 16),

        # Preprocessing (same as classifier if reused)
        "feature_cols" : feature_cols,
        "imputer"      : imputer,
        "scaler"       : scaler,

        # Calibration statistics for anomaly normalisation
        "calibration"  : stats["calibration"],

        # Training hyper-params for reproducibility
        "sigma_min"    : args.sigma_min,
        "sigma_max"    : args.sigma_max,
        "lambda_adv"   : args.lambda_adv,

        # Loss history
        "history"      : stats["history"],
    }

    torch.save(bundle, args.save)
    print(f"\n  Denoiser bundle saved → {args.save}")

    # Print calibration JSON for easy reference
    print("\n  Calibration stats (copy into denoiser_bundle.pth or use directly):")
    print("  " + json.dumps(stats["calibration"], indent=4).replace("\n", "\n  "))


if __name__ == "__main__":
    main()
