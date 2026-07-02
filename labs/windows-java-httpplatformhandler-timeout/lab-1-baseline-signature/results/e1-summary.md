# E1 baseline signature probe results (preliminary)

- Target:     `https://app-winjavatol1-cevxrss3aa7mk.azurewebsites.net`
- Endpoint:   `/slow/240`
- Iterations: 10
- CSV:        `e1-signature-probes.csv`

## Client-side observations

| # | http | time_total_s | curl_exit |
|---|---|---|---|
| 1 | 500 | 230.664435 | 0 |
| 2 | 500 | 230.665107 | 0 |
| 3 | 500 | 230.699105 | 0 |
| 4 | 500 | 230.719540 | 0 |
| 5 | 500 | 230.675099 | 0 |
| 6 | 500 | 230.730103 | 0 |
| 7 | 500 | 230.682451 | 0 |
| 8 | 500 | 230.879593 | 0 |
| 9 | 500 | 230.665140 | 0 |
| 10 | 500 | 230.757789 | 0 |

## Adaptive extension trigger evaluation

This script does NOT decide whether to extend iterations because
AppServiceHTTPLogs ingestion has ~2-5 minute latency. Run `verify.sh`
after post-flight config collection to:

1. Query server-side `ScStatus`, `ScSubStatus`, `ScWin32Status`, `TimeTaken` for these iterations.
2. Evaluate L1-H1R success criterion: 100% `500/121` and `TimeTaken` in [229800, 230500] ms with stddev < 200 ms.
3. Evaluate L1-H2R success criterion: 100% `ScWin32Status = 0`.
4. If either criterion fails and this run used <\ 20 iterations, re-run with:
   `ITERATIONS=20 bash run-e1-signature-probe.sh https://app-winjavatol1-cevxrss3aa7mk.azurewebsites.net ./results`
