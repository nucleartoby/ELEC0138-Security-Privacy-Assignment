"""
Liveness Classifier Training — PyTorch MLP on Sync_rPPG Feature Set

Trains LivenessNet (model.py) on DWT-based rPPG features from extract_features.py.

Training details:
  • Adam optimiser + ReduceLROnPlateau scheduler
  • Weighted BCE loss  (fakes upweighted to penalise false negatives)
  • BatchNorm + Dropout for regularisation on small datasets
  • Early stopping on validation AUC
  • 4-fold stratified cross-validation (matches paper protocol)

Usage:
  python train_classifier.py --csv celebdf_subset_features.csv
  python train_classifier.py --csv features.csv --fake_weight 3.0  # stricter

  # Train on denoised features (matches the inference pipeline when
  # a denoiser bundle is present):
  python train_classifier.py --csv features.csv --denoiser denoiser_bundle.pth
"""

import argparse
import copy
import os
import time

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance as sk_perm_importance
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix,
    f1_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

from model import LivenessNet, FeatureDenoiser


# ── Training helpers ───────────────────────────────────────────────────────────

def make_loader(X, y, sw, batch_size: int, shuffle: bool = True) -> DataLoader:
    ds = TensorDataset(
        torch.tensor(X,  dtype=torch.float32),
        torch.tensor(y,  dtype=torch.float32),
        torch.tensor(sw, dtype=torch.float32),
    )
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle, drop_last=False)


def fgsm_perturb(net, Xb: torch.Tensor, yb: torch.Tensor,
                  criterion, epsilon: float) -> torch.Tensor:
    """
    Fast Gradient Sign Method (FGSM) — feature-space adversarial examples.

    Generates a perturbation in the direction that maximises the loss:
        X_adv = X + ε · sign(∇_X  L(f(X), y))

    In our context X is the scaled feature vector (not raw pixels), so this
    forces the MLP to be robust against small corruptions of rPPG features —
    mimicking an attacker who slightly manipulates face colour to spoof the
    green-channel signal.

    The FGSM forward/backward is kept separate from the optimiser step so
    the model weights are not modified by the perturbation gradient.
    """
    net.train()                                      # need BN in train mode
    Xb_adv = Xb.clone().detach().requires_grad_(True)
    loss   = criterion(net(Xb_adv), yb).mean()
    loss.backward()
    with torch.no_grad():
        Xb_adv = Xb + epsilon * Xb_adv.grad.sign()
    return Xb_adv.detach()


def train_one_epoch(net, loader, optimizer, criterion,
                    adv_eps: float = 0.0, adv_alpha: float = 0.5):
    """
    One training epoch, optionally with FGSM adversarial training.

    When adv_eps > 0 each mini-batch loss is a convex combination of:
        L = (1 − α)·L_clean  +  α·L_adv
    where L_adv is computed on FGSM-perturbed feature vectors.
    This regularises the model to be insensitive to small feature-space
    perturbations without requiring extra labelled data.

    Args:
        adv_eps   : FGSM perturbation magnitude (0 = disabled)
        adv_alpha : weight of adversarial loss term  (default 0.5)
    """
    net.train()
    total_loss = 0.0
    for Xb, yb, wb in loader:

        if adv_eps > 0.0:
            # ── Adversarial branch ────────────────────────────────────────────
            Xb_adv = fgsm_perturb(net, Xb, yb, criterion, adv_eps)
            optimizer.zero_grad()
            loss_clean = (criterion(net(Xb),     yb) * wb).mean()
            loss_adv   = (criterion(net(Xb_adv), yb) * wb).mean()
            loss       = (1.0 - adv_alpha) * loss_clean + adv_alpha * loss_adv
        else:
            # ── Standard branch ───────────────────────────────────────────────
            optimizer.zero_grad()
            loss = (criterion(net(Xb), yb) * wb).mean()

        loss.backward()
        optimizer.step()
        total_loss += loss.item()

    return total_loss / max(len(loader), 1)


@torch.no_grad()
def evaluate(net, X_t: torch.Tensor, y: np.ndarray):
    """Return (preds, probs, auc, f1) on a pre-tensorised set."""
    net.eval()
    probs = net(X_t).cpu().numpy()
    preds = (probs >= 0.4).astype(int)
    auc   = roc_auc_score(y, probs) if len(np.unique(y)) > 1 else 0.0
    f1    = f1_score(y, preds, zero_division=0)
    return preds, probs, auc, f1




def train_fold(X_tr, y_tr, sw_tr, X_val, y_val, n_features, args):
    """
    Train LivenessNet for one CV fold.

    Returns: (best_net, val_preds, val_probs, epochs_run)
    """
    net       = LivenessNet(n_features, LivenessNet.DEFAULT_HIDDEN,
                             LivenessNet.DEFAULT_DROPOUT)
    optimizer = torch.optim.Adam(net.parameters(),
                                  lr=args.lr, weight_decay=1e-3)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="max", patience=10, factor=0.5
    )
    criterion = nn.BCELoss(reduction="none")
    loader    = make_loader(X_tr, y_tr, sw_tr, args.batch_size)

    X_val_t = torch.tensor(X_val, dtype=torch.float32)

    best_auc   = -1.0
    best_state = None
    no_improve = 0

    for epoch in range(1, args.max_epochs + 1):
        train_one_epoch(net, loader, optimizer, criterion,
                        adv_eps=args.adv_eps, adv_alpha=args.adv_alpha)

        _, _, val_auc, _ = evaluate(net, X_val_t, y_val)
        scheduler.step(val_auc)

        if val_auc > best_auc + 1e-4:
            best_auc   = val_auc
            best_state = copy.deepcopy(net.state_dict())
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= args.patience:
                break

    net.load_state_dict(best_state)
    net.eval()
    val_preds, val_probs, _, _ = evaluate(net, X_val_t, y_val)
    return net, val_preds, val_probs, epoch


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Train PyTorch liveness classifier on Sync_rPPG features."
    )
    parser.add_argument("--csv",         type=str,   default="celebdf_subset_features.csv")
    parser.add_argument("--model_out",   type=str,   default="liveness_model.pth")
    parser.add_argument("--fake_weight", type=float, default=2.0,
                        help="Loss weight multiplier for fake class (default 2.0)")
    parser.add_argument("--lr",          type=float, default=1e-3)
    parser.add_argument("--batch_size",  type=int,   default=32)
    parser.add_argument("--max_epochs",  type=int,   default=400)
    parser.add_argument("--patience",    type=int,   default=40,
                        help="Early-stopping patience (epochs, default 40)")
    parser.add_argument("--cv_folds",    type=int,   default=4)
    parser.add_argument("--adv_eps",     type=float, default=0.05,
                        help="FGSM epsilon for adversarial training "
                             "(0 = disabled, 0.05 = recommended)")
    parser.add_argument("--adv_alpha",   type=float, default=0.5,
                        help="Weight of adversarial loss vs clean loss (default 0.5)")
    parser.add_argument("--denoiser",    type=str,   default=None,
                        help="Path to a denoiser_bundle.pth. When provided, the "
                             "classifier is trained on features passed through "
                             "the denoiser (matches the inference pipeline).")
    args = parser.parse_args()

    torch.manual_seed(42)
    np.random.seed(42)

    # ── Load data ──────────────────────────────────────────────────────────────
    df = pd.read_csv(args.csv)
    print(f"Loaded {len(df)} samples from {args.csv}")
    print(df["label_name"].value_counts(dropna=False).to_string())

    drop_cols    = ["video_path", "video_name", "label_name", "label"]
    feature_cols = [c for c in df.columns if c not in drop_cols]
    n_features   = len(feature_cols)

    X_raw = df[feature_cols].values.astype(np.float64)
    y     = df["label"].values.astype(int)

    n_real = int(np.sum(y == 0))
    n_fake = int(np.sum(y == 1))
    print(f"\nClass distribution — real: {n_real}  fake: {n_fake}")
    print(f"Architecture: {n_features} → {LivenessNet.DEFAULT_HIDDEN} → 1")

    # ── 80/20 hold-out split (stratified) ────────────────────────────────────
    X_train_raw, X_test_raw, y_train, y_test = train_test_split(
        X_raw, y, test_size=0.2, random_state=42, stratify=y
    )

    # ── Preprocessing: impute → scale (fit on train only) ────────────────────
    imputer = SimpleImputer(strategy="median")
    scaler  = StandardScaler()

    X_train_clean = imputer.fit_transform(X_train_raw)
    X_train_scaled = scaler.fit_transform(X_train_clean).astype(np.float32)

    X_test_clean  = imputer.transform(X_test_raw)
    X_test_scaled = scaler.transform(X_test_clean).astype(np.float32)

    # ── Optional ADDM denoiser as preprocessing ──────────────────────────────
    # When --denoiser is supplied, pass scaled features through the pretrained
    # FeatureDenoiser so the classifier learns on the SAME distribution it will
    # see at inference time (raw → scaler → denoiser → classifier).
    # The denoiser's weights are frozen here — only the classifier trains.
    if args.denoiser and os.path.exists(args.denoiser):
        den_bundle = torch.load(args.denoiser, map_location="cpu", weights_only=False)
        denoiser   = FeatureDenoiser(
            n_features = den_bundle["n_features"],
            hidden     = tuple(den_bundle.get("denoiser_hidden", (64, 32, 16))),
        )
        denoiser.load_state_dict(den_bundle["denoiser_state_dict"])
        denoiser.eval()

        with torch.no_grad():
            X_train_scaled = (
                denoiser(torch.tensor(X_train_scaled, dtype=torch.float32))
                .cpu().numpy().astype(np.float32)
            )
            X_test_scaled = (
                denoiser(torch.tensor(X_test_scaled, dtype=torch.float32))
                .cpu().numpy().astype(np.float32)
            )
        print(f"Applied denoiser from {args.denoiser} "
              f"(train/test features now pass through ADDM denoiser)")
    elif args.denoiser:
        print(f"WARNING: denoiser path {args.denoiser} not found — "
              "training on RAW scaled features.")

    # ── Sample weights for fake upweighting ───────────────────────────────────
    sw_train = compute_sample_weight(
        class_weight={0: 1.0, 1: args.fake_weight}, y=y_train
    ).astype(np.float32)

    # ── 4-fold stratified cross-validation ────────────────────────────────────
    print(f"\nRunning {args.cv_folds}-fold stratified CV …")
    skf = StratifiedKFold(n_splits=args.cv_folds, shuffle=True, random_state=42)
    cv_accs, cv_f1s, cv_aucs = [], [], []

    for fold, (tr_idx, val_idx) in enumerate(
        skf.split(X_train_scaled, y_train), 1
    ):
        X_tr,  X_val  = X_train_scaled[tr_idx],  X_train_scaled[val_idx]
        y_tr,  y_val  = y_train[tr_idx],          y_train[val_idx]
        sw_tr         = sw_train[tr_idx]

        # Re-fit scaler on this fold's train split
        fold_scaler = StandardScaler()
        X_tr  = fold_scaler.fit_transform(X_tr).astype(np.float32)
        X_val = fold_scaler.transform(X_val).astype(np.float32)
        fold_sw = compute_sample_weight(
            {0: 1.0, 1: args.fake_weight}, y=y_tr
        ).astype(np.float32)

        _, val_preds, val_probs, n_epoch = train_fold(
            X_tr, y_tr, fold_sw, X_val, y_val, n_features, args
        )

        acc = accuracy_score(y_val, val_preds)
        f1  = f1_score(y_val, val_preds, zero_division=0)
        auc = roc_auc_score(y_val, val_probs)
        cv_accs.append(acc); cv_f1s.append(f1); cv_aucs.append(auc)

        print(f"  Fold {fold}: acc={acc:.4f}  f1={f1:.4f}  "
              f"auc={auc:.4f}  (stopped @ epoch {n_epoch})")

    print(f"\nCV mean — acc={np.mean(cv_accs):.4f}±{np.std(cv_accs):.4f}"
          f"  f1={np.mean(cv_f1s):.4f}±{np.std(cv_f1s):.4f}"
          f"  auc={np.mean(cv_aucs):.4f}±{np.std(cv_aucs):.4f}")

    # ── Final model on full training split ─────────────────────────────────────
    print("\nTraining final model on full training split …")
    final_net, _, _, n_epoch = train_fold(
        X_train_scaled, y_train, sw_train,
        X_test_scaled,  y_test,
        n_features, args
    )
    print(f"Final model stopped at epoch {n_epoch}")

    # ── Evaluation on held-out test set ───────────────────────────────────────
    X_test_t = torch.tensor(X_test_scaled, dtype=torch.float32)
    y_pred, y_proba, test_auc, test_f1 = evaluate(final_net, X_test_t, y_test)

    print(f"\n── Hold-out test set ─────────────────────────────────────")
    print(f"Accuracy : {accuracy_score(y_test, y_pred):.4f}")
    print(f"F1 score : {test_f1:.4f}")
    print(f"ROC-AUC  : {test_auc:.4f}")
    print(f"\nConfusion Matrix:\n{confusion_matrix(y_test, y_pred)}")
    print(f"\nClassification Report:\n"
          f"{classification_report(y_test, y_pred, digits=4, zero_division=0)}")

   
    

    # ── Save bundle ───────────────────────────────────────────────────────────
    bundle = {
        "model_state_dict": final_net.state_dict(),
        "n_features"      : n_features,
        "hidden_sizes"    : LivenessNet.DEFAULT_HIDDEN,
        "dropouts"        : LivenessNet.DEFAULT_DROPOUT,
        "feature_cols"    : feature_cols,
        "imputer"         : imputer,    
        "scaler"          : scaler,     
        "threshold"       : 0.4,        
    }
    torch.save(bundle, args.model_out)
    print(f"\nSaved model → {args.model_out}")


if __name__ == "__main__":
    main()
