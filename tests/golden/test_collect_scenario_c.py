#!/usr/bin/env python3
"""The Scenario C collector must report the swap, not judge it.

`trigger.sh` computed these same facts and printed them as prose, which
no assertion could be checked against. Moving the computation into a
collector only helps if the collector stays a reporter: these tests pin
that every emitted value traces to a capture, that an unperformed step
cannot become supporting evidence, and that the emitted evidence is
capable of refusing the hypothesis.
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


collect_c = _load("collect_c", "scripts/golden/collect_scenario_c.py")
ev = _load("ev_c", "scripts/golden/evaluate_run.py")

MANIFEST = json.loads(
    (ROOT / "labs/slot-swap-config-drift/golden/manifest.template.json").read_text())

PROD_BEFORE = {"FEATURE_FLAG": "off", "DB_CONNECTION_STRING": "prod-db",
               "PROCESS_START_UTC": "2026-09-27T10:00:00Z"}
STAGING_BEFORE = {"FEATURE_FLAG": "on", "DB_CONNECTION_STRING": "staging-db",
                  "PROCESS_START_UTC": "2026-09-27T10:00:00Z"}
PROD_AFTER = {"FEATURE_FLAG": "on", "DB_CONNECTION_STRING": "prod-db",
              "PROCESS_START_UTC": "2026-09-27T10:05:00Z"}
STAGING_AFTER = {"FEATURE_FLAG": "off", "DB_CONNECTION_STRING": "staging-db",
                 "PROCESS_START_UTC": "2026-09-27T10:05:00Z"}


def build_run(**overrides):
    """A run directory shaped like the trigger's captures."""
    directory = pathlib.Path(tempfile.mkdtemp()) / "run"
    directory.mkdir(parents=True)
    files = {
        "run.json": {"run_id": "20260927T100000Z-c0ffee123456",
                     "started_at": "2026-09-27T10:00:00+00:00"},
        "prod-before.json": overrides.get("prod_before", PROD_BEFORE),
        "staging-before.json": overrides.get("staging_before", STAGING_BEFORE),
        "prod-after.json": overrides.get("prod_after", PROD_AFTER),
        "staging-after.json": overrides.get("staging_after", STAGING_AFTER),
        "swap.json": {"exit_code": overrides.get("swap_exit", 0)},
        "console-query-0.json": {"stdout": overrides.get("console", "[]")},
    }
    if "rollback" in overrides:
        if overrides["rollback"] is not None:
            files["prod-after-rollback.json"] = overrides["rollback"]
    else:
        files["prod-after-rollback.json"] = PROD_BEFORE
    for name in overrides.get("omit", ()):
        files.pop(name, None)
    for name, body in files.items():
        (directory / name).write_text(json.dumps(body))
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
        observations = collect_c.collect(build_run())["observations"]
        declared = {a["field"] for a in MANIFEST["assertions"]}
        self.assertEqual(declared - set(observations), set())

    def test_evidence_binds_to_its_manifest(self):
        self.assertEqual(
            evaluate_with(collect_c.collect(build_run()))["evidence_identity"], "BOUND")

    def test_a_faithful_swap_is_supported(self):
        self.assertEqual(
            evaluate_with(collect_c.collect(build_run()))["hypothesis_status"], "SUPPORTED")


class UnperformedStepTests(unittest.TestCase):
    """A step that never ran cannot become supporting evidence."""

    def test_no_rollback_leaves_the_field_absent(self):
        evidence = collect_c.collect(build_run(rollback=None))
        self.assertNotIn("post_rollback_matches_pre_swap", evidence["observations"])
        self.assertIn("post_rollback_matches_pre_swap", evidence["incomplete_fields"])

    def test_no_rollback_is_inconclusive_not_contradicted(self):
        self.assertEqual(
            evaluate_with(collect_c.collect(build_run(rollback=None)))["hypothesis_status"],
            "INCONCLUSIVE")

    def test_a_rollback_that_does_not_restore_contradicts(self):
        drifted = dict(PROD_BEFORE, FEATURE_FLAG="on")
        self.assertEqual(
            evaluate_with(collect_c.collect(build_run(rollback=drifted)))["hypothesis_status"],
            "CONTRADICTED")

    def test_an_absent_restart_timestamp_is_not_a_false_restart(self):
        before = {k: v for k, v in PROD_BEFORE.items() if k != "PROCESS_START_UTC"}
        evidence = collect_c.collect(build_run(prod_before=before))
        self.assertNotIn("production_restart_observed", evidence["observations"])
        self.assertIn("production_restart_observed", evidence["incomplete_fields"])

    def test_a_missing_required_capture_is_refused(self):
        with self.assertRaises(collect_c.CollectionError):
            collect_c.collect(build_run(omit=("prod-after.json",)))

    def test_a_malformed_capture_is_refused(self):
        run = build_run()
        (run / "swap.json").write_text("{not json")
        with self.assertRaises(collect_c.CollectionError):
            collect_c.collect(run)


class DiscriminationTests(unittest.TestCase):
    """The collected evidence must be able to disappoint the hypothesis."""

    def test_a_sticky_setting_that_moved_contradicts(self):
        moved = dict(PROD_AFTER, DB_CONNECTION_STRING="staging-db")
        self.assertEqual(
            evaluate_with(collect_c.collect(build_run(prod_after=moved)))["hypothesis_status"],
            "CONTRADICTED")

    def test_a_non_sticky_setting_that_stayed_contradicts(self):
        stayed = dict(PROD_AFTER, FEATURE_FLAG="off")
        self.assertEqual(
            evaluate_with(collect_c.collect(build_run(prod_after=stayed)))["hypothesis_status"],
            "CONTRADICTED")

    def test_a_failed_swap_contradicts(self):
        self.assertEqual(
            evaluate_with(collect_c.collect(build_run(swap_exit=1)))["hypothesis_status"],
            "CONTRADICTED")

    def test_deployment_errors_contradict(self):
        self.assertEqual(
            evaluate_with(collect_c.collect(
                build_run(console='[{"Level":"Error"}]')))["hypothesis_status"],
            "CONTRADICTED")

    def test_no_restart_contradicts(self):
        same = dict(PROD_AFTER, PROCESS_START_UTC=PROD_BEFORE["PROCESS_START_UTC"])
        self.assertEqual(
            evaluate_with(collect_c.collect(build_run(prod_after=same)))["hypothesis_status"],
            "CONTRADICTED")


class SwapSemanticsTests(unittest.TestCase):

    def test_a_one_sided_move_is_not_a_swap(self):
        """Both halves must move, or something other than the swap changed it."""
        self.assertFalse(collect_c.swapped_with_code(
            {"F": "a"}, {"F": "b"}, {"F": "b"}, {"F": "b"}, "F"))

    def test_a_one_sided_stay_is_not_stickiness(self):
        self.assertFalse(collect_c.remained_with_slot(
            {"D": "p"}, {"D": "s"}, {"D": "p"}, {"D": "p"}, "D"))

    def test_absent_console_yields_no_error_count(self):
        self.assertIsNone(collect_c.error_row_count(None))
        self.assertEqual(collect_c.error_row_count({"stdout": "[]"}), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
