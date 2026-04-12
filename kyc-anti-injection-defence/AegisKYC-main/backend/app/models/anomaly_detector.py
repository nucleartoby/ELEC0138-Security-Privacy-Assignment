"""
Anomaly detector for session/behavioral signals (scaffolding)
Provides: detect(features) -> {anomaly_score, is_anomaly, details}
"""
import numpy as np

class AnomalyDetector:
    def __init__(self, model_path=None):
        self.model_path = model_path
        self._loaded = True

    def detect(self, features: dict):
        """
        features: dict of numerical signals (typing_speed, error_rate, mouse_smoothness, etc.)
        """
        try:
            keys = ['typing_speed','error_rate','mouse_smoothness','session_duration']
            vals = [float(features.get(k,0.0)) for k in keys]
            # Simple z-score like heuristic against benign baseline
            baseline = np.array([40.0, 0.05, 0.8, 300.0])
            diffs = np.abs((np.array(vals) - baseline) / (baseline + 1e-6))
            score = float(np.mean(diffs))
            anomaly_score = round(min(1.0, score/2.0),3)
            is_anomaly = anomaly_score > 0.4
            return {'anomaly_score': anomaly_score, 'is_anomaly': is_anomaly, 'details': {'diffs': diffs.tolist()}}
        except Exception as e:
            return {'anomaly_score': 0.5, 'is_anomaly': False, 'details': {'error': str(e)}}
