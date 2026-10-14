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
from unittest import mock
import hashlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "repro", ROOT / "scripts/golden/check_reproduction.py")
repro = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(repro)


def record(**over):
    base = {
        "reviewer": "second-operator",
        "reviewer_kind": "human",
        "original_operator": "first-operator",
        "original_operator_kind": "human",
        "commit": "a5d8ed9e0cc276788ee82c6755b0a6ad9b0c89a8",
        "attempted_at": "2026-09-27T03:00:00Z",
        "scenario": "deployment-succeeded-startup-failed",
        "original_run_id": "20260927T104304Z-aba0d3a9daa7",
        "replay_run_id": "20260927T104304Z-aba0d3a9daa7",
        "original_hypothesis_status": "SUPPORTED",
        "replay_hypothesis_status": "SUPPORTED",
        "consulted_source_to_fill_doc_gap": False,
        "deviations": [],
    }
    base.update(over)
    return base


def write(rec):
    d = pathlib.Path(tempfile.mkdtemp()) / "reproduction.json"
    d.write_text(rec if isinstance(rec, str) else json.dumps(rec))
    return d


class IndependenceTests(unittest.TestCase):
    def test_nonexistent_run_ids_are_rejected(self):
        rec = record(replay_run_id="missing-run", reviewer_kind="human",
                     original_operator_kind="human")
        with self.assertRaises(repro.ReproductionError):
            repro.check(write(rec))

    def test_replay_reusing_the_original_run_id_is_not_independent(self):
        rec = record(replay_run_id=record()["original_run_id"])
        result = repro.check(write(rec))
        self.assertEqual(result["reproduction_result"], "NOT_INDEPENDENT")

    def test_same_operator_replaying_their_own_run_is_not_independent(self):
        rec = record(reviewer="first-operator")
        result = repro.check(write(rec))
        self.assertEqual(result["reproduction_result"], "NOT_INDEPENDENT")

    def test_agent_replay_is_repeatability_not_independent_reproduction(self):
        rec = record(reviewer_kind="agent")
        result = repro.check(write(rec))
        self.assertEqual(result["reproduction_result"], "NOT_INDEPENDENT")
        self.assertFalse(result["passed"])

    def test_diverging_verdict_is_a_failed_reproduction(self):
        rec = record(replay_hypothesis_status="CONTRADICTED")
        rec["replay_run_id"] = "different-run"
        result = repro.classify_reproduction(rec)
        self.assertEqual(result, "FAILED")


class DocumentationGapTests(unittest.TestCase):
    def test_reading_source_fails_documentation_even_when_the_verdict_matches(self):
        rec = record(consulted_source_to_fill_doc_gap=True)
        result = repro.check(write(rec))
        self.assertEqual(result["reproduction_result"], "NOT_INDEPENDENT")
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
            reviewer_kind="human",
            original_operator_kind="human",
            original_hypothesis_status="NOT_TESTED",
            replay_hypothesis_status="NOT_TESTED")
        with self.assertRaises(repro.ReproductionError):
            repro.check(path)

    def test_nonexistent_matching_runs_do_not_reproduce(self):
        path = self._record(
            replay_run_id="fabricated",
            reviewer_kind="human",
            original_operator_kind="human",
            original_hypothesis_status="SUPPORTED",
            replay_hypothesis_status="SUPPORTED",
            consulted_source_to_fill_doc_gap=False,
            deviations=[])
        with self.assertRaises(repro.ReproductionError):
            repro.check(path)


class RetainedRunIntegrityMutations(unittest.TestCase):
    def test_short_fake_commit_is_rejected(self):
        with self.assertRaises(repro.ReproductionError):
            repro.check(write(record(commit="deadbee")))

    def test_malformed_attempt_date_is_rejected(self):
        with self.assertRaises(repro.ReproductionError):
            repro.check(write(record(attempted_at="not-a-date")))

    def test_future_attempt_date_is_rejected(self):
        with self.assertRaises(repro.ReproductionError):
            repro.check(write(record(attempted_at="2999-01-01T00:00:00Z")))

    def test_committed_agent_records_remain_not_independent(self):
        for path in sorted((ROOT / "evidence/reproductions").glob("*.json")):
            with self.subTest(path=path.name):
                try:
                    result = repro.check(path)
                except repro.ReproductionError:
                    continue
                self.assertEqual(result["reproduction_result"], "NOT_INDEPENDENT")
                self.assertFalse(result["passed"])


class RunPackageMutationTests(unittest.TestCase):
    def setUp(self):
        self.runs = pathlib.Path(tempfile.mkdtemp())
        self.patch = mock.patch.object(repro, "RUNS", self.runs)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def _run(self, run_id, scenario, resource_group, app_name, status=503,
             cleanup_verified=True):
        directory = self.runs / run_id
        directory.mkdir()
        captured = "2026-09-27T03:00:00Z"
        manifest = {
            "run_id": run_id,
            "resource_id": f"/subscriptions/<subscription-id>/resourceGroups/{resource_group}/providers/Microsoft.Web/sites/{app_name}",
            "captured_at": captured,
            "execution_status": "COMPLETE",
            "source_commit": "a" * 40,
            "environment": {"resource_group": resource_group, "app_name": app_name},
            "recipe_digest": "sha256:" + "b" * 64,
            "collector_digest": "sha256:" + "c" * 64,
            "hypothesis": "A causal hypothesis.",
            "hypothesis_claim_level": "Inferred",
            "assertions": [
                {"id": "symptom", "role": "symptom", "field": "status", "equals": status},
                {"id": "cause", "role": "discriminating", "field": "cause", "equals": True},
                {"id": "recovery", "role": "recovery", "field": "recovery", "equals": 200},
            ],
        }
        evidence = {"run_id": run_id, "resource_id": manifest["resource_id"],
                    "captured_at": captured,
                    "observations": {"status": status, "cause": True, "recovery": 200}}
        (directory / "manifest.json").write_text(json.dumps(manifest))
        (directory / "evidence.json").write_text(json.dumps(evidence))
        result = repro.evaluator.evaluate(directory)
        (directory / "result.json").write_text(json.dumps(result))
        provenance = {
            "scenario": scenario,
            "cleanup_verified": cleanup_verified,
            "digests": {
                name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                for name in ("manifest.json", "evidence.json", "result.json")
            },
        }
        (directory / "provenance.json").write_text(json.dumps(provenance))

    def _record(self, **overrides):
        value = record(original_run_id="original", replay_run_id="replay")
        value.update(overrides)
        return write(value)

    def test_synthetic_directories_without_provenance_cannot_pass(self):
        self._run("original", "deployment-succeeded-startup-failed", "rg-one", "app-one")
        self._run("replay", "deployment-succeeded-startup-failed", "rg-two", "app-two")
        (self.runs / "replay" / "provenance.json").unlink()
        with self.assertRaises(repro.ReproductionError):
            repro.check(self._record())

    def test_stored_supported_verdict_is_recomputed_from_raw_evidence(self):
        self._run("original", "deployment-succeeded-startup-failed", "rg-one", "app-one")
        self._run("replay", "deployment-succeeded-startup-failed", "rg-two", "app-two")
        evidence = json.loads((self.runs / "replay/evidence.json").read_text())
        evidence["observations"]["cause"] = False
        (self.runs / "replay/evidence.json").write_text(json.dumps(evidence))
        provenance = json.loads((self.runs / "replay/provenance.json").read_text())
        provenance["digests"]["evidence.json"] = hashlib.sha256(
            (self.runs / "replay/evidence.json").read_bytes()).hexdigest()
        (self.runs / "replay/provenance.json").write_text(json.dumps(provenance))
        with self.assertRaises(repro.ReproductionError):
            repro.check(self._record())

    def test_duplicate_and_case_variant_record_keys_are_rejected(self):
        duplicate = json.dumps(record())[:-1] + ',"reviewer":"other"}'
        with self.assertRaises(repro.ReproductionError):
            repro.check(write(duplicate))
        lookalike = record()
        lookalike["Reviewer_Kind"] = lookalike["reviewer_kind"]
        with self.assertRaises(repro.ReproductionError):
            repro.check(write(lookalike))

    def test_record_scenario_must_match_both_runs(self):
        self._run("original", "deployment-succeeded-startup-failed", "rg-one", "app-one")
        self._run("replay", "other-scenario", "rg-two", "app-two")
        with self.assertRaises(repro.ReproductionError):
            repro.check(self._record())

    def test_runs_must_use_different_resource_groups_and_apps(self):
        self._run("original", "deployment-succeeded-startup-failed", "rg-shared", "app-shared")
        self._run("replay", "deployment-succeeded-startup-failed", "rg-shared", "app-shared")
        with self.assertRaises(repro.ReproductionError):
            repro.check(self._record())

    def test_cleanup_evidence_is_required_for_both_runs(self):
        self._run("original", "deployment-succeeded-startup-failed", "rg-one", "app-one")
        self._run("replay", "deployment-succeeded-startup-failed", "rg-two", "app-two",
                  cleanup_verified=False)
        with self.assertRaises(repro.ReproductionError):
            repro.check(self._record())


if __name__ == "__main__":
    unittest.main(verbosity=1)
