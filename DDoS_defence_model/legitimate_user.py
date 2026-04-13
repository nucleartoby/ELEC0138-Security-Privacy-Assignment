#!/usr/bin/env python3
"""
False-positive rate measurement.

Simulates a legitimate user (slow, varied requests, unique source IP)
while an attack is running against the same server. Reports how many
of the legitimate requests were blocked — this is the false positive
rate for the defence.

A good defence blocks attackers without affecting legitimate users, so
the false positive rate under attack should be near zero.

Usage:
    # Terminal 1
    python protected_server.py --port 5002
    # Terminal 2
    python attack_client.py --target http://localhost:5002 --threads 50 --duration 30
    # Terminal 3 (this script)
    python legitimate_user.py --target http://localhost:5002 --duration 30
"""

from __future__ import annotations

import argparse
import random
import time

import requests


def main():
    parser = argparse.ArgumentParser(description="Legitimate user simulator")
    parser.add_argument("--target", default="http://localhost:5002")
    parser.add_argument("--duration", type=int, default=30,
                        help="How long to simulate the user for (seconds)")
    parser.add_argument("--interval", type=float, default=1.0,
                        help="Seconds between requests (default 1.0)")
    parser.add_argument("--source-ip", default="203.0.113.50",
                        help="Spoofed X-Forwarded-For (legitimate user's IP)")
    args = parser.parse_args()

    target = args.target.rstrip("/")
    paths = ["/api/balance", "/api/transactions"]

    print(f"Legitimate user simulation")
    print(f"  target    : {target}")
    print(f"  duration  : {args.duration}s")
    print(f"  source ip : {args.source_ip}")
    print(f"  interval  : {args.interval}s")
    print()

    attempts = 0
    ok = 0
    blocked = 0
    failed = 0
    start = time.time()

    session = requests.Session()
    while time.time() - start < args.duration:
        path = random.choice(paths)
        try:
            r = session.get(
                f"{target}{path}",
                headers={"X-Forwarded-For": args.source_ip},
                timeout=5,
            )
            attempts += 1
            if r.status_code == 200:
                ok += 1
                status = "OK "
            elif r.status_code in (429, 403):
                blocked += 1
                status = "BLK"
            else:
                failed += 1
                status = "ERR"
            print(f"  [{time.time() - start:5.1f}s] {status} {path} -> {r.status_code}")
        except requests.exceptions.RequestException as e:
            attempts += 1
            failed += 1
            print(f"  [{time.time() - start:5.1f}s] ERR {path} -> {e.__class__.__name__}")

        # Add slight jitter to mimic real user behaviour
        sleep = args.interval + random.uniform(-0.2, 0.2)
        time.sleep(max(0.1, sleep))

    print()
    print(f"attempts       : {attempts}")
    print(f"successful 200 : {ok}")
    print(f"blocked        : {blocked}")
    print(f"failed / error : {failed}")

    if attempts:
        success_rate = ok / attempts * 100
        false_positive_rate = blocked / attempts * 100
        print(f"success rate   : {success_rate:.1f}%")
        print(f"FPR            : {false_positive_rate:.1f}%")
    print()


if __name__ == "__main__":
    main()