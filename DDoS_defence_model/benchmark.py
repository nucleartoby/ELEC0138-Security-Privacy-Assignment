#!/usr/bin/env python3
"""
Before/after benchmark.

Runs identical attacks against two servers (one vulnerable, one defended)
and writes a comparison CSV plus a bar chart PNG.

Prerequisites — start both servers in separate terminals:
    python protected_server.py --no-defence --port 5001
    python protected_server.py --port 5002
"""

import argparse
import csv
import threading
import time

import requests


class Benchmark:
    def __init__(self, url: str, threads: int, duration: int, label: str):
        self.url = url.rstrip("/")
        self.threads = threads
        self.duration = duration
        self.label = label
        self._running = False

    def _flood(self):
        session = requests.Session()
        while self._running:
            try:
                session.get(f"{self.url}/api/balance", timeout=2)
            except requests.exceptions.RequestException:
                pass

    def run(self) -> dict:
        print(f"Running: {self.label}")
        print(f"  url      : {self.url}")
        print(f"  threads  : {self.threads}")
        print(f"  duration : {self.duration}s")

        try:
            requests.post(f"{self.url}/api/defence/reset", timeout=2)
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.5)

        self._running = True
        workers = [
            threading.Thread(target=self._flood, daemon=True)
            for _ in range(self.threads)
        ]
        for w in workers:
            w.start()

        time.sleep(self.duration)
        self._running = False
        time.sleep(1.0)

        try:
            final = requests.get(f"{self.url}/api/stats", timeout=2).json()
            s = final.get("server", {})
            d = final.get("defence", {})
            print(f"  result   : total={s.get('total_requests', 0)} "
                  f"allowed={d.get('allowed', 0)} "
                  f"blocked={d.get('total_blocked', 0)}")
            return final
        except requests.exceptions.RequestException as e:
            print(f"  result   : server unreachable at end of test ({e})")
            return {}


def extract(result: dict) -> dict:
    if not result:
        return {"total": 0, "allowed": 0, "blocked": 0}
    s = result.get("server", {})
    d = result.get("defence", {})
    if s.get("defence_enabled"):
        allowed = d.get("allowed", 0)
        blocked = d.get("total_blocked", 0)
    else:
        allowed = s.get("processed_requests", 0)
        blocked = s.get("rejected_requests", 0)
    return {
        "total": s.get("total_requests", 0),
        "allowed": allowed,
        "blocked": blocked,
    }


def save_csv(vuln: dict, defended: dict, path: str) -> None:
    v_pct = (vuln["blocked"] / vuln["total"] * 100) if vuln["total"] else 0
    d_pct = (defended["blocked"] / defended["total"] * 100) if defended["total"] else 0
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "vulnerable", "defended"])
        w.writerow(["total_requests", vuln["total"], defended["total"]])
        w.writerow(["served_200", vuln["allowed"], defended["allowed"]])
        w.writerow(["blocked", vuln["blocked"], defended["blocked"]])
        w.writerow(["block_rate_pct", f"{v_pct:.1f}", f"{d_pct:.1f}"])


def save_chart(vuln: dict, defended: dict, path: str) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    categories = ["Total\nrequests", "Allowed\n(200 OK)", "Blocked\n(429/403)"]
    vuln_values = [vuln["total"], vuln["allowed"], vuln["blocked"]]
    def_values = [defended["total"], defended["allowed"], defended["blocked"]]

    fig, ax = plt.subplots(figsize=(10, 6))
    x = list(range(len(categories)))
    width = 0.35

    bars1 = ax.bar([i - width / 2 for i in x], vuln_values, width,
                   label="Vulnerable", color="#FF6B6B",
                   edgecolor="#0D1621", linewidth=2)
    bars2 = ax.bar([i + width / 2 for i in x], def_values, width,
                   label="Defended", color="#00D4AA",
                   edgecolor="#0D1621", linewidth=2)

    ax.set_ylabel("Request count", fontsize=12, fontweight="bold")
    ax.set_title("DDoS Defence: Before vs After", fontsize=14, fontweight="bold", pad=16)
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=11)
    ax.legend(fontsize=11, loc="upper right")
    ax.grid(axis="y", alpha=0.3, linestyle="--")

    for bars in (bars1, bars2):
        for bar in bars:
            h = bar.get_height()
            ax.annotate(f"{int(h):,}",
                        xy=(bar.get_x() + bar.get_width() / 2, h),
                        xytext=(0, 4), textcoords="offset points",
                        ha="center", fontsize=10, fontweight="bold")

    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    return True


def main():
    parser = argparse.ArgumentParser(description="Before/after benchmark")
    parser.add_argument("--vulnerable-url", default="http://localhost:5001")
    parser.add_argument("--defended-url", default="http://localhost:5002")
    parser.add_argument("--threads", type=int, default=30)
    parser.add_argument("--duration", type=int, default=10)
    parser.add_argument("--csv", default="benchmark_results.csv")
    parser.add_argument("--chart", default="benchmark_chart.png")
    args = parser.parse_args()

    for label, url in [("vulnerable", args.vulnerable_url),
                       ("defended",   args.defended_url)]:
        try:
            r = requests.get(f"{url}/api/health", timeout=2)
            s = r.json()
            print(f"{label:10s} {url} -> ok (defence={s['defence_enabled']})")
        except requests.exceptions.RequestException as e:
            print(f"{label:10s} {url} -> unreachable ({e})")
            print("Start both servers first:")
            print("  python protected_server.py --no-defence --port 5001")
            print("  python protected_server.py --port 5002")
            return

    print()
    vuln_result = Benchmark(args.vulnerable_url, args.threads,
                            args.duration, "vulnerable server").run()
    time.sleep(2)
    def_result = Benchmark(args.defended_url, args.threads,
                           args.duration, "defended server").run()
    print()

    v = extract(vuln_result)
    d = extract(def_result)

    save_csv(v, d, args.csv)
    print(f"csv saved   : {args.csv}")

    if save_chart(v, d, args.chart):
        print(f"chart saved : {args.chart}")
    else:
        print("chart       : matplotlib not installed, skipped")

    print()
    print(f"{'metric':<18} {'vulnerable':>12} {'defended':>12}")
    print("-" * 46)
    print(f"{'total requests':<18} {v['total']:>12,} {d['total']:>12,}")
    print(f"{'served (200)':<18} {v['allowed']:>12,} {d['allowed']:>12,}")
    print(f"{'blocked':<18} {v['blocked']:>12,} {d['blocked']:>12,}")
    v_pct = (v['blocked'] / v['total'] * 100) if v['total'] else 0
    d_pct = (d['blocked'] / d['total'] * 100) if d['total'] else 0
    print(f"{'block rate':<18} {v_pct:>11.1f}% {d_pct:>11.1f}%")


if __name__ == "__main__":
    main()