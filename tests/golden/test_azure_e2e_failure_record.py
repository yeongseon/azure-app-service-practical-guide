from __future__ import annotations

import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.golden.azure_e2e_guard import FailureRecord, write_failure_record
from scripts.golden.azure_e2e_sanitize import scan_sanitized_tree


class AzureE2EFailureRecordTests(unittest.TestCase):
    def test_failure_record_supports_every_workflow_stage(self) -> None:
        blocked_stages = {"target-validation", "oidc-config", "oidc-login"}
        stages = (
            "target-validation",
            "oidc-config",
            "oidc-login",
            "provisioning",
            "deployment",
            "runner-start",
            "runner-crash",
            "evaluation",
            "sanitize",
        )
        for stage in stages:
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "failure-record.json"
                evidence_run_id = "12345-2" if stage in {"runner-crash", "evaluation", "sanitize"} else None

                write_failure_record(
                    path,
                    FailureRecord(
                        status="BLOCKED" if stage in blocked_stages else "FAILED",
                        failure_stage=stage,
                        github_run_id="12345",
                        github_run_attempt="2",
                        evidence_run_id=evidence_run_id,
                        exit_code=3 if stage in blocked_stages else 4,
                        started_at="2026-10-18T01:02:03Z",
                        ended_at="2026-10-18T01:03:03Z",
                    ),
                )

                scan_sanitized_tree(path.parent)


if __name__ == "__main__":
    unittest.main()
