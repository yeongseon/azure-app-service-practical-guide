"""Offline tests for non-destructive versioned priority-label synchronization."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("labels", ROOT / "scripts/ci/sync_priority_labels.py")
labels = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = labels
SPEC.loader.exec_module(labels)


class PriorityLabelTests(unittest.TestCase):
    def test_plan_is_empty_when_definitions_match(self):
        # Given: a repository matching the committed definitions.
        definitions = {"priority:high": ("d93f0b", "High")}

        # When: synchronization planning compares the labels.
        operations = labels.plan(definitions, {"priority:high": ("d93f0b", "High")})

        # Then: no operation is needed.
        self.assertEqual(operations, ())

    def test_plan_creates_missing_versioned_label(self):
        # Given: a definition absent from the repository.
        definitions = {"priority:high": ("d93f0b", "High")}

        # When: synchronization planning compares the labels.
        operations = labels.plan(definitions, {})

        # Then: it creates the defined label.
        self.assertEqual(operations, (labels.LabelOperation("priority:high", "High", "d93f0b", "create"),))

    def test_plan_updates_only_drifted_versioned_label(self):
        # Given: a stale priority description and an unrelated label.
        definitions = {"priority:high": ("d93f0b", "High")}
        existing = {"priority:high": ("ededed", "Old"), "documentation": ("ededed", "Unrelated")}

        # When: synchronization planning compares the labels.
        operations = labels.plan(definitions, existing)

        # Then: it updates only the defined priority label.
        self.assertEqual(operations, (labels.LabelOperation("priority:high", "High", "d93f0b", "edit"),))


if __name__ == "__main__":
    unittest.main()
