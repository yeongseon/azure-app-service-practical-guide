#!/usr/bin/env python3
"""The two evaluators must mean the same thing by the same exit code.

An independent reproduction found that they did not. `run.py` returned 1
for evidence that failed validation and 3 for a contradicted hypothesis,
while `evaluate_run.py` returned 1 for CONTRADICTED and 3 for NOT_TESTED.
A caller reading 3 could not tell a refuted hypothesis from one that was
never tested, which is exactly the distinction this model exists to keep.

Both documents describing them were individually accurate, which is why
reading either one alone could not reveal the conflict. Only running both
tools did.
"""

import importlib.util
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pilot = _load("pilot_x", "labs/deployment-succeeded-startup-failed/run.py")
evaluator = _load("ev_x", "scripts/golden/evaluate_run.py")


class AgreementTests(unittest.TestCase):

    def test_both_tools_publish_the_same_mapping(self):
        self.assertEqual(pilot.EXIT_CODES, evaluator.EXIT_CODES)

    def test_the_mapping_covers_the_frozen_vocabulary(self):
        self.assertEqual(
            sorted(evaluator.EXIT_CODES), sorted(evaluator.HYPOTHESIS_STATUS))

    def test_every_status_has_a_distinct_code(self):
        codes = list(evaluator.EXIT_CODES.values())
        self.assertEqual(len(codes), len(set(codes)))

    def test_a_supported_hypothesis_is_the_only_success(self):
        for status, code in evaluator.EXIT_CODES.items():
            with self.subTest(status=status):
                self.assertEqual(code == 0, status == "SUPPORTED")

    def test_contradicted_and_not_tested_are_not_the_same_code(self):
        """The exact collision the reproduction surfaced."""
        self.assertNotEqual(
            evaluator.EXIT_CODES["CONTRADICTED"],
            evaluator.EXIT_CODES["NOT_TESTED"])


class EvidenceFailureTests(unittest.TestCase):
    """Invalid evidence supports no hypothesis verdict, so it gets its own code."""

    def test_evidence_failure_has_a_code_outside_the_hypothesis_set(self):
        self.assertNotIn(pilot.EXIT_EVIDENCE_INVALID, evaluator.EXIT_CODES.values())

    def test_failed_validation_returns_that_code(self):
        self.assertEqual(
            pilot.exit_code_for({"evidence_validation": "FAIL"}),
            pilot.EXIT_EVIDENCE_INVALID)

    def test_a_contradicted_hypothesis_returns_the_shared_code(self):
        self.assertEqual(
            pilot.exit_code_for({"evidence_validation": "PASS",
                                 "hypothesis_evaluation": "CONTRADICTED"}),
            evaluator.EXIT_CODES["CONTRADICTED"])

    def test_inconclusive_evidence_returns_the_shared_code(self):
        self.assertEqual(
            pilot.exit_code_for({"evidence_validation": "INCONCLUSIVE"}),
            evaluator.EXIT_CODES["INCONCLUSIVE"])

    def test_a_supported_hypothesis_returns_zero(self):
        self.assertEqual(
            pilot.exit_code_for({"evidence_validation": "PASS",
                                 "hypothesis_evaluation": "SUPPORTED"}), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
