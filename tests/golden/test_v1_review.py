#!/usr/bin/env python3
"""The Golden v1 review must be checkable against the tree it reviews.

A review is the easiest document in a repository to falsify, because every
status in it is a claim about work the reviewer did. Writing MET fifteen
times produces a green-looking artifact that nothing contradicts.

These tests re-derive the parts that are derivable. Counts are recomputed
from the items rather than read from the header, the two NOT_MET verdicts
are checked against the conditions that make them true, and the overall
verdict is required to follow from the items. The suite fails if the
review is made more flattering than the tree supports.
"""

import json
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[2]
REVIEW = json.loads((ROOT / "docs" / "reference" / "golden-v1-review.json").read_text())
ITEMS = REVIEW["items"]

STATUSES = ("MET", "PARTIAL", "NOT_MET")


def by_id(item_id):
    return next(item for item in ITEMS if item["id"] == item_id)


def attempted_reproductions():
    directory = ROOT / "evidence" / "reproductions"
    return [
        path for path in sorted(directory.glob("*.json"))
        if json.loads(path.read_text()).get("replay_run_id")
    ]


#: The three labs the epic designates Scenario A, B and C. Scenario B is
#: named explicitly because it carries no golden/ directory, so deriving the
#: scenario set from the classification file or from manifests on disk
#: silently omits it. An earlier version of this suite did exactly that, and
#: a cleanup script added to snat-exhaustion went unnoticed.
SCENARIO_LABS = (
    "deployment-succeeded-startup-failed",
    "snat-exhaustion",
    "slot-swap-config-drift",
)


def classified_golden():
    data = json.loads((ROOT / "labs" / "golden-classification.json").read_text())
    return [row["lab"] for row in data["labs"] if row["classification"] == "golden"]


def golden_labs():
    """Every lab the review speaks about when it says Golden scenario."""
    return sorted(set(SCENARIO_LABS) | set(classified_golden()))


class StructureTests(unittest.TestCase):

    def test_every_dod_item_is_present(self):
        self.assertEqual([item["id"] for item in ITEMS], list(range(1, 16)))

    def test_counts_are_recomputed_not_asserted(self):
        for status in STATUSES:
            with self.subTest(status=status):
                self.assertEqual(
                    REVIEW["counts"][status],
                    sum(1 for item in ITEMS if item["status"] == status),
                    msg=f"the {status} count disagrees with the items")
        self.assertEqual(REVIEW["counts"]["total"], len(ITEMS))

    def test_statuses_come_from_the_fixed_set(self):
        for item in ITEMS:
            with self.subTest(item=item["id"]):
                self.assertIn(item["status"], STATUSES)

    def test_every_item_cites_evidence(self):
        for item in ITEMS:
            with self.subTest(item=item["id"]):
                self.assertTrue(item["evidence"].strip())

    def test_anything_short_of_met_names_the_gap(self):
        for item in ITEMS:
            if item["status"] != "MET":
                with self.subTest(item=item["id"]):
                    self.assertTrue(
                        item.get("gap", "").strip(),
                        msg=f"item {item['id']} is {item['status']} without saying what is missing")

    def test_verify_commands_reference_files_that_exist(self):
        for item in ITEMS:
            for token in item["verify"].split():
                if token.endswith(".py") or token.endswith(".json"):
                    with self.subTest(item=item["id"], path=token):
                        self.assertTrue(
                            (ROOT / token).is_file(),
                            msg=f"item {item['id']} verifies with a path that does not exist")


class VerdictTests(unittest.TestCase):

    def test_verdict_follows_from_the_items(self):
        complete = all(item["status"] == "MET" for item in ITEMS)
        self.assertEqual(
            REVIEW["verdict"], "COMPLETE" if complete else "NOT_COMPLETE",
            msg="the verdict does not follow from the item statuses")

    def test_an_incomplete_review_lists_what_blocks_it(self):
        if REVIEW["verdict"] == "NOT_COMPLETE":
            self.assertTrue(REVIEW["blocking_for_v1"])

    def test_each_blocker_names_an_item_that_is_not_met(self):
        for blocker in REVIEW["blocking_for_v1"]:
            number = int(blocker.split(":")[0].replace("Item", "").strip())
            with self.subTest(item=number):
                self.assertNotEqual(by_id(number)["status"], "MET")


class GroundedVerdictTests(unittest.TestCase):
    """The two NOT_MET verdicts must match the tree, in both directions."""

    def test_reproduction_is_not_met_because_none_was_attempted(self):
        self.assertEqual(by_id(10)["status"], "NOT_MET")
        self.assertEqual(
            attempted_reproductions(), [],
            msg="a reproduction now exists, so item 10 must be re-decided")

    def test_the_scenario_set_is_wider_than_the_classification(self):
        """Guards golden_labs() against silently shrinking to the manifests."""
        self.assertIn("snat-exhaustion", golden_labs())
        self.assertGreaterEqual(len(golden_labs()), 3)

    def test_cleanup_is_not_met_because_golden_scenarios_lack_one(self):
        self.assertEqual(by_id(11)["status"], "NOT_MET")
        for lab in golden_labs():
            with self.subTest(lab=lab):
                self.assertFalse(
                    (ROOT / "labs" / lab / "cleanup.sh").exists(),
                    msg=f"{lab} now has a cleanup script, so item 11 must be re-decided")

    def test_scenarios_are_partial_because_nothing_has_run(self):
        self.assertEqual(by_id(9)["status"], "PARTIAL")
        for path in (ROOT / "labs").glob("*/golden/manifest.template.json"):
            with self.subTest(path=path.name):
                self.assertEqual(
                    json.loads(path.read_text())["execution_status"], "NOT_RUN",
                    msg="a manifest reports a run, so item 9 must be re-decided")

    def test_classification_is_met_and_covers_the_labs(self):
        self.assertEqual(by_id(13)["status"], "MET")
        classified = {
            row["lab"] for row in
            json.loads((ROOT / "labs" / "golden-classification.json").read_text())["labs"]
        }
        on_disk = {
            d.name for d in (ROOT / "labs").iterdir()
            if d.is_dir() and d.name != "_shared"
        }
        self.assertEqual(classified, on_disk)

    def test_a_gate_is_either_shown_to_have_run_or_disclosed_as_unrun(self):
        """Item 15 is about gates, so it may not be vague about them.

        This replaced a test that pinned the gate as unrun. That was true
        while mkdocs was unavailable locally, and it stopped being true when
        CI executed the strict build, at which point the test failed and the
        item was re-decided rather than left stale. The durable property is
        that the item either points at an execution or names what was skipped.
        """
        item = by_id(15)
        if item["status"] == "MET":
            self.assertNotIn(
                "NOT RUN", item.get("gap", "") + item["evidence"],
                msg="item 15 claims MET while still disclosing an unrun gate")
            self.assertRegex(
                item["evidence"].lower(), r"mkdocs|ci|checks? pass",
                msg="item 15 claims MET without naming the execution that proves it")
        else:
            self.assertTrue(item["gap"].strip())

    def test_the_strict_build_is_accounted_for_somewhere(self):
        """The gate most likely to catch a nav defect must not go unmentioned."""
        item = by_id(15)
        self.assertIn("mkdocs", (item["evidence"] + item.get("gap", "")).lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
