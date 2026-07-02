# Lab 1 verify report

Generated: 2026-07-01T10:54:35Z

- App: `app-winjavatol1-cevxrss3aa7mk`
- RG:  `rg-lab-winjavatol1`
- Workspace: `law-winjavatol1-cevxrss3aa7mk` (customer id `7b9ca5c9-31da-4f69-9c4a-907b4630071c`)
- Output dir: `./results`

## E1 baseline signature statistics

| metric | value |
|---|---|
| row_count (AppServiceHTTPLogs) | 10 |
| mean TimeTaken (ms) | 230001.3 |
| stdev TimeTaken (ms) | 5.437524320469748 |
| min TimeTaken (ms) | 229993 |
| max TimeTaken (ms) | 230007 |
| ScStatus/ScSubStatus 500/121 count | 10 / 10 |
| ScWin32Status == 0 count | 10 / 10 |
| ScWin32Status == 64 count | 0 / 10 |

### H1R verdict: CONFIRMED
- 500/121 = 100% (10/10)
- mean 230001 ms in [229800, 230500], stdev 5 < 200

### H2R verdict: CONFIRMED
- ScWin32Status = 0 in 100% (10/10), zero .64

## E2 Kudu config visibility

### H3R verdict: FALSIFIED
- 0/7 Kudu probes returned HTTP 200; effective config not Kudu-accessible

See `e2-kudu-fetch-manifest.csv` for the 7-probe manifest and `e2-httpplatform-grep.log` for grep results.

## E3 stream absolute-vs-idle

| metric | value |
|---|---|
| server TimeTaken (ms) | 230005 |
| server ScStatus | 500 |
| server ScSubStatus | 121 |
| client chunks received | 0 |

### H4 verdict: AMBIGUOUS
- TimeTaken=230005 ms, ScStatus/ScSubStatus=500/121, chunks=0

## E4 (optional) client vs IIS outer status

### H5R verdict: CONFIRMED
- Client sees 500 in 10/10 iterations, zero 502 (direct App Service request path)

## Raw artifacts

- E1 per-request rows: `verify-e1-http-rows.json`
- E1 summary stats:    `verify-e1-stats.json`
- E3 HTTP rows:        `verify-e3-http-rows.json`
- E3 console rows:     `verify-e3-console-rows.json`

## Next

If H2R = FALSIFIED with `.64` present AND E1 ran < 20 iterations, re-run:

```bash
ITERATIONS=20 bash run-e1-signature-probe.sh https://app-winjavatol1-cevxrss3aa7mk.azurewebsites.net ./results
bash verify.sh app-winjavatol1-cevxrss3aa7mk rg-lab-winjavatol1 law-winjavatol1-cevxrss3aa7mk ./results
```

Otherwise, proceed to `lab-1-interpretation.md` authoring.
