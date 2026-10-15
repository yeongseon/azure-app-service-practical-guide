# Retained Artifact PII Redaction Review

The retained lab artifacts were rescanned after broadening `scan_lab_pii.py` to detect 64-character hexadecimal identifiers under any JSON key and deployment-suffixed App Service resource paths with alphanumeric suffixes.

Existing retained `artifacts-sanitized/` and `results/` packages were not rewritten. Their deployment-suffixed App Service resource paths are covered by path-and-category-specific entries in `scripts/lab-pii-allowlist.txt`, with the retention rationale recorded there. No artifact was deleted or re-dated.

Files under `evidence/runs/` are immutable retained evidence. The expanded scan produced no new finding there, so no allowlist entry was required.
