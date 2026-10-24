"""Offline guard for the documented Always On plan-tier capability.

Microsoft Learn's App Service limits table marks Always On as supported on
Basic, Standard, Premium and Isolated plans, and not on Free or Shared. The
guide once contradicted itself (a limits-table "No" for Basic and a runtime page
saying "Standard and above"). This is a static consistency check of the guide's
own text; it neither reads Azure nor proves any SKU behavior.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
LIMITS = DOCS / "reference" / "platform-limits.md"

# "Always On ... Standard (tier) and above/or higher" within one sentence.
WRONG_FLOOR = re.compile(
    r"always[ -]?on[^.\n]{0,80}\bstandard\b(?:\s+(?:tier|plan|sku))?\s+(?:and|or)\s+(?:above|higher|up)",
    re.IGNORECASE,
)
EXPECTED = {"Free": "No", "Basic": "Yes", "Standard": "Yes", "Premium": "Yes"}


def always_on_by_tier(markdown):
    """Map the leading tier word of each row to its cell under the Always On column."""
    result, column = {}, None
    for line in markdown.splitlines():
        if not line.startswith("|"):
            column = None
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if "Always On" in cells:
            column = cells.index("Always On")
        elif column is not None and len(cells) > column:
            tier = re.sub(r"[*_`]", "", cells[0]).split()
            if tier:
                result[tier[0]] = cells[column]
    return result


class AlwaysOnTierDocumentationTests(unittest.TestCase):
    def test_pattern_flags_the_original_wrong_floor(self):
        # Given: the sentence that previously shipped in nodejs-runtime.md.
        original = 'Enable "Always On" (Standard tier and above) to keep the container loaded.'

        # When / Then: it is flagged, while the corrected wording is not.
        self.assertTrue(WRONG_FLOOR.search(original))
        self.assertFalse(WRONG_FLOOR.search('Enable "Always On" (Basic tier and above) to keep'))

    def test_limits_table_matches_the_documented_tiers(self):
        # Given: the guide's plan-limits table.
        # When: the Always On column is read per tier.
        actual = always_on_by_tier(LIMITS.read_text(encoding="utf-8"))

        # Then: Basic supports Always On and Free does not, matching Microsoft Learn.
        for tier, expected in EXPECTED.items():
            self.assertEqual(actual.get(tier), expected, f"{tier}: {actual}")

    def test_no_page_claims_standard_is_the_minimum_tier(self):
        # Given: every Markdown page under docs/.
        offenders = []
        for path in sorted(DOCS.rglob("*.md")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if WRONG_FLOOR.search(line):
                    offenders.append(f"{path.relative_to(ROOT)}:{number}")

        # Then: none states Standard as the Always On floor.
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
