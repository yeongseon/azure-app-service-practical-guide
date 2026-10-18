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

LEAK_FORMS = (
    "accessToken=plain-secret",
    r'payload={"\u0061ccessToken":"escaped-secret"}',
    r'payload={"pass\u0077ord":"escaped-secret"}',
    'password="first line\nsecond line"',
    "Authorization: Basic dXNlcjpwYXNz",
    "Authorization: Bearer bearer-secret",
    "https://user:password@example.test/path",
    "QWxhZGRpbjpvcGVuIHNlc2FtZQ==",
    "VGhpc0lzQUxvbmdPcGFxdWVCbG9iV2l0aG91dERpZ2l0cw==",
    "/x?sig=S&token=T&ok=1 status=200",
    "x-api-key: short-secret",
    "client_secret=short-secret",
    "DefaultEndpointsProtocol=https;AccountKey=secret",
    "public=203.0.113.9 private=10.1.2.3 ipv6=2603:1030:20e:3::23",
    "owner=user@contoso.com",
    "tenant=12345678-1234-1234-1234-123456789abc",
    "sv=2026-01-01&sig=secret",
    '{"outer":{"password":"nested-secret"}}',
    '[{"token":"array-secret"}]',
)


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

    def test_every_reviewed_leak_form_is_dropped_from_log_summary(self) -> None:
        source = "safe runner status 200\n" + "\n".join(LEAK_FORMS)

        destination, temporary = self._sanitize({"scenario-a.log": source})
        self.addCleanup(temporary.cleanup)
        retained = (destination / "log-0001.txt").read_text(encoding="utf-8")

        self.assertIn("line 1: safe runner status 200", retained)
        self.assertEqual(retained.count("<line dropped: unsafe>"), len(LEAK_FORMS) + 1)
        for leak in LEAK_FORMS:
            self.assertNotIn(leak, retained)
        guard.scan_sanitized_tree(destination)

    def test_query_filter_drops_whole_line_without_collapsing_neighboring_evidence(self) -> None:
        source = "before status 201\n/x?sig=S&token=T&ok=1 status=200\nafter status 202\n"

        destination, temporary = self._sanitize({"scenario-a.log": source})
        self.addCleanup(temporary.cleanup)
        retained = (destination / "log-0001.txt").read_text(encoding="utf-8")

        self.assertIn("line 1: before status 201", retained)
        self.assertIn("line 2: <line dropped: unsafe>", retained)
        self.assertIn("line 3: after status 202", retained)

    def test_sanitizing_an_allowlist_artifact_is_idempotent(self) -> None:
        first, temporary = self._sanitize({
            "run.json": json.dumps({
                "run_id": "20261018T010203Z-abcdef123456",
                "execution_status": "FAILED",
                "started_at": "2026-10-18T01:02:03Z",
                "ended_at": "2026-10-18T01:03:03Z",
            }),
            "scenario-a.log": "safe status 200\npassword=drop-me\n",
        })
        self.addCleanup(temporary.cleanup)
        second = Path(temporary.name) / "sanitized-again"

        guard.sanitize_tree(first, second)

        first_files = {path.name: path.read_bytes() for path in first.iterdir()}
        second_files = {path.name: path.read_bytes() for path in second.iterdir()}
        self.assertEqual(second_files, first_files)

    def test_deterministic_fuzz_never_retains_credential_like_strings(self) -> None:
        randomizer = random.Random(218)
        alphabet = string.ascii_letters + string.digits
        lines: list[str] = []
        secrets: list[str] = []
        keys = ("accessToken", "password", "client_secret", "x-api-key", "sig")
        for _ in range(600):
            secret = "".join(randomizer.choice(alphabet) for _ in range(randomizer.randint(20, 60)))
            key = randomizer.choice(keys)
            prefix = "".join(randomizer.choice(alphabet + " .-/") for _ in range(randomizer.randint(0, 20)))
            suffix = "".join(randomizer.choice(alphabet + " .-/") for _ in range(randomizer.randint(0, 20)))
            lines.append(f"{prefix}{key}={secret}{suffix}")
            secrets.append(secret)

        destination, temporary = self._sanitize({"fuzz.log": "\n".join(lines)})
        self.addCleanup(temporary.cleanup)
        retained = (destination / "log-0001.txt").read_text(encoding="utf-8")

        self.assertTrue(all(secret not in retained for secret in secrets))
        guard.scan_sanitized_tree(destination)

    def test_independent_scanner_rejects_non_allowlisted_shapes(self) -> None:
        fixtures = {
            "unexpected.json": "{}\n",
            "run.json": '{"run_id":"valid","password":"leak"}\n',
            "log-0001.txt": "source_lines: 1\nline 1: Authorization Basic leak\n",
        }
        for name, content in fixtures.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / name).write_text(content, encoding="utf-8")
                with self.assertRaises(guard.GuardError):
                    guard.scan_sanitized_tree(root)


if __name__ == "__main__":
    unittest.main()
