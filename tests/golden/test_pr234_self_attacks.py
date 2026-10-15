#!/usr/bin/env python3
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evaluator = load("self_attack_evaluator", "scripts/golden/evaluate_run.py")
reproduction = load("self_attack_reproduction", "scripts/golden/check_reproduction.py")


class EvaluatorSelfAttacks(unittest.TestCase):
    def _run(self, assertion, observed):
        directory = pathlib.Path(tempfile.mkdtemp())
        manifest = {
            "run_id": "self-attack",
            "resource_id": "/subscriptions/<subscription-id>/resourceGroups/rg/providers/Microsoft.Web/sites/app",
            "captured_at": "2026-09-27T00:00:00Z",
            "execution_status": "COMPLETE",
            "source_commit": "3e0442bb19b966766598ffeae1fb47f3f6960837",
            "environment": {"subscription_kind": "test", "region": "local",
                            "runtime": "Python 3.11", "sku": "test-sku"},
            "recipe_digest": "sha256:" + "0123456789abcdef" * 4,
            "collector_digest": "sha256:" + "fedcba9876543210" * 4,
            "hypothesis": "A declared causal claim.",
            "hypothesis_claim_level": "Inferred",
            "assertions": [assertion],
        }
        evidence = {
            "run_id": "self-attack",
            "resource_id": manifest["resource_id"],
            "captured_at": manifest["captured_at"],
            "observations": {assertion["field"]: observed},
        }
        (directory / "manifest.json").write_text(json.dumps(manifest))
        (directory / "evidence.json").write_text(json.dumps(evidence))
        return evaluator.evaluate(directory)

    def test_numeric_membership_rejects_boolean_alias(self):
        result = self._run(
            {"id": "a", "role": "discriminating", "field": "count", "in": [1, 2]},
            True,
        )
        self.assertEqual(result["assertion_outcomes"]["a"], "CONTRADICTED")

    def test_numeric_not_in_rejects_boolean_alias(self):
        result = self._run(
            {"id": "a", "role": "discriminating", "field": "count", "not_in": [2, 3]},
            True,
        )
        self.assertEqual(result["assertion_outcomes"]["a"], "CONTRADICTED")


class AttestationSelfAttacks(unittest.TestCase):
    def _record(self, **attestation):
        return {
            "replay_run_id": "replay",
            "original_run_id": "original",
            "reviewer": "reviewer",
            "reviewer_kind": "human",
            "original_operator": "operator",
            "original_operator_kind": "human",
            "original_hypothesis_status": "SUPPORTED",
            "replay_hypothesis_status": "SUPPORTED",
            "attestation": attestation,
        }

    def test_case_variant_identity_collision_is_not_independent(self):
        record = self._record(
            url="https://github.com/o/r/pull/1#pullrequestreview-1",
            reviewer_login="Reviewer",
            original_operator_login="reviewer",
            pr_author_login="author",
        )
        self.assertEqual(reproduction.classify_reproduction(record), "NOT_INDEPENDENT")

    def test_false_verifier_hook_cannot_confirm_attestation(self):
        record = self._record(
            url="https://github.com/o/r/pull/1#pullrequestreview-1",
            reviewer_login="reviewer",
            original_operator_login="operator",
            pr_author_login="author",
        )
        self.assertEqual(
            reproduction.classify_reproduction(record, attestation_verifier=lambda value: False),
            "ATTESTATION_UNVERIFIED",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
