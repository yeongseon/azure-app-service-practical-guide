#!/usr/bin/env python3
"""README claims must not outrun the evidence the repository actually holds.

The README previously advertised Troubleshooting as "Lab-validated" and
defined that status as "reproducible labs prove the guidance", while no lab
had been re-verified under the Golden evidence model and no independent
reproduction had been attempted. It also stated a lab count that had drifted
from the tree.

These tests pin the properties, not the wording: a stated count tracks the
directory it counts, and a status that asserts proof is only available once
something has been proven.
"""

import json
import pathlib
import re
import sys
import unittest

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[2]
README = (ROOT / "README.md").read_text()

#: Words that assert the labs have established the guidance is correct.
#: "Evidence-retained" deliberately is not one: retaining a capture is a
#: claim about custody, not about proof.
PROOF_WORDS = ("prove", "proves", "proven", "validated", "verified")


def lab_dirs():
    """Lab directories, excluding the shared harness.

    labs/_shared holds fixtures used by the labs and is not itself a lab,
    which is the same exclusion labs/golden-classification.json applies.
    """
    return sorted(
        d for d in (ROOT / "labs").iterdir()
        if d.is_dir() and d.name != "_shared"
    )


def attempted_reproductions():
    """Reproduction records that actually carry a replay run.

    A record exists for a scenario before anyone replays it, carrying
    NOT_ATTEMPTED; presence of the file is not evidence of a replay.
    """
    directory = ROOT / "evidence" / "reproductions"
    if not directory.is_dir():
        return []
    return [
        path for path in sorted(directory.glob("*.json"))
        if json.loads(path.read_text()).get("replay_run_id")
    ]


def completed_runs():
    """Runs each scenario declares it has actually executed.

    This previously read execution_status from the manifest templates,
    which are required to ship NOT_RUN because they are templates. The
    check therefore reported "nothing has run" no matter what had run,
    and let a stale README pass CI after two scenarios had executed
    against Azure. The classifications declare the runs instead.
    """
    runs = []
    for path in sorted((ROOT / "labs").glob("*/golden/evidence-classification.json")):
        for run_id in json.loads(path.read_text()).get("executed_runs") or []:
            runs.append((path.parent.parent.name, run_id))
    return runs


def status_legend():
    """The line defining what each status badge means."""
    for line in README.splitlines():
        if line.startswith("**Status legend**"):
            return line
    raise AssertionError("README no longer has a status legend to check")


class LabCountTests(unittest.TestCase):

    def test_readme_lab_count_matches_the_tree(self):
        match = re.search(r"(\d+) hands-on labs in `labs/`", README)
        self.assertIsNotNone(match, "README no longer states a lab count")
        self.assertEqual(
            int(match.group(1)), len(lab_dirs()),
            msg="the README lab count has drifted from labs/")

    def test_the_count_excludes_the_shared_harness(self):
        self.assertNotIn(ROOT / "labs" / "_shared", lab_dirs())

    def test_classification_covers_exactly_the_counted_labs(self):
        classified = {
            row["lab"] for row in
            json.loads((ROOT / "labs" / "golden-classification.json").read_text())["labs"]
        }
        self.assertEqual(classified, {d.name for d in lab_dirs()})


class ProofClaimTests(unittest.TestCase):

    def test_no_reproduction_has_been_attempted_yet(self):
        """Guards the tests below from passing for the wrong reason.

        Once a replay lands this fails, and the proof-claim tests must be
        re-decided against the evidence that then exists rather than
        silently continuing to forbid a claim that has become true.
        """
        self.assertEqual(
            attempted_reproductions(), [],
            msg="a reproduction now exists; re-decide what the README may claim")

    def test_the_legend_matches_whether_anything_has_run(self):
        """The claim must track the executed-run registry, both ways."""
        legend = status_legend().lower()
        if completed_runs():
            self.assertNotIn(
                "no lab has yet been re-verified", legend,
                msg="scenarios have run under the Golden model; the legend denies it")
        else:
            self.assertIn("no lab has yet been re-verified", legend)

    def test_legend_does_not_claim_the_labs_prove_the_guidance(self):
        legend = status_legend().lower()
        head = re.split(r"but (no lab|only)", legend)[0]
        for word in PROOF_WORDS:
            self.assertNotRegex(
                head, rf"\b{word}\b",
                msg=f"the legend asserts {word!r} while nothing has been "
                    "reproduced or run to completion")

    def test_no_status_claims_production_readiness(self):
        """Coverage of a topic is not evidence a reader can ship on it.

        The legend called Comprehensive sections production-ready. Being
        thorough and source-reviewed is a claim about the document; being
        production-ready is a claim about someone else's system, which this
        repository has no way to establish.
        """
        legend = status_legend().lower()
        for phrase in ("production-ready", "production ready"):
            self.assertNotIn(
                phrase, legend,
                msg="a status legend asserts production readiness the repository cannot evidence")

    def test_legend_states_what_is_missing(self):
        legend = status_legend().lower()
        self.assertIn("independently reproduced", legend)
        self.assertIn("golden evidence model", legend)

    def test_troubleshooting_row_carries_the_hedged_status(self):
        row = next(
            line for line in README.splitlines()
            if "/troubleshooting/" in line and line.startswith("|"))
        self.assertIn("Evidence-retained", row)

    def test_no_section_still_advertises_lab_validated(self):
        self.assertNotIn("Lab-validated", README)


if __name__ == "__main__":
    unittest.main(verbosity=2)
