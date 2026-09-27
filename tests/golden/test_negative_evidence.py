"""Negative tests for the Golden v1 evaluator (#185).

Every case here corresponds to a defect that actually reached `main`
somewhere in this series and survived review until a fixture reproduced
it. They are written as negatives because each one describes evidence the
evaluator must REFUSE to accept, and a suite that only demonstrates the
happy path cannot distinguish a working gate from a vacuous one.
"""

import sys

# Bytecode caching silently defeats these tests. `importlib` will reuse a
# cached .pyc when a restored file's mtime and size collide with the
# version that produced it, so a reverted evaluator can keep executing
# sabotaged logic while the source on disk reads correctly. During
# mutation testing that presents as a passing suite over broken code.
sys.dont_write_bytecode = True

import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("ev", ROOT / "scripts/golden/evaluate_run.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)

RUN_ID = "20260927T000000Z-abc123"
RESOURCE = "/subscriptions/x/resourceGroups/rg/providers/Microsoft.Web/sites/app"


def make_run(**over):
    """Build a run directory. Nothing is inherited from the repository."""
    d = pathlib.Path(tempfile.mkdtemp()) / "run"
    d.mkdir(parents=True)
    manifest = {
        "run_id": RUN_ID,
        "resource_id": RESOURCE,
        "captured_at": "2026-09-27T00:00:00Z",
        "execution_status": over.pop("execution_status", "COMPLETE"),
        "assertions": over.pop("assertions", [
            {"id": "symptom-503", "role": "symptom", "field": "status", "equals": 503},
        ]),
    }
    manifest.update(over.pop("manifest", {}))
    if over.pop("omit_manifest", False) is False:
        (d / "manifest.json").write_text(json.dumps(manifest))
    evidence = over.pop("evidence", {"status": 503})
    if evidence is not None:
        (d / "evidence.json").write_text(
            evidence if isinstance(evidence, str) else json.dumps(evidence))
    return d


class MissingAndEmptyEvidenceTests(unittest.TestCase):
    def test_missing_evidence_file_is_not_supported(self):
        self.assertNotEqual(
            ev.evaluate(make_run(evidence=None))["hypothesis_status"], "SUPPORTED")

    def test_empty_evidence_object_is_inconclusive_not_contradicted(self):
        result = ev.evaluate(make_run(evidence={}))
        self.assertEqual(result["hypothesis_status"], "INCONCLUSIVE")

    def test_missing_manifest_is_a_model_error(self):
        with self.assertRaises(ev.ModelError):
            ev.evaluate(make_run(omit_manifest=True))


class MalformedEvidenceTests(unittest.TestCase):
    def test_malformed_json_is_rejected_not_silently_ignored(self):
        with self.assertRaises(ev.ModelError):
            ev.evaluate(make_run(evidence="{not json"))

    def test_unknown_execution_status_is_rejected(self):
        with self.assertRaises(ev.ModelError):
            ev.evaluate(make_run(execution_status="PROBABLY_FINE"))

    def test_unknown_evidence_role_is_rejected(self):
        run = make_run(assertions=[
            {"id": "a", "role": "vibes", "field": "status", "equals": 503}])
        with self.assertRaises(ev.ModelError):
            ev.evaluate(run)

    def test_assertion_without_a_comparison_is_rejected(self):
        run = make_run(assertions=[{"id": "a", "role": "symptom", "field": "status"}])
        with self.assertRaises(ev.ModelError):
            ev.evaluate(run)


class RawOverGeneratedVerdictTests(unittest.TestCase):
    def test_generated_pass_string_does_not_override_contradicting_raw(self):
        run = make_run(evidence={"status": 200})
        (run / "result.json").write_text(json.dumps({"hypothesis_status": "SUPPORTED"}))
        result = ev.evaluate(run)
        self.assertEqual(result["hypothesis_status"], "CONTRADICTED")
        self.assertTrue(result["generated_verdict_rejected"])

    def test_generated_verdict_is_never_read_as_input(self):
        """Deleting the raw evidence must not leave the stored verdict usable."""
        run = make_run(evidence=None)
        (run / "result.json").write_text(json.dumps({"hypothesis_status": "SUPPORTED"}))
        self.assertNotEqual(ev.evaluate(run)["hypothesis_status"], "SUPPORTED")


class AbsentVersusContradictoryTests(unittest.TestCase):
    """Missing data and refuted data must not share a code path."""

    def test_absent_field_never_reports_contradicted(self):
        self.assertEqual(
            ev.evaluate(make_run(evidence={"other": 1}))["hypothesis_status"],
            "INCONCLUSIVE")

    def test_present_but_wrong_field_reports_contradicted(self):
        self.assertEqual(
            ev.evaluate(make_run(evidence={"status": 200}))["hypothesis_status"],
            "CONTRADICTED")

    def test_one_refutation_outranks_many_confirmations(self):
        run = make_run(
            assertions=[
                {"id": "a", "role": "symptom", "field": "status", "equals": 503},
                {"id": "b", "role": "supporting", "field": "phase", "equals": "fault"},
                {"id": "c", "role": "control", "field": "cmd", "equals": "bad"},
            ],
            evidence={"status": 503, "phase": "fault", "cmd": "good"})
        self.assertEqual(ev.evaluate(run)["hypothesis_status"], "CONTRADICTED")

    def test_one_unevaluable_assertion_blocks_supported(self):
        run = make_run(
            assertions=[
                {"id": "a", "role": "symptom", "field": "status", "equals": 503},
                {"id": "b", "role": "recovery", "field": "recovered", "equals": 200},
            ],
            evidence={"status": 503})
        self.assertEqual(ev.evaluate(run)["hypothesis_status"], "INCONCLUSIVE")


class ExecutionStatusTests(unittest.TestCase):
    def test_incomplete_execution_cannot_produce_a_hypothesis_verdict(self):
        for status in ("PARTIAL", "BLOCKED", "FAILED", "NOT_RUN"):
            with self.subTest(status=status):
                run = make_run(execution_status=status, evidence={"status": 503})
                result = ev.evaluate(run)
                self.assertEqual(result["execution_status"], status)
                self.assertEqual(result["hypothesis_status"], "NOT_TESTED")


class ClaimPromotionTests(unittest.TestCase):
    def test_inferred_cannot_become_observed(self):
        with self.assertRaises(ev.ClaimPromotionError):
            ev.promote_claim("Inferred", "Observed")

    def test_weakening_a_claim_is_allowed(self):
        self.assertEqual(ev.promote_claim("Observed", "Inferred"), "Inferred")

    def test_unknown_claim_level_is_rejected(self):
        with self.assertRaises(ev.ModelError):
            ev.promote_claim("Observed", "Probably")


class EvaluatorScopeTests(unittest.TestCase):
    def test_evaluator_never_emits_a_root_cause(self):
        payload = json.dumps(ev.evaluate(make_run())).lower()
        for forbidden in ("root_cause", "root cause", "because"):
            self.assertNotIn(forbidden, payload)


class VacuityRegressionTests(unittest.TestCase):
    """Two false-positive paths found by review, not by these suites.

    Both were vacuity of exactly the kind this model exists to reject: a
    predicate that appears to consult evidence while structurally ignoring
    it. They are pinned here because both suites were green while the
    defects were live.
    """

    def _run(self, manifest, evidence):
        directory = pathlib.Path(tempfile.mkdtemp())
        (directory / "manifest.json").write_text(json.dumps(manifest))
        (directory / "evidence.json").write_text(json.dumps(evidence))
        return directory

    def test_duplicate_assertion_ids_are_rejected(self):
        """A repeated id silently overwrote the earlier outcome.

        A manifest declaring the same id twice could drop a CONTRADICTED
        result and report SUPPORTED, losing the refutation entirely.
        """
        directory = self._run(
            {"run_id": "r1", "execution_status": "COMPLETE",
             "captured_at": "2026-09-27T00:00:00Z",
             "assertions": [{"id": "same", "field": "a", "equals": 1},
                            {"id": "same", "field": "b", "equals": 2}]},
            {"a": 999, "b": 2})
        with self.assertRaises(ev.ModelError) as caught:
            ev.evaluate(directory)
        self.assertIn("duplicate assertion id", str(caught.exception))

    def test_a_dropped_contradiction_cannot_be_reported_as_supported(self):
        """The concrete false positive, stated as its own case."""
        directory = self._run(
            {"run_id": "r1", "execution_status": "COMPLETE",
             "captured_at": "2026-09-27T00:00:00Z",
             "assertions": [{"id": "dup", "field": "a", "equals": 1},
                            {"id": "dup", "field": "b", "equals": 2}]},
            {"a": 999, "b": 2})
        try:
            result = ev.evaluate(directory)
        except ev.ModelError:
            return
        self.fail(f"a contradiction was dropped and reported {result['hypothesis_status']!r}")


if __name__ == "__main__":
    unittest.main(verbosity=1)
