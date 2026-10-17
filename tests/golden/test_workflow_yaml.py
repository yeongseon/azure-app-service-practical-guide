#!/usr/bin/env python3
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

from ruamel.yaml import YAML

ROOT = pathlib.Path(__file__).resolve().parents[2]


class WorkflowYamlTests(unittest.TestCase):
    def test_every_workflow_rejects_no_duplicate_keys(self):
        yaml = YAML(typ="safe")
        yaml.allow_duplicate_keys = False
        for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
            with self.subTest(path=path.name), path.open() as stream:
                yaml.load(stream)

    def test_commit_hash_validation_requires_hex_format(self):
        # Given: the Python heredoc embedded in the provenance-fetch workflow step.
        yaml = YAML(typ="safe")
        workflow_path = ROOT / ".github/workflows/validate-content-sources.yml"
        with workflow_path.open(encoding="utf-8") as stream:
            workflow = yaml.load(stream)
        steps = workflow["jobs"]["validate-golden-contracts"]["steps"]
        fetch_step = next(
            step
            for step in steps
            if step.get("name") == "Fetch retained Golden provenance commits"
        )
        script_match = re.search(
            r"python3 - <<'PY'[^\n]*\n(?P<script>.*?)\nPY(?:\n|$)",
            fetch_step["run"],
            re.DOTALL,
        )
        self.assertIsNotNone(script_match)
        script = script_match.group("script")

        valid_lowercase = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        invalid_non_hex = "g" * 40
        invalid_uppercase = "A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6A1B2"
        with tempfile.TemporaryDirectory() as temporary_directory:
            runs_directory = pathlib.Path(temporary_directory) / "evidence/runs"
            valid_directory = runs_directory / "valid"
            valid_directory.mkdir(parents=True)
            (valid_directory / "manifest.json").write_text(
                json.dumps({"source_commit": valid_lowercase}), encoding="utf-8"
            )
            non_hex_directory = runs_directory / "non-hex"
            non_hex_directory.mkdir()
            (non_hex_directory / "provenance.json").write_text(
                json.dumps(
                    {"derivation": {"collector_commit": invalid_non_hex}}
                ),
                encoding="utf-8",
            )
            uppercase_directory = runs_directory / "uppercase"
            uppercase_directory.mkdir()
            (uppercase_directory / "provenance.json").write_text(
                json.dumps(
                    {"derivation": {"collector_commit": invalid_uppercase}}
                ),
                encoding="utf-8",
            )

            # When: the exact extracted workflow code discovers commits to fetch.
            completed = subprocess.run(
                [sys.executable, "-c", script],
                cwd=temporary_directory,
                check=True,
                capture_output=True,
                text=True,
            )

        # Then: only a lowercase hexadecimal SHA is emitted.
        self.assertEqual(completed.stdout.splitlines(), [valid_lowercase])


if __name__ == "__main__":
    unittest.main(verbosity=2)
