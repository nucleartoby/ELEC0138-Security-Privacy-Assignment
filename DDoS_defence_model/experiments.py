#!/usr/bin/env python3
"""
Five-variant attack evaluation.

Runs a series of distinct attack patterns against the defended server
and records block rate + per-layer breakdown for each. Outputs a CSV
and a markdown table ready for the report.

Prerequisite: defended server must be running at --target URL.

    python protected_server.py --port 5002
    python experiments.py --target http://localhost:5002
"""

from __future__ import annotations

import argparse
import csv
import random
import threading
import time

import requests


# Each variant is (name, description, runner_fn)
# Runner takes (target, duration) and returns nothing (just sends traffic).


def _single_source_burst(target: str, duration: int) -> None:
    """Classic flood: one IP, many threads, sustained."""
    stop = [False]

    def worker():
        s = requests.Session()
        while not stop[0]:
            try:
                s.get(f"{target}/api/balance", timeout=2)
            except requests.exceptions.RequestException:
                pass

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(50)]
    for t in threads:
        t.start()
    time.sleep(duration)
    stop[0] = True
    time.sleep(0.5)


def _sustained_flood(target: str, duration: int) -> None:
    """Lower thread count, longer duration — tests sliding window."""
    stop = [False]

    def worker():
        s = requests.Session()
        while not stop[0]:
            try:
                s.get(f"{target}/api/balance", timeout=2)
            except requests.exceptions.RequestException:
                pass

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(15)]
    for t in threads:
        t.start()
    time.sleep(duration)
    stop[0] = True
    time.sleep(0.5)


def _distributed_botnet(target: str, duration: int) -> None:
    """Spoofed source IPs simulating a 20-node botnet."""
    stop = [False]
    bots = [f"172.16.{random.randint(0, 255)}.{random.randint(1, 254)}"
            for _ in range(20)]

    def worker():
        s = requests.Session()
        while not stop[0]:
            ip = random.choice(bots)
            try:
                s.get(f"{target}/api/balance",
                      headers={"X-Forwarded-For": ip},
                      timeout=2)
            except requests.exceptions.RequestException:
                pass

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(40)]
    for t in threads:
        t.start()
    time.sleep(duration)
    stop[0] = True
    time.sleep(0.5)


def _slow_drip(target: str, duration: int) -> None:
    """Low-and-slow: 100 bots each making 1 req/sec. Designed to
    bypass rate limits by staying under per-IP thresholds."""
    stop = [False]
    bots = [f"10.20.{random.randint(0, 255)}.{random.randint(1, 254)}"
            for _ in range(100)]

    def worker(ip):
        s = requests.Session()
        while not stop[0]:
            try:
                s.get(f"{target}/api/balance",
                      headers={"X-Forwarded-For": ip},
                      timeout=2)
            except requests.exceptions.RequestException:
                pass
            time.sleep(1.0)

    threads = [threading.Thread(target=worker, args=(ip,), daemon=True)
               for ip in bots]
    for t in threads:
        t.start()
    time.sleep(duration)
    stop[0] = True
    time.sleep(0.5)


def _mixed_pattern(target: str, duration: int) -> None:
    """Realistic mix: 10 bots alternating between bursts and idle
    periods, rotating target endpoints."""
    stop = [False]
    bots = [f"192.0.2.{random.randint(1, 254)}" for _ in range(10)]
    # Only non-exempt paths — /api/health bypasses the defence entirely
    paths = ["/api/balance", "/api/transactions"]

    def worker(ip):
        s = requests.Session()
        while not stop[0]:
            # Burst phase
            for _ in range(15):
                if stop[0]:
                    return
                try:
                    s.get(f"{target}{random.choice(paths)}",
                          headers={"X-Forwarded-For": ip},
                          timeout=2)
                except requests.exceptions.RequestException:
                    pass
            # Idle phase
            time.sleep(0.5)

    threads = [threading.Thread(target=worker, args=(ip,), daemon=True)
               for ip in bots]
    for t in threads:
        t.start()
    time.sleep(duration)
    stop[0] = True
    time.sleep(0.5)


VARIANTS = [
    ("A", "Single-source burst",
     "50 threads, one IP, sustained flood",
     _single_source_burst),
    ("B", "Sustained flood",
     "15 threads, one IP, longer duration — tests sliding window",
     _sustained_flood),
    ("C", "Distributed botnet",
     "40 threads across 20 spoofed bot IPs",
     _distributed_botnet),
    ("D", "Slow drip (low-and-slow)",
     "100 bots at 1 req/sec — attempts to bypass rate limits",
     _slow_drip),
    ("E", "Mixed burst/idle",
     "10 bots alternating burst and idle phases across multiple endpoints",
     _mixed_pattern),
]


def _fetch_stats(target: str) -> dict:
    try:
        r = requests.get(f"{target}/api/stats", timeout=2)
        return r.json()
    except requests.exceptions.RequestException:
        return {}


def _reset_stats(target: str) -> None:
    try:
        requests.post(f"{target}/api/defence/reset", timeout=2)
    except requests.exceptions.RequestException:
        pass


def _run_variant(name: str, description: str, detail: str, runner, target: str, duration: int) -> dict:
    print(f"Running variant {name}: {description}")
    print(f"  {detail}")
    _reset_stats(target)
    time.sleep(0.5)

    runner(target, duration)
    time.sleep(1.0)

    stats = _fetch_stats(target)
    server = stats.get("server", {})
    defence = stats.get("defence", {})
    total = server.get("total_requests", 0)
    allowed = defence.get("allowed", 0)
    blocked = defence.get("total_blocked", 0)
    block_rate = (blocked / total * 100) if total else 0.0

    result = {
        "variant": name,
        "name": description,
        "total": total,
        "allowed": allowed,
        "blocked": blocked,
        "block_rate": round(block_rate, 1),
        "blocked_blocklist": defence.get("blocked_blocklist", 0),
        "blocked_rate_limit": defence.get("blocked_rate_limit", 0),
        "blocked_anomaly": defence.get("blocked_anomaly", 0),
        "blocked_reputation": defence.get("blocked_reputation", 0),
        "blocked_ml": defence.get("blocked_ml", 0),
    }
    print(f"  total={total} allowed={allowed} blocked={blocked} "
          f"block_rate={block_rate:.1f}%")
    print()
    return result


def _write_csv(results: list, path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)


def _write_markdown(results: list, path: str) -> None:
    """Write a markdown table ready to paste into the report."""
    with open(path, "w") as f:
        f.write("# Attack Variant Evaluation\n\n")
        f.write("| Variant | Attack Pattern | Total | Allowed | Blocked | Block Rate |\n")
        for r in results:
            f.write(f"| {r['variant']} | {r['name']} | "
                    f"{r['total']:,} | {r['allowed']:,} | "
                    f"{r['blocked']:,} | {r['block_rate']:.1f}% |\n")

        f.write("\n## Per-layer breakdown\n\n")
        f.write("| Variant | Blocklist | Rate Limit | Anomaly | Reputation | ML |\n")
        for r in results:
            f.write(f"| {r['variant']} | {r['blocked_blocklist']:,} | "
                    f"{r['blocked_rate_limit']:,} | "
                    f"{r['blocked_anomaly']:,} | "
                    f"{r['blocked_reputation']:,} | "
                    f"{r['blocked_ml']:,} |\n")


def main():
    parser = argparse.ArgumentParser(description="Five-variant attack evaluation")
    parser.add_argument("--target", default="http://localhost:5002",
                        help="Defended server URL")
    parser.add_argument("--duration", type=int, default=10,
                        help="Duration of each variant in seconds")
    parser.add_argument("--csv", default="experiments_results.csv")
    parser.add_argument("--md", default="experiments_results.md")
    args = parser.parse_args()

    # Check target is reachable
    try:
        h = requests.get(f"{args.target}/api/health", timeout=2).json()
        print(f"Target: {args.target} (defence={h.get('defence_enabled')})")
        if not h.get("defence_enabled"):
            print("Warning: target has defence DISABLED. Start with:")
            print("  python protected_server.py --port 5002")
            return
    except requests.exceptions.RequestException as e:
        print(f"Target unreachable: {e}")
        print("Start the defended server first:")
        print("  python protected_server.py --port 5002")
        return

    print()
    results = []
    for variant, name, detail, runner in VARIANTS:
        r = _run_variant(variant, name, detail, runner, args.target, args.duration)
        results.append(r)
        time.sleep(2)  # cooldown between variants

    _write_csv(results, args.csv)
    _write_markdown(results, args.md)

    print("Summary")
    print(f"{'variant':<10s} {'name':<30s} {'total':>8s} {'blocked':>9s} {'rate':>8s}")
    for r in results:
        print(f"{r['variant']:<10s} {r['name']:<30s} "
              f"{r['total']:>8,} {r['blocked']:>9,} {r['block_rate']:>7.1f}%")
    print()
    print(f"csv        : {args.csv}")
    print(f"markdown   : {args.md}")


if __name__ == "__main__":
    main()