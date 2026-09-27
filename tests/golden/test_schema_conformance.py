#!/usr/bin/env python3
"""Schema validation must actually reject a non-conforming document.

The Golden job called `json.load` on these files and reported success,
which proved they were JSON and nothing more. Sixteen violations lived
behind that green check: undeclared properties under
`additionalProperties: false`, a trust vocabulary the schema did not list,
and an execution status the evaluator accepted but no schema knew.

A validator that cannot fail is the same defect wearing a better name, so
these tests plant violations and require each to be caught.
"""

import importlib.util
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "validate_schemas", ROOT / "scripts/golden/validate_schemas.py")
validate_schemas = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_schemas)

SCHEMA_DIR = ROOT / "schemas" / "golden"


def check(document: dict, schema_name: str):
    """Validate one in-memory document, returning its errors."""
    import jsonschema
    schema = json.loads((SCHEMA_DIR / schema_name).read_text())
    validator = jsonschema.Draft202012Validator(
        schema, registry=validate_schemas._registry())
    return sorted(validator.iter_errors(document), key=lambda e: list(e.path))


def a_manifest(**overrides):
    base = json.loads(
        (ROOT / "labs/deployment-succeeded-startup-failed/golden/manifest.template.json").read_text())
    base.update(overrides)
    return base


class TreeConformanceTests(unittest.TestCase):

    def test_every_golden_document_conforms_today(self):
        self.assertEqual(validate_schemas.validate(), [])

    def test_the_checker_examined_something(self):
        """Guards the assertion above from passing on an empty document set."""
        self.assertGreaterEqual(len(validate_schemas.documents()), 4)

    def test_every_schema_is_itself_valid(self):
        import jsonschema
        for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
            with self.subTest(schema=path.name):
                jsonschema.Draft202012Validator.check_schema(
                    json.loads(path.read_text()))


class PlantedViolationTests(unittest.TestCase):
    """Each is a violation that previously passed the json.load check."""

    def test_an_undeclared_property_is_rejected(self):
        self.assertTrue(check(a_manifest(smuggled="value"), "manifest.schema.json"))

    def test_an_unknown_execution_status_is_rejected(self):
        self.assertTrue(check(a_manifest(execution_status="FINISHED"),
                              "manifest.schema.json"))

    def test_a_known_execution_status_is_accepted(self):
        """Guards the check above from rejecting everything."""
        for status in ("COMPLETE", "NOT_RUN", "RUNNING"):
            with self.subTest(status=status):
                self.assertEqual(
                    check(a_manifest(execution_status=status), "manifest.schema.json"), [])

    def test_the_wrong_trust_vocabulary_is_rejected(self):
        """The provenance words do not belong in the custody field.

        Scenario B carried `primary` here, which the schema does not list.
        Two axes sharing one field name is what made that possible.
        """
        self.assertTrue(check(a_manifest(evidence_trust="primary"),
                              "manifest.schema.json"))

    def test_an_assertion_missing_its_field_is_rejected(self):
        """An assertion with no field names nothing and can evaluate nothing."""
        manifest = a_manifest()
        manifest["assertions"] = [{"id": "x", "role": "symptom"}]
        self.assertTrue(check(manifest, "manifest.schema.json"))

    def test_a_complete_assertion_is_accepted(self):
        """Guards the check above from rejecting every assertion."""
        manifest = a_manifest()
        manifest["assertions"] = [
            {"id": "x", "role": "symptom", "field": "status", "equals": 503}]
        self.assertEqual(check(manifest, "manifest.schema.json"), [])

    def test_an_assertion_with_an_unknown_role_is_rejected(self):
        manifest = a_manifest()
        manifest["assertions"] = [{"id": "x", "role": "vibes", "field": "f"}]
        self.assertTrue(check(manifest, "manifest.schema.json"))


class TemplateHonestyTests(unittest.TestCase):
    """A template must be allowed to be honestly empty."""

    def test_a_template_may_carry_no_identity(self):
        manifest = a_manifest(run_id=None, captured_at=None, resource_id=None)
        self.assertEqual(check(manifest, "manifest.schema.json"), [])

    def test_a_real_run_identity_is_still_accepted(self):
        manifest = a_manifest(run_id="20260927T104304Z-aba0d3a9daa7",
                              captured_at="2026-09-27T10:43:04+00:00")
        self.assertEqual(check(manifest, "manifest.schema.json"), [])

    def test_hypothesis_and_notes_are_declared_not_tolerated(self):
        schema = json.loads((SCHEMA_DIR / "manifest.schema.json").read_text())
        self.assertIs(schema.get("additionalProperties"), False)
        for key in ("hypothesis", "notes"):
            self.assertIn(key, schema["properties"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
