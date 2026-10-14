#!/usr/bin/env python3
import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "oracle_evaluator", ROOT / "scripts/golden/evaluate_run.py")
ev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ev)

RUN_ID = "20260927T000000Z-abc123"
RESOURCE = "/subscriptions/<subscription-id>/resourceGroups/rg/providers/Microsoft.Web/sites/app"
CAPTURED = "2026-09-27T00:00:00Z"


def manifest(assertions=None):
    return {
        "run_id": RUN_ID,
        "resource_id": RESOURCE,
        "captured_at": CAPTURED,
        "capture_window": {
            "started_at": "2026-09-26T23:59:00Z",
            "ended_at": "2026-09-27T00:01:00Z",
        },
        "execution_status": "COMPLETE",
        "source_commit": "a" * 40,
        "environment": {"platform": "Azure App Service", "os": "Linux"},
        "recipe_digest": "sha256:" + "b" * 64,
        "collector_digest": "sha256:" + "c" * 64,
        "hypothesis": "The declared cause produced the observed symptom.",
        "hypothesis_claim_level": "Inferred",
        "assertions": assertions or [
            {"id": "symptom", "role": "symptom", "field": "status", "equals": 503,
             "claim_level": "Observed"},
            {"id": "cause", "role": "discriminating", "field": "cause_seen", "equals": True,
             "claim_level": "Observed"},
        ],
    }


def evidence(**overrides):
    value = {
        "run_id": RUN_ID,
        "resource_id": RESOURCE,
        "captured_at": CAPTURED,
        "observations": {"status": 503, "cause_seen": True},
    }
    value.update(overrides)
    return value


def write_run(manifest_doc=None, evidence_doc=None, result_doc=None):
    directory = pathlib.Path(tempfile.mkdtemp())
    (directory / "manifest.json").write_text(json.dumps(manifest_doc or manifest()))
    if evidence_doc is not None:
        (directory / "evidence.json").write_text(
            evidence_doc if isinstance(evidence_doc, str) else json.dumps(evidence_doc))
    if result_doc is not None:
        (directory / "result.json").write_text(
            result_doc if isinstance(result_doc, str) else json.dumps(result_doc))
    return directory


class EvidenceBindingMutations(unittest.TestCase):
    def test_wrong_resource_is_rejected(self):
        doc = evidence(resource_id=RESOURCE + "-other")
        with self.assertRaises(ev.ModelError):
            ev.evaluate(write_run(evidence_doc=doc))

    def test_mismatched_capture_time_is_rejected(self):
        doc = evidence(captured_at="2026-09-27T00:02:00Z")
        with self.assertRaises(ev.ModelError):
            ev.evaluate(write_run(evidence_doc=doc))

    def test_malformed_manifest_date_is_rejected(self):
        doc = manifest()
        doc["captured_at"] = "not-a-date"
        with self.assertRaises(ev.ModelError):
            ev.evaluate(write_run(manifest_doc=doc, evidence_doc=evidence()))

    def test_future_capture_is_rejected(self):
        doc = manifest()
        doc["captured_at"] = "2999-01-01T00:00:00Z"
        with self.assertRaises(ev.ModelError):
            ev.evaluate(write_run(manifest_doc=doc, evidence_doc=evidence()))


class CausalSupportMutations(unittest.TestCase):
    def test_symptom_only_manifest_is_inconclusive(self):
        assertions = [
            {"id": "symptom", "role": "symptom", "field": "status", "equals": 503,
             "claim_level": "Observed"}
        ]
        result = ev.evaluate(write_run(manifest_doc=manifest(assertions),
                                       evidence_doc=evidence(observations={"status": 503})))
        self.assertEqual(result["hypothesis_status"], "INCONCLUSIVE")

    def test_missing_discriminating_observation_is_inconclusive(self):
        result = ev.evaluate(write_run(evidence_doc=evidence(observations={"status": 503})))
        self.assertEqual(result["hypothesis_status"], "INCONCLUSIVE")

    def test_not_proven_causal_claim_cannot_be_supported(self):
        doc = manifest()
        doc["hypothesis_claim_level"] = "Not Proven"
        result = ev.evaluate(write_run(manifest_doc=doc, evidence_doc=evidence()))
        self.assertEqual(result["hypothesis_status"], "INCONCLUSIVE")

    def test_empty_assertions_are_not_supported(self):
        doc = manifest()
        doc["assertions"] = []
        result = ev.evaluate(write_run(manifest_doc=doc, evidence_doc=evidence()))
        self.assertNotEqual(result["hypothesis_status"], "SUPPORTED")

    def test_absorbed_strong_branch_is_rejected(self):
        assertions = [
            {"id": "weak", "role": "symptom", "field": "status", "in": [503, 200],
             "claim_level": "Observed"},
            {"id": "strong", "role": "discriminating", "field": "status", "equals": 503,
             "claim_level": "Observed"},
        ]
        with self.assertRaises(ev.ModelError):
            ev.evaluate(write_run(manifest_doc=manifest(assertions), evidence_doc=evidence()))


class GeneratedResultIntegrityMutations(unittest.TestCase):
    def recomputed(self, directory):
        return ev.evaluate(directory)

    def test_result_naming_another_run_is_rejected(self):
        directory = write_run(evidence_doc=evidence())
        stored = self.recomputed(directory)
        stored["run_id"] = "another-run"
        (directory / "result.json").write_text(json.dumps(stored))
        self.assertTrue(ev.evaluate(directory)["generated_verdict_rejected"])

    def test_stale_assertion_outcomes_are_rejected(self):
        directory = write_run(evidence_doc=evidence())
        stored = self.recomputed(directory)
        stored["assertion_outcomes"] = {"old-run-assertion": "SUPPORTED"}
        (directory / "result.json").write_text(json.dumps(stored))
        self.assertTrue(ev.evaluate(directory)["generated_verdict_rejected"])

    def test_duplicate_json_keys_are_rejected(self):
        duplicate = '{"run_id":"%s","run_id":"other","resource_id":"%s",' \
                    '"captured_at":"%s","execution_status":"COMPLETE","assertions":[]}' \
                    % (RUN_ID, RESOURCE, CAPTURED)
        with self.assertRaises(ev.ModelError):
            ev.evaluate(write_run(manifest_doc=manifest(), evidence_doc=evidence(),
                                  result_doc=duplicate))

    def test_lookalike_result_key_is_rejected(self):
        directory = write_run(evidence_doc=evidence())
        stored = self.recomputed(directory)
        stored["run_ıd"] = stored.pop("run_id")
        (directory / "result.json").write_text(json.dumps(stored, ensure_ascii=False))
        self.assertTrue(ev.evaluate(directory)["generated_verdict_rejected"])


class OfflineReplayMutation(unittest.TestCase):
    def test_only_evaluated_at_may_change(self):
        directory = write_run(evidence_doc=evidence())
        first = ev.evaluate(directory)
        second = ev.evaluate(directory)
        for key in first.keys() | second.keys():
            if key != "evaluated_at":
                self.assertEqual(first[key], second[key], key)


if __name__ == "__main__":
    unittest.main(verbosity=2)
