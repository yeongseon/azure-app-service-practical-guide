#!/usr/bin/env python3
"""Custody and provenance are separate axes and must stay separately named.

One field named `trust` carried two vocabularies. `evidence.schema.json`
used it for how an observation was obtained (`primary`, `derived`,
`reported`) while the evidence classifications used it for how fresh an
artifact is (`trusted-current`, `trusted-historical`, `unverified`,
`invalid`). The collision was not hypothetical: a classification was
found holding `primary`, `trusted-current` and `trusted-historical` in
the same field, and a manifest failed schema validation outright because
a provenance word had been written into a custody field.

The axes answer different questions. Where a value came from does not
say how stale it is, and how fresh an artifact is does not say whether
anyone observed it directly. These tests keep the names distinct so the
two can never be confused by writing into the wrong one.
"""

import json
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[2]

#: How fresh an artifact is, and whether it may still be relied on.
CUSTODY = ("trusted-current", "trusted-historical", "unverified", "invalid")

#: How an observation was obtained.
PROVENANCE = ("primary", "derived", "reported")


def classifications():
    return sorted((ROOT / "labs").glob("*/golden/evidence-classification.json"))


def evidence_documents():
    return sorted((ROOT / "evidence" / "runs").glob("*/evidence.json"))


class SeparationTests(unittest.TestCase):

    def test_the_two_vocabularies_do_not_overlap(self):
        """If a word meant both things, no naming could disambiguate it."""
        self.assertEqual(set(CUSTODY) & set(PROVENANCE), set())

    def test_no_document_still_uses_the_ambiguous_name(self):
        """`trust` meant either axis depending on the file, so it is retired."""
        for path in classifications() + evidence_documents():
            text = path.read_text()
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotRegex(
                    text, r'"trust"\s*:',
                    msg="use retention_status for custody or capture_provenance "
                        "for provenance")


class ClassificationTests(unittest.TestCase):

    def test_some_classifications_were_found(self):
        """Guards every test below from passing on an empty list."""
        self.assertGreaterEqual(len(classifications()), 3)

    def test_every_artifact_declares_its_custody(self):
        for path in classifications():
            for artifact in json.loads(path.read_text())["artifacts"]:
                with self.subTest(path=path.parent.parent.name, artifact=artifact["path"]):
                    self.assertIn(artifact.get("retention_status"), CUSTODY)

    def test_custody_never_holds_a_provenance_word(self):
        """The exact defect: `primary` written into a custody field."""
        for path in classifications():
            for artifact in json.loads(path.read_text())["artifacts"]:
                with self.subTest(path=path.parent.parent.name, artifact=artifact["path"]):
                    self.assertNotIn(artifact.get("retention_status"), PROVENANCE)

    def test_provenance_is_optional_but_constrained_when_present(self):
        for path in classifications():
            for artifact in json.loads(path.read_text())["artifacts"]:
                if "capture_provenance" not in artifact:
                    continue
                with self.subTest(path=path.parent.parent.name, artifact=artifact["path"]):
                    self.assertIn(artifact["capture_provenance"], PROVENANCE)


class EvidenceDocumentTests(unittest.TestCase):

    def test_some_evidence_documents_were_found(self):
        self.assertGreaterEqual(len(evidence_documents()), 2)

    def test_every_evidence_document_declares_its_provenance(self):
        for path in evidence_documents():
            with self.subTest(run=path.parent.name):
                self.assertIn(
                    json.loads(path.read_text()).get("capture_provenance"), PROVENANCE)

    def test_provenance_never_holds_a_custody_word(self):
        for path in evidence_documents():
            with self.subTest(run=path.parent.name):
                self.assertNotIn(
                    json.loads(path.read_text()).get("capture_provenance"), CUSTODY)


class SchemaTests(unittest.TestCase):

    def test_the_evidence_schema_names_the_provenance_axis(self):
        schema = json.loads((ROOT / "schemas/golden/evidence.schema.json").read_text())
        self.assertIn("capture_provenance", schema["properties"])
        self.assertNotIn("trust", schema["properties"])
        self.assertEqual(
            tuple(schema["properties"]["capture_provenance"]["enum"]), PROVENANCE)

    def test_the_manifest_schema_keeps_the_custody_axis(self):
        schema = json.loads((ROOT / "schemas/golden/manifest.schema.json").read_text())
        self.assertEqual(
            tuple(schema["properties"]["evidence_trust"]["enum"]), CUSTODY)


if __name__ == "__main__":
    unittest.main(verbosity=2)
