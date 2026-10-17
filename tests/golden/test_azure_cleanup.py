from __future__ import annotations

import importlib.util
import json
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

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
            {"name": "rg-golden-e2e-12345-1", "tags": {"owner": "golden-e2e", "repository": cleanup.REPOSITORY, "run-id": "12345-1", "ttl": "2026-10-15T00:00:00Z"}},
            {"name": "rg-golden-e2e-12346-1", "tags": {"owner": "golden-e2e", "repository": cleanup.REPOSITORY, "run-id": "12346-1", "ttl": "2026-10-17T00:00:00Z"}},
            {"name": "foreign", "tags": {"owner": "someone-else", "repository": cleanup.REPOSITORY, "run-id": "12345-1", "ttl": "2026-10-15T00:00:00Z"}},
            {"name": "other-repository", "tags": {"owner": "golden-e2e", "repository": "other/repo", "run-id": "12345-1", "ttl": "2026-10-15T00:00:00Z"}},
            {"name": "missing-run", "tags": {"owner": "golden-e2e", "repository": cleanup.REPOSITORY, "ttl": "2026-10-15T00:00:00Z"}},
            {"name": "untagged", "tags": {}},
        ]

        selected = cleanup.expired_owned_groups(
            resources, datetime(2026, 10, 16, tzinfo=UTC)
        )

        self.assertEqual(selected, ("rg-golden-e2e-12345-1",))

    def test_run_cleanup_requires_exact_run_tags(self) -> None:
        tags = {"owner": "golden-e2e", "repository": cleanup.REPOSITORY, "run-id": "other"}

        with self.assertRaises(cleanup.CleanupError):
            cleanup.require_run_ownership(tags, "expected")

    def test_owned_name_must_bind_exactly_to_run_id(self) -> None:
        for name in ("rg-foreign-production", "rg-golden-e2e-12345-1-copy", "rg-golden-e2e-12345"):
            with self.subTest(name=name), self.assertRaises(cleanup.CleanupError):
                cleanup.require_owned_name(name, "12345-1")

    def test_spoofed_tags_on_foreign_name_are_not_swept(self) -> None:
        resources = [{
            "name": "rg-foreign-production",
            "tags": {"owner": cleanup.OWNER, "repository": cleanup.REPOSITORY, "run-id": "12345-1", "ttl": "2026-10-15T00:00:00Z"},
        }]
        selected = cleanup.expired_owned_groups(resources, datetime(2026, 10, 16, tzinfo=UTC))
        self.assertEqual(selected, ())

    def test_invalid_and_future_ttls_are_not_swept(self) -> None:
        resources = [
            {"name": "rg-golden-e2e-12345-1", "tags": {"owner": cleanup.OWNER, "repository": cleanup.REPOSITORY, "run-id": "12345-1", "ttl": "not-a-time"}},
            {"name": "rg-golden-e2e-12346-1", "tags": {"owner": cleanup.OWNER, "repository": cleanup.REPOSITORY, "run-id": "12346-1", "ttl": "2026-10-17T00:00:00Z"}},
        ]
        selected = cleanup.expired_owned_groups(resources, datetime(2026, 10, 16, tzinfo=UTC))
        self.assertEqual(selected, ())

    def test_utc_z_ttl_is_selected_when_expired(self) -> None:
        resources = [{
            "name": "rg-golden-e2e-12345-1",
            "tags": {"owner": cleanup.OWNER, "repository": cleanup.REPOSITORY, "run-id": "12345-1", "ttl": "2026-10-15T00:00:00Z"},
        }]

        selected = cleanup.expired_owned_groups(resources, datetime(2026, 10, 16, tzinfo=UTC))

        self.assertEqual(selected, ("rg-golden-e2e-12345-1",))

    def test_active_run_is_excluded_from_ttl_sweep(self) -> None:
        resources = [{
            "name": "rg-golden-e2e-12345-1",
            "tags": {"owner": cleanup.OWNER, "repository": cleanup.REPOSITORY, "run-id": "12345-1", "ttl": "2026-10-15T00:00:00Z"},
        }]
        selected = cleanup.expired_owned_groups(
            resources,
            datetime(2026, 10, 16, tzinfo=UTC),
            active_run_ids=frozenset({"12345-1"}),
        )
        self.assertEqual(selected, ())

    def test_concurrently_running_workflow_is_excluded_from_ttl_sweep(self) -> None:
        resources = [{
            "name": "rg-golden-e2e-67890-2",
            "tags": {"owner": cleanup.OWNER, "repository": cleanup.REPOSITORY, "run-id": "67890-2", "ttl": "2026-10-15T00:00:00Z"},
        }]

        selected = cleanup.expired_owned_groups(
            resources,
            datetime(2026, 10, 16, tzinfo=UTC),
            active_run_ids=frozenset({"12345-1", "67890-2"}),
        )

        self.assertEqual(selected, ())

    def test_ttl_hours_accepts_only_safe_decimal_integer(self) -> None:
        self.assertEqual(cleanup.parse_ttl_hours("3"), 3)
        self.assertEqual(cleanup.parse_ttl_hours("72"), 72)
        for value in ("-1", "0", "1", "2", "73", "999999", "1 day ago", "01", "+1"):
            with self.subTest(value=value), self.assertRaises(cleanup.CleanupError):
                cleanup.parse_ttl_hours(value)

    def test_delete_waits_for_control_plane_absence(self) -> None:
        group = {
            "tags": {
                "owner": cleanup.OWNER,
                "repository": cleanup.REPOSITORY,
                "run-id": "12345-1",
            }
        }
        responses = iter((json.dumps(group), "{}", "true", "true", "false"))
        with patch.object(cleanup, "_az", side_effect=lambda *args: next(responses)), patch.object(
            cleanup.time, "sleep"
        ) as sleep:
            cleanup.delete_group("rg-golden-e2e-12345-1", "12345-1")
        self.assertEqual(sleep.call_count, 2)


if __name__ == "__main__":
    unittest.main()
