#!/usr/bin/env python3

import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("scan_lab_pii", ROOT / "scripts/scan_lab_pii.py")
scanner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scanner)


class RetainedArtifactMutationTests(unittest.TestCase):
    def categories(self, value):
        return {category for _, category, _ in scanner.find_pii(value)}

    def test_64_hex_instance_id_is_flagged(self):
        self.assertIn("instance-id", self.categories('"WEBSITE_INSTANCE_ID":"' + "b" * 64 + '"'))

    def test_deployment_suffixed_resource_path_is_flagged(self):
        value = "/providers/Microsoft.Web/sites/app-demo-a1b2c3/config/web"
        self.assertIn("deployment-resource-path", self.categories(value))

    def test_rfc1918_address_is_flagged(self):
        self.assertIn("rfc1918-ip", self.categories("registry 10.24.8.9:443"))

    def test_approved_private_placeholder_is_not_flagged(self):
        self.assertNotIn("rfc1918-ip", self.categories("registry 10.0.0.0:443"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
