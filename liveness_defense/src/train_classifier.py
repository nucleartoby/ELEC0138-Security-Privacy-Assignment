import argparse
import joblib
import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=str, default="celebdf_subset_features.csv")
    parser.add_argument("--model_out", type=str, default="rf_liveness_model.pkl")
    args = parser.parse_args()

    df = pd.read_csv(args.csv)

    drop_cols = ["video_path", "video_name", "label_name", "label"]
    feature_cols = [c for c in df.columns if c not in drop_cols]

    X = df[feature_cols]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )

    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("clf", RandomForestClassifier(
            n_estimators=500,
            max_depth=12,
            class_weight={0:1, 1:2},  # boost fake importance
            random_state=42
        ))
    ])

    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    print("\nAccuracy:", accuracy_score(y_test, y_pred))
    print("F1 score:", f1_score(y_test, y_pred))
    print("\nConfusion Matrix:\n", confusion_matrix(y_test, y_pred))
    print("\nClassification Report:\n", classification_report(y_test, y_pred, digits=4))
    clf = model.named_steps["clf"]
    importances = clf.feature_importances_

    for name, score in sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True):
        print(f"{name}: {score:.4f}")
    joblib.dump({
        "model": model,
        "feature_cols": feature_cols,
    }, args.model_out)

    print(f"\nSaved model to {args.model_out}")


if __name__ == "__main__":
    main()