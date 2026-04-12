"""
Face matcher wrapper: lightweight wrappers for face embedding comparison.
In production, replace with ArcFace/FaceNet model.
Provides: compare(face_img1, face_img2) -> {match_score, matched}
"""
import cv2
import numpy as np

class FaceMatcher:
    def __init__(self, model_path=None):
        self.model_path = model_path
        self._loaded = True

    def _get_embedding(self, img_cv2):
        # Simple embedding: color histogram + HOG-like features
        try:
            img = cv2.resize(img_cv2, (128,128))
            hist = cv2.calcHist([img], [0,1,2], None, [8,8,8], [0,256,0,256,0,256])
            hist = cv2.normalize(hist, hist).flatten()
            return hist
        except Exception:
            return None

    def compare(self, img1, img2):
        try:
            emb1 = self._get_embedding(img1)
            emb2 = self._get_embedding(img2)
            if emb1 is None or emb2 is None:
                return {'match_score': 0.0, 'matched': False}
            # Cosine similarity
            dot = np.dot(emb1, emb2)
            denom = (np.linalg.norm(emb1) * np.linalg.norm(emb2))
            sim = float(dot / denom) if denom>0 else 0.0
            score = round(sim * 100, 2)
            return {'match_score': score, 'matched': score > 60}
        except Exception as e:
            return {'match_score': 0.0, 'matched': False, 'error': str(e)}
