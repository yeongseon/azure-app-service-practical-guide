#!/bin/bash
# Build a ready-to-run ZIP (no extra root directory) from app/ without needing the zip CLI.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_ZIP="${1:-deploy.zip}"

python3 - "$SCRIPT_DIR/app" "$OUTPUT_ZIP" <<'PY'
import os
import sys
import zipfile

source_dir, output_zip = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as archive:
    for root, _dirs, files in os.walk(source_dir):
        for name in sorted(files):
            full_path = os.path.join(root, name)
            archive.write(full_path, os.path.relpath(full_path, source_dir))
print(output_zip)
PY
sha256sum "$OUTPUT_ZIP"
