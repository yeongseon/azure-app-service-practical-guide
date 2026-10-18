from __future__ import annotations

import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

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

    def test_validator_accepted_trees_are_sanitizer_fixed_points(self) -> None:
        randomizer = random.Random(218)
        documents = {
            "run.json": {
                "run_id": "20261018T010203Z-abcdef123456",
                "execution_status": "FAILED",
                "started_at": "2026-10-18T01:02:03Z",
                "assertion_count": 7,
            },
            "evaluation.json": {
                "run_id": "20261018T010203Z-abcdef123456",
                "evaluated_at": "2026-10-18T01:03:03Z",
                "evidence_validation": "FAIL",
            },
            "cleanup-result.json": {
                "github_run_id": "12345",
                "github_run_attempt": "2",
                "cleanup_status": "VERIFIED",
                "exists": False,
            },
            "raw-log-0001.json": {
                "role": "runner-log",
                "byte_length": 123,
                "line_count": 4,
                "sha256": "a" * 64,
            },
            "failure-record.json": {
                "status": "FAILED",
                "failure_stage": "runner-crash",
                "github_run_id": "12345",
                "github_run_attempt": "2",
                "evidence_run_id": "20261018T010203Z-abcdef123456",
                "exit_code": 4,
                "started_at": "2026-10-18T01:02:03Z",
                "ended_at": "2026-10-18T01:03:03Z",
            },
        }
        names = tuple(documents)

        for case_index in range(2_048):
            with self.subTest(case_index=case_index), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "accepted"
                source.mkdir()
                selected = randomizer.sample(names, randomizer.randint(1, len(names)))
                for name in selected:
                    document = documents[name]
                    keys = randomizer.sample(tuple(document), randomizer.randint(1, len(document)))
                    canonical = {key: document[key] for key in keys}
                    (source / name).write_text(
                        json.dumps(canonical, sort_keys=True, separators=(",", ":")) + "\n",
                        encoding="utf-8",
                    )
                before = {path.name: path.read_bytes() for path in source.iterdir()}

                scan_sanitized_tree(source)
                destination = root / "resanitized"
                sanitize_tree(source, destination)

                self.assertEqual(
                    {path.name: path.read_bytes() for path in destination.iterdir()},
                    before,
                )

    def test_raw_inputs_always_produce_validator_accepted_output(self) -> None:
        randomizer = random.Random(248)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for case_index in range(64):
                source = root / f"raw-{case_index}"
                source.mkdir()
                payload = bytes(randomizer.randrange(256) for _ in range(randomizer.randrange(1, 512)))
                (source / "runner.log").write_bytes(payload)
                destination = root / f"sanitized-{case_index}"

                sanitize_tree(source, destination)

                scan_sanitized_tree(destination)

    def test_validator_rejects_noncanonical_json_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "run.json").write_text('{ "run_id": "20261018T010203Z-abcdef123456" }\n')

            with self.assertRaises(SanitizationError):
                scan_sanitized_tree(root)

    def test_cli_reports_huge_integer_as_controlled_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "run.json").write_text('{"assertion_count":' + "9" * 10_000 + "}\n")

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/golden/azure_e2e_cli.py"),
                    "sanitize",
                    str(source),
                    str(root / "output"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 4)
            self.assertIn("FAILED:", result.stderr)

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

    def test_timestamp_with_non_ascii_format_character_is_dropped(self) -> None:
        raw = {
            "run_id": "20261018T010203Z-abcdef123456",
            "started_at": "2026-10-18T01:02:03\u200b+00:00",
        }
        destination, temporary = self._sanitize({"run.json": json.dumps(raw)})
        self.addCleanup(temporary.cleanup)

        retained = json.loads((destination / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(retained, {"run_id": raw["run_id"]})

    def test_independent_scanner_rejects_all_free_text_files(self) -> None:
        for name in ("notes.txt", "runner.log", "log-0001.txt"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / name).write_text("public 203.0.113.9\n", encoding="utf-8")
                with self.assertRaises(SanitizationError):
                    scan_sanitized_tree(root)

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
