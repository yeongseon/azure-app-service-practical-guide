#!/usr/bin/env python3
"""The Scenario B collector must classify through the lab's own rules.

Scenario B's verdict depends on two transports agreeing about the same
response. That agreement is only real if one implementation classifies for
both. The lab previously held the identical predicate in two handlers,
which read as agreement and was not: `urllib` raised on 4xx so its
comparison never ran, while `requests` returned the 4xx and counted it a
success. A collector carrying its own copy of the bands would reintroduce
that confounder from a third direction.

These tests pin three things: the collector imports rather than reimplements
the classifier, a phase that was not captured stays absent rather than
becoming zero, and the emitted evidence can refuse the hypothesis.
"""

import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


collect_b = _load("collect_b", "scripts/golden/collect_scenario_b.py")
ev = _load("ev_b", "scripts/golden/evaluate_run.py")
classification = _load("cls_b", "labs/snat-exhaustion/app/classification.py")

MANIFEST = json.loads(
    (ROOT / "labs/snat-exhaustion/golden/manifest.template.json").read_text())


def build_run(baseline=None, load=None, recovery=None, health=200, omit=()):
    directory = pathlib.Path(tempfile.mkdtemp()) / "run"
    directory.mkdir(parents=True)
    (directory / "run.json").write_text(json.dumps({
        "run_id": "20260927T110000Z-b0b0b0b0b0b0",
        "started_at": "2026-09-27T11:00:00+00:00"}))
    phases = {
        "baseline": [{"status": 200}] * 50 if baseline is None else baseline,
        "load": ([{"transport_error": "EADDRNOTAVAIL"}] * 7 + [{"status": 200}] * 43
                 if load is None else load),
        "recovery": [{"status": 200}] * 50 if recovery is None else recovery,
    }
    for name, probes in phases.items():
        if name in omit:
            continue
        (directory / name).mkdir()
        (directory / name / "probes.json").write_text(json.dumps(probes))
    if "destination-health.json" not in omit and health is not None:
        (directory / "destination-health.json").write_text(json.dumps({"status": health}))
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


class SharedClassifierTests(unittest.TestCase):

    def test_the_collector_does_not_carry_its_own_status_bands(self):
        """A second copy of the predicate is the defect, not the fix."""
        source = (ROOT / "scripts/golden/collect_scenario_b.py").read_text()
        self.assertNotRegex(source, r"\d{3}\s*<=\s*\w+\s*<\s*\d{3}")
        self.assertIn("classification.py", source)

    def test_the_collector_agrees_with_the_workload_on_every_status(self):
        """The property the shared module exists to guarantee."""
        for status in (200, 204, 301, 400, 404, 429, 500, 503):
            with self.subTest(status=status):
                probe = {"status": status}
                self.assertEqual(
                    collect_b.classify_probe(probe, classification),
                    classification.classify_status(status))

    def test_a_4xx_is_not_counted_as_a_transport_failure(self):
        """The original defect: 4xx must not look like connection loss."""
        self.assertNotEqual(
            collect_b.classify_probe({"status": 404}, classification),
            classification.TRANSPORT_FAILURE)

    def test_a_transport_error_is_not_folded_into_http_failure(self):
        self.assertEqual(
            collect_b.classify_probe({"transport_error": "EADDRNOTAVAIL"}, classification),
            classification.TRANSPORT_FAILURE)

    def test_an_unclassifiable_probe_is_refused(self):
        with self.assertRaises(collect_b.CollectionError):
            collect_b.classify_probe({"note": "nothing useful"}, classification)


class ProvenanceTests(unittest.TestCase):

    def test_every_declared_field_is_emitted(self):
        observations = collect_b.collect(build_run())["observations"]
        declared = {a["field"] for a in MANIFEST["assertions"]}
        self.assertEqual(declared - set(observations), set())

    def test_evidence_binds_to_its_manifest(self):
        self.assertEqual(
            evaluate_with(collect_b.collect(build_run()))["evidence_identity"], "BOUND")

    def test_a_faithful_run_is_supported(self):
        self.assertEqual(
            evaluate_with(collect_b.collect(build_run()))["hypothesis_status"], "SUPPORTED")


class HonestAbsenceTests(unittest.TestCase):

    def test_an_uncaptured_phase_leaves_its_fields_absent(self):
        evidence = collect_b.collect(build_run(omit=("load",)))
        self.assertNotIn("load_transport_failure_count", evidence["observations"])
        self.assertIn("load_transport_failure_count", evidence["incomplete_fields"])

    def test_an_uncaptured_phase_is_inconclusive_not_contradicted(self):
        self.assertEqual(
            evaluate_with(collect_b.collect(build_run(omit=("load",))))["hypothesis_status"],
            "INCONCLUSIVE")

    def test_a_missing_destination_probe_is_inconclusive(self):
        """Without it, exhaustion cannot be separated from a dead destination."""
        evidence = collect_b.collect(build_run(omit=("destination-health.json",)))
        self.assertIn("destination_health_status", evidence["incomplete_fields"])
        self.assertEqual(evaluate_with(evidence)["hypothesis_status"], "INCONCLUSIVE")

    def test_zero_transport_failures_is_reported_not_omitted(self):
        """A real zero must stay a zero; only an uncaptured phase is absent."""
        evidence = collect_b.collect(build_run(load=[{"status": 200}] * 50))
        self.assertEqual(evidence["observations"]["load_transport_failure_count"], 0)
        self.assertNotIn("load_transport_failure_count", evidence["incomplete_fields"])

    def test_a_malformed_capture_is_refused(self):
        run = build_run()
        (run / "load" / "probes.json").write_text("{not json")
        with self.assertRaises(collect_b.CollectionError):
            collect_b.collect(run)


class DiscriminationTests(unittest.TestCase):
    """The collected evidence must be able to disappoint the hypothesis."""

    def test_an_unhealthy_destination_contradicts(self):
        """The discriminating case: the destination was down all along."""
        self.assertEqual(
            evaluate_with(collect_b.collect(build_run(health=503)))["hypothesis_status"],
            "CONTRADICTED")

    def test_no_transport_failures_under_load_contradicts(self):
        self.assertEqual(
            evaluate_with(collect_b.collect(
                build_run(load=[{"status": 200}] * 50)))["hypothesis_status"],
            "CONTRADICTED")

    def test_http_errors_instead_of_transport_failures_contradict(self):
        load = [{"status": 500}] * 7 + [{"status": 200}] * 43
        self.assertEqual(
            evaluate_with(collect_b.collect(build_run(load=load)))["hypothesis_status"],
            "CONTRADICTED")

    def test_a_broken_baseline_contradicts(self):
        self.assertEqual(
            evaluate_with(collect_b.collect(
                build_run(baseline=[{"status": 500}] * 50)))["hypothesis_status"],
            "CONTRADICTED")

    def test_no_recovery_contradicts(self):
        self.assertEqual(
            evaluate_with(collect_b.collect(
                build_run(recovery=[{"transport_error": "x"}] * 50)))["hypothesis_status"],
            "CONTRADICTED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
