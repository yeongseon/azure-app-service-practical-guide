#!/usr/bin/env python3
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock
import contextlib
import io

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "oracle_evaluator", ROOT / "scripts/golden/evaluate_run.py")
ev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ev)

RUN_ID = "20260927T000000Z-abc123"
RESOURCE = "/subscriptions/<subscription-id>/resourceGroups/rg/providers/Microsoft.Web/sites/app"
CAPTURED = "2026-09-27T00:00:00Z"
SOURCE_COMMIT = "3e0442bb19b966766598ffeae1fb47f3f6960837"


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
        "source_commit": SOURCE_COMMIT,
        "environment": {
            "subscription_kind": "Visual Studio Enterprise",
            "region": "koreacentral",
            "runtime": "Python 3.11",
            "sku": "B1",
        },
        "recipe_digest": "sha256:" + "0123456789abcdef" * 4,
        "collector_digest": "sha256:" + "fedcba9876543210" * 4,
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

    def test_future_capture_is_rejected_after_timezone_normalization(self):
        doc = manifest()
        doc["captured_at"] = "2999-01-01T00:00:00+14:00"
        with self.assertRaises(ev.ModelError):
            ev.evaluate(write_run(manifest_doc=doc, evidence_doc=evidence()))

    def test_new_run_rejects_malformed_provenance(self):
        for key, value in (("source_commit", "abc1234"),
                           ("recipe_digest", "sha256:abc"),
                           ("environment", {})):
            with self.subTest(key=key):
                doc = manifest()
                doc[key] = value
                with self.assertRaises(ev.ModelError):
                    ev.evaluate(write_run(manifest_doc=doc, evidence_doc=evidence()))

    def test_new_run_rejects_placeholder_provenance(self):
        cases = (
            ("source_commit", "0" * 40),
            ("recipe_digest", "sha256:" + "0" * 64),
            ("environment", {
                "subscription_kind": "unknown",
                "region": "<region>",
                "runtime": "TBD",
                "sku": "none",
            }),
        )
        for key, value in cases:
            with self.subTest(key=key):
                doc = manifest()
                doc[key] = value
                with self.assertRaises(ev.ModelError):
                    ev.evaluate(write_run(manifest_doc=doc, evidence_doc=evidence()))

    def test_source_commit_must_resolve_unless_explicitly_skipped(self):
        doc = manifest()
        doc["source_commit"] = "1234567890abcdef1234567890abcdef12345678"
        with self.assertRaises(ev.ModelError):
            ev.evaluate(write_run(manifest_doc=doc, evidence_doc=evidence()))

        result = ev.evaluate(
            write_run(manifest_doc=doc, evidence_doc=evidence()),
            skip_source_commit_resolution=True,
        )
        self.assertEqual(result["source_commit_resolution"], "SKIPPED_EXPLICITLY")

    def test_cli_records_explicit_source_commit_resolution_skip(self):
        doc = manifest()
        doc["source_commit"] = "1234567890abcdef1234567890abcdef12345678"
        directory = write_run(manifest_doc=doc, evidence_doc=evidence())
        stdout = io.StringIO()
        with mock.patch.object(
                ev.sys,
                "argv",
                ["evaluate_run.py", str(directory), "--skip-source-commit-resolution"],
        ), contextlib.redirect_stdout(stdout):
            self.assertEqual(ev.main(), 0)
        self.assertEqual(
            json.loads(stdout.getvalue())["source_commit_resolution"],
            "SKIPPED_EXPLICITLY",
        )

    def test_attacker_selected_historical_shape_does_not_bypass_provenance(self):
        doc = manifest()
        doc["resource_id"] = None
        doc["evidence_trust"] = "unverified"
        for key in ("source_commit", "environment", "recipe_digest", "collector_digest",
                    "hypothesis_claim_level"):
            del doc[key]
        with self.assertRaises(ev.ModelError):
            ev.evaluate(write_run(manifest_doc=doc, evidence_doc=evidence(resource_id=None)))

    def test_fabricated_historical_entry_in_head_does_not_bypass_provenance(self):
        doc = manifest()
        for key in ("source_commit", "environment", "recipe_digest", "collector_digest",
                    "hypothesis_claim_level"):
            del doc[key]
        with mock.patch.object(ev, "RETAINED_DIGESTS") as digest_path:
            digest_path.read_text.return_value = json.dumps({
                "packages": {RUN_ID: {"historical": True, "files": {"x": "0" * 64}}}
            })
            with self.assertRaises(ev.ModelError):
                ev.evaluate(write_run(manifest_doc=doc, evidence_doc=evidence()))


class CausalSupportMutations(unittest.TestCase):
    def test_complete_non_historical_run_requires_every_provenance_field(self):
        required = ("source_commit", "environment", "recipe_digest",
                    "hypothesis_claim_level")
        for key in required:
            with self.subTest(key=key):
                doc = manifest()
                del doc[key]
                with self.assertRaises(ev.ModelError):
                    ev.evaluate(write_run(manifest_doc=doc, evidence_doc=evidence()))

        doc = manifest()
        for key in required:
            del doc[key]
        with self.assertRaises(ev.ModelError):
            ev.evaluate(write_run(manifest_doc=doc, evidence_doc=evidence()))

    def test_symptom_only_manifest_is_inconclusive(self):
        assertions = [
            {"id": "symptom", "role": "symptom", "field": "status", "equals": 503,
             "claim_level": "Observed"}
        ]
        result = ev.evaluate(write_run(manifest_doc=manifest(assertions),
                                       evidence_doc=evidence(observations={"status": 503})))
        self.assertEqual(result["hypothesis_status"], "INCONCLUSIVE")

    def test_observed_causal_claim_still_requires_discriminating_evidence(self):
        doc = manifest([{"id": "symptom", "role": "symptom", "field": "status",
                         "equals": 503, "claim_level": "Observed"}])
        doc["hypothesis_claim_level"] = "Observed"
        result = ev.evaluate(write_run(manifest_doc=doc,
                                       evidence_doc=evidence(observations={"status": 503})))
        self.assertEqual(result["hypothesis_status"], "INCONCLUSIVE")

    def test_causal_claim_without_level_is_a_model_error(self):
        doc = manifest([{"id": "symptom", "role": "symptom", "field": "status",
                         "equals": 503, "claim_level": "Observed"}])
        del doc["hypothesis_claim_level"]
        with self.assertRaises(ev.ModelError):
            ev.evaluate(write_run(manifest_doc=doc,
                                  evidence_doc=evidence(observations={"status": 503})))

    def test_unbound_discriminating_evidence_cannot_support_a_causal_claim(self):
        result = ev.evaluate(write_run(evidence_doc={"status": 503, "cause_seen": True}))
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

    def test_absorbed_in_predicate_is_rejected(self):
        assertions = [
            {"id": "weak", "role": "symptom", "field": "status", "in": [200, 503]},
            {"id": "strong", "role": "discriminating", "field": "status", "in": [503]},
        ]
        with self.assertRaises(ev.ModelError):
            ev.evaluate(write_run(manifest_doc=manifest(assertions), evidence_doc=evidence()))

    def test_unknown_regex_containment_is_rejected_conservatively(self):
        assertions = [
            {"id": "weak", "role": "symptom", "field": "message", "regex": "5.*"},
            {"id": "strong", "role": "discriminating", "field": "message", "regex": "503"},
        ]
        with self.assertRaises(ev.ModelError):
            ev.evaluate(write_run(manifest_doc=manifest(assertions),
                                  evidence_doc=evidence(observations={"message": "503"})))

    def test_zero_over_zero_reported_as_one_is_not_supported(self):
        assertions = [{"id": "ratio", "role": "discriminating", "field": "failure_ratio",
                       "equals": 1.0}]
        observations = {"failure_ratio": {"numerator": 0, "denominator": 0,
                                            "ratio": 1.0, "per_file_limit": 10}}
        result = ev.evaluate(write_run(manifest_doc=manifest(assertions),
                                       evidence_doc=evidence(observations=observations)))
        self.assertNotEqual(result["hypothesis_status"], "SUPPORTED")

    def test_ratio_is_recomputed_from_raw_counts(self):
        assertions = [{"id": "ratio", "role": "discriminating", "field": "failure_ratio",
                       "equals": 1.0}]
        observations = {"failure_ratio": {"numerator": 1, "denominator": 2,
                                            "ratio": 1.0, "per_file_limit": 10}}
        result = ev.evaluate(write_run(manifest_doc=manifest(assertions),
                                       evidence_doc=evidence(observations=observations)))
        self.assertEqual(result["assertion_outcomes"]["ratio"], "CONTRADICTED")

    def test_ratio_without_positive_per_file_limit_is_inconclusive(self):
        assertions = [{"id": "ratio", "role": "discriminating", "field": "failure_ratio",
                       "equals": 1.0}]
        observations = {"failure_ratio": {"numerator": 1, "denominator": 1, "ratio": 1.0}}
        result = ev.evaluate(write_run(manifest_doc=manifest(assertions),
                                       evidence_doc=evidence(observations=observations)))
        self.assertEqual(result["assertion_outcomes"]["ratio"], "INCONCLUSIVE")

    def test_boolean_does_not_satisfy_numeric_equality(self):
        assertions = [{"id": "numeric", "role": "discriminating", "field": "count",
                       "equals": 1, "claim_level": "Observed"}]
        result = ev.evaluate(write_run(manifest_doc=manifest(assertions),
                                       evidence_doc=evidence(observations={"count": True})))
        self.assertNotEqual(result["assertion_outcomes"]["numeric"], "SUPPORTED")

    def test_numeric_one_does_not_satisfy_boolean_predicates(self):
        for predicate in ({"equals": True}, {"in": [True]}, {"not_in": [False]}):
            with self.subTest(predicate=predicate):
                assertion = {"id": "typed", "role": "discriminating", "field": "value",
                             "claim_level": "Observed"} | predicate
                result = ev.evaluate(write_run(manifest_doc=manifest([assertion]),
                                               evidence_doc=evidence(observations={"value": 1})))
                self.assertEqual(result["assertion_outcomes"]["typed"], "CONTRADICTED")

    def test_membership_requires_homogeneous_scalar_choices(self):
        for choices in ([1, True], [[1]], [None], [{"x": 1}]):
            with self.subTest(choices=choices):
                assertion = {"id": "typed", "role": "discriminating", "field": "value",
                             "in": choices, "claim_level": "Observed"}
                result = ev.evaluate(write_run(manifest_doc=manifest([assertion]),
                                               evidence_doc=evidence(observations={"value": 1})))
                self.assertEqual(result["assertion_outcomes"]["typed"], "CONTRADICTED")

    def test_non_finite_numeric_observation_is_rejected(self):
        assertions = [{"id": "numeric", "role": "discriminating", "field": "count",
                       "range": {"minimum": 0}, "claim_level": "Observed"}]
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaises(ev.ModelError):
                    ev.evaluate(write_run(manifest_doc=manifest(assertions),
                                          evidence_doc=evidence(observations={"count": value})))

    def test_not_proven_discriminating_assertion_cannot_contribute_support(self):
        assertions = [
            {"id": "symptom", "role": "symptom", "field": "status", "equals": 503,
             "claim_level": "Observed"},
            {"id": "cause", "role": "discriminating", "field": "cause_seen", "equals": True,
             "claim_level": "Not Proven"},
        ]
        result = ev.evaluate(write_run(manifest_doc=manifest(assertions), evidence_doc=evidence()))
        self.assertNotEqual(result["hypothesis_status"], "SUPPORTED")


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

    def test_rejected_generated_verdict_has_distinct_nonzero_exit(self):
        directory = write_run(evidence_doc=evidence())
        stored = self.recomputed(directory)
        stored["run_id"] = "forged-run"
        (directory / "result.json").write_text(json.dumps(stored))
        with mock.patch.object(ev.sys, "argv", ["evaluate_run.py", str(directory)]), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ev.main(), 4)

    def test_json_nan_token_is_rejected_at_parse_boundary(self):
        directory = write_run(evidence_doc='{"run_id":"%s","resource_id":"%s",'
                               '"captured_at":"%s","observations":{"count":NaN}}'
                               % (RUN_ID, RESOURCE, CAPTURED))
        with self.assertRaises(ev.ModelError):
            ev.evaluate(directory)

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

    def test_evaluation_writes_a_fresh_evaluated_at_without_changing_capture(self):
        directory = write_run(evidence_doc=evidence())
        with mock.patch.object(ev.datetime, "datetime", wraps=ev.datetime.datetime) as clock:
            now = ev.datetime.datetime(2026, 10, 14, 12, 0, tzinfo=ev.datetime.timezone.utc)
            clock.now.return_value = now
            result = ev.evaluate(directory)
        self.assertEqual(result["evaluated_at"], "2026-10-14T12:00:00Z")
        self.assertEqual(result["captured_at"], CAPTURED)
        self.assertEqual(json.loads((directory / "manifest.json").read_text())["captured_at"],
                         CAPTURED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
