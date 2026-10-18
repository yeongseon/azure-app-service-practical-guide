from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.golden.azure_e2e_sanitize import (
    SanitizationError,
    sanitize_tree,
    scan_sanitized_tree,
)


class AzureE2EArtifactContractTests(unittest.TestCase):
    def _sanitize(self, files: dict[str, str]) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
        temporary = tempfile.TemporaryDirectory()
        source = Path(temporary.name) / "source"
        source.mkdir()
        for name, content in files.items():
            (source / name).write_text(content, encoding="utf-8")
        destination = Path(temporary.name) / "sanitized"
        try:
            sanitize_tree(source, destination)
        except SanitizationError:
            temporary.cleanup()
            raise
        return destination, temporary

    def test_allowlisted_json_is_rewritten_to_canonical_bytes(self) -> None:
        source = '{ "started_at" : "2026-10-18T01:02:03Z", "execution_status" : "FAILED", "run_id" : "20261018T010203Z-abcdef123456" }'
        destination, temporary = self._sanitize({"run.json": source})
        self.addCleanup(temporary.cleanup)
        expected = (
            '{"execution_status":"FAILED","run_id":"20261018T010203Z-abcdef123456",'
            '"started_at":"2026-10-18T01:02:03Z"}\n'
        )
        self.assertEqual((destination / "run.json").read_text(encoding="utf-8"), expected)

    def test_allowlisted_log_is_rechecked_and_canonicalized(self) -> None:
        source = (
            "source_lines: 2\n"
            "exit_code: 0\n"
            "line 1: safe status 200\n"
            "line 2: abcd1234efgh5678\n"
        )
        destination, temporary = self._sanitize({"log-0001.txt": source})
        self.addCleanup(temporary.cleanup)

        retained = (destination / "log-0001.txt").read_text(encoding="utf-8")
        self.assertIn("line 1: safe status 200", retained)
        self.assertIn("line 2: <line dropped: unsafe>", retained)
        self.assertNotIn("abcd1234efgh5678", retained)

    def test_duplicate_json_keys_are_rejected_regardless_of_secret_position(self) -> None:
        fixtures = (
            '{"scenario":"Bearer EXFILTRATED-SECRET","scenario":"deployment-succeeded-startup-failed"}',
            '{"scenario":"deployment-succeeded-startup-failed","scenario":"Bearer EXFILTRATED-SECRET"}',
        )
        for content in fixtures:
            with self.subTest(content=content), self.assertRaises(SanitizationError):
                self._sanitize({"run.json": content})

    def test_non_finite_json_numbers_are_rejected(self) -> None:
        for value in ("NaN", "Infinity", "-Infinity"):
            content = f'{{"run_id":"20261018T010203Z-abcdef123456","assertion_count":{value}}}'
            with self.subTest(value=value), self.assertRaises(SanitizationError):
                self._sanitize({"run.json": content})

    def test_wrong_per_key_scalar_types_are_rejected(self) -> None:
        raw = {"run_id": 12345, "execution_status": True, "exit_code": "0", "assertion_count": False}
        with self.assertRaises(SanitizationError):
            self._sanitize({"run.json": json.dumps(raw)})

    def test_oversize_or_out_of_range_timestamps_are_dropped(self) -> None:
        raw = {
            "run_id": "20261018T010203Z-abcdef123456",
            "started_at": "2026-10-18T01:02:03+00:00" + "0" * 10_000,
            "ended_at": "2200-10-18T01:02:03+00:00",
            "captured_at": "2026-10-18T01:02:03",
        }
        destination, temporary = self._sanitize({"run.json": json.dumps(raw)})
        self.addCleanup(temporary.cleanup)
        retained = json.loads((destination / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(retained, {"run_id": raw["run_id"]})

    def test_secret_bearing_values_are_rejected_in_all_string_fields(self) -> None:
        fixtures = {
            "run.json": {key: "Bearer EXFILTRATED-SECRET" for key in (
                "run_id", "execution_status", "started_at", "source_commit", "scenario", "resource_id"
            )},
            "evaluation.json": {key: "Bearer EXFILTRATED-SECRET" for key in (
                "run_id", "evaluated_at", "evidence_validation"
            )},
            "cleanup-result.json": {key: "Bearer EXFILTRATED-SECRET" for key in (
                "github_run_id", "github_run_attempt", "run_id", "group_name", "cleanup_status", "verified_at"
            )},
        }
        with self.assertRaises(SanitizationError):
            self._sanitize({name: json.dumps(document) for name, document in fixtures.items()})

    def test_independent_scanner_rejects_invalid_per_key_values(self) -> None:
        invalid_documents = (
            {"run_id": 12345}, {"execution_status": True}, {"exit_code": "0"},
            {"assertion_count": float("nan")},
            {"started_at": "2026-10-18T01:02:03Z" + "0" * 10_000},
            {"scenario": "Bearer EXFILTRATED-SECRET"},
        )
        for document in invalid_documents:
            with self.subTest(document=document), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "run.json").write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaises(SanitizationError):
                    scan_sanitized_tree(root)

    def test_independent_scanner_rejects_duplicate_keys_and_constants(self) -> None:
        fixtures = (
            '{"scenario":"Bearer EXFILTRATED-SECRET","scenario":"deployment-succeeded-startup-failed"}',
            '{"scenario":"deployment-succeeded-startup-failed","scenario":"Bearer EXFILTRATED-SECRET"}',
            '{"assertion_count":NaN}', '{"assertion_count":Infinity}', '{"assertion_count":-Infinity}',
        )
        for content in fixtures:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "run.json").write_text(content, encoding="utf-8")
                with self.assertRaises(SanitizationError):
                    scan_sanitized_tree(root)


if __name__ == "__main__":
    unittest.main()
