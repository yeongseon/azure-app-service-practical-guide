"""Golden Scenario A conformance tests (#184).

The scenario asks whether deployment success and runtime success can be
separated with evidence. These tests check the declared contract, not a
live run: no Azure call happens here, so the template's execution status
must remain NOT_RUN and the evaluator must refuse to report any
hypothesis verdict from it.
"""

import sys

# See tests/golden/test_evaluate_run.py: a restored module can keep
# executing cached bytecode whose mtime and size still match.
sys.dont_write_bytecode = True

import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
LAB = ROOT / "labs/deployment-succeeded-startup-failed/golden"
_spec = importlib.util.spec_from_file_location("ev", ROOT / "scripts/golden/evaluate_run.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)

TEMPLATE = json.loads((LAB / "manifest.template.json").read_text())
EXACT_ASSERTIONS = json.loads(
    (ROOT / "evidence/runs/20261016T075147Z-6d019de6e2f2/manifest.json").read_text()
)["assertions"]
BAD_CMD = "gunicorn --bind=0.0.0.0:8000 --timeout=120 wrong_module:app"


def run_with(evidence, execution="COMPLETE", assertions=None):
    d = pathlib.Path(tempfile.mkdtemp()) / "run"
    d.mkdir(parents=True)
    manifest = dict(TEMPLATE)
    manifest["assertions"] = EXACT_ASSERTIONS if assertions is None else assertions
    manifest.update(run_id="20260927T010203Z-a1b2c3",
                    resource_id="/subscriptions/x/rg/app",
                    captured_at="2026-09-27T01:02:03Z",
                    execution_status=execution,
                    source_commit="3e0442bb19b966766598ffeae1fb47f3f6960837",
                    environment={"subscription_kind": "test", "region": "local",
                                 "runtime": "Python 3.11", "sku": "test-sku"},
                    recipe_digest="sha256:" + "0123456789abcdef" * 4,
                    collector_digest="sha256:" + "fedcba9876543210" * 4)
    (d / "manifest.json").write_text(json.dumps(manifest))
    (d / "evidence.json").write_text(json.dumps({
        "run_id": manifest["run_id"],
        "resource_id": manifest["resource_id"],
        "captured_at": manifest["captured_at"],
        "observations": evidence,
    }))
    return d


COMPLETE_EVIDENCE = {
    "baseline_status": 200,
    "deploy_exit_code": 0,
    "fault_startup_command": BAD_CMD,
    "fault_config_readback": BAD_CMD,
    "fault_status": 503,
    "fault_import_error_signature": "ModuleNotFoundError: No module named 'wrong_module'",
    "phase_order_valid": True,
    "recovery_status": 200,
}


class ContractShapeTests(unittest.TestCase):
    def test_every_required_evidence_role_is_declared(self):
        roles = {a["role"] for a in TEMPLATE["assertions"]}
        self.assertEqual(roles, {"control", "symptom", "discriminating", "recovery"})

    def test_all_assertion_roles_are_valid_vocabulary(self):
        for a in TEMPLATE["assertions"]:
            self.assertIn(a["role"], ev.EVIDENCE_ROLES)

    def test_assertion_ids_are_unique(self):
        ids = [a["id"] for a in TEMPLATE["assertions"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_template_ships_as_not_run(self):
        self.assertEqual(TEMPLATE["execution_status"], "NOT_RUN")
        self.assertIsNone(TEMPLATE["captured_at"])


class NotRunHonestyTests(unittest.TestCase):
    def test_template_alone_yields_no_hypothesis_verdict(self):
        result = ev.evaluate(run_with(COMPLETE_EVIDENCE, execution="NOT_RUN"))
        self.assertEqual(result["execution_status"], "NOT_RUN")
        self.assertEqual(result["hypothesis_status"], "NOT_TESTED")

    def test_complete_run_with_full_evidence_is_supported(self):
        self.assertEqual(
            ev.evaluate(run_with(COMPLETE_EVIDENCE))["hypothesis_status"], "SUPPORTED")


class ActivationPreconditionTests(unittest.TestCase):
    """A control-plane write is not proof the worker was recycled."""

    def test_missing_readback_cannot_reach_a_verdict(self):
        evidence = dict(COMPLETE_EVIDENCE)
        del evidence["fault_config_readback"]
        self.assertEqual(
            ev.evaluate(run_with(evidence))["hypothesis_status"], "INCONCLUSIVE")

    def test_readback_showing_the_healthy_command_is_contradicted(self):
        evidence = dict(COMPLETE_EVIDENCE,
                        fault_config_readback="gunicorn --bind=0.0.0.0:8000 --timeout=120 app:app")
        self.assertEqual(
            ev.evaluate(run_with(evidence))["hypothesis_status"], "CONTRADICTED")

    def test_a_healthy_response_without_console_evidence_is_inconclusive(self):
        evidence = dict(COMPLETE_EVIDENCE, fault_status=200)
        del evidence["fault_import_error_signature"]
        self.assertEqual(
            ev.evaluate(run_with(evidence))["hypothesis_status"], "INCONCLUSIVE")

    def test_a_healthy_response_with_no_activation_evidence_at_all_is_inconclusive(self):
        evidence = dict(COMPLETE_EVIDENCE, fault_status=200)
        del evidence["fault_config_readback"]
        del evidence["fault_import_error_signature"]
        self.assertEqual(
            ev.evaluate(run_with(evidence))["hypothesis_status"], "INCONCLUSIVE")

    def test_the_healthy_response_still_contradicts_its_own_assertion(self):
        evidence = dict(COMPLETE_EVIDENCE, fault_status=200)
        del evidence["fault_import_error_signature"]
        outcomes = ev.evaluate(run_with(evidence))["assertion_outcomes"]
        self.assertEqual(outcomes["symptom-runtime-503"], "CONTRADICTED")
        self.assertEqual(outcomes["discriminating-import-error"], "INCONCLUSIVE")

    def test_the_same_response_contradicts_once_activation_evidence_is_available(self):
        early = dict(COMPLETE_EVIDENCE, fault_status=200)
        del early["fault_import_error_signature"]
        late = dict(early, fault_import_error_signature=COMPLETE_EVIDENCE["fault_import_error_signature"])
        self.assertEqual(
            ev.evaluate(run_with(early))["hypothesis_status"], "INCONCLUSIVE")
        self.assertEqual(
            ev.evaluate(run_with(late))["hypothesis_status"], "CONTRADICTED")


class SymptomWeightTests(unittest.TestCase):
    """A contradicted symptom decides the hypothesis only when some discriminating assertion is not INCONCLUSIVE."""

    CASES = (
        ("one symptom and an inconclusive discriminator",
         (("s", "symptom", "CONTRADICTED"), ("d", "discriminating", "INCONCLUSIVE")), "INCONCLUSIVE"),
        ("every contradicted symptom loses its weight",
         (("s1", "symptom", "CONTRADICTED"), ("s2", "symptom", "CONTRADICTED"),
          ("d", "discriminating", "INCONCLUSIVE")), "INCONCLUSIVE"),
        ("every discriminator inconclusive",
         (("s", "symptom", "CONTRADICTED"), ("d1", "discriminating", "INCONCLUSIVE"),
          ("d2", "discriminating", "INCONCLUSIVE")), "INCONCLUSIVE"),
        ("one supported discriminator keeps the contradiction",
         (("s", "symptom", "CONTRADICTED"), ("d1", "discriminating", "SUPPORTED"),
          ("d2", "discriminating", "INCONCLUSIVE")), "CONTRADICTED"),
        ("a contradicted discriminator decides by itself",
         (("s", "symptom", "CONTRADICTED"), ("d", "discriminating", "CONTRADICTED")), "CONTRADICTED"),
        ("no discriminating assertion keeps the ordinary aggregation",
         (("s", "symptom", "CONTRADICTED"),), "CONTRADICTED"),
        ("a contradicted recovery still decides",
         (("s", "symptom", "CONTRADICTED"), ("d", "discriminating", "INCONCLUSIVE"),
          ("r", "recovery", "CONTRADICTED")), "CONTRADICTED"),
        ("a contradicted control still decides",
         (("s", "symptom", "CONTRADICTED"), ("d", "discriminating", "INCONCLUSIVE"),
          ("c", "control", "CONTRADICTED")), "CONTRADICTED"),
        ("a satisfied symptom next to an inconclusive discriminator stays inconclusive",
         (("s", "symptom", "SUPPORTED"), ("d", "discriminating", "INCONCLUSIVE")), "INCONCLUSIVE"),
    )

    def test_the_weight_of_a_contradicted_symptom(self):
        for name, rows, expected in self.CASES:
            with self.subTest(case=name):
                assertions = [{"id": key, "role": role} for key, role, _ in rows]
                outcomes = {key: outcome for key, _, outcome in rows}
                self.assertEqual(
                    ev.combine(ev._hypothesis_outcomes(assertions, outcomes).values()), expected)

    def test_the_outcomes_it_is_given_are_left_as_they_were(self):
        assertions = [{"id": "s", "role": "symptom"}, {"id": "d", "role": "discriminating"}]
        outcomes = {"s": "CONTRADICTED", "d": "INCONCLUSIVE"}
        ev._hypothesis_outcomes(assertions, outcomes)
        self.assertEqual(outcomes, {"s": "CONTRADICTED", "d": "INCONCLUSIVE"})

    def test_a_discriminator_weakened_by_its_claim_level_does_not_ground_the_symptom(self):
        weakened = [dict(a, claim_level="Not Proven") if a["role"] == "discriminating" else a
                    for a in EXACT_ASSERTIONS]
        result = ev.evaluate(run_with(dict(COMPLETE_EVIDENCE, fault_status=200), assertions=weakened))
        self.assertEqual(result["assertion_outcomes"]["discriminating-import-error"], "INCONCLUSIVE")
        self.assertEqual(result["assertion_outcomes"]["symptom-runtime-503"], "CONTRADICTED")
        self.assertEqual(result["hypothesis_status"], "INCONCLUSIVE")

    def test_the_evidence_of_an_unfinished_run_still_decides_nothing(self):
        evidence = dict(COMPLETE_EVIDENCE, fault_status=200)
        del evidence["fault_import_error_signature"]
        for execution in ("PARTIAL", "BLOCKED", "FAILED", "NOT_RUN"):
            with self.subTest(execution=execution):
                self.assertEqual(
                    ev.evaluate(run_with(evidence, execution=execution))["hypothesis_status"],
                    "NOT_TESTED")


class ContradictionReachableTests(unittest.TestCase):
    def test_healthy_app_under_an_activated_fault_contradicts(self):
        evidence = dict(COMPLETE_EVIDENCE, fault_status=200)
        self.assertEqual(
            ev.evaluate(run_with(evidence))["hypothesis_status"], "CONTRADICTED")

    def test_missing_recovery_blocks_supported(self):
        evidence = dict(COMPLETE_EVIDENCE)
        del evidence["recovery_status"]
        self.assertEqual(
            ev.evaluate(run_with(evidence))["hypothesis_status"], "INCONCLUSIVE")

    def test_absent_import_error_is_inconclusive_not_contradicted(self):
        evidence = dict(COMPLETE_EVIDENCE)
        del evidence["fault_import_error_signature"]
        self.assertEqual(
            ev.evaluate(run_with(evidence))["hypothesis_status"], "INCONCLUSIVE")

    def test_http_500_does_not_satisfy_the_503_assertion(self):
        evidence = dict(COMPLETE_EVIDENCE, fault_status=500)
        self.assertEqual(
            ev.evaluate(run_with(evidence))["hypothesis_status"], "CONTRADICTED")

    def test_unrelated_import_error_does_not_satisfy_the_signature(self):
        evidence = dict(
            COMPLETE_EVIDENCE,
            fault_import_error_signature="ImportError: unrelated_dependency",
        )
        self.assertEqual(
            ev.evaluate(run_with(evidence))["hypothesis_status"], "CONTRADICTED")

    def test_generic_import_error_count_without_signature_does_not_support(self):
        evidence = dict(COMPLETE_EVIDENCE, fault_import_error_hits=4)
        del evidence["fault_import_error_signature"]
        self.assertEqual(
            ev.evaluate(run_with(evidence))["hypothesis_status"], "INCONCLUSIVE")

    def test_out_of_order_phases_do_not_support(self):
        evidence = dict(COMPLETE_EVIDENCE, phase_order_valid=False)
        self.assertEqual(
            ev.evaluate(run_with(evidence))["hypothesis_status"], "CONTRADICTED")

    def test_a_failed_recovery_contradicts(self):
        evidence = dict(COMPLETE_EVIDENCE, recovery_status=503)
        self.assertEqual(
            ev.evaluate(run_with(evidence))["hypothesis_status"], "CONTRADICTED")


class HistoricalEvidenceTests(unittest.TestCase):
    def test_every_retained_artifact_is_classified_not_deleted(self):
        data = json.loads((LAB / "evidence-classification.json").read_text())
        self.assertTrue(data["artifacts"])
        for item in data["artifacts"]:
            self.assertIn(item["retention_status"], ev.EVIDENCE_TRUST)
            self.assertTrue(item["reason"].strip())
            self.assertTrue((ROOT / item["path"]).exists(), item["path"])

    def test_the_unordered_trigger_set_is_not_marked_trusted_current(self):
        data = json.loads((LAB / "evidence-classification.json").read_text())
        trigger = [a for a in data["artifacts"] if a["path"].endswith("trigger/")][0]
        self.assertNotEqual(trigger["retention_status"], "trusted-current")


if __name__ == "__main__":
    unittest.main(verbosity=1)
