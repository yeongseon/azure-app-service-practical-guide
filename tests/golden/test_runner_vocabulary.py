#!/usr/bin/env python3
"""The pilot runner's status strings must stay inside the frozen vocabulary.

An earlier plan called the runner a duplicate of the Golden evaluator and
proposed folding one into the other. Measuring first showed that premise
does not hold: `evaluate()` in the runner carries roughly forty-five
phase and temporal references -- phase ordering, time-window containment,
run and resource identity across phases, fingerprint integrity, the
activation precondition -- while the generic evaluator has essentially
none. One validates that a three-phase experiment hangs together in time;
the other evaluates declared assertions against captured evidence. Fusing
them would either push scenario-specific temporal logic into a generic
evaluator or lose the nuance that makes the runner correct.

The genuine shared surface is narrower: both name hypothesis and
execution statuses, and the runner spells them as bare literals. Importing
the tuples would couple a standalone lab runner to a repository path and
break the lab if it is copied elsewhere, so the coupling is enforced here
instead. The runner stays independent; the vocabulary stays single.
"""

import ast
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNNER = ROOT / "labs/deployment-succeeded-startup-failed/run.py"

#: Literals that look like a status but belong to another axis. The runner
#: records independent reproduction and cleanup separately from the
#: hypothesis, and those axes legitimately use their own words.
OTHER_AXES = {
    # The runner records five axes separately. Only the hypothesis and
    # execution axes share the evaluator's vocabulary; the rest are its own.
    "NOT_ATTEMPTED", "REPRODUCED", "CLEANED", "SKIPPED", "PENDING",
    "VERIFIED",          # cleanup_status
    "PASS", "FAIL",      # evidence-validation verdict, not a hypothesis verdict
    # Not a status at all: an argument to `git rev-parse`.
    "HEAD",
}


def frozen_vocabulary():
    """The tuples the evaluator actually enforces, read from its source.

    Parsed rather than imported so this test states what the evaluator
    declares, not what some other import has already mutated.
    """
    tree = ast.parse((ROOT / "scripts/golden/evaluate_run.py").read_text())
    names = ("HYPOTHESIS_STATUS", "EXECUTION_STATUS", "CLAIM_LEVELS",
             "EVIDENCE_ROLES", "EVIDENCE_TRUST")
    allowed = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in names:
                for element in getattr(node.value, "elts", []):
                    if isinstance(element, ast.Constant) and isinstance(element.value, str):
                        allowed.add(element.value)
    return allowed


def runner_status_literals():
    """SCREAMING_CASE string constants the runner emits."""
    tree = ast.parse(RUNNER.read_text())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
            if text.isupper() and text.replace("_", "").isalpha() and len(text) > 3:
                found.add(text)
    return found


class VocabularyBoundaryTests(unittest.TestCase):

    def test_the_parser_found_the_frozen_vocabulary(self):
        """Guards every test below from passing on an empty set."""
        vocabulary = frozen_vocabulary()
        self.assertIn("CONTRADICTED", vocabulary)
        self.assertIn("NOT_TESTED", vocabulary)
        self.assertIn("NOT_RUN", vocabulary)
        self.assertGreaterEqual(len(vocabulary), 10)

    def test_the_parser_found_literals_in_the_runner(self):
        self.assertGreaterEqual(len(runner_status_literals()), 4)

    def test_every_runner_status_is_from_the_frozen_vocabulary(self):
        unknown = runner_status_literals() - frozen_vocabulary() - OTHER_AXES
        self.assertEqual(
            unknown, set(),
            msg="the runner emits statuses the evaluator does not recognise; "
                "either add them to the frozen tuples or use an existing term")

    def test_the_runner_does_not_reintroduce_the_retired_terms(self):
        for retired in ("REFUTED", "NOT_EVALUATED"):
            self.assertNotIn(retired, runner_status_literals())

    def test_the_runner_stays_independent_of_the_evaluator(self):
        """The lab must remain runnable when copied out of this repository.

        If the runner ever imports the evaluator, this guard becomes
        unnecessary and should be deleted in the same change rather than
        left as a second, weaker check of the same property.
        """
        source = RUNNER.read_text()
        self.assertNotIn("evaluate_run", source)
        self.assertNotIn("scripts.golden", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
