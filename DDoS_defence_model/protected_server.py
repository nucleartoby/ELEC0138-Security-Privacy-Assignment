#!/usr/bin/env python3
"""
Mock fintech API gateway protected by the DDoS defence engine.

Every request passes through DDoSDefence.evaluate() before reaching the
backend handlers. Monitoring and control endpoints are exempt so
operators can always observe and control the system under attack.

Usage:
    python protected_server.py                 # defended (default)
    python protected_server.py --no-defence    # vulnerable baseline
    python protected_server.py --aggressive    # tighter thresholds
"""

import argparse
import threading
import time

from flask import Flask, jsonify, request

from defence_engine import DDoSDefence, DefenceConfig, Verdict

app = Flask(__name__)

# Mock user database for the login endpoint. These credentials exist
# only inside this prototype and are never checked against any real
# authentication system.
USERS = {
    "alice@example.com":   {"password": "7xQ!mN2pR9vL",  "balance":  2847.53},
    "bob@example.com":     {"password": "K4#jH8wT3fZ",   "balance": 15420.10},
    "charlie@example.com": {"password": "P9$dF2cBgY6",   "balance":   412.88},
}

_server_start = time.time()
_server_stats = {
    "total_requests": 0,
    "processed_requests": 0,
    "rejected_requests": 0,
}
_stats_lock = threading.Lock()

_defence: DDoSDefence
_defence_enabled = True

# Monitoring and control endpoints bypass the defence so operators can
# always observe and control the system during an attack.
EXEMPT_PATHS = {
    "/api/health",
    "/api/stats",
    "/api/defence/toggle",
    "/api/defence/reset",
}

HONEYPOT_PATHS = {
    "/admin.php",
    "/wp-login.php",
    "/wp-admin",
    "/.env",
    "/.git/config",
    "/phpmyadmin",
    "/api/admin/debug",
}

@app.before_request
def defence_middleware():
    if request.path in EXEMPT_PATHS:
        return None

    client_ip = request.headers.get("X-Forwarded-For") or request.remote_addr or "0.0.0.0"

    with _stats_lock:
        _server_stats["total_requests"] += 1

    if request.path in HONEYPOT_PATHS:
        _defence.blocklist_ip(client_ip, reason="honeypot")
        with _stats_lock:
            _server_stats["rejected_requests"] += 1
        return jsonify(error="forbidden"), 403

    if not _defence_enabled:
        with _stats_lock:
            _server_stats["processed_requests"] += 1
        return None

    verdict = _defence.evaluate(client_ip, request.path)

    if verdict == Verdict.ALLOW:
        with _stats_lock:
            _server_stats["processed_requests"] += 1
        return None

    with _stats_lock:
        _server_stats["rejected_requests"] += 1

    if verdict == Verdict.BLOCK_RATE_LIMIT:
        return jsonify(error="rate_limit_exceeded", retry_after=10), 429
    if verdict == Verdict.BLOCK_ANOMALY:
        return jsonify(error="anomaly_detected"), 429
    if verdict == Verdict.BLOCK_ML:
        return jsonify(error="ml_anomaly_detected"), 429
    if verdict == Verdict.BLOCK_BLOCKLIST:
        return jsonify(error="ip_blocked"), 403
    if verdict == Verdict.BLOCK_REPUTATION:
        return jsonify(error="reputation_blocked"), 403
    return jsonify(error="blocked"), 429


@app.route("/")
def root():
    return jsonify(
        service="Protected API Gateway",
        defence_enabled=_defence_enabled,
        endpoints=[
            "/api/health",
            "/api/login",
            "/api/balance",
            "/api/transactions",
            "/api/transfer",
            "/api/stats",
        ],
    )


@app.route("/api/health")
def health():
    return jsonify(
        status="ok",
        uptime_seconds=round(time.time() - _server_start, 1),
        defence_enabled=_defence_enabled,
    )


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "")
    password = data.get("password", "")

    time.sleep(0.02)  # simulate backend work

    user = USERS.get(email)
    if user and user["password"] == password:
        return jsonify(
            status="success",
            token=f"mock-token-{int(time.time())}",
        )
    return jsonify(status="failed", error="invalid_credentials"), 401


@app.route("/api/balance")
def balance():
    time.sleep(0.01)
    return jsonify(account_id="ACC-001", balance=2847.53, currency="GBP")


@app.route("/api/transactions")
def transactions():
    time.sleep(0.03)
    return jsonify(transactions=[
        {"id": "TXN-001", "amount":  -12.99, "merchant": "Tesco",       "date": "2026-04-08"},
        {"id": "TXN-002", "amount":   -3.50, "merchant": "TfL",         "date": "2026-04-08"},
        {"id": "TXN-003", "amount": 2500.00, "merchant": "Salary",      "date": "2026-04-07"},
        {"id": "TXN-004", "amount":  -45.20, "merchant": "Sainsbury's", "date": "2026-04-07"},
    ])


@app.route("/api/transfer", methods=["POST"])
def transfer():
    data = request.get_json(silent=True) or {}
    time.sleep(0.05)
    return jsonify(
        status="pending",
        transfer_id=f"TRF-{int(time.time())}",
        amount=data.get("amount", 0),
    )


@app.route("/api/stats")
def api_stats():
    uptime = time.time() - _server_start
    with _stats_lock:
        srv = dict(_server_stats)
    rps = (srv["total_requests"] / uptime) if uptime > 0 else 0
    return jsonify(
        server={
            "uptime_seconds": round(uptime, 1),
            "total_requests": srv["total_requests"],
            "processed_requests": srv["processed_requests"],
            "rejected_requests": srv["rejected_requests"],
            "requests_per_second": round(rps, 1),
            "defence_enabled": _defence_enabled,
        },
        defence=_defence.get_stats(),
    )


@app.route("/api/defence/toggle", methods=["POST"])
def api_toggle():
    global _defence_enabled
    _defence_enabled = not _defence_enabled
    _defence.set_enabled(_defence_enabled)
    return jsonify(defence_enabled=_defence_enabled)


@app.route("/api/defence/reset", methods=["POST"])
def api_reset():
    _defence.reset()
    with _stats_lock:
        for k in _server_stats:
            _server_stats[k] = 0
    return jsonify(status="reset")


def main():
    global _defence, _defence_enabled

    parser = argparse.ArgumentParser(description="Protected API gateway")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--no-defence", action="store_true",
                        help="Run without defence (vulnerable baseline)")
    parser.add_argument("--aggressive", action="store_true",
                        help="Use tighter defence thresholds")
    args = parser.parse_args()

    if args.aggressive:
        cfg = DefenceConfig(
            bucket_capacity=5,
            refill_rate=2.0,
            window_threshold=20,
            window_seconds=5,
            auto_block_seconds=120,
        )
    else:
        cfg = DefenceConfig()

    _defence = DDoSDefence(cfg)
    _defence_enabled = not args.no_defence
    _defence.set_enabled(_defence_enabled)

    mode = "defended" if _defence_enabled else "vulnerable"
    print(f"Protected API gateway listening on http://{args.host}:{args.port} [{mode}]")
    if _defence_enabled:
        print(f"  token bucket : {cfg.bucket_capacity} tokens, refill {cfg.refill_rate}/s")
        print(f"  window       : {cfg.window_threshold} reqs / {cfg.window_seconds}s")
        print(f"  auto-block   : {cfg.auto_block_seconds}s after reputation {cfg.reputation_block_threshold}")
        if _defence.ml_detector is not None:
            print(f"  ml layer     : IsolationForest (contamination={cfg.ml_contamination})")
        else:
            print(f"  ml layer     : disabled (sklearn not installed)")

    # Prefer waitress (production WSGI server) for throughput on Windows.
    try:
        from waitress import serve
        print(f"  wsgi server  : waitress")
        print()
        serve(app, host=args.host, port=args.port, threads=8)
    except ImportError:
        print(f"  wsgi server  : flask dev server (install 'waitress' for better performance)")
        print()
        app.run(host=args.host, port=args.port, threaded=True, debug=False)


if __name__ == "__main__":
    main()