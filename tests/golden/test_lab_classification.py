"""Legacy lab classification tests (#182).

The classification is only useful if it cannot drift away from the
repository. A lab added later and never classified would otherwise sit
outside the Golden migration entirely while the file still looked
complete, so coverage is checked against the filesystem rather than
against a hand-maintained count.
"""

import sys

sys.dont_write_bytecode = True

import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CLASSIFICATION = ROOT / "labs/golden-classification.json"
DATA = json.loads(CLASSIFICATION.read_text())

VALID = {"golden", "migration-needed", "archive-candidate"}

_spec = importlib.util.spec_from_file_location("ev", ROOT / "scripts/golden/evaluate_run.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)


def labs_on_disk():
    return {
        p.name for p in (ROOT / "labs").iterdir()
        if p.is_dir() and not p.name.startswith("_")
    }


class CoverageTests(unittest.TestCase):
    def test_every_lab_on_disk_is_classified(self):
        classified = {row["lab"] for row in DATA["labs"]}
        missing = labs_on_disk() - classified
        self.assertEqual(
            missing, set(),
            msg="labs exist on disk with no Golden classification; they would be "
                "silently excluded from the migration")

    def test_no_classification_refers_to_a_lab_that_does_not_exist(self):
        classified = {row["lab"] for row in DATA["labs"]}
        stale = classified - labs_on_disk()
        self.assertEqual(stale, set(), msg="classification refers to removed labs")

    def test_shared_harness_is_not_classified_as_a_lab(self):
        self.assertNotIn("_shared", {row["lab"] for row in DATA["labs"]})


class ShapeTests(unittest.TestCase):
    def test_every_classification_uses_the_declared_vocabulary(self):
        for row in DATA["labs"]:
            self.assertIn(row["classification"], VALID, msg=row["lab"])

    def test_every_lab_carries_a_substantive_reason(self):
        for row in DATA["labs"]:
            self.assertGreater(
                len(row["reason"].strip()), 40,
                msg=f"{row['lab']} needs a reason that states why, not a label")

    def test_criteria_are_defined_for_every_used_classification(self):
        used = {row["classification"] for row in DATA["labs"]}
        self.assertTrue(used <= set(DATA["criteria"]))

    def test_lab_entries_are_unique(self):
        names = [row["lab"] for row in DATA["labs"]]
        self.assertEqual(len(names), len(set(names)))


class GoldenClaimTests(unittest.TestCase):
    """A lab may only be called Golden if it actually declares a contract."""

    def test_golden_labs_have_a_manifest_declaring_assertions(self):
        for row in DATA["labs"]:
            if row["classification"] != "golden":
                continue
            manifest = ROOT / "labs" / row["lab"] / "golden/manifest.template.json"
            self.assertTrue(manifest.is_file(), msg=f"{row['lab']} claims golden with no manifest")
            data = json.loads(manifest.read_text())
            self.assertTrue(data["assertions"], msg=f"{row['lab']} declares no assertions")

    def test_golden_labs_declare_all_four_evidence_roles(self):
        for row in DATA["labs"]:
            if row["classification"] != "golden":
                continue
            manifest = json.loads(
                (ROOT / "labs" / row["lab"] / "golden/manifest.template.json").read_text())
            roles = {a["role"] for a in manifest["assertions"]}
            self.assertEqual(
                roles, {"control", "symptom", "discriminating", "recovery"}, msg=row["lab"])

    def test_golden_labs_ship_not_run_until_azure_produces_evidence(self):
        for row in DATA["labs"]:
            if row["classification"] != "golden":
                continue
            manifest = json.loads(
                (ROOT / "labs" / row["lab"] / "golden/manifest.template.json").read_text())
            self.assertEqual(manifest["execution_status"], "NOT_RUN", msg=row["lab"])

    def test_a_lab_without_a_manifest_is_not_called_golden(self):
        for row in DATA["labs"]:
            has_manifest = (ROOT / "labs" / row["lab"] / "golden/manifest.template.json").is_file()
            if not has_manifest:
                self.assertNotEqual(row["classification"], "golden", msg=row["lab"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
