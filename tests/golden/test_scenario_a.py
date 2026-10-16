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


def run_with(evidence, execution="COMPLETE"):
    d = pathlib.Path(tempfile.mkdtemp()) / "run"
    d.mkdir(parents=True)
    manifest = dict(TEMPLATE)
    manifest["assertions"] = EXACT_ASSERTIONS
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
