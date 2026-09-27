#!/usr/bin/env python3
"""The Scenario A collector must read captures, not invent them.

A collector is the easiest place to launder a verdict: it sits between raw
captures and the evaluator, and anything it fabricates arrives looking like
evidence. These tests pin the two properties that keep it honest -- every
emitted value traces to a capture, and a value the run failed to capture
stays absent rather than becoming a zero that reads as a refutation.
"""

import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "collect_a", ROOT / "scripts/golden/collect_scenario_a.py")
collect_a = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(collect_a)

_spec2 = importlib.util.spec_from_file_location(
    "ev_a", ROOT / "scripts/golden/evaluate_run.py")
ev = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(ev)

MANIFEST = json.loads(
    (ROOT / "labs/deployment-succeeded-startup-failed/golden/manifest.template.json").read_text())


def build_run(**overrides):
    """A minimal run directory shaped like run.py's output."""
    directory = pathlib.Path(tempfile.mkdtemp()) / "run"
    directory.mkdir(parents=True)
    (directory / "run.json").write_text(json.dumps({
        "run_id": "20260927T000000Z-abcdef123456",
        "started_at": "2026-09-27T00:00:00+00:00",
        "resource_id": "/subscriptions/x/rg/app"}))
    (directory / "deploy.json").write_text(json.dumps(
        {"exit_code": overrides.get("deploy_exit", 0)}))
    (directory / "console-query-0.json").write_text(json.dumps(
        {"stdout": overrides.get("console", '[{"Msg":"ModuleNotFoundError: wrong_module"}]')}))
    statuses = {"baseline": 200, "fault": 503, "recovery": 200}
    statuses.update(overrides.get("statuses", {}))
    command = "gunicorn --bind=0.0.0.0:8000 --timeout=120 wrong_module:app"
    for name, status in statuses.items():
        if name in overrides.get("skip_phases", ()):
            continue
        phase = directory / name
        phase.mkdir()
        (phase / "phase.json").write_text(json.dumps({
            "run_id": "20260927T000000Z-abcdef123456",
            "status": status,
            "startup": command if name == "fault" else "gunicorn app:app",
            "config_readback": command if name == "fault" else "gunicorn app:app",
            "command_exit": 0}))
    return directory


def evaluate_with(evidence):
    directory = pathlib.Path(tempfile.mkdtemp()) / "g"
    directory.mkdir(parents=True)
    manifest = dict(MANIFEST)
    manifest.update(run_id=evidence["run_id"], captured_at=evidence["captured_at"],
                    execution_status="COMPLETE")
    (directory / "manifest.json").write_text(json.dumps(manifest))
    (directory / "evidence.json").write_text(json.dumps(evidence))
    return ev.evaluate(directory)


class ProvenanceTests(unittest.TestCase):

    def test_every_declared_field_is_emitted(self):
        observations = collect_a.collect(build_run())["observations"]
        declared = {a["field"] for a in MANIFEST["assertions"]}
        self.assertEqual(declared - set(observations), set())

    def test_evidence_carries_the_run_identity(self):
        evidence = collect_a.collect(build_run())
        self.assertEqual(evidence["run_id"], "20260927T000000Z-abcdef123456")
        self.assertEqual(evidence["captured_at"], "2026-09-27T00:00:00+00:00")

    def test_collected_evidence_binds_to_its_manifest(self):
        self.assertEqual(evaluate_with(collect_a.collect(build_run()))["evidence_identity"], "BOUND")

    def test_a_faithful_run_is_supported(self):
        self.assertEqual(evaluate_with(collect_a.collect(build_run()))["hypothesis_status"], "SUPPORTED")


class HonestAbsenceTests(unittest.TestCase):

    def test_a_missing_phase_is_refused_not_defaulted(self):
        with self.assertRaises(collect_a.CollectionError):
            collect_a.collect(build_run(skip_phases=("recovery",)))

    def test_an_uncaptured_status_stays_absent(self):
        """An absent field must not become a value the evaluator can refute."""
        run = build_run()
        phase = json.loads((run / "recovery" / "phase.json").read_text())
        del phase["status"]
        (run / "recovery" / "phase.json").write_text(json.dumps(phase))
        evidence = collect_a.collect(run)
        self.assertNotIn("recovery_status", evidence["observations"])
        self.assertIn("recovery_status", evidence["incomplete_fields"])

    def test_an_absent_field_yields_inconclusive_not_contradicted(self):
        run = build_run()
        phase = json.loads((run / "recovery" / "phase.json").read_text())
        del phase["status"]
        (run / "recovery" / "phase.json").write_text(json.dumps(phase))
        self.assertEqual(
            evaluate_with(collect_a.collect(run))["hypothesis_status"], "INCONCLUSIVE")

    def test_a_malformed_capture_is_refused(self):
        run = build_run()
        (run / "deploy.json").write_text("{not json")
        with self.assertRaises(collect_a.CollectionError):
            collect_a.collect(run)


class DiscriminationTests(unittest.TestCase):
    """The collected evidence must be able to disappoint the hypothesis."""

    def test_a_healthy_fault_phase_contradicts(self):
        result = evaluate_with(collect_a.collect(build_run(statuses={"fault": 200})))
        self.assertEqual(result["hypothesis_status"], "CONTRADICTED")

    def test_a_failed_recovery_contradicts(self):
        result = evaluate_with(collect_a.collect(build_run(statuses={"recovery": 503})))
        self.assertEqual(result["hypothesis_status"], "CONTRADICTED")

    def test_no_import_error_contradicts(self):
        result = evaluate_with(collect_a.collect(build_run(console="[]")))
        self.assertEqual(result["hypothesis_status"], "CONTRADICTED")

    def test_a_failed_deploy_contradicts(self):
        result = evaluate_with(collect_a.collect(build_run(deploy_exit=1)))
        self.assertEqual(result["hypothesis_status"], "CONTRADICTED")


class StatusClassTests(unittest.TestCase):

    def test_classes_restate_the_observed_code(self):
        self.assertEqual(collect_a.status_class(503), "5xx")
        self.assertEqual(collect_a.status_class(404), "4xx")
        self.assertEqual(collect_a.status_class(200), "2xx")

    def test_an_absent_status_has_no_class(self):
        self.assertIsNone(collect_a.status_class(None))
        self.assertIsNone(collect_a.status_class("503"))

    def test_import_errors_are_counted_from_raw_rows(self):
        self.assertEqual(collect_a.import_error_hits({"stdout": "[]"}), 0)
        self.assertEqual(collect_a.import_error_hits({"stdout": "not json"}), 0)
        self.assertEqual(collect_a.import_error_hits(
            {"stdout": '[{"Msg":"ModuleNotFoundError"},{"Msg":"fine"}]'}), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
