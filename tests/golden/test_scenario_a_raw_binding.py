#!/usr/bin/env python3
import copy
import importlib.util
import json
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUN_ID = "20261016T075147Z-6d019de6e2f2"
SOURCE = ROOT / "evidence/runs" / RUN_ID
SPEC = importlib.util.spec_from_file_location(
    "raw_binding_evaluator", ROOT / "scripts/golden/evaluate_run.py")
evaluator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluator)


class ScenarioARawBindingTests(unittest.TestCase):
    def setUp(self):
        self.directory = pathlib.Path(tempfile.mkdtemp()) / RUN_ID
        shutil.copytree(SOURCE, self.directory)
        (self.directory / "result.json").unlink()
        self.evidence_path = self.directory / "evidence.json"
        self.manifest_path = self.directory / "manifest.json"
        self.document = json.loads(self.evidence_path.read_text())

    def evaluate(self):
        self.evidence_path.write_text(json.dumps(self.document))
        return evaluator.evaluate(self.directory)

    def test_valid_retained_package_is_supported(self):
        self.assertEqual(self.evaluate()["hypothesis_status"], "SUPPORTED")

    def test_unrelated_import_error_row_is_rejected(self):
        self.document["observations"]["fault_console_rows"] = [{
            "timestamp": "2026-10-16T07:58:00.393401Z",
            "signature": "ImportError: unrelated_dependency",
        }]
        with self.assertRaises(evaluator.ModelError):
            self.evaluate()

    def test_wrong_module_name_rows_are_rejected(self):
        self.document["observations"]["fault_console_rows"] = [{
            "timestamp": "2026-10-16T07:58:00.393401Z",
            "signature": "ModuleNotFoundError: No module named 'other_module'",
        }]
        with self.assertRaises(evaluator.ModelError):
            self.evaluate()

    def test_fault_probe_500_cannot_hide_behind_503_summary(self):
        probes = self.document["observations"]["fault_probes"]
        probes[-1]["status"] = 500
        with self.assertRaises(evaluator.ModelError):
            self.evaluate()

    def test_recovery_before_baseline_is_rejected(self):
        windows = self.document["observations"]["phase_windows"]
        windows["recovery"] = copy.deepcopy(windows["baseline"])
        with self.assertRaises(evaluator.ModelError):
            self.evaluate()

    def test_fault_row_outside_fault_window_is_rejected(self):
        rows = self.document["observations"]["fault_console_rows"]
        rows[0]["timestamp"] = "2026-10-16T08:01:30Z"
        with self.assertRaises(evaluator.ModelError):
            self.evaluate()

    def test_503_probe_outside_fault_window_is_rejected(self):
        probes = self.document["observations"]["fault_probes"]
        probes[-1]["captured_at"] = "2026-10-16T08:01:30Z"
        with self.assertRaises(evaluator.ModelError):
            self.evaluate()

    def test_scalar_disagreement_with_raw_rows_is_rejected(self):
        self.document["observations"]["fault_import_error_signature"] = "ImportError: other"
        with self.assertRaises(evaluator.ModelError):
            self.evaluate()

    def test_valid_but_unrelated_provenance_digests_are_rejected(self):
        provenance_path = self.directory / "provenance.json"
        provenance = json.loads(provenance_path.read_text())
        provenance["derivation"]["collector_digest"] = "sha256:" + "2" * 64
        provenance_path.write_text(json.dumps(provenance))
        with self.assertRaises(evaluator.ModelError):
            self.evaluate()

    def test_later_source_commit_with_recomputed_digests_is_rejected(self):
        manifest = json.loads(self.manifest_path.read_text())
        manifest["source_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        manifest["runner_source_commit"] = manifest["source_commit"]
        fingerprints = {
            pathlib.PurePosixPath(path).name: evaluator.hashlib.sha256(
                evaluator._git_bytes(manifest["source_commit"], path)).hexdigest()
            for path in manifest["recipe_paths"]
        }
        canonical = json.dumps(fingerprints, sort_keys=True, separators=(",", ":")).encode()
        manifest["recipe_digest"] = "sha256:" + evaluator.hashlib.sha256(canonical).hexdigest()
        self.manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(evaluator.ModelError):
            self.evaluate()

    def test_old_collector_digest_with_new_shape_is_rejected(self):
        provenance_path = self.directory / "provenance.json"
        provenance = json.loads(provenance_path.read_text())
        provenance["derivation"]["collector_commit"] = manifest_commit = (
            "af75d0024472edce67401042fdaa97d00dfbe6ac")
        collector = evaluator.hashlib.sha256(evaluator._git_bytes(
            manifest_commit, provenance["derivation"]["collector_path"])).hexdigest()
        provenance["derivation"]["collector_digest"] = f"sha256:{collector}"
        provenance_path.write_text(json.dumps(provenance))
        with self.assertRaises(evaluator.ModelError):
            self.evaluate()

    def test_wrong_derivation_collector_commit_is_rejected(self):
        provenance_path = self.directory / "provenance.json"
        provenance = json.loads(provenance_path.read_text())
        provenance["derivation"]["collector_commit"] = (
            "ceb730d8b22455c811742d405a99e42f3f996aad")
        provenance_path.write_text(json.dumps(provenance))
        with self.assertRaises(evaluator.ModelError):
            self.evaluate()

    def test_derivation_before_capture_is_rejected(self):
        provenance_path = self.directory / "provenance.json"
        provenance = json.loads(provenance_path.read_text())
        provenance["derivation"]["derived_at"] = "2026-10-16T07:00:00Z"
        provenance_path.write_text(json.dumps(provenance))
        with self.assertRaises(evaluator.ModelError):
            self.evaluate()

    def test_dropping_required_recipe_path_is_rejected(self):
        manifest = json.loads(self.manifest_path.read_text())
        manifest["recipe_paths"].remove(
            "labs/deployment-succeeded-startup-failed/app/requirements.txt")
        self.manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(evaluator.ModelError):
            self.evaluate()

    def test_truncating_probes_to_favorable_rows_is_rejected(self):
        observations = self.document["observations"]
        observations["baseline_probes"] = [observations["baseline_probes"][0]]
        observations["fault_probes"] = [observations["fault_probes"][-1]]
        observations["recovery_probes"] = [observations["recovery_probes"][-1]]
        with self.assertRaises(evaluator.ModelError):
            self.evaluate()

    def test_duplicate_normalized_probe_timestamps_are_rejected(self):
        probes = self.document["observations"]["fault_probes"]
        duplicate = copy.deepcopy(probes[-1])
        duplicate["captured_at"] = duplicate["captured_at"].replace("+00:00", "Z")
        probes.append(duplicate)
        with self.assertRaises(evaluator.ModelError):
            self.evaluate()

    def test_new_directory_cannot_reuse_frozen_historical_run_id(self):
        frozen = "20260927T104304Z-aba0d3a9daa7"
        manifest = json.loads(self.manifest_path.read_text())
        manifest["run_id"] = frozen
        self.manifest_path.write_text(json.dumps(manifest))
        self.document["run_id"] = frozen
        with self.assertRaises(evaluator.ModelError):
            self.evaluate()


if __name__ == "__main__":
    unittest.main(verbosity=2)
