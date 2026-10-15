#!/usr/bin/env python3
import pathlib
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
