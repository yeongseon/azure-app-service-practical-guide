#!/bin/bash
# Build a ready-to-run ZIP (no extra root directory) for a given build id.
# build.txt and data/lockme.txt change with the build id AND in size, so an overwrite is visible
# in the app state and cannot be skipped by a size comparison. PAYLOAD_MB adds an incompressible
# payload so a deployment takes long enough to overlap with another one.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_ZIP="${1:-deploy.zip}"
BUILD_ID="${2:-1}"
PAYLOAD_MB="${PAYLOAD_MB:-0}"

python3 - "$SCRIPT_DIR/app" "$OUTPUT_ZIP" "$BUILD_ID" "$PAYLOAD_MB" <<'PY'
import os
import sys
import zipfile

source_dir, output_zip, build_id, payload_mb = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
pad = int(build_id) * 100 if build_id.isdigit() else 100
overrides = {
    'build.txt': 'build=' + build_id + '\n' + ('b' * pad) + '\n',
    os.path.join('data', 'lockme.txt'): 'build=' + build_id + '\n' + ('x' * pad) + '\n',
}
with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as archive:
    for root, _dirs, files in os.walk(source_dir):
        for name in sorted(files):
            full_path = os.path.join(root, name)
            rel = os.path.relpath(full_path, source_dir)
            if rel in overrides:
                archive.writestr(rel, overrides[rel])
            else:
                archive.write(full_path, rel)
    for index in range(payload_mb):
        archive.writestr(zipfile.ZipInfo('payload/part-%03d.bin' % index), os.urandom(1024 * 1024), compress_type=zipfile.ZIP_STORED)
print(output_zip)
PY
sha256sum "$OUTPUT_ZIP"
