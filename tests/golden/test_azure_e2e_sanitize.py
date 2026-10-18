from __future__ import annotations

import importlib.util
import json
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
    def test_embedded_credential_assignments_are_redacted_and_scan_safe(self) -> None:
        hostile_lines = (
            "INFO payload accessToken=LOGLEAK request=42",
            'INFO payload={"accessToken":"EMBEDDEDLEAK"} request=42',
            r'INFO payload={"pass\u0077ord":"ESCAPELEAK"} request=42',
            '"accessToken":"QUOTEDLEAK"',
            'nested={"outer":{"clientSecret":"NESTED LEAK"}} done=true',
            'items=[{"api_key":"ARRAYLEAK"},{"password":"SECOND LEAK"}], status=done',
            'token="value with spaces", password=last-value.',
            "access-key='first value'; account_key=second-value, request=42",
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "capture.log"
            artifact.write_text("\n".join(hostile_lines), encoding="utf-8")

            sanitized = guard.sanitize_text(artifact.read_text(encoding="utf-8"))
            artifact.write_text(sanitized, encoding="utf-8")

            self.assertNotIn("LEAK", sanitized)
            self.assertEqual(sanitized.count("<REDACTED>"), 11)
            self.assertEqual(guard.sanitize_text(sanitized), sanitized)
            guard.scan_sanitized_tree(root)

    def test_scan_independently_rejects_embedded_credential_assignments(self) -> None:
        hostile_lines = (
            "INFO payload accessToken=LOGLEAK request=42",
            'INFO payload={"accessToken":"EMBEDDEDLEAK"} request=42',
            r'INFO payload={"pass\u0077ord":"ESCAPELEAK"} request=42',
            '"accessToken":"QUOTEDLEAK"',
            'nested=[{"clientSecret":"NESTED LEAK"}]',
            'token="value with spaces", password=last-value.',
        )
        for line in hostile_lines:
            with self.subTest(line=line), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "capture.log").write_text(line, encoding="utf-8")

                with self.assertRaises(guard.GuardError):
                    guard.scan_sanitized_tree(root)

    def test_json_credential_keys_are_redacted_after_normalization(self) -> None:
        raw = r'{"pass\u0077ord":"LEAKED","accessToken":"short-opaque-secret","client-secret":"opaque"}'

        sanitized = guard.sanitize_text(raw)

        self.assertEqual(json.loads(sanitized), {
            "password": "<REDACTED>",
            "accessToken": "<REDACTED>",
            "client-secret": "<REDACTED>",
        })
        self.assertEqual(guard.sanitize_text(sanitized), sanitized)

    def test_scan_independently_rejects_json_credential_keys(self) -> None:
        for document in (
            r'{"pass\u0077ord":"LEAKED"}',
            '{"accessToken":"short-opaque-secret"}',
            '{"api_key":"tiny"}',
        ):
            with self.subTest(document=document), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "capture.json").write_text(document, encoding="utf-8")
                with self.assertRaises(guard.GuardError):
                    guard.scan_sanitized_tree(root)

    def test_scan_requires_existing_nonempty_artifact_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for artifact_root in (root / "missing", root / "empty"):
                with self.subTest(artifact_root=artifact_root):
                    if artifact_root.name == "empty":
                        artifact_root.mkdir()
                    with self.assertRaises(guard.GuardError):
                        guard.scan_sanitized_tree(artifact_root)

    def test_scan_rejects_dotfile_only_and_placeholder_only_artifact_directories(self) -> None:
        fixtures = ((".gitkeep", ""), ("placeholder.txt", "placeholder\n"))
        for name, content in fixtures:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / name).write_text(content, encoding="utf-8")

                with self.assertRaises(guard.GuardError):
                    guard.scan_sanitized_tree(root)

    def test_hostile_secrets_are_sanitized_end_to_end(self) -> None:
        hostile_values = (
            "https://example.invalid/blob?sv=2024-11-04&se=2026-10-17&sig=abc%2Bdef%3D",
            "DefaultEndpointsProtocol=https;AccountName=private;AccountKey=base64secret==;EndpointSuffix=core.windows.net",
            "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.signature",
            "PASSWORD=super-secret-password",
            "client_secret: confidential-value",
            '{"password":"hunter2"}',
            "AZURE_CLIENT_SECRET=raw-azure-secret",
            "ARM_CLIENT_SECRET='raw-arm-secret'",
            'DB_PASSWORD="very secret password with spaces"',
            "{'client_secret': 'secret value;with=punctuation'}",
            "ipv6=2603:1030:20e:3::23 link_local=fe80::1",
        )
        for index, hostile in enumerate(hostile_values):
            with self.subTest(hostile=hostile), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "source"
                source.mkdir()
                (source / f"capture-{index}.txt").write_text(hostile, encoding="utf-8")
                destination = root / "sanitized"
                guard.sanitize_tree(source, destination)
                guard.scan_sanitized_tree(destination)

    def test_sanitizer_preserves_timestamps_and_is_idempotent(self) -> None:
        raw = (
            "at 12:34:56 ipv6 2603:1030:20e:3::23 resource "
            "/subscriptions/12345678-1234-1234-1234-123456789abc/"
            "resourceGroups/private/providers/Microsoft.Web/sites/private-app"
        )

        sanitized = guard.sanitize_text(raw)

        self.assertIn("12:34:56", sanitized)
        self.assertIn("2001:db8::1", sanitized)
        self.assertIn(guard.RESOURCE_ID_PLACEHOLDER, sanitized)
        self.assertEqual(guard.sanitize_text(sanitized), sanitized)


if __name__ == "__main__":
    unittest.main()
