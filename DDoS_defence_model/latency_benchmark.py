#!/usr/bin/env python3
"""
Latency overhead benchmark.

Measures per-request response-time distribution (p50, p95, p99) for a
single legitimate user, with and without the defence enabled, under no
attack. The intent is to show that the defence adds negligible latency
to normal operation.

Requests are paced at 2 per second (below the default token bucket
refill rate of 5/s) so the rate limiter never fires during the
measurement — any blocks would reject the response and skew the
percentile statistics.

Prerequisites: both servers running.
    python protected_server.py --no-defence --port 5001
    python protected_server.py --port 5002
    python latency_benchmark.py
"""

from __future__ import annotations

import argparse
import csv
import statistics
import time

import requests


def _measure(url: str, samples: int, interval: float) -> list[float]:
    """Return a list of successful request durations in milliseconds."""
    timings: list[float] = []
    rejected = 0
    session = requests.Session()

    # Warmup (not recorded) — lets DNS, TCP and Flask thread pools
    # stabilise before we start measuring.
    for _ in range(5):
        try:
            session.get(f"{url}/api/balance", timeout=5)
        except requests.exceptions.RequestException:
            pass
        time.sleep(interval)

    for i in range(samples):
        start = time.perf_counter()
        try:
            r = session.get(f"{url}/api/balance", timeout=5)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            if r.status_code == 200:
                timings.append(elapsed_ms)
            else:
                rejected += 1
        except requests.exceptions.RequestException:
            rejected += 1
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{samples}")
        time.sleep(interval)

    if rejected:
        print(f"  (warning: {rejected}/{samples} requests were rejected and "
              f"excluded from timings)")
    return timings


def _percentile(data: list[float], pct: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * pct / 100.0
    lower = int(k)
    upper = min(lower + 1, len(s) - 1)
    if lower == upper:
        return s[lower]
    return s[lower] + (s[upper] - s[lower]) * (k - lower)


def _summarise(name: str, times: list[float]) -> dict | None:
    if not times:
        print(f"{name}: no samples")
        return None
    mean = statistics.mean(times)
    p50 = _percentile(times, 50)
    p95 = _percentile(times, 95)
    p99 = _percentile(times, 99)
    print(f"{name:<12s} n={len(times):>4d}  mean={mean:6.2f} ms  "
          f"p50={p50:6.2f}  p95={p95:6.2f}  p99={p99:6.2f}")
    return {"name": name, "n": len(times), "mean": mean,
            "p50": p50, "p95": p95, "p99": p99}


def main():
    parser = argparse.ArgumentParser(description="Latency overhead benchmark")
    parser.add_argument("--vulnerable-url", default="http://localhost:5001")
    parser.add_argument("--defended-url", default="http://localhost:5002")
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--interval", type=float, default=0.5,
                        help="Seconds between requests (default 0.5 = 2/s)")
    parser.add_argument("--csv", default="latency_results.csv")
    args = parser.parse_args()

    for label, url in [("vulnerable", args.vulnerable_url),
                       ("defended",   args.defended_url)]:
        try:
            requests.get(f"{url}/api/health", timeout=2)
        except requests.exceptions.RequestException as e:
            print(f"{label} {url} unreachable: {e}")
            return

    print(f"Sampling {args.samples} sequential requests per server "
          f"at {1 / args.interval:.1f} req/s")
    print()
    print("Vulnerable:")
    vuln_times = _measure(args.vulnerable_url, args.samples, args.interval)
    print("Defended:")
    def_times = _measure(args.defended_url, args.samples, args.interval)

    print()
    v = _summarise("vulnerable", vuln_times)
    d = _summarise("defended", def_times)
    print()

    if v is None or d is None:
        return

    overhead_mean = d["mean"] - v["mean"]
    overhead_p50 = d["p50"] - v["p50"]
    overhead_p95 = d["p95"] - v["p95"]
    overhead_p99 = d["p99"] - v["p99"]
    print("defence overhead")
    print(f"  mean : {overhead_mean:+.2f} ms")
    print(f"  p50  : {overhead_p50:+.2f} ms")
    print(f"  p95  : {overhead_p95:+.2f} ms")
    print(f"  p99  : {overhead_p99:+.2f} ms")

    with open(args.csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "vulnerable_ms", "defended_ms", "overhead_ms"])
        w.writerow(["mean", f"{v['mean']:.2f}", f"{d['mean']:.2f}", f"{overhead_mean:+.2f}"])
        w.writerow(["p50",  f"{v['p50']:.2f}",  f"{d['p50']:.2f}",  f"{overhead_p50:+.2f}"])
        w.writerow(["p95",  f"{v['p95']:.2f}",  f"{d['p95']:.2f}",  f"{overhead_p95:+.2f}"])
        w.writerow(["p99",  f"{v['p99']:.2f}",  f"{d['p99']:.2f}",  f"{overhead_p99:+.2f}"])
    print(f"\ncsv saved : {args.csv}")


if __name__ == "__main__":
    main()