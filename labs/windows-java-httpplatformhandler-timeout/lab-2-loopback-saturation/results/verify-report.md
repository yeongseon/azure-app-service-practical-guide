# Lab 2 Verification Report

## Metadata
- Lab: Windows Java httpPlatformHandler timeout - Lab 2 (loopback saturation)
- Generated: 2026-07-02T01:51:56Z
- Sub: <subscription-id>
- RG: rg-lab-winjaval2cap
- Web App: app-winjaval2cap-wjo6i7zextarg

## Cost Breakdown
| Item | Rate | Units | Cost |
|------|------|-------|------|
| App Service Plan B1 | TBD/hour | ~3.6h wall time | TBD - verify pricing |
| Log Analytics ingestion | TBD/GB | ~0.3GB estimated | TBD - verify pricing |
| **TOTAL** | | | **$~1-2** |

**NOTE**: Verify current regional price sheet before execution. This table uses placeholder rates.

Sources:
- App Service pricing: https://azure.microsoft.com/en-us/pricing/details/app-service/windows/
- Log Analytics pricing: https://azure.microsoft.com/en-us/pricing/details/monitor/

## Experiment: Pre-E1 (Baseline Recheck)

Status: EVALUATING

- [Observed] Manifest loaded from pre-e1/manifest.json with window 2026-07-02T01:34:47Z .. 2026-07-02T01:47:48Z
- [Measured] Baseline rows for /slow/240: 2 (raw KQL: kql-baseline-rows.json)
- [Measured] Exact status rows (500/121/*): 2/3; win32=0 rows: 2/3; TimeTaken in [229800,230500] ms: 2/3; rows with win32=64: 0
- [Observed] Baseline verdict=degraded
- [Observed] Section verdict: MISSING

## Overall Verdict
Signature 500.121.64 status: [INSUFFICIENT DATA]
Mitigation M1a effect: [UNTESTED]
Mitigation M2 effect: [UNTESTED]
Mitigation M3 (scale-out) effect: [UNTESTED]

## Take-away
Loopback saturation evidence must be anchored to the App Service _ResourceId-scoped logs and compared across baseline, load, and mitigation windows. Treat M2 as unverifiable when platform Auto-Heal events do not surface in AppServicePlatformLogs, even if the HTTP trend looks directionally favorable.
