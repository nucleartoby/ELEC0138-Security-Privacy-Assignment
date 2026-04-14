import joblib
import pandas as pd
from extract_features import extract_features_from_video

MODEL_PATH = "rf_liveness_model.pkl"

bundle = joblib.load(MODEL_PATH)
model = bundle["model"]
feature_cols = bundle["feature_cols"]

def predict_video(video_path, max_frames=150):
    feats = extract_features_from_video(video_path, max_frames=max_frames)
    if feats is None:
        return None

    x = pd.DataFrame([feats])
    x = x.reindex(columns=feature_cols, fill_value=0)

    prob = model.predict_proba(x)[0][1]
    pred = 1 if prob >= 0.4 else 0

    return {
        "prediction": int(pred),   # 0 real, 1 fake
        "fake_probability": float(prob),
        "features": feats
    }

if __name__ == "__main__":
    import sys

    video_path = sys.argv[1] if len(sys.argv) > 1 else "test.mp4"

    result = predict_video(video_path)

    if result is None:
        print("Could not extract features")
    else:
        print("\nPrediction:", "FAKE" if result["prediction"] == 1 else "REAL")
        print("Fake probability:", result["fake_probability"])



def predict_features(feats):
    import pandas as pd

    x = pd.DataFrame([feats])
    x = x.reindex(columns=feature_cols, fill_value=0)

    prob = model.predict_proba(x)[0][1]
    pred = 1 if prob > 0.4 else 0

    return pred, prob