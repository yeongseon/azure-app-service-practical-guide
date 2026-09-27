#!/usr/bin/env python3
"""One vocabulary across the repository, not two.

The startup-failure runner predates the Golden model and used REFUTED
where the model says CONTRADICTED, and NOT_EVALUATED where it says
NOT_TESTED. Two vocabularies in one repository is not a naming
inconvenience: REFUTED reads as a finding, while the distinction the
model draws is between evidence that contradicts a hypothesis and
evidence that is merely absent. A repository carrying both will
eventually report missing data as disproof.
"""

import pathlib
import re
import sys
import unittest

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[2]

RETIRED = ("REFUTED", "NOT_EVALUATED")

#: Two files reference the retired terms on purpose.
#:
#: The migration spec documents the old-to-new mapping and must keep both
#: terms, or it could not tell a sibling repository what to rename.
#:
#: check_reproduction.py lists NOT_EVALUATED among the statuses meaning
#: "never put at risk", so a legacy record carrying the old term is still
#: treated as untested. Removing it to satisfy this check would let a pair
#: of legacy non-runs reproduce each other again, which is the defect the
#: tuple exists to prevent. Defending against a term is not using it.
ALLOWED = {
    "docs/reference/golden-migration-spec.md",
    "scripts/golden/check_reproduction.py",
}

SCANNED = ("*.py", "*.json", "*.sh", "*.md")


def offenders():
    found = []
    for root in ("labs", "docs", "scripts", "schemas"):
        base = ROOT / root
        if not base.is_dir():
            continue
        for pattern in SCANNED:
            for path in base.rglob(pattern):
                rel = path.relative_to(ROOT).as_posix()
                if rel in ALLOWED:
                    continue
                text = path.read_text(errors="ignore")
                for term in RETIRED:
                    if re.search(rf"\b{term}\b", text):
                        found.append((rel, term))
    return sorted(set(found))


class VocabularyTests(unittest.TestCase):

    def test_no_file_uses_the_retired_vocabulary(self):
        self.assertEqual(
            offenders(), [],
            msg="these files still use the pre-Golden vocabulary; map REFUTED to "
                "CONTRADICTED and NOT_EVALUATED to NOT_TESTED")

    def test_the_scanner_actually_finds_things(self):
        """Guards the test above from passing because it scanned nothing."""
        spec = ROOT / "docs/reference/golden-migration-spec.md"
        text = spec.read_text()
        self.assertRegex(text, r"\bREFUTED\b")
        self.assertRegex(text, r"\bNOT_EVALUATED\b")

    def test_the_spec_is_exempt_for_a_stated_reason(self):
        self.assertIn("docs/reference/golden-migration-spec.md", ALLOWED)

    def test_the_retired_term_survives_only_as_a_defence(self):
        """The exemption is narrow: it may appear in the untested tuple only.

        If check_reproduction.py ever starts emitting the old term rather
        than merely recognising it, this fails.
        """
        text = (ROOT / "scripts/golden/check_reproduction.py").read_text()
        for line in text.splitlines():
            if "NOT_EVALUATED" in line:
                self.assertIn(
                    "UNTESTED_STATUS", line,
                    msg="NOT_EVALUATED appears outside the defensive tuple")

    def test_the_defence_actually_covers_the_legacy_term(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "cr", ROOT / "scripts/golden/check_reproduction.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIn("NOT_EVALUATED", module.UNTESTED_STATUS)
        self.assertIn("NOT_TESTED", module.UNTESTED_STATUS)

    def test_the_replacement_terms_are_the_frozen_ones(self):
        evaluator = (ROOT / "scripts/golden/evaluate_run.py").read_text()
        frozen = re.search(r"HYPOTHESIS_STATUS = \((.*?)\)", evaluator, re.S).group(1)
        for term in ("CONTRADICTED", "NOT_TESTED"):
            self.assertIn(f'"{term}"', frozen)


if __name__ == "__main__":
    unittest.main(verbosity=2)
