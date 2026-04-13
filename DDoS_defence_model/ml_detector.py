#!/usr/bin/env python3
"""
IsolationForest-based anomaly detector for DDoS traffic.

Maintains per-IP rolling feature vectors (request rate, inter-arrival
statistics, path diversity, burst ratio) and scores them against a
model fit at startup on synthetic 'normal' traffic patterns. IPs
scoring as outliers are flagged as anomalous.

Runs on CPU. No external training data required; the synthetic fit is
deterministic via the random_state parameter.
"""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque
from typing import Any, cast

import numpy as np
from sklearn.ensemble import IsolationForest


class _IPRecord:
    """Rolling record of request events for one IP."""

    __slots__ = ("events",)

    def __init__(self):
        # Each entry is a (timestamp, path) pair. Using a single deque
        # keeps the two fields in lock-step when pruning.
        self.events: deque[tuple[float, str]] = deque(maxlen=200)


class MLDetector:
    """IsolationForest anomaly detector over per-IP feature vectors.

    Feature vector computed over a rolling window per IP:
      - request rate (requests per second over the window)
      - mean inter-arrival time (seconds)
      - stddev of inter-arrival times (low for uniform attackers,
        high for bursty humans)
      - path diversity (unique paths / total requests)
      - burst ratio (largest 1-second burst / total requests)
    """

    def __init__(
        self,
        window_seconds: int = 10,
        min_requests: int = 8,
        contamination: float = 0.05,
        random_state: int = 42,
    ):
        self.window_seconds = window_seconds
        self.min_requests = min_requests
        self.contamination = contamination
        self._ips: dict[str, _IPRecord] = defaultdict(_IPRecord)
        self._lock = threading.Lock()

        # IsolationForest accepts a float in [0, 0.5] or the string
        # "auto" for `contamination`, but sklearn's type stubs annotate
        # this parameter too strictly. Cast to Any to silence the
        # checker without changing runtime behaviour.
        self._model = IsolationForest(
            n_estimators=100,
            contamination=cast(Any, contamination),
            random_state=random_state,
        )
        self._train_model()

    def _train_model(self) -> None:
        """Fit the model on synthetic 'normal' traffic.

        Legitimate users make requests at low, irregular rates to a
        varied set of paths. We generate 1000 such samples with a
        fixed seed for reproducibility and fit the IsolationForest
        once at startup.
        """
        rng = np.random.default_rng(42)
        samples = np.empty((1000, 5), dtype=np.float64)
        for i in range(1000):
            rate = rng.uniform(0.1, 2.0)
            mean_gap = 1.0 / rate
            std_gap = mean_gap * rng.uniform(0.3, 0.8)
            path_diversity = rng.uniform(0.4, 1.0)
            burst_ratio = rng.uniform(0.0, 0.3)
            samples[i] = [rate, mean_gap, std_gap, path_diversity, burst_ratio]
        self._model.fit(samples)

    def record(self, ip: str, path: str) -> None:
        """Record a request event for later scoring."""
        with self._lock:
            record = self._ips[ip]
            now = time.time()
            cutoff = now - self.window_seconds
            events = record.events
            while events and events[0][0] < cutoff:
                events.popleft()
            events.append((now, path))

    def is_anomalous(self, ip: str) -> bool:
        """Return True if this IP's rolling behaviour is an outlier."""
        with self._lock:
            record = self._ips.get(ip)
            if record is None or len(record.events) < self.min_requests:
                return False
            features = self._compute_features(record)

        # IsolationForest.predict returns +1 for inliers, -1 for outliers
        prediction = self._model.predict(np.array([features]))
        return bool(prediction[0] == -1)

    def _compute_features(self, record: _IPRecord) -> list[float]:
        """Extract a 5-dim feature vector from an IP's event window."""
        events = list(record.events)
        n = len(events)
        timestamps = [ts for ts, _ in events]
        paths = [p for _, p in events]

        rate = n / max(self.window_seconds, 1)

        gaps = [timestamps[i] - timestamps[i - 1] for i in range(1, n)]
        if gaps:
            mean_gap = sum(gaps) / len(gaps)
            variance = sum((g - mean_gap) ** 2 for g in gaps) / len(gaps)
            std_gap = math.sqrt(variance)
        else:
            mean_gap = 0.0
            std_gap = 0.0

        path_diversity = len(set(paths)) / n

        # Burst ratio: largest number of events in any 1-second window,
        # as a fraction of total events. Uses a linear-time sliding
        # window over the sorted timestamps.
        max_burst = 0
        right = 0
        for left in range(n):
            while right < n and timestamps[right] - timestamps[left] < 1.0:
                right += 1
            burst = right - left
            if burst > max_burst:
                max_burst = burst
        burst_ratio = max_burst / n

        return [rate, mean_gap, std_gap, path_diversity, burst_ratio]


def _self_test():
    import random

    detector = MLDetector(window_seconds=5, min_requests=3)

    # Legitimate user: irregular slow requests to varied paths
    for _ in range(10):
        detector.record(
            "10.0.0.1",
            random.choice(["/api/balance", "/api/transactions", "/api/login"]),
        )
        time.sleep(0.5)
    print(f"legit user anomalous : {detector.is_anomalous('10.0.0.1')}")

    # Attacker: fast uniform requests to a single path
    for _ in range(50):
        detector.record("10.0.0.99", "/api/balance")
    print(f"attacker anomalous   : {detector.is_anomalous('10.0.0.99')}")


if __name__ == "__main__":
    _self_test()