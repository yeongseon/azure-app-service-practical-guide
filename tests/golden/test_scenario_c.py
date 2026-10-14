"""Golden Scenario C conformance tests (#181).

Scenario C asks whether a configuration/state change can be separated
from a deployment failure with evidence. A slot swap relocates settings
by stickiness: a non-sticky app setting travels with the code, a slot
setting stays with the slot. Both produce a changed production
configuration, and a broken deployment produces overlapping user-visible
symptoms, so the discriminating evidence is *which* settings moved.

No Azure call happens here. The template's execution status must remain
NOT_RUN and the evaluator must refuse to report a hypothesis verdict.
"""

import sys

sys.dont_write_bytecode = True

import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
LAB = ROOT / "labs/slot-swap-config-drift/golden"
_spec = importlib.util.spec_from_file_location("ev", ROOT / "scripts/golden/evaluate_run.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)

TEMPLATE = json.loads((LAB / "manifest.template.json").read_text())

COMPLETE_EVIDENCE = {
    "swap_exit_code": 0,
    "production_restart_observed": True,
    "non_sticky_feature_flag_swapped": True,
    "sticky_db_connection_remained": True,
    "production_config_changed": True,
    "deployment_error_count": 0,
    "post_rollback_matches_pre_swap": True,
}


def run_with(evidence, execution="COMPLETE"):
    d = pathlib.Path(tempfile.mkdtemp()) / "run"
    d.mkdir(parents=True)
    manifest = dict(TEMPLATE)
    manifest.update(run_id="20260927T020304Z-c3d4e5",
                    resource_id="/subscriptions/x/rg/app",
                    captured_at="2026-09-27T02:03:04Z",
                    execution_status=execution)
    (d / "manifest.json").write_text(json.dumps(manifest))
    (d / "evidence.json").write_text(json.dumps(evidence))
    return d


class ContractShapeTests(unittest.TestCase):
    def test_every_required_evidence_role_is_declared(self):
        roles = {a["role"] for a in TEMPLATE["assertions"]}
        self.assertEqual(roles, {"control", "symptom", "discriminating", "recovery"})

    def test_both_stickiness_outcomes_are_discriminating_not_symptom(self):
        """Which settings moved is what separates drift from a failed deploy."""
        by_id = {a["id"]: a for a in TEMPLATE["assertions"]}
        for key in ("non-sticky-travelled-with-code", "sticky-remained-with-slot"):
            self.assertEqual(by_id[key]["role"], "discriminating")

    def test_a_changed_production_config_is_only_a_symptom(self):
        by_id = {a["id"]: a for a in TEMPLATE["assertions"]}
        self.assertEqual(by_id["symptom-production-config-changed"]["role"], "symptom")

    def test_all_roles_and_ids_are_valid_and_unique(self):
        ids = [a["id"] for a in TEMPLATE["assertions"]]
        self.assertEqual(len(ids), len(set(ids)))
        for a in TEMPLATE["assertions"]:
            self.assertIn(a["role"], ev.EVIDENCE_ROLES)

    def test_template_ships_as_not_run(self):
        self.assertEqual(TEMPLATE["execution_status"], "NOT_RUN")
        self.assertIsNone(TEMPLATE["captured_at"])


class NotRunHonestyTests(unittest.TestCase):
    def test_template_alone_yields_no_hypothesis_verdict(self):
        result = ev.evaluate(run_with(COMPLETE_EVIDENCE, execution="NOT_RUN"))
        self.assertEqual(result["hypothesis_status"], "NOT_TESTED")

    def test_complete_run_with_full_evidence_is_supported(self):
        self.assertEqual(
            ev.evaluate(run_with(COMPLETE_EVIDENCE))["hypothesis_status"], "SUPPORTED")


class ActivationPreconditionTests(unittest.TestCase):
    """A swap exit code is not proof the worker restarted onto the new config."""

    def test_missing_restart_observation_cannot_reach_a_verdict(self):
        evidence = dict(COMPLETE_EVIDENCE)
        del evidence["production_restart_observed"]
        self.assertEqual(
            ev.evaluate(run_with(evidence))["hypothesis_status"], "INCONCLUSIVE")

    def test_swap_that_never_restarted_production_is_contradicted(self):
        evidence = dict(COMPLETE_EVIDENCE, production_restart_observed=False)
        self.assertEqual(
            ev.evaluate(run_with(evidence))["hypothesis_status"], "CONTRADICTED")


class CompetingHypothesisTests(unittest.TestCase):
    def test_a_failing_deployment_contradicts_the_drift_hypothesis(self):
        """Drift and a broken deploy share user-visible symptoms."""
        evidence = dict(COMPLETE_EVIDENCE, deployment_error_count=7)
        self.assertEqual(
            ev.evaluate(run_with(evidence))["hypothesis_status"], "CONTRADICTED")

    def test_sticky_setting_that_moved_contradicts_the_mechanism(self):
        evidence = dict(COMPLETE_EVIDENCE, sticky_db_connection_remained=False)
        self.assertEqual(
            ev.evaluate(run_with(evidence))["hypothesis_status"], "CONTRADICTED")

    def test_absent_stickiness_evidence_is_inconclusive_not_contradicted(self):
        evidence = dict(COMPLETE_EVIDENCE)
        del evidence["non_sticky_feature_flag_swapped"]
        self.assertEqual(
            ev.evaluate(run_with(evidence))["hypothesis_status"], "INCONCLUSIVE")

    def test_missing_recovery_blocks_supported(self):
        evidence = dict(COMPLETE_EVIDENCE)
        del evidence["post_rollback_matches_pre_swap"]
        self.assertEqual(
            ev.evaluate(run_with(evidence))["hypothesis_status"], "INCONCLUSIVE")


class HistoricalEvidenceTests(unittest.TestCase):
    def test_retained_artifacts_are_classified_not_deleted(self):
        data = json.loads((LAB / "evidence-classification.json").read_text())
        self.assertTrue(data["artifacts"])
        for item in data["artifacts"]:
            self.assertIn(item["retention_status"], ev.EVIDENCE_TRUST)
            self.assertTrue(item["reason"].strip())
            self.assertTrue((ROOT / item["path"]).exists(), item["path"])

    def test_pre_golden_captures_are_not_trusted_current(self):
        """Retained captures predate this contract and cannot be current.

        The rule is about captures, not about every entry. It was written
        when the only entries were retained artifacts, so forbidding
        trusted-current outright was equivalent. A collector added later
        is not a capture: it is executable, tested, and current by
        definition, so the check now names what it actually governs.
        """
        data = json.loads((LAB / "evidence-classification.json").read_text())
        captures = [i for i in data["artifacts"]
                    if not i["path"].endswith((".py", ".sh"))]
        self.assertTrue(captures, "no retained captures left to check")
        for item in captures:
            with self.subTest(path=item["path"]):
                self.assertNotEqual(item["retention_status"], "trusted-current")

    def test_a_retained_capture_still_cannot_claim_currency(self):
        """Guards the narrowed check from being satisfied vacuously."""
        data = json.loads((LAB / "evidence-classification.json").read_text())
        paths = [i["path"] for i in data["artifacts"]]
        self.assertTrue(
            any("artifacts-sanitized" in p for p in paths),
            "the classification no longer lists any retained capture")


if __name__ == "__main__":
    unittest.main(verbosity=1)
