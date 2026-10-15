#!/usr/bin/env python3
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class RetainedPackageImmutabilityTests(unittest.TestCase):
    def test_committed_retained_packages_are_unchanged_from_base(self):
        completed = subprocess.run(
            [sys.executable, "scripts/golden/check_retained_packages.py", "--base-ref", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
