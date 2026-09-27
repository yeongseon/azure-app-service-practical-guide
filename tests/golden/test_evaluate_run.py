"""Tests for the Golden v1 reference evaluator (#183)."""
import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("ev", ROOT / "scripts/golden/evaluate_run.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def run_dir(assertions, evidence, execution="COMPLETE"):
    d = pathlib.Path(tempfile.mkdtemp()) / "run"
    (d / "baseline").mkdir(parents=True)
    manifest = {
        "run_id": "20260927T000000Z-abc123",
        "resource_id": "/subscriptions/x/resourceGroups/rg/providers/Microsoft.Web/sites/app",
        "captured_at": "2026-09-27T00:00:00Z",
        "execution_status": execution,
        "assertions": assertions,
    }
    (d / "manifest.json").write_text(json.dumps(manifest))
    (d / "evidence.json").write_text(json.dumps(evidence))
    return d


class VocabularyTests(unittest.TestCase):
    def test_hypothesis_statuses_are_the_frozen_set(self):
        self.assertEqual(
            ev.HYPOTHESIS_STATUS,
            ("SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "NOT_TESTED"),
        )

    def test_claim_levels_are_the_frozen_set(self):
        self.assertEqual(ev.CLAIM_LEVELS, ("Documented", "Observed", "Inferred", "Not Proven"))

    def test_inferred_may_not_be_promoted_to_observed(self):
        with self.assertRaises(ev.ClaimPromotionError):
            ev.promote_claim("Inferred", "Observed")


class EvaluationTests(unittest.TestCase):
    def test_supported_when_evidence_satisfies_assertion(self):
        d = run_dir([{"id": "a1", "role": "symptom", "field": "status", "equals": 503}],
                    {"status": 503})
        self.assertEqual(ev.evaluate(d)["hypothesis_status"], "SUPPORTED")

    def test_contradicted_when_evidence_refutes_assertion(self):
        d = run_dir([{"id": "a1", "role": "symptom", "field": "status", "equals": 503}],
                    {"status": 200})
        self.assertEqual(ev.evaluate(d)["hypothesis_status"], "CONTRADICTED")

    def test_absent_field_is_inconclusive_not_contradicted(self):
        d = run_dir([{"id": "a1", "role": "symptom", "field": "status", "equals": 503}], {})
        self.assertEqual(ev.evaluate(d)["hypothesis_status"], "INCONCLUSIVE")

    def test_execution_not_complete_blocks_any_hypothesis_verdict(self):
        d = run_dir([{"id": "a1", "role": "symptom", "field": "status", "equals": 503}],
                    {"status": 503}, execution="FAILED")
        r = ev.evaluate(d)
        self.assertEqual(r["execution_status"], "FAILED")
        self.assertEqual(r["hypothesis_status"], "NOT_TESTED")

    def test_generated_verdict_disagreeing_with_raw_is_rejected(self):
        d = run_dir([{"id": "a1", "role": "symptom", "field": "status", "equals": 503}],
                    {"status": 200})
        (d / "result.json").write_text(json.dumps({"hypothesis_status": "SUPPORTED"}))
        r = ev.evaluate(d)
        self.assertEqual(r["hypothesis_status"], "CONTRADICTED")
        self.assertTrue(r["generated_verdict_rejected"])

    def test_evaluator_never_reports_a_root_cause(self):
        d = run_dir([{"id": "a1", "role": "symptom", "field": "status", "equals": 503}],
                    {"status": 503})
        self.assertNotIn("root_cause", json.dumps(ev.evaluate(d)).lower())


if __name__ == "__main__":
    unittest.main(verbosity=1)
