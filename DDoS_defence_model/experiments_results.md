# Attack Variant Evaluation

| Variant | Attack Pattern | Total | Allowed | Blocked | Block Rate |
|:-------:|---------------|------:|--------:|--------:|-----------:|
| A | Single-source burst | 11,962 | 9 | 11,953 | 99.9% |
| B | Sustained flood | 11,537 | 9 | 11,528 | 99.9% |
| C | Distributed botnet | 11,396 | 9 | 11,387 | 99.9% |
| D | Slow drip (low-and-slow) | 1,008 | 9 | 999 | 99.1% |
| E | Mixed burst/idle | 2,790 | 9 | 2,781 | 99.7% |

## Per-layer breakdown

| Variant | Blocklist | Rate Limit | Anomaly | Reputation | ML |
|:-------:|----------:|-----------:|--------:|-----------:|---:|
| A | 11,948 | 0 | 0 | 0 | 5 |
| B | 11,523 | 0 | 0 | 0 | 5 |
| C | 11,382 | 0 | 0 | 0 | 5 |
| D | 994 | 0 | 0 | 0 | 5 |
| E | 2,776 | 0 | 0 | 0 | 5 |
