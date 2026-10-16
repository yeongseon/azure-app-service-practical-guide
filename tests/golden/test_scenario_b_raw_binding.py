#!/usr/bin/env python3
import copy
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "scenario_b_raw_evaluator", ROOT / "scripts/golden/evaluate_run.py")
evaluator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluator)

RUN_ID = "20261016T120000Z-abcdef012345"
CAPTURE = {
    "started_at": "2026-10-16T10:00:00Z",
    "ended_at": "2026-10-16T10:20:00Z",
}


def observations():
    phases = {
        "baseline": {
            "started_at": "2026-10-16T10:01:00Z",
            "ended_at": "2026-10-16T10:02:00Z",
            "probes": [{"captured_at": "2026-10-16T10:01:30Z", "status": 200,
                        "inner": {"success": 40, "failure": 0, "transport_failure": 0}}],
        },
        "load": {
            "started_at": "2026-10-16T10:03:00Z",
            "ended_at": "2026-10-16T10:04:00Z",
            "probes": [{"captured_at": "2026-10-16T10:03:30Z", "status": 200,
                        "inner": {"success": 0, "failure": 0, "transport_failure": 40}}],
        },
        "recovery": {
            "started_at": "2026-10-16T10:10:00Z",
            "ended_at": "2026-10-16T10:11:00Z",
            "probes": [{"captured_at": "2026-10-16T10:10:30Z", "status": 200,
                        "inner": {"success": 40, "failure": 0, "transport_failure": 0}}],
        },
    }
    return {
        "phase_windows": {name: {"started_at": phase["started_at"],
                                  "ended_at": phase["ended_at"]}
                          for name, phase in phases.items()},
        "phase_probes": {name: phase["probes"] for name, phase in phases.items()},
        "destination_health": {"captured_at": "2026-10-16T10:03:45Z", "status": 200},
        "destination_binding": True,
        "snat_port_pressure": "unavailable",
    }


class ScenarioBRawBindingTests(unittest.TestCase):
    def derive(self, document):
        manifest = {"run_id": RUN_ID, "capture_window": CAPTURE}
        return evaluator._derive_scenario_b(document, manifest)

    def test_worker_symptom_without_direct_pressure_is_inconclusive_input(self):
        derived = self.derive(observations())
        self.assertEqual(derived["load_transport_failure_count"], 1)
        self.assertEqual(derived["snat_port_pressure"], "unavailable")

    def test_unrelated_destination_binding_is_rejected(self):
        document = observations()
        document["destination_binding"] = False
        with self.assertRaises(evaluator.ModelError):
            self.derive(document)

    def test_wrong_run_phase_is_rejected(self):
        document = observations()
        document["phase_probes"]["load"][0]["run_id"] = "other-run"
        with self.assertRaises(evaluator.ModelError):
            self.derive(document)

    def test_out_of_window_probe_is_rejected(self):
        document = observations()
        document["phase_probes"]["load"][0]["captured_at"] = "2026-10-16T10:09:00Z"
        with self.assertRaises(evaluator.ModelError):
            self.derive(document)

    def test_unrelated_telemetry_cannot_supply_port_pressure(self):
        document = observations()
        document["worker_timeout_count"] = 99
        derived = self.derive(document)
        self.assertEqual(derived["snat_port_pressure"], "unavailable")

    def test_phase_order_is_enforced(self):
        document = observations()
        document["phase_windows"]["recovery"] = copy.deepcopy(
            document["phase_windows"]["baseline"])
        with self.assertRaises(evaluator.ModelError):
            self.derive(document)


if __name__ == "__main__":
    unittest.main(verbosity=2)
