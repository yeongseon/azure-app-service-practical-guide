#!/usr/bin/env python3
"""The Scenario B runner must record raw outcomes the collector can read.

The runner and the collector were written separately, so the shape one
writes and the shape the other expects is a join nothing checked. A
mismatch there does not fail loudly: the collector would report absent
fields and the evaluation would return INCONCLUSIVE forever, looking
like a shortage of evidence rather than a wiring fault.

These tests pin the join, and the one distinction the whole experiment
rests on: a server that answered is an HTTP outcome, and a connection
that never completed is a transport outcome. Folding the second into the
first discards the only signal that discriminates the hypothesis.
"""

import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
import urllib.error

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load("run_b", "scripts/golden/run_scenario_b.py")
collector = _load("collect_b2", "scripts/golden/collect_scenario_b.py")
classification = _load("cls_b2", "labs/snat-exhaustion/app/classification.py")


def runner_shaped_run(load_transport=7, destination_status=200):
    """A directory in exactly the layout `execute` writes."""
    directory = pathlib.Path(tempfile.mkdtemp()) / "run"
    directory.mkdir(parents=True)
    (directory / "run.json").write_text(json.dumps({
        "run_id": "20260927T150000Z-abcdef012345",
        "started_at": "2026-09-27T15:00:00+00:00"}))
    phases = {
        "baseline": [{"at": "t", "status": 200}] * runner.PROBES_PER_PHASE,
        "load": ([{"at": "t", "transport_error": "EADDRNOTAVAIL"}] * load_transport
                 + [{"at": "t", "status": 200}] * (runner.PROBES_PER_PHASE - load_transport)),
        "recovery": [{"at": "t", "status": 200}] * runner.PROBES_PER_PHASE,
    }
    for name, probes in phases.items():
        (directory / name).mkdir()
        (directory / name / "probes.json").write_text(json.dumps(probes))
    (directory / "destination-health.json").write_text(
        json.dumps({"at": "t", "status": destination_status}))
    return directory


class JoinTests(unittest.TestCase):
    """What the runner writes, the collector must be able to read."""

    def test_the_collector_reads_every_field_from_the_runner_layout(self):
        observations = collector.collect(runner_shaped_run())["observations"]
        declared = {
            a["field"] for a in json.loads(
                (ROOT / "labs/snat-exhaustion/golden/manifest.template.json").read_text()
            )["assertions"]}
        self.assertEqual(declared - set(observations), set())

    def test_nothing_is_reported_absent_from_a_complete_run(self):
        self.assertEqual(collector.collect(runner_shaped_run())["incomplete_fields"], [])

    def test_the_counts_match_what_was_recorded(self):
        observations = collector.collect(runner_shaped_run(load_transport=9))["observations"]
        self.assertEqual(observations["load_transport_failure_count"], 9)
        self.assertEqual(observations["baseline_success_count"], runner.PROBES_PER_PHASE)


class ContractAgreementTests(unittest.TestCase):
    """The contract's expected counts must follow the runner's constant.

    The manifest previously repeated the number 50 in two assertions while
    the runner defined its own PROBES_PER_PHASE. Changing one would have
    left the other contradicting every run, and the contradiction would
    have read as the platform failing rather than as a stale expectation.
    """

    MANIFEST = json.loads(
        (ROOT / "labs/snat-exhaustion/golden/manifest.template.json").read_text())

    def _expected(self, field):
        return next(a for a in self.MANIFEST["assertions"] if a["field"] == field)

    def test_full_phase_counts_equal_the_probe_constant(self):
        for field in ("baseline_success_count", "recovery_success_count"):
            with self.subTest(field=field):
                self.assertEqual(
                    self._expected(field)["equals"], runner.PROBES_PER_PHASE,
                    msg="the contract expects a count the runner cannot produce")

    def test_the_transport_failure_range_fits_within_a_phase(self):
        allowed = self._expected("load_transport_failure_count")["in"]
        self.assertLessEqual(
            max(allowed), runner.PROBES_PER_PHASE,
            msg="the contract allows more failures than there are probes")
        self.assertGreaterEqual(
            min(allowed), 1,
            msg="zero transport failures must not satisfy the symptom assertion")

    def test_a_faithful_run_of_that_size_is_supported(self):
        """The constant and the contract agree in practice, not just in numbers."""
        evidence = collector.collect(runner_shaped_run())
        directory = pathlib.Path(tempfile.mkdtemp()) / "g"
        directory.mkdir(parents=True)
        manifest = dict(self.MANIFEST)
        manifest.update(run_id=evidence["run_id"], captured_at=evidence["captured_at"],
                        execution_status="COMPLETE")
        (directory / "manifest.json").write_text(json.dumps(manifest))
        (directory / "evidence.json").write_text(json.dumps(evidence))
        evaluator = _load("ev_b2", "scripts/golden/evaluate_run.py")
        self.assertEqual(evaluator.evaluate(directory)["hypothesis_status"], "SUPPORTED")

    def test_the_probe_count_is_small_enough_to_finish(self):
        """A run nobody can supervise to the end is a run that never happens.

        One probe fans out into roughly forty outbound calls, measured on a
        live deployment. This keeps a three-phase run inside a window that
        can be watched and cleaned up after.
        """
        self.assertLessEqual(runner.PROBES_PER_PHASE * 40 * 3, 2000)
        self.assertGreaterEqual(runner.PROBES_PER_PHASE, 10)


class ProbeRecordTests(unittest.TestCase):
    """A probe records what happened, not what it means."""

    def test_a_probe_record_is_classifiable(self):
        for record in ({"status": 200}, {"status": 503}, {"transport_error": "x"}):
            with self.subTest(record=record):
                self.assertIn(
                    collector.classify_probe(record, classification),
                    classification.OUTCOMES)

    def test_an_http_error_is_recorded_as_a_status_not_a_transport_error(self):
        """urllib raises on 4xx and 5xx; the server still answered.

        This is the defect the shared classifier was written to remove,
        arriving from the capture side instead. A 503 recorded as a
        transport error would be counted as the SNAT signal.
        """
        source = (ROOT / "scripts/golden/run_scenario_b.py").read_text()
        self.assertIn("urllib.error.HTTPError", source)
        index_http = source.index("except urllib.error.HTTPError")
        index_url = source.index("except (urllib.error.URLError")
        self.assertLess(
            index_http, index_url,
            msg="HTTPError must be caught before URLError, or answered "
                "requests are recorded as connection failures")

    #: A status band, however it is spelled. The first version of this
    #: pattern used \w+ for the operand, which does not match an attribute
    #: like `response.status`, so a planted band went undetected. The
    #: guard looked correct and discriminated nothing.
    STATUS_BAND = r"\d{3}\s*<=?\s*[\w.\[\]'\"]+\s*<=?\s*\d{3}"

    def test_the_runner_classifies_nothing_itself(self):
        """Classification belongs to one module, and this is not it."""
        source = (ROOT / "scripts/golden/run_scenario_b.py").read_text()
        self.assertNotIn("classify_status", source)
        self.assertNotRegex(source, self.STATUS_BAND)
        for word in ("success", "failure", "transport_failure"):
            self.assertNotIn(
                f'"{word}"', source,
                msg="the runner names an outcome; only the shared classifier may")

    def test_the_band_pattern_matches_the_shapes_it_must(self):
        """Guards the guard: the pattern missed attribute access once."""
        import re
        for spelling in ("200 <= status < 500",
                         "200 <= response.status < 500",
                         "200 <= record['status'] < 500",
                         "200<=s<500"):
            with self.subTest(spelling=spelling):
                self.assertRegex(spelling, self.STATUS_BAND)


class PressureTests(unittest.TestCase):

    def test_pressure_is_concurrent_not_merely_repeated(self):
        """Exhaustion is a function of sockets held at once."""
        self.assertGreaterEqual(runner.LOAD_WORKERS, 2)
        source = (ROOT / "scripts/golden/run_scenario_b.py").read_text()
        self.assertIn("ThreadPoolExecutor", source)

    def test_recovery_waits_for_ports_to_return(self):
        """Ports in TIME_WAIT are not immediately reusable."""
        self.assertGreaterEqual(runner.RECOVERY_SETTLE_SECONDS, 30)

    def test_applying_pressure_returns_a_record_not_a_verdict(self):
        source = (ROOT / "scripts/golden/run_scenario_b.py").read_text()
        body = source[source.index("def apply_pressure"):source.index("def execute")]
        for word in ("SUPPORTED", "CONTRADICTED", "exhausted", "reproduced"):
            self.assertNotIn(word, body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
