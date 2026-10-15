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
    return re.findall(r"`(test_\w+\.py)`", SPEC.split("authors itself")[1])


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


class TransferTableTests(unittest.TestCase):

    def test_the_table_was_parsed(self):
        """Guards every test below from passing on an empty list."""
        self.assertGreaterEqual(len(spec_rows()), 8)
        self.assertGreaterEqual(len(claimed_unchanged()), 7)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
