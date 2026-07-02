# E3 stream absolute-vs-idle probe results (preliminary)

- Target:     `https://app-winjavatol1-cevxrss3aa7mk.<azurewebsites-domain-redacted>`
- Endpoint:   `/stream/300`
- CSV:        `e3-stream-probe.csv`
- Body:       `e3-stream-body.ndjson`

## Client observation

| field | value |
|---|---|
| http_code | 500 |
| time_total | 230.671957s |
| curl_exit_code | 0 |
| bytes_received | 221 |
| chunk_count | 0
0 |
| started_utc | 2026-07-01T10:38:19Z |
| ended_utc | 2026-07-01T10:42:10Z |

## Preliminary H4 verdict

- **unknown** - chunk_count=0
0 time_total=230.671957s does not match either interpretation cleanly; investigate

Authoritative verdict is written by `verify.sh` using `AppServiceHTTPLogs.TimeTaken`
and `AppServiceConsoleLogs` `stream.start/chunk/end/interrupted` events.

## Interpretation matrix (from design-proposal.md)

| server TimeTaken | client chunks | verdict |
|---|---|---|
| ~230000 ms | ~8 | ABSOLUTE (front-end 230s is total request duration) |
| ~300000 ms | 11 | IDLE (server-sent bytes reset front-end counter) |
| other | other | ambiguous - document as anomaly |

## Next

```bash
bash collect-effective-config.sh <APP_NAME> <RESOURCE_GROUP_NAME> ./results
bash verify.sh <APP_NAME> <RESOURCE_GROUP_NAME> <WORKSPACE_ID> ./results
```
