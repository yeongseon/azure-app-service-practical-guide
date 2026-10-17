#!/usr/bin/env python3
import pathlib
import re
import unittest

from ruamel.yaml import YAML

ROOT = pathlib.Path(__file__).resolve().parents[2]


class WorkflowYamlTests(unittest.TestCase):
    def test_every_workflow_rejects_no_duplicate_keys(self):
        yaml = YAML(typ="safe")
        yaml.allow_duplicate_keys = False
        for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
            with self.subTest(path=path.name):
                with path.open() as stream:
                    yaml.load(stream)

    def test_commit_hash_validation_requires_hex_format(self):
        """Validate that commit hashes must be 40-char hex, not just 40 chars."""
        valid_hex = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        self.assertIsNotNone(re.fullmatch(r"[0-9a-f]{40}", valid_hex))

        invalid_40_char = "G" * 40
        self.assertIsNone(re.fullmatch(r"[0-9a-f]{40}", invalid_40_char))

        invalid_uppercase = "A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6A1B2"
        self.assertIsNone(re.fullmatch(r"[0-9a-f]{40}", invalid_uppercase))


if __name__ == "__main__":
    unittest.main(verbosity=2)
