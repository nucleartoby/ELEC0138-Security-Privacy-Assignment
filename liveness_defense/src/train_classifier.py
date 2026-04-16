import argparse
import joblib
import pandas as pd
import numpy as np

from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPClassifier
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.metrics import (
    classification_report, confusion_matrix,
    accuracy_score, f1_score, roc_auc_score,
)
from sklearn.inspection import permutation_importance


def build_model():
    """
    Pipeline: median imputation → z-score scaling → MLP classifier.

    Architecture: 35 features → 128 → 64 → 32 → sigmoid output
    - ReLU activations, Adam optimiser, adaptive learning rate
    - L2 weight decay (alpha=0.01) prevents overfitting on small datasets
    - Early stopping on a held-out validation slice so we never over-train
    Class imbalance is handled externally via sample_weight (2x on fakes),
    because MLPClassifier has no built-in class_weight parameter.
    """
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler",  StandardScaler()),
        ("clf", MLPClassifier(
            hidden_layer_sizes=(128, 64, 32),   # 3 hidden layers, shrinking
            activation="relu",
            solver="adam",
            alpha=0.01,                         # L2 weight decay
            batch_size=32,
            learning_rate="adaptive",           # halves lr when loss plateaus
            learning_rate_init=0.001,
            max_iter=1000,
            early_stopping=True,                # stops before overfitting
            validation_fraction=0.15,           # held out from training split
            n_iter_no_change=30,                # patience
            random_state=42,
            verbose=False,
        )),
    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv",       type=str, default="celebdf_subset_features.csv")
    parser.add_argument("--model_out", type=str, default="rf_liveness_model.pkl")
    parser.add_argument("--cv_folds",  type=int, default=4)
    parser.add_argument("--fake_weight", type=float, default=2.0,
                        help="Sample weight multiplier for fake class (default 2.0)")
    args = parser.parse_args()

    # ── Load ──────────────────────────────────────────────────────────────────
    df = pd.read_csv(args.csv)
    print(f"Loaded {len(df)} samples")
    print(df["label_name"].value_counts(dropna=False).to_string())

    drop_cols    = ["video_path", "video_name", "label_name", "label"]
    feature_cols = [c for c in df.columns if c not in drop_cols]

    X = df[feature_cols].values.astype(np.float64)
    y = df["label"].values.astype(int)

    n_real = int(np.sum(y == 0))
    n_fake = int(np.sum(y == 1))
    print(f"\nClass distribution — real: {n_real}  fake: {n_fake}")
    print(f"Fake sample weight multiplier: {args.fake_weight}x")

    # ── 4-fold stratified cross-validation ────────────────────────────────────
    print(f"\nRunning {args.cv_folds}-fold stratified CV …")
    skf     = StratifiedKFold(n_splits=args.cv_folds, shuffle=True, random_state=42)
    cv_accs, cv_f1s, cv_aucs = [], [], []

    for fold, (tr_idx, val_idx) in enumerate(skf.split(X, y), 1):
        X_tr, X_val = X[tr_idx], X[val_idx]
        y_tr, y_val = y[tr_idx], y[val_idx]

        # Upweight fakes so the MLP penalises false negatives more
        sw = compute_sample_weight(
            class_weight={0: 1.0, 1: args.fake_weight}, y=y_tr
        )

        m = build_model()
        m.fit(X_tr, y_tr, clf__sample_weight=sw)

        y_pred  = m.predict(X_val)
        y_proba = m.predict_proba(X_val)[:, 1]

        acc = accuracy_score(y_val, y_pred)
        f1  = f1_score(y_val, y_pred, zero_division=0)
        auc = roc_auc_score(y_val, y_proba)
        cv_accs.append(acc); cv_f1s.append(f1); cv_aucs.append(auc)

        print(f"  Fold {fold}:  acc={acc:.4f}  f1={f1:.4f}  auc={auc:.4f}"
              f"  (stopped @ iter {m.named_steps['clf'].n_iter_})")

    print(f"\nCV mean — acc={np.mean(cv_accs):.4f}±{np.std(cv_accs):.4f}"
          f"  f1={np.mean(cv_f1s):.4f}±{np.std(cv_f1s):.4f}"
          f"  auc={np.mean(cv_aucs):.4f}±{np.std(cv_aucs):.4f}")

    # ── Final model on 80/20 hold-out ─────────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    sw_train = compute_sample_weight(
        class_weight={0: 1.0, 1: args.fake_weight}, y=y_train
    )

    final_model = build_model()
    final_model.fit(X_train, y_train, clf__sample_weight=sw_train)

    y_pred  = final_model.predict(X_test)
    y_proba = final_model.predict_proba(X_test)[:, 1]

    print(f"\n── Hold-out test set ─────────────────────────────────────")
    print(f"Accuracy : {accuracy_score(y_test, y_pred):.4f}")
    print(f"F1 score : {f1_score(y_test, y_pred, zero_division=0):.4f}")
    print(f"ROC-AUC  : {roc_auc_score(y_test, y_proba):.4f}")
    print(f"\nConfusion Matrix:\n{confusion_matrix(y_test, y_pred)}")
    print(f"\nClassification Report:\n"
          f"{classification_report(y_test, y_pred, digits=4, zero_division=0)}")
    print(f"MLP converged in {final_model.named_steps['clf'].n_iter_} iterations")

    # ── Permutation feature importance (MLP has no built-in importances) ──────
    print("\n── Top 15 features by permutation importance ────────────")
    perm = permutation_importance(
        final_model, X_test, y_test,
        n_repeats=20, random_state=42, scoring="f1"
    )
    indices = np.argsort(perm.importances_mean)[::-1]
    for i in indices[:15]:
        print(f"  {feature_cols[i]:<30}  "
              f"mean={perm.importances_mean[i]:.4f}  "
              f"std={perm.importances_std[i]:.4f}")

    # ── Inference latency ─────────────────────────────────────────────────────
    import time
    sample = X_test[:1]
    for _ in range(50): final_model.predict_proba(sample)   # warm-up
    t0 = time.perf_counter()
    for _ in range(2000): final_model.predict_proba(sample)
    lat_ms = (time.perf_counter() - t0) / 2.0
    print(f"\n── Inference latency ─────────────────────────────────────")
    print(f"  {lat_ms:.4f} ms per call  "
          f"({lat_ms / 33.3 * 100:.1f}% of 30fps frame budget)")

    # ── Save ──────────────────────────────────────────────────────────────────
    joblib.dump({"model": final_model, "feature_cols": feature_cols}, args.model_out)
    print(f"\nSaved model → {args.model_out}")


if __name__ == "__main__":
    main()
