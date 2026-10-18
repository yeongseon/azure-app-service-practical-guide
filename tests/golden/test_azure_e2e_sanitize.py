from __future__ import annotations

import importlib.util
import json
import random
import string
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/golden"))
SPEC = importlib.util.spec_from_file_location(
    "azure_e2e_guard", ROOT / "scripts/golden/azure_e2e_guard.py"
)
assert SPEC is not None and SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)

class AzureE2ESanitizeTests(unittest.TestCase):
    def _sanitize(self, files: dict[str, str]) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        source = root / "source"
        source.mkdir()
        for name, content in files.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        destination = root / "sanitized"
        try:
            guard.sanitize_tree(source, destination)
        except guard.GuardError:
            temporary.cleanup()
            raise
        return destination, temporary

    def test_structured_json_keeps_only_typed_allowlisted_evidence(self) -> None:
        run = {
            "run_id": "20261018T010203Z-abcdef123456",
            "started_at": "2026-10-18T01:02:03+00:00",
            "ended_at": "2026-10-18T01:12:03+00:00",
            "execution_status": "FAILED",
            "cleanup_status": "PENDING",
            "source_sha": "a" * 40,
            "resource_id": "/subscriptions/12345678-1234-1234-1234-123456789abc/resourceGroups/private/providers/Microsoft.Web/sites/private",
            "error": "accessToken=must-drop",
            "artifacts": {"secret.json": {"sha256": "b" * 64}},
        }
        evaluation = {
            "run_id": run["run_id"],
            "evaluated_at": "2026-10-18T01:13:03Z",
            "evidence_validation": "FAIL",
            "hypothesis_evaluation": "INCONCLUSIVE",
            "matching_import_errors": 0,
            "errors": ["password=must-drop"],
        }

        destination, temporary = self._sanitize({
            "private/run.json": json.dumps(run),
            "private/evaluation-deadbeef.json": json.dumps(evaluation),
        })
        self.addCleanup(temporary.cleanup)

        retained_run = json.loads((destination / "run.json").read_text(encoding="utf-8"))
        retained_evaluation = json.loads((destination / "evaluation.json").read_text(encoding="utf-8"))
        self.assertEqual(retained_run["resource_id"], guard.RESOURCE_ID_PLACEHOLDER)
        self.assertEqual(retained_run["started_at"], run["started_at"])
        self.assertEqual(retained_run["source_commit"], run["source_sha"])
        self.assertNotIn("error", retained_run)
        self.assertNotIn("artifacts", retained_run)
        self.assertEqual(retained_evaluation["evidence_validation"], "FAIL")
        self.assertNotIn("errors", retained_evaluation)
        guard.scan_sanitized_tree(destination)

    def test_cleanup_record_keeps_owned_group_and_timestamps_only(self) -> None:
        raw = {
            "github_run_id": "12345",
            "github_run_attempt": "2",
            "cleanup_status": "VERIFIED",
            "verified_at": "2026-10-18T01:13:03+00:00",
            "group_name": "rg-golden-e2e-12345-2",
            "exists": False,
            "error": "client_secret=must-drop",
        }

        destination, temporary = self._sanitize({"cleanup-result.json": json.dumps(raw)})
        self.addCleanup(temporary.cleanup)

        retained = json.loads((destination / "cleanup-result.json").read_text(encoding="utf-8"))
        self.assertEqual(retained["group_name"], "rg-golden-e2e-12345-2")
        self.assertIs(retained["exists"], False)
        self.assertNotIn("error", retained)
        guard.scan_sanitized_tree(destination)

    def test_raw_log_retains_only_typed_metadata(self) -> None:
        source = "safe runner status 200\r\npassword=\r\nhunter2\r\n"

        destination, temporary = self._sanitize({"scenario-a.log": source})
        self.addCleanup(temporary.cleanup)
        retained = json.loads((destination / "raw-log-0001.json").read_text(encoding="utf-8"))

        self.assertEqual(retained["role"], "scenario-runner")
        self.assertEqual(retained["byte_length"], len(source.encode("utf-8")))
        self.assertEqual(retained["line_count"], 3)
        self.assertRegex(retained["sha256"], r"^[0-9a-f]{64}$")
        self.assertNotIn("safe runner status", json.dumps(retained))
        self.assertNotIn("hunter2", json.dumps(retained))
        guard.scan_sanitized_tree(destination)

    def test_deterministic_property_no_free_text_appears_in_output_tree(self) -> None:
        randomizer = random.Random(218)
        alphabet = string.ascii_letters + string.digits + " .-/:=_?@[]{}'\""
        separators = ("\n", "\r\n", "\r")
        records: list[str] = []
        for index in range(600):
            secret = "".join(randomizer.choice(string.ascii_letters + string.digits) for _ in range(32))
            key = randomizer.choice(("accessToken", "password", "client_secret", "Authorization Basic", "public"))
            prefix = "".join(randomizer.choice(alphabet) for _ in range(randomizer.randint(0, 24)))
            suffix = "".join(randomizer.choice(alphabet) for _ in range(randomizer.randint(0, 24)))
            records.append(f"case-{index}-{prefix}{key}={secret}{suffix}")
        source = "".join(record + separators[index % len(separators)] for index, record in enumerate(records))

        destination, temporary = self._sanitize({"scenario-a.log": source})
        self.addCleanup(temporary.cleanup)
        output = b"".join(path.read_bytes() for path in destination.iterdir())

        self.assertTrue(all(record.encode("utf-8") not in output for record in records))
        guard.scan_sanitized_tree(destination)

    def test_independent_scanner_rejects_non_allowlisted_shapes(self) -> None:
        fixtures = {
            "unexpected.json": "{}\n",
            "run.json": '{"run_id":"valid","password":"leak"}\n',
            "notes.txt": "password secret\n",
            "runner.log": "Authorization Basic leak\n",
        }
        for name, content in fixtures.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / name).write_text(content, encoding="utf-8")
                with self.assertRaises(guard.GuardError):
                    guard.scan_sanitized_tree(root)


if __name__ == "__main__":
    unittest.main()
