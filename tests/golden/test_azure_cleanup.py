from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "azure_cleanup", ROOT / "scripts/golden/azure_cleanup.py"
)
assert SPEC is not None and SPEC.loader is not None
cleanup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cleanup)


class AzureCleanupTests(unittest.TestCase):
    def test_sweep_selects_only_owned_expired_resource_groups(self) -> None:
        resources = [
            {"name": "expired", "tags": {"owner": "golden-e2e", "repository": cleanup.REPOSITORY, "run-id": "12345-1", "ttl": "2026-10-15T00:00:00Z"}},
            {"name": "current", "tags": {"owner": "golden-e2e", "repository": cleanup.REPOSITORY, "run-id": "12345-1", "ttl": "2026-10-17T00:00:00Z"}},
            {"name": "foreign", "tags": {"owner": "someone-else", "repository": cleanup.REPOSITORY, "run-id": "12345-1", "ttl": "2026-10-15T00:00:00Z"}},
            {"name": "other-repository", "tags": {"owner": "golden-e2e", "repository": "other/repo", "run-id": "12345-1", "ttl": "2026-10-15T00:00:00Z"}},
            {"name": "missing-run", "tags": {"owner": "golden-e2e", "repository": cleanup.REPOSITORY, "ttl": "2026-10-15T00:00:00Z"}},
            {"name": "untagged", "tags": {}},
        ]

        selected = cleanup.expired_owned_groups(
            resources, datetime(2026, 10, 16, tzinfo=timezone.utc)
        )

        self.assertEqual(selected, ("expired",))

    def test_run_cleanup_requires_exact_run_tags(self) -> None:
        tags = {"owner": "golden-e2e", "repository": cleanup.REPOSITORY, "run-id": "other"}

        with self.assertRaises(cleanup.CleanupError):
            cleanup.require_run_ownership(tags, "expected")


if __name__ == "__main__":
    unittest.main()
