#!/usr/bin/env python3
"""The migration specification's portability claims must be measured.

The specification tells a sibling repository which assets transfer
unchanged. That table is the part most likely to rot: someone adds an
App Service reference to the evaluator, or names a local lab in a suite
listed as portable, and the table keeps claiming a portability that no
longer holds. A sibling only discovers it after copying the file.

These tests re-derive the claim. Assets the specification lists as
transferring unchanged are checked for references to this repository, its
service and its labs; assets it lists as repository-specific are checked
for the coupling that justifies excluding them, so the table cannot list
everything as portable to stay green.
"""

import pathlib
import re
import sys
import unittest

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = (ROOT / "docs" / "reference" / "golden-migration-spec.md").read_text()

#: Tokens that tie a file to this repository rather than the series.
COUPLING = re.compile(
    r"app[ -]?service|webapp|appsvc|azure-app-service-practical-guide"
    r"|snat-exhaustion|slot-swap-config-drift|deployment-succeeded-startup-failed",
    re.IGNORECASE,
)


def spec_rows():
    """(asset, change-needed) pairs from the transfer table."""
    rows = []
    for line in SPEC.splitlines():
        match = re.match(r"\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|\s*$", line)
        if match:
            rows.append((match.group(1), match.group(2)))
    return rows


def claimed_unchanged():
    """Assets the table says need no edit at all."""
    return [asset for asset, change in spec_rows() if change.strip() == "None"]


def named_repo_specific():
    """Suites the specification names as not transferring."""
    # Only the "What each repository authors itself" section names them; later sections
    # mention the generic suites too (entry criteria, order of adoption).
    section = SPEC.split("authors itself")[1].split("\n## ")[0]
    return re.findall(r"`(test_\w+\.py)`", section)


def coupling_in(rel_path):
    """Lines of a file that tie it to this repository."""
    path = ROOT / rel_path
    if not path.is_file():
        return [f"MISSING: {rel_path}"]
    return [
        f"{rel_path}:{n}: {line.strip()[:70]}"
        for n, line in enumerate(path.read_text().splitlines(), 1)
        if COUPLING.search(line)
    ]


class EvaluatorBoundaryTests(unittest.TestCase):
    """The table must not call the evaluator portable while it carries Scenario A."""

    def test_the_evaluator_is_not_claimed_unchanged_while_it_carries_scenario_a(self):
        evaluator = (ROOT / "scripts/golden/evaluate_run.py").read_text()
        self.assertIn("def _derive_scenario_a(", evaluator)
        self.assertNotIn("scripts/golden/evaluate_run.py", claimed_unchanged())
        self.assertIn("_derive_scenario_a", SPEC)

    def test_prerequisites_name_the_gates_third_party_imports(self):
        gate = (ROOT / "scripts/golden/check_reproduction.py").read_text()
        for module in re.findall(r"^(?:import|from) (jsonschema|referencing)\b", gate, re.MULTILINE):
            with self.subTest(module=module):
                self.assertIn(f"`{module}`", SPEC)


class AdaptedSuiteTests(unittest.TestCase):
    """Suites that read this repository's own data must not be listed as portable."""

    COUPLED = {
        "tests/golden/test_lab_classification.py": ("EXPECTED_SCENARIO_COUNT = 15", "windows-java-httpplatformhandler-timeout"),
        "tests/golden/test_readme_claims.py": ("20261016T075147Z-6d019de6e2f2",),
        "tests/golden/test_repository_audit.py": ("docs/reference/golden-repository-audit.json", "DOCUMENTATION_CONTRACT.md"),
    }

    def test_coupled_suites_are_not_claimed_unchanged(self):
        for asset, markers in self.COUPLED.items():
            with self.subTest(asset=asset):
                text = (ROOT / asset).read_text()
                for marker in markers:
                    self.assertIn(marker, text, msg=f"{asset} no longer carries {marker!r}; re-derive the claim")
                self.assertNotIn(asset, claimed_unchanged())
                self.assertIn(asset, [row[0] for row in spec_rows()])

    def test_the_schema_count_in_the_text_is_the_real_count(self):
        count = len(list((ROOT / "schemas/golden").glob("*.json")))
        words = {3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}
        self.assertIn(f"The {words[count]} schemas under `schemas/golden/`", SPEC)

    def test_preservation_never_promotes_trust_by_copying(self):
        section = SPEC.split("## Preserving evidence on adoption")[1].split("\n## ")[0]
        for phrase in ("`trusted-historical`", "`known_gaps`", "source commit", "recipe digest"):
            self.assertIn(phrase, section)


class TransferTableTests(unittest.TestCase):

    def test_the_table_was_parsed(self):
        """Guards every test below from passing on an empty list."""
        self.assertGreaterEqual(len(spec_rows()), 8)
        # Three assets: the evaluator and three suites are no longer "None" because they
        # carry Scenario A or read this repository's own data (measured by the tests below).
        self.assertGreaterEqual(len(claimed_unchanged()), 3)

    def test_assets_claimed_unchanged_are_free_of_repo_coupling(self):
        for asset in claimed_unchanged():
            if "*" in asset:
                continue
            with self.subTest(asset=asset):
                self.assertEqual(
                    coupling_in(asset), [],
                    msg=f"the specification says {asset} transfers unchanged, "
                        "but it names this repository, its service or its labs")

    def test_every_asset_claimed_unchanged_exists(self):
        for asset in claimed_unchanged():
            if "*" in asset:
                continue
            with self.subTest(asset=asset):
                self.assertTrue((ROOT / asset).is_file())


class RepoSpecificTests(unittest.TestCase):

    def test_the_specification_names_which_suites_do_not_transfer(self):
        self.assertGreaterEqual(len(named_repo_specific()), 3)

    def test_suites_named_repo_specific_really_are_coupled(self):
        """Stops the table from listing everything as portable.

        If a suite named as repository-specific has no coupling, either it
        was portable all along or the coupling pattern stopped matching,
        and both make the table's exclusions meaningless.
        """
        for suite in named_repo_specific():
            with self.subTest(suite=suite):
                self.assertNotEqual(
                    coupling_in(f"tests/golden/{suite}"), [],
                    msg=f"{suite} is excluded as repository-specific but shows "
                        "no coupling to this repository")

    def test_the_two_lists_do_not_overlap(self):
        unchanged = {pathlib.Path(a).name for a in claimed_unchanged()}
        self.assertEqual(unchanged & set(named_repo_specific()), set())


class VocabularyTests(unittest.TestCase):

    def test_spec_maps_the_earlier_terms_to_the_frozen_ones(self):
        for earlier, golden in (("REFUTED", "CONTRADICTED"), ("NOT_EVALUATED", "NOT_TESTED")):
            with self.subTest(term=earlier):
                self.assertRegex(SPEC, rf"`{earlier}`\s*\|\s*`{golden}`")

    def test_the_mapping_targets_match_the_evaluator(self):
        """The spec must not invent a vocabulary the evaluator rejects."""
        evaluator = (ROOT / "scripts" / "golden" / "evaluate_run.py").read_text()
        frozen = re.search(r"HYPOTHESIS_STATUS = \((.*?)\)", evaluator, re.S).group(1)
        for golden in ("CONTRADICTED", "NOT_TESTED"):
            with self.subTest(term=golden):
                self.assertIn(f'"{golden}"', frozen)


class EntryCriteriaTests(unittest.TestCase):

    def test_criteria_are_enumerated(self):
        criteria = re.findall(r"^\d+\. ", SPEC.split("## Entry criteria")[1], re.M)
        self.assertGreaterEqual(len(criteria), 6)

    def test_criteria_cover_the_two_prose_satisfiable_rules(self):
        section = SPEC.split("## Entry criteria")[1].lower()
        self.assertIn("independent reproduction", section)
        self.assertIn("invoked by a workflow", section)


class AdaptationBoundaryTests(unittest.TestCase):
    def test_spec_pins_a_reviewed_source_commit(self):
        self.assertRegex(SPEC, r"`[0-9a-f]{40}`")
        for pull_request in ("#234", "#235", "#236"):
            self.assertIn(pull_request, SPEC)

    def test_spec_names_service_specific_operational_constraints(self):
        for constraint in ("authentication", "operating systems", "telemetry delay", "recovery", "cleanup"):
            with self.subTest(constraint=constraint):
                self.assertIn(constraint, SPEC.lower())

    def test_aca_patterns_do_not_authorize_predicate_copying(self):
        aca = SPEC.split("Reviewed Azure Container Apps", 1)[1]
        self.assertIn("predicates are not", aca)
        self.assertIn("mutation-tested", aca)


if __name__ == "__main__":
    unittest.main(verbosity=2)
