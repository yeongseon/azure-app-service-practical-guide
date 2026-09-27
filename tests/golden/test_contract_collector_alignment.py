#!/usr/bin/env python3
"""A contract may not assert on fields nothing can produce, silently.

Scenario B declared five assertions and its collector emitted five
entirely different keys. The sets did not intersect, so a real run would
have returned INCONCLUSIVE on every assertion while the contract looked
complete and its suite passed. The evidence classification named one
missing collector when all five were missing.

A declared-but-uncollectable field is legitimate: a contract can state
what a future collector must produce. What is not legitimate is leaving
that unsaid, because a reader cannot then tell an aspirational contract
from a runnable one. This pins the disclosure, not the gap.
"""

import json
import pathlib
import re
import sys
import unittest

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[2]


def scenarios():
    """(lab_name, manifest, classification) for every lab with a contract."""
    found = []
    for manifest_path in sorted((ROOT / "labs").glob("*/golden/manifest.template.json")):
        lab = manifest_path.parent.parent
        classification_path = lab / "golden" / "evidence-classification.json"
        if not classification_path.is_file():
            continue
        found.append((
            lab.name,
            json.loads(manifest_path.read_text()),
            json.loads(classification_path.read_text()),
        ))
    return found


def emitted_fields(lab_name):
    """Keys any collector in the lab writes into an evidence document.

    Read from the shell collectors' JSON heredocs. This is deliberately
    textual: the point is to compare what the scripts actually write
    against what the contract claims, without executing Azure.
    """
    fields = set()
    sources = list((ROOT / "labs" / lab_name).glob("*.sh"))
    # A lab may also be served by a collector under scripts/golden/ that
    # re-expresses its captures under the contract's names. Scenario A is
    # collected that way, from a run directory its runner already produced.
    for collector in sorted((ROOT / "scripts/golden").glob("collect_*.py")):
        declared = re.search(r'^LAB = "([^"]+)"', collector.read_text(), re.M)
        if declared and declared.group(1) == lab_name:
            sources.append(collector)
    for path in sorted(sources):
        text = path.read_text()
        for match in re.finditer(r'"([a-z][a-z0-9_]*)"\s*:', text):
            fields.add(match.group(1))
    return fields


class ContractCollectorAlignmentTests(unittest.TestCase):

    def test_some_scenarios_were_discovered(self):
        """Guards every test below from passing on an empty list."""
        self.assertGreaterEqual(len(scenarios()), 3)

    def test_uncollectable_fields_are_disclosed_in_known_gaps(self):
        for lab, manifest, classification in scenarios():
            declared = {a["field"] for a in manifest["assertions"]}
            missing = declared - emitted_fields(lab)
            if not missing:
                continue
            gaps = " ".join(classification.get("known_gaps") or []).lower()
            with self.subTest(lab=lab):
                self.assertTrue(
                    gaps,
                    msg=f"{lab} asserts on {sorted(missing)} which no collector emits, "
                        "and known_gaps is empty")
                # The disclosure must be honest about the scale of the gap:
                # naming one field while five are missing is what happened.
                if len(missing) == len(declared):
                    self.assertRegex(
                        gaps, r"no collector|not intersect|none of",
                        msg=f"{lab} has NO collectable field but known_gaps does not say so")

    def test_a_scenario_claiming_no_gaps_really_has_none(self):
        for lab, manifest, classification in scenarios():
            if classification.get("known_gaps"):
                continue
            declared = {a["field"] for a in manifest["assertions"]}
            with self.subTest(lab=lab):
                self.assertEqual(
                    declared - emitted_fields(lab), set(),
                    msg=f"{lab} lists no known gaps but asserts on fields nothing emits")

    def test_the_field_scanner_finds_real_keys(self):
        """Guards the comparison from passing because it scanned nothing."""
        fields = emitted_fields("snat-exhaustion")
        self.assertIn("http_total_sampled", fields)
        self.assertGreaterEqual(len(fields), 4)

    def test_a_collectable_contract_still_says_it_has_not_run(self):
        """Collectable is not the same as executed, and must not read as it.

        This replaced a test asserting Scenario B had no collectable field
        at all. That was true until a collector was written, at which point
        it failed and forced this re-decision rather than letting a stale
        claim survive. The durable property is that a contract which can
        now be collected still discloses that nothing has been collected.
        """
        for lab, manifest, classification in scenarios():
            declared = {a["field"] for a in manifest["assertions"]}
            if declared - emitted_fields(lab):
                continue  # not collectable yet; the earlier tests cover it
            # A manifest template always ships NOT_RUN because it is a
            # template, so it cannot say whether the scenario ever ran.
            # The classification declares that instead.
            if classification.get("executed_runs"):
                continue  # genuinely executed; nothing to disclose
            gaps = " ".join(classification.get("known_gaps") or []).lower()
            with self.subTest(lab=lab):
                self.assertRegex(
                    gaps, r"no run|has not been (deployed|executed)|not been run",
                    msg=f"{lab} is collectable and unrun, but says neither")

    def test_a_declared_run_is_a_real_run_identifier(self):
        """Guards executed_runs from being set to silence the check."""
        for lab, _, classification in scenarios():
            for run_id in classification.get("executed_runs") or []:
                with self.subTest(lab=lab, run=run_id):
                    self.assertRegex(
                        run_id, r"^\d{8}T\d{6}Z-[0-9a-f]{12}$",
                        msg="executed_runs must name a run the runner produced")

    def test_every_scenario_is_now_collectable(self):
        """Records the state this suite was built to change.

        If a contract ever stops being collectable, the disclosure tests
        above take over; this one states plainly that today none needs to.
        """
        for lab, manifest, _ in scenarios():
            declared = {a["field"] for a in manifest["assertions"]}
            with self.subTest(lab=lab):
                self.assertEqual(
                    declared - emitted_fields(lab), set(),
                    msg=f"{lab} declares fields no collector emits")


if __name__ == "__main__":
    unittest.main(verbosity=2)
