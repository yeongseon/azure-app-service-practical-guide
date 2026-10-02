#!/bin/bash
set -euo pipefail

APP_URL_INPUT="${1:-${APP_URL:-}}"
ENDPOINT="${2:-outbound}"

if [ -z "$APP_URL_INPUT" ] || { [ "$ENDPOINT" != "outbound" ] && [ "$ENDPOINT" != "outbound-fixed" ]; }; then
    echo "Usage: $0 <APP_URL> [outbound|outbound-fixed]"
    echo "  outbound        new connection per call (default)"
    echo "  outbound-fixed  pooled session, same load shape, for the matched control"
    echo "Example: $0 https://app-labsnat-xxxxxxxx.azurewebsites.net outbound"
    exit 1
fi

APP_URL="${APP_URL_INPUT%/}"

echo "Starting trigger against: $APP_URL/$ENDPOINT"
echo "Sending 200 requests (calls=40, at most 20 in flight) to /$ENDPOINT"

status_dir=$(mktemp --directory)

# The wrapper endpoint answers 200 even when every inner call fails, so the
# outcome is read from each JSON body (inner successes/failures), not the status.
for request_number in $(seq 1 200); do
    (
        curl \
            --silent \
            --max-time 180 \
            --output "$status_dir/$request_number.json" \
            --write-out "%{http_code}" \
            "$APP_URL/$ENDPOINT?calls=40" > "$status_dir/$request_number.status" 2>/dev/null
    ) &

    while [ "$(jobs -r | wc -l)" -ge 20 ]; do
        sleep 0.2
    done

    if [ $((request_number % 20)) -eq 0 ]; then
        echo "  progress: $request_number/200"
    fi
done

wait

python3 - "$status_dir" <<'SUMMARY'
import glob
import json
import sys

status_dir = sys.argv[1]
codes = {}
inner_ok = inner_failed = 0
for path in glob.glob(f"{status_dir}/*.status"):
    code = open(path, encoding="utf-8").read().strip() or "000"
    codes[code] = codes.get(code, 0) + 1
for path in glob.glob(f"{status_dir}/*.json"):
    try:
        body = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        continue
    inner_ok += body.get("successes", 0)
    inner_failed += body.get("failures", 0)

print()
print("Trigger complete.")
print("  Outer status codes (000 = no response within 180s):", dict(sorted(codes.items())))
print(f"  Inner outbound calls: {inner_ok} completed, {inner_failed} failed")
SUMMARY

rm --recursive --force "$status_dir"

echo
echo "Next: run verify.sh to compare dependency latency, result codes, and HTTP time."
