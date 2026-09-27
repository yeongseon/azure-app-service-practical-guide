#!/usr/bin/env python3
"""A retained run must replay from this repository alone.

The review recorded run identifiers and their verdicts while the runs
themselves lived only on the machine that produced them. A reader could
therefore read that a scenario returned SUPPORTED and had no way to check
it. Declaring an execution and retaining evidence of it are different
claims, and only the second is verifiable.

These tests replay every retained package and require the recomputed
verdict to match the stored one, so a package that has been edited, or a
verdict that has drifted from its evidence, fails here.
"""

import importlib.util
import json
import pathlib
import re
import sys
import unittest

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNS = ROOT / "evidence" / "runs"

_spec = importlib.util.spec_from_file_location("ev_r", ROOT / "scripts/golden/evaluate_run.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)

GUID = re.compile(r"(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?![0-9a-f])", re.I)
ZERO = "00000000-0000-0000-0000-000000000000"


def packages():
    if not RUNS.is_dir():
        return []
    return [d for d in sorted(RUNS.iterdir()) if (d / "manifest.json").is_file()]


def declared_runs():
    found = set()
    for path in (ROOT / "labs").glob("*/golden/evidence-classification.json"):
        found.update(json.loads(path.read_text()).get("executed_runs") or [])
    return found


class ReplayTests(unittest.TestCase):

    def test_at_least_one_run_is_retained(self):
        """Guards every test below from passing on an empty directory."""
        self.assertGreaterEqual(len(packages()), 2)

    def test_each_package_replays_to_its_stored_verdict(self):
        for directory in packages():
            with self.subTest(run=directory.name):
                stored = json.loads((directory / "result.json").read_text())
                recomputed = ev.evaluate(directory)
                self.assertEqual(
                    recomputed["hypothesis_status"], stored["hypothesis_status"],
                    msg="the stored verdict disagrees with its own evidence")
                self.assertEqual(recomputed["execution_status"], stored["execution_status"])

    def test_each_package_binds_its_evidence(self):
        for directory in packages():
            with self.subTest(run=directory.name):
                self.assertEqual(ev.evaluate(directory)["evidence_identity"], "BOUND")

    def test_every_declared_run_is_retained(self):
        """A declared execution with no package is an unverifiable claim."""
        self.assertEqual(
            declared_runs() - {d.name for d in packages()}, set(),
            msg="a scenario declares a run that this repository cannot replay")

    def test_every_retained_run_is_declared(self):
        self.assertEqual(
            {d.name for d in packages()} - declared_runs(), set(),
            msg="a retained package names a run no scenario claims")


class SanitisationTests(unittest.TestCase):

    def test_no_live_identifier_survives(self):
        for directory in packages():
            for path in sorted(directory.glob("*.json")):
                text = path.read_text()
                with self.subTest(path=path.relative_to(ROOT)):
                    for found in GUID.findall(text):
                        self.assertEqual(
                            found, ZERO,
                            msg="a real Azure identifier is retained in a replay package")
                    self.assertNotRegex(text, r"(?i)\bMCAPS[-A-Za-z0-9_]*\b")

    def test_each_package_states_how_to_replay_it(self):
        for directory in packages():
            with self.subTest(run=directory.name):
                provenance = json.loads((directory / "provenance.json").read_text())
                self.assertIn("evaluate_run.py", provenance["replay"])
                self.assertTrue(provenance["sanitisation"].strip())


if __name__ == "__main__":
    unittest.main(verbosity=2)
