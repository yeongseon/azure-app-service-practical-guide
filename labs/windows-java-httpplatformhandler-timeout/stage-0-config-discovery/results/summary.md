# Stage 0 timeout probe results

- Target: `https://app-winjavatimeout-eliroyg74lvho.<azurewebsites-domain-redacted>`
- Started: 2026-07-01T08:43:49Z
- Ended:   2026-07-01T09:16:06Z

## /slow/{n} probes

| requested_s | http_code | time_total_s | curl_exit |
|---|---|---|---|
| 60 | 200 | 61.425287 | 0 |
| 180 | 200 | 180.646660 | 0 |
| 210 | 200 | 210.802651 | 0 |
| 220 | 200 | 220.840205 | 0 |
| 225 | 200 | 225.751277 | 0 |
| 240 | 500 | 230.688024 | 0 |
| 300 | 500 | 230.714654 | 0 |
| 360 | 500 | 230.682930 | 0 |

## /stream/300 probe (H7 test)

| requested_s | http_code | time_total_s | curl_exit | bytes_received |
|---|---|---|---|---|
| 300 | 200 | 32.226953 | 0 | 145 |

## Interpretation (see stage-0-config-discovery/README.md)

- If /slow/{n} succeeds for all n <= 230 and cuts around 230s for n > 230: front-end limit is 230s (default)
- If /slow cuts around 120s: httpPlatformHandler requestTimeout default (120s) is in force
- If /stream/300 completes with 11 chunks: 230s is an IDLE timeout
- If /stream/300 cuts around 230s: 230s is an ABSOLUTE request-duration limit
