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
