#!/usr/bin/env python3
"""
DDoS defence engine: multi-layer request evaluation.

Exposes DDoSDefence, DefenceConfig and Verdict. Each incoming request is
evaluated by five layers in order. The first layer that fires decides
the outcome. Layers 3-5 feed into a reputation score that can promote an
IP to the dynamic blocklist, at which point subsequent requests from
that IP are rejected by Layer 1 in constant time.

    1. IPBlocklist           static + dynamic blocklist
    2. ReputationTracker     score-based blocking with time decay
    3. TokenBucket           per-IP burst + sustained rate limit
    4. SlidingWindowDetector rolling-window request count anomaly
    5. MLDetector            IsolationForest-based statistical anomaly
"""

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class Verdict(Enum):
    ALLOW = "ALLOW"
    BLOCK_BLOCKLIST = "BLOCK_BLOCKLIST"
    BLOCK_RATE_LIMIT = "BLOCK_RATE_LIMIT"
    BLOCK_ANOMALY = "BLOCK_ANOMALY"
    BLOCK_REPUTATION = "BLOCK_REPUTATION"
    BLOCK_ML = "BLOCK_ML"


@dataclass
class DefenceConfig:
    # Token bucket
    bucket_capacity: int = 20
    refill_rate: float = 5.0
    # Sliding window anomaly detector
    window_seconds: int = 10
    window_threshold: int = 80
    # Reputation
    reputation_decay_rate: float = 0.1
    reputation_block_threshold: float = 100.0
    reputation_autoblock_threshold: float = 60.0
    penalty_rate_limit: float = 5.0
    penalty_anomaly: float = 20.0
    penalty_ml: float = 15.0
    # Auto-blocklist
    auto_block_seconds: int = 60
    # ML detector
    ml_enabled: bool = True
    ml_min_requests: int = 8
    ml_contamination: float = 0.05


@dataclass
class _BucketState:
    tokens: float = 0.0
    last_refill: float = 0.0
    initialised: bool = False


class IPBlocklist:
    """Static + dynamic (time-limited) IP blocklist."""

    def __init__(self):
        self._static: set[str] = set()
        self._dynamic: dict[str, float] = {}
        self._lock = threading.Lock()

    def add_static(self, ip: str) -> None:
        with self._lock:
            self._static.add(ip)

    def add_dynamic(self, ip: str, duration: int) -> None:
        with self._lock:
            self._dynamic[ip] = time.time() + duration

    def is_blocked(self, ip: str) -> bool:
        with self._lock:
            if ip in self._static:
                return True
            expiry = self._dynamic.get(ip)
            if expiry is None:
                return False
            if time.time() < expiry:
                return True
            del self._dynamic[ip]
            return False

    def size(self) -> tuple[int, int]:
        with self._lock:
            return len(self._static), len(self._dynamic)


class TokenBucket:
    """Per-IP token bucket rate limiter.

    Each IP has a bucket of `bucket_capacity` tokens that refills at
    `refill_rate` tokens per second. Each request costs one token.
    Allows short bursts up to the capacity but caps sustained traffic
    at the refill rate.
    """

    def __init__(self, config: DefenceConfig):
        self.config = config
        self._states: dict[str, _BucketState] = defaultdict(_BucketState)
        self._lock = threading.Lock()

    def allow(self, ip: str) -> bool:
        with self._lock:
            state = self._states[ip]
            now = time.time()

            if not state.initialised:
                state.tokens = float(self.config.bucket_capacity)
                state.last_refill = now
                state.initialised = True

            elapsed = now - state.last_refill
            state.tokens = min(
                float(self.config.bucket_capacity),
                state.tokens + elapsed * self.config.refill_rate,
            )
            state.last_refill = now

            if state.tokens >= 1.0:
                state.tokens -= 1.0
                return True
            return False


class SlidingWindowDetector:
    """Rolling window of request timestamps per IP.

    Flags an IP when it has made more than `window_threshold` requests
    in the last `window_seconds` seconds.
    """

    def __init__(self, config: DefenceConfig):
        self.config = config
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def record_and_check(self, ip: str) -> bool:
        with self._lock:
            now = time.time()
            window = self._windows[ip]
            window.append(now)

            cutoff = now - self.config.window_seconds
            while window and window[0] < cutoff:
                window.popleft()

            return len(window) > self.config.window_threshold


class ReputationTracker:
    """Per-IP reputation score with linear time decay.

    Penalties from defence layers add points; points decay at
    `reputation_decay_rate` per second so legitimate users who briefly
    exceed a threshold recover automatically.
    """

    def __init__(self, config: DefenceConfig):
        self.config = config
        self._scores: dict[str, float] = defaultdict(float)
        self._last_update: dict[str, float] = {}
        self._lock = threading.Lock()

    def penalise(self, ip: str, points: float) -> None:
        with self._lock:
            self._decay_locked(ip)
            self._scores[ip] += points

    def get_score(self, ip: str) -> float:
        with self._lock:
            self._decay_locked(ip)
            return self._scores[ip]

    def is_bad(self, ip: str) -> bool:
        return self.get_score(ip) >= self.config.reputation_block_threshold

    def _decay_locked(self, ip: str) -> None:
        now = time.time()
        last = self._last_update.get(ip, now)
        elapsed = now - last
        if elapsed > 0:
            self._scores[ip] = max(
                0.0,
                self._scores[ip] - elapsed * self.config.reputation_decay_rate,
            )
        self._last_update[ip] = now


class DDoSDefence:
    """Orchestrates all defence layers. Thread-safe."""

    def __init__(self, config: Optional[DefenceConfig] = None):
        self.config = config or DefenceConfig()
        self.blocklist = IPBlocklist()
        self.bucket = TokenBucket(self.config)
        self.detector = SlidingWindowDetector(self.config)
        self.reputation = ReputationTracker(self.config)
        self.ml_detector = self._make_ml_detector()

        self.stats: dict[str, int] = {
            "total_requests": 0,
            "allowed": 0,
            "blocked_blocklist": 0,
            "blocked_rate_limit": 0,
            "blocked_anomaly": 0,
            "blocked_reputation": 0,
            "blocked_ml": 0,
        }
        self._stats_lock = threading.Lock()
        self.enabled = True

    def _make_ml_detector(self):
        """Create an MLDetector if sklearn is available, else None."""
        if not self.config.ml_enabled:
            return None
        try:
            from ml_detector import MLDetector
        except ImportError:
            return None
        return MLDetector(
            window_seconds=self.config.window_seconds,
            min_requests=self.config.ml_min_requests,
            contamination=self.config.ml_contamination,
        )

    def evaluate(self, ip: str, path: str = "/") -> Verdict:
        with self._stats_lock:
            self.stats["total_requests"] += 1

        if not self.enabled:
            with self._stats_lock:
                self.stats["allowed"] += 1
            return Verdict.ALLOW

        # Layer 1: blocklist — constant-time rejection for known bad IPs
        if self.blocklist.is_blocked(ip):
            self._record("blocked_blocklist")
            return Verdict.BLOCK_BLOCKLIST

        # Layer 2: reputation check
        if self.reputation.is_bad(ip):
            self._record("blocked_reputation")
            self.blocklist.add_dynamic(ip, self.config.auto_block_seconds)
            return Verdict.BLOCK_REPUTATION

        # Layer 3: token bucket rate limit
        if not self.bucket.allow(ip):
            self._record("blocked_rate_limit")
            self.reputation.penalise(ip, self.config.penalty_rate_limit)
            return Verdict.BLOCK_RATE_LIMIT

        # Layer 4: sliding-window anomaly detector
        if self.detector.record_and_check(ip):
            self._record("blocked_anomaly")
            self.reputation.penalise(ip, self.config.penalty_anomaly)
            self._maybe_auto_block(ip)
            return Verdict.BLOCK_ANOMALY

        # Layer 5: ML anomaly detector (IsolationForest)
        if self.ml_detector is not None:
            self.ml_detector.record(ip, path)
            if self.ml_detector.is_anomalous(ip):
                self._record("blocked_ml")
                self.reputation.penalise(ip, self.config.penalty_ml)
                self._maybe_auto_block(ip)
                return Verdict.BLOCK_ML

        with self._stats_lock:
            self.stats["allowed"] += 1
        return Verdict.ALLOW

    def _maybe_auto_block(self, ip: str) -> None:
        """Promote to dynamic blocklist if reputation crosses threshold."""
        if self.reputation.get_score(ip) >= self.config.reputation_autoblock_threshold:
            self.blocklist.add_dynamic(ip, self.config.auto_block_seconds)

    def _record(self, key: str) -> None:
        with self._stats_lock:
            self.stats[key] += 1

    def get_stats(self) -> dict[str, Any]:
        with self._stats_lock:
            out: dict[str, Any] = dict(self.stats)
        total_blocked = sum(
            v for k, v in out.items() if k.startswith("blocked_")
        )
        out["total_blocked"] = total_blocked
        total = out["total_requests"]
        out["block_rate"] = (total_blocked / total) if total else 0.0
        static, dynamic = self.blocklist.size()
        out["blocklist_static"] = static
        out["blocklist_dynamic"] = dynamic
        out["enabled"] = self.enabled
        return out

    def reset(self) -> None:
        self.blocklist = IPBlocklist()
        self.bucket = TokenBucket(self.config)
        self.detector = SlidingWindowDetector(self.config)
        self.reputation = ReputationTracker(self.config)
        self.ml_detector = self._make_ml_detector()
        with self._stats_lock:
            for k in self.stats:
                self.stats[k] = 0

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled


def _self_test():
    cfg = DefenceConfig(
        bucket_capacity=10,
        refill_rate=2.0,
        window_threshold=30,
        window_seconds=5,
    )
    defence = DDoSDefence(cfg)

    # Phase 1: legitimate user, 1 request every 0.5s
    phase1_allowed = 0
    for _ in range(5):
        if defence.evaluate("10.0.0.1") == Verdict.ALLOW:
            phase1_allowed += 1
        time.sleep(0.5)

    # Phase 2: attacker, 50 rapid requests from one IP
    phase2_blocked = sum(
        1 for _ in range(50)
        if defence.evaluate("10.0.0.99") != Verdict.ALLOW
    )

    # Phase 3: distributed, 10 IPs x 20 requests
    for i in range(10):
        for _ in range(20):
            defence.evaluate(f"172.16.0.{i}")

    stats = defence.get_stats()
    print(f"Phase 1 legit user    : {phase1_allowed}/5 allowed")
    print(f"Phase 2 attacker      : {phase2_blocked}/50 blocked")
    print(f"Phase 3 distributed   : 200 requests sent")
    print()
    for key in ("total_requests", "allowed",
                "blocked_blocklist", "blocked_rate_limit",
                "blocked_anomaly", "blocked_reputation",
                "blocked_ml", "total_blocked"):
        print(f"  {key:22s} {stats[key]}")
    print(f"  block_rate             {stats['block_rate']:.1%}")


if __name__ == "__main__":
    _self_test()