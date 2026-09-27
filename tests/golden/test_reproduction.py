"""Independent reproduction gate tests (#179).

A reproduction is only independent if a second operator, given the
repository, a target commit, the public documentation and an environment,
reaches the same verdict *from the documentation alone*.

Two failure modes matter more than a matching verdict:

A replay that reuses the original run's artifacts is not a reproduction.
It will always agree, because it is the same evidence.

A reviewer who had to read source to fill a documentation gap has proven
the code works and the documentation does not. The verdict may match; the
documentation reproduction still FAILED. Recording only the verdict would
hide exactly the defect this gate exists to surface.
"""

import sys

sys.dont_write_bytecode = True

import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "repro", ROOT / "scripts/golden/check_reproduction.py")
repro = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(repro)


def record(**over):
    base = {
        "reviewer": "second-operator",
        "original_operator": "first-operator",
        "commit": "a5d8ed9e0cc276788ee82c6755b0a6ad9b0c89a8",
        "attempted_at": "2026-09-27T03:00:00Z",
        "scenario": "deployment-succeeded-startup-failed",
        "original_run_id": "20260927T010203Z-a1b2c3",
        "replay_run_id": "20260927T040506Z-f6e5d4",
        "original_hypothesis_status": "SUPPORTED",
        "replay_hypothesis_status": "SUPPORTED",
        "consulted_source_to_fill_doc_gap": False,
        "deviations": [],
    }
    base.update(over)
    return base


def write(rec):
    d = pathlib.Path(tempfile.mkdtemp()) / "reproduction.json"
    d.write_text(json.dumps(rec))
    return d


class IndependenceTests(unittest.TestCase):
    def test_a_clean_matching_replay_passes(self):
        result = repro.check(write(record()))
        self.assertEqual(result["reproduction_result"], "REPRODUCED")
        self.assertEqual(result["documentation_result"], "REPRODUCED")

    def test_replay_reusing_the_original_run_id_is_not_independent(self):
        rec = record(replay_run_id="20260927T010203Z-a1b2c3")
        result = repro.check(write(rec))
        self.assertEqual(result["reproduction_result"], "NOT_INDEPENDENT")

    def test_same_operator_replaying_their_own_run_is_not_independent(self):
        rec = record(reviewer="first-operator")
        result = repro.check(write(rec))
        self.assertEqual(result["reproduction_result"], "NOT_INDEPENDENT")

    def test_diverging_verdict_is_a_failed_reproduction(self):
        rec = record(replay_hypothesis_status="CONTRADICTED")
        result = repro.check(write(rec))
        self.assertEqual(result["reproduction_result"], "FAILED")


class DocumentationGapTests(unittest.TestCase):
    def test_reading_source_fails_documentation_even_when_the_verdict_matches(self):
        rec = record(consulted_source_to_fill_doc_gap=True)
        result = repro.check(write(rec))
        self.assertEqual(result["reproduction_result"], "REPRODUCED")
        self.assertEqual(
            result["documentation_result"], "FAILED",
            msg="reading code to fill a doc gap proves the code works, not the docs")

    def test_documentation_failure_is_reported_even_on_a_passing_run(self):
        rec = record(consulted_source_to_fill_doc_gap=True)
        self.assertFalse(repro.check(write(rec))["passed"])


class RecordIntegrityTests(unittest.TestCase):
    def test_missing_required_field_is_rejected(self):
        rec = record()
        del rec["commit"]
        with self.assertRaises(repro.ReproductionError):
            repro.check(write(rec))

    def test_unknown_hypothesis_status_is_rejected(self):
        rec = record(replay_hypothesis_status="PROBABLY")
        with self.assertRaises(repro.ReproductionError):
            repro.check(write(rec))

    def test_undeclared_deviation_type_is_rejected(self):
        rec = record(deviations=[{"note": "changed a thing"}])
        with self.assertRaises(repro.ReproductionError):
            repro.check(write(rec))

    def test_declared_deviations_are_preserved_in_the_result(self):
        rec = record(deviations=[
            {"step": "3.4", "kind": "undocumented-step", "detail": "had to set PORT manually"}])
        result = repro.check(write(rec))
        self.assertEqual(len(result["deviations"]), 1)

    def test_any_deviation_fails_documentation_reproduction(self):
        """A step the reader had to invent is a documentation gap."""
        rec = record(deviations=[
            {"step": "3.4", "kind": "undocumented-step", "detail": "had to set PORT manually"}])
        self.assertEqual(repro.check(write(rec))["documentation_result"], "FAILED")


class NotRunHonestyTests(unittest.TestCase):
    def test_not_attempted_is_a_valid_recordable_state(self):
        rec = record(replay_run_id=None, replay_hypothesis_status="NOT_TESTED")
        result = repro.check(write(rec))
        self.assertEqual(result["reproduction_result"], "NOT_ATTEMPTED")
        self.assertFalse(result["passed"])

    def test_an_unattempted_run_does_not_claim_the_docs_reproduced(self):
        """Nobody read the documentation, so it was not tested either.

        Reporting REPRODUCED here would assert a documentation pass that no
        reviewer ever produced, which is the same false-positive shape the
        evidence model exists to prevent.
        """
        rec = record(replay_run_id=None, replay_hypothesis_status="NOT_TESTED")
        self.assertEqual(repro.check(write(rec))["documentation_result"], "NOT_ATTEMPTED")


class UntestedPairRegressionTests(unittest.TestCase):
    """Equal statuses are not reproduction when neither side was tested.

    A fabricated record naming runs that do not exist, with NOT_TESTED on
    both sides, previously returned passed: True. Two runs that never
    happened cannot reproduce each other.
    """

    def _record(self, **overrides):
        record = json.loads(
            (ROOT / "evidence" / "reproductions" / "scenario-a.json").read_text())
        record.update(overrides)
        directory = pathlib.Path(tempfile.mkdtemp())
        path = directory / "rep.json"
        path.write_text(json.dumps(record))
        return path

    def test_two_untested_runs_do_not_reproduce_each_other(self):
        path = self._record(
            replay_run_id="fabricated",
            original_hypothesis_status="NOT_TESTED",
            replay_hypothesis_status="NOT_TESTED")
        result = repro.check(path)
        self.assertFalse(result["passed"])
        self.assertEqual(result["reproduction_result"], "INCONCLUSIVE")

    def test_a_genuine_matching_verdict_still_reproduces(self):
        """Guards the fix from rejecting every reproduction."""
        path = self._record(
            replay_run_id="fabricated",
            original_hypothesis_status="SUPPORTED",
            replay_hypothesis_status="SUPPORTED",
            consulted_source_to_fill_doc_gap=False,
            deviations=[])
        self.assertEqual(
            repro.check(path)["reproduction_result"], "REPRODUCED")


if __name__ == "__main__":
    unittest.main(verbosity=1)
