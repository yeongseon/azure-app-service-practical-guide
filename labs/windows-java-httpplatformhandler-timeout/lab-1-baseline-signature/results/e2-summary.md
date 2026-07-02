# E2 Kudu config visibility results (preliminary)

- Target: `app-winjavatol1-cevxrss3aa7mk` (rg=`rg-lab-winjavatol1`)
- Manifest: `e2-kudu-fetch-manifest.csv`
- Grep log: `e2-httpplatform-grep.log`

## Fetch manifest

| probe | method | path/command | http | bytes | outfile |
|---|---|---|---|---|---|
| P1 | GET | `/api/vfs/systemdrive/inetpub/config/applicationHost.config` | 401 | 0 | `e2-p1-inetpub-applicationhost.config.http-401` |
| P2 | GET | `/api/vfs/systemdrive/Windows/System32/inetsrv/config/applicationHost.config` | 401 | 0 | `e2-p2-inetsrv-applicationhost.config.http-401` |
| P3 | POST | `dir C:\home\site` | 401 | 0 | `e2-p3-dir-home-site.json.http-401` |
| P4 | POST | `type C:\home\site\config\applicationHost.xdt` | 401 | 0 | `e2-p4-applicationhost-xdt.json.http-401` |
| P5 | POST | `dir C:\home\LogFiles\httpPlatform` | 401 | 0 | `e2-p5-dir-httpplatform-logs.json.http-401` |
| P6 | GET | `/api/vfs/LogFiles/httpPlatform/` | 401 | 0 | `e2-p6-vfs-httpplatform-listing.json.http-401` |
| P7 | POST | `reg query HKLM\System\CurrentControlSet\Services\W3SVC\Parameters` | 401 | 0 | `e2-p7-reg-w3svc.json.http-401` |

## Preliminary H3R verdict

- **Zero** artifacts contain `httpPlatform` or `requestTimeout` markers.
- Preliminary H3R verdict: **FALSIFIED** (effective config not Kudu-accessible on Windows App Service Java SE).
- This is still a useful platform-limitation finding for the final lab guide.

## Next

```bash
bash run-e3-stream-test.sh <APP_URL> ./results
```
