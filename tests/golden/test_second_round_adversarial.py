#!/usr/bin/env python3

import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evaluator = load("second_round_evaluator", "scripts/golden/evaluate_run.py")
reproduction = load("second_round_reproduction", "scripts/golden/check_reproduction.py")


def write_run(assertions, observations):
    directory = pathlib.Path(tempfile.mkdtemp())
    manifest = {
        "run_id": "run-one",
        "resource_id": "/subscriptions/<subscription-id>/resourceGroups/rg/providers/Microsoft.Web/sites/app",
        "captured_at": "2026-09-27T00:00:00Z",
        "execution_status": "COMPLETE",
        "source_commit": "3e0442bb19b966766598ffeae1fb47f3f6960837",
        "environment": {"subscription_kind": "test", "region": "local",
                        "runtime": "Python 3.11", "sku": "test-sku"},
        "recipe_digest": "sha256:" + "0123456789abcdef" * 4,
        "collector_digest": "sha256:" + "fedcba9876543210" * 4,
        "hypothesis": "A causal hypothesis.",
        "hypothesis_claim_level": "Inferred",
        "assertions": assertions,
    }
    evidence = {"run_id": manifest["run_id"], "resource_id": manifest["resource_id"],
                "captured_at": manifest["captured_at"], "observations": observations}
    (directory / "manifest.json").write_text(json.dumps(manifest))
    (directory / "evidence.json").write_text(json.dumps(evidence))
    return directory


class EvaluatorSelfAttackTests(unittest.TestCase):
    def test_nan_ratio_cannot_bypass_raw_count_recomputation(self):
        directory = write_run(
            [{"id": "ratio", "role": "discriminating", "field": "ratio", "equals": 1.0}],
            {"ratio": {"numerator": float("nan"), "denominator": 1,
                       "ratio": 1.0, "per_file_limit": 10}})
        with self.assertRaises(evaluator.ModelError):
            evaluator.evaluate(directory)

    def test_discriminating_exists_predicate_is_conservatively_absorbed(self):
        directory = write_run(
            [{"id": "weak", "role": "symptom", "field": "cause", "exists": True},
             {"id": "strong", "role": "discriminating", "field": "cause", "exists": True}],
            {"cause": True})
        with self.assertRaises(evaluator.ModelError):
            evaluator.evaluate(directory)

    def test_capture_window_with_end_before_start_is_rejected(self):
        directory = write_run(
            [{"id": "cause", "role": "discriminating", "field": "cause", "equals": True}],
            {"cause": True})
        manifest = json.loads((directory / "manifest.json").read_text())
        manifest["capture_window"] = {"started_at": "2026-09-27T00:01:00Z",
                                      "ended_at": "2026-09-26T23:59:00Z"}
        (directory / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaises(evaluator.ModelError):
            evaluator.evaluate(directory)


class ReproductionSelfAttackTests(unittest.TestCase):
    def setUp(self):
        self.runs = pathlib.Path(tempfile.mkdtemp())
        self.patch = mock.patch.object(reproduction, "RUNS", self.runs)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def test_uppercase_digest_is_rejected(self):
        self.assertFalse(reproduction.valid_digest("A" * 64))

    def test_resource_names_differing_only_by_case_are_not_independent(self):
        self.assertFalse(reproduction.resources_are_independent(
            {"environment": {"resource_group": "RG-One", "app_name": "App-One"}},
            {"environment": {"resource_group": "rg-one", "app_name": "app-one"}}))

    def test_symlinked_replay_directory_is_rejected(self):
        original = self.runs / "original"
        original.mkdir()
        (self.runs / "replay").symlink_to(original, target_is_directory=True)
        with self.assertRaises(reproduction.ReproductionError):
            reproduction._load_run("replay")


if __name__ == "__main__":
    unittest.main(verbosity=2)
