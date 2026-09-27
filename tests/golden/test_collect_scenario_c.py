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
               "PROCESS_START_UTC": "2026-09-27T10:00:00+00:00"}
STAGING_BEFORE = {"FEATURE_FLAG": "on", "DB_CONNECTION_STRING": "staging-db",
                  "PROCESS_START_UTC": "2026-09-27T10:00:00+00:00"}
PROD_AFTER = {"FEATURE_FLAG": "on", "DB_CONNECTION_STRING": "prod-db",
              "PROCESS_START_UTC": "2026-09-27T10:05:00+00:00"}
# The staging worker must have started AFTER the swap to be carrying this
# slot's settings. A real run showed the destination answering from the
# pre-swap process, which holds the other slot's environment in memory.
# A swap has a window. The platform recycles workers inside it, so the
# CLI returns after the restart has already happened; the boundary for
# "did this worker restart as part of the swap" is when the swap BEGAN.
SWAP_STARTED = "2026-09-27T10:01:00+00:00"
SWAP_ENDED = "2026-09-27T10:06:00+00:00"
STAGING_AFTER = {"FEATURE_FLAG": "off", "DB_CONNECTION_STRING": "staging-db",
                 "PROCESS_START_UTC": "2026-09-27T10:05:00+00:00"}


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
        "swap.json": {"exit_code": overrides.get("swap_exit", 0),
                      "started_at": overrides.get("swap_started", SWAP_STARTED),
                      "ended_at": overrides.get("swap_ended", SWAP_ENDED)},
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


class ActivationPreconditionTests(unittest.TestCase):
    """Stickiness is unobservable until the destination worker restarts.

    A real run produced CONTRADICTED on this assertion. Investigation
    showed the staging slot was still answering from the pre-swap
    production process, whose environment describes where it came from
    rather than where it now is. Reading stickiness from that snapshot
    measures the capture window, not the platform.
    """

    def test_a_worker_predating_the_swap_cannot_show_stickiness(self):
        stale = dict(STAGING_AFTER, PROCESS_START_UTC="2026-09-27T10:00:30+00:00")
        evidence = collect_c.collect(build_run(staging_after=stale))
        self.assertNotIn("sticky_db_connection_remained", evidence["observations"])
        self.assertIn("sticky_db_connection_remained", evidence["incomplete_fields"])

    def test_that_run_is_inconclusive_not_contradicted(self):
        stale = dict(STAGING_AFTER, PROCESS_START_UTC="2026-09-27T10:00:30+00:00")
        self.assertEqual(
            evaluate_with(collect_c.collect(build_run(staging_after=stale)))["hypothesis_status"],
            "INCONCLUSIVE")

    def test_a_restarted_worker_does_show_stickiness(self):
        """Guards the precondition from rejecting every run."""
        evidence = collect_c.collect(build_run())
        self.assertIs(evidence["observations"]["sticky_db_connection_remained"], True)

    def test_a_rollback_is_matched_on_configuration_not_process_identity(self):
        """A rollback restarts the worker, so timestamps must differ."""
        restarted = dict(PROD_BEFORE, PROCESS_START_UTC="2026-09-27T10:09:00+00:00")
        evidence = collect_c.collect(build_run(rollback=restarted))
        self.assertIs(evidence["observations"]["post_rollback_matches_pre_swap"], True)


class UnreachableSnapshotTests(unittest.TestCase):
    """A slot that answered nothing cannot refute anything.

    fetch_config records an unreachable slot rather than raising, so the
    run keeps its evidence. Comparing against that record silently yields
    False for every setting, which reads as the platform misbehaving when
    the truth is that nothing was observed. A real run hit exactly this:
    the staging slot was still cold-starting when its pre-swap snapshot
    was taken, and two confident False values appeared while the swap had
    in fact behaved correctly.
    """

    UNREACHABLE = {"unreachable": "timed out"}

    def test_an_unreachable_snapshot_is_not_a_configuration(self):
        self.assertFalse(collect_c.is_usable(self.UNREACHABLE))
        self.assertFalse(collect_c.is_usable({}))
        self.assertTrue(collect_c.is_usable(PROD_BEFORE))

    def test_a_missing_pre_swap_snapshot_absents_the_comparisons(self):
        evidence = collect_c.collect(build_run(staging_before=self.UNREACHABLE))
        for field in ("non_sticky_feature_flag_swapped", "sticky_db_connection_remained"):
            with self.subTest(field=field):
                self.assertNotIn(field, evidence["observations"])
                self.assertIn(field, evidence["incomplete_fields"])

    def test_that_run_is_inconclusive_not_contradicted(self):
        """The defect produced CONTRADICTED; the fix must produce INCONCLUSIVE."""
        self.assertEqual(
            evaluate_with(collect_c.collect(
                build_run(staging_before=self.UNREACHABLE)))["hypothesis_status"],
            "INCONCLUSIVE")

    def test_an_unreachable_production_absents_the_config_change(self):
        evidence = collect_c.collect(build_run(prod_after=self.UNREACHABLE))
        self.assertIn("production_config_changed", evidence["incomplete_fields"])


class SwapWindowTests(unittest.TestCase):
    """The restart boundary is the swap's start, not its return."""

    def test_a_worker_recycled_during_the_swap_counts_as_restarted(self):
        during = dict(STAGING_AFTER, PROCESS_START_UTC="2026-09-27T10:03:00+00:00")
        evidence = collect_c.collect(build_run(staging_after=during))
        self.assertIn("sticky_db_connection_remained", evidence["observations"])

    def test_a_worker_predating_the_swap_does_not(self):
        before = dict(STAGING_AFTER, PROCESS_START_UTC="2026-09-27T10:00:30+00:00")
        evidence = collect_c.collect(build_run(staging_after=before))
        self.assertIn("sticky_db_connection_remained", evidence["incomplete_fields"])


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
