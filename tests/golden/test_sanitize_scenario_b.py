#!/usr/bin/env python3
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sanitize_b", ROOT / "scripts/golden/sanitize_scenario_b.py")
sanitize = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sanitize)


class ScenarioBSanitisationTests(unittest.TestCase):
    def test_replaces_only_identifier_fields_deterministically(self):
        raw = {
            "run_id": "run-one",
            "resource_id": "/subscriptions/private/site/app",
            "observations": {
                "destination": "https://private.azurewebsites.net/",
                "phase_probes": {"baseline": [{
                    "target": "https://private.azurewebsites.net/", "status": 200}]},
                "pooled_phase_probes": {"baseline": [{
                    "target": "https://private.azurewebsites.net/", "status": 200}]},
                "destination_health_status": 200,
            },
        }
        public = sanitize.sanitise(raw)
        self.assertIsNone(public["resource_id"])
        self.assertEqual(public["observations"]["destination"], sanitize.PUBLIC_DESTINATION)
        self.assertEqual(public["observations"]["destination_health_status"], 200)
        self.assertEqual(raw["observations"]["destination"],
                         "https://private.azurewebsites.net/")


if __name__ == "__main__":
    unittest.main(verbosity=2)
