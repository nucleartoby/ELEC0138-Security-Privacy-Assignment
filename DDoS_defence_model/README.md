# DDoS Defence Model

Defence prototype for ELEC0138 Coursework 2. Pairs with Toby's
NS3 attack simulation in `../ddos_sim/`.

It's a Flask API gateway that simulates a fintech service (login, balance,
transactions, transfer), with a middleware that runs every request through
five defence layers before it reaches the handler.

## Files

- `defence_engine.py` — the core library. Five layer classes and an
  orchestrator that runs them in order.
- `ml_detector.py` — Isolation Forest anomaly detector, used as layer 5.
- `protected_server.py` — the Flask app. Run this to start the gateway.
- `attack_client.py` — HTTP flood generator for the demo.
- `benchmark.py` — runs an attack against a vulnerable server and a
  defended server and produces a before/after bar chart.
- `experiments.py` — runs five different attack patterns against the
  defended server and dumps a markdown results table.
- `legitimate_user.py` — simulates one real user while an attack is
  running, to measure how often real users get blocked by mistake.
- `latency_benchmark.py` — measures p50/p95/p99 request latency with
  and without the defence enabled, under no attack.
- `monitoring_dashboard.py` — a small Flask dashboard that polls the
  protected server's stats endpoint and displays live block counts.

## Defence layers

Each request is evaluated in order. The first layer that matches decides
the outcome.

1. **IP blocklist** — static plus a dynamic time-limited blocklist.
   Blocked IPs get an immediate 403. Repeat offenders from later layers
   are promoted here automatically.
2. **Reputation check** — each IP has a decaying reputation score.
   IPs above the block threshold get 403 and are added to the dynamic
   blocklist.
3. **Token bucket** — 20-token burst capacity per IP, refilling at
   5 tokens per second. One token per request. Empty bucket returns 429.
4. **Sliding window** — counts requests from each IP over the last
   10 seconds. More than 80 in the window returns 429 and penalises
   reputation.
5. **Isolation Forest** — a scikit-learn model trained at startup on
   synthetic normal traffic. Extracts five features per IP (rate, mean
   inter-arrival time, stddev of inter-arrival times, path diversity,
   burst ratio) over a rolling window and flags statistical outliers.

Layers 3–5 feed into the reputation score. Hitting layer 3 adds 5 points,
layer 4 adds 20, layer 5 adds 15. Reputation decays at 0.1 points per
second so legitimate users recover in seconds. Crossing 60 points promotes
the IP to the dynamic blocklist for 60 seconds, after which subsequent
requests short-circuit in layer 1.

## Requirements

```
pip install flask waitress requests matplotlib scikit-learn numpy
```

Tested on Python 3.13 with Flask 3.1, waitress 3.0, scikit-learn 1.8.

On Windows, waitress is essential — the Flask dev server tops out around
25 req/s on localhost because of Windows socket overhead, which makes the
benchmark numbers meaningless. With waitress it reaches several hundred
req/s which is enough to properly stress the defence.

## Running the demo

Minimum demo is three terminals.

Terminal 1, start the vulnerable baseline:
```
python protected_server.py --no-defence --port 5001
```

Terminal 2, start the defended server:
```
python protected_server.py --port 5002
```

Terminal 3, run the before/after benchmark:
```
python benchmark.py --threads 50 --duration 15
```

This produces `benchmark_chart.png` and `benchmark_results.csv`. The
chart goes into the report.

To demonstrate that legitimate users still get through during an attack,
add a fourth terminal. Start an attack, then in a fifth terminal run the
legitimate user simulator (spoofs X-Forwarded-For so it looks like a
different IP than the attacker):

```
# Terminal 4
python attack_client.py --target http://localhost:5002 --threads 50 --duration 40

# Terminal 5, start immediately after terminal 4
python legitimate_user.py --target http://localhost:5002 --duration 30
```

The legitimate user should show 100% success rate while the attack is
being blocked at roughly 98%.

To run all five attack variants and get a results table:
```
python experiments.py --target http://localhost:5002 --duration 10
```

To measure the latency overhead of the defence (needs both servers from
the benchmark setup):
```
python latency_benchmark.py --samples 200
```

The latency benchmark paces requests at 2 per second so the token bucket
never fires — if it did, the blocked responses would distort the timing
percentiles.

## Monitoring dashboard

Start the defended server, then:
```
python monitoring_dashboard.py --target http://localhost:5002
```

Browse to `http://localhost:5050`. It polls the server's `/api/stats`
endpoint every 500ms and shows total/allowed/blocked counters, a live
SVG traffic chart, and per-layer block counts that highlight when each
layer is actively firing.

## Tuning thresholds

Defaults are in `DefenceConfig` at the top of `defence_engine.py`:

| Parameter | Default | Notes |
| `bucket_capacity` | 20 | max burst per IP |
| `refill_rate` | 5/s | sustained rate per IP |
| `window_seconds` | 10 | sliding window length |
| `window_threshold` | 80 | requests in window before flagging |
| `reputation_block_threshold` | 100 | score for immediate 403 |
| `reputation_autoblock_threshold` | 60 | score for blocklist promotion |
| `reputation_decay_rate` | 0.1/s | how fast reputation recovers |
| `auto_block_seconds` | 60 | how long a dynamic block lasts |
| `ml_contamination` | 0.05 | IsolationForest outlier fraction |
| `ml_min_requests` | 8 | minimum requests before ML scores an IP |

There's also an `--aggressive` flag on `protected_server.py` that uses
tighter values (bucket 5, refill 2/s, window 20/5s, auto-block 120s) for
testing the defence under harsher conditions.

## Notes

The middleware exempts four endpoints from the defence so operators can
always observe and control the server even during an attack:
`/api/health`, `/api/stats`, `/api/defence/toggle`, `/api/defence/reset`.

`attack_client.py` is a lab tool. Run it only against this prototype on
your own machine. Launching it against anything you don't own is a
criminal offence in the UK under the Computer Misuse Act 1990 section 3.