"""Offline guard for the classes and values on the platform-limits page.

Issue #253: the page once published universal numbers (128 MB request body, 8192
URL characters, 10,000 app settings, 30-90 day log retention) that no primary
source supports as App Service limits. This is a static check of the page's own
text: it neither reads Azure nor proves any limit.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PAGE = (ROOT / "docs/reference/platform-limits.md").read_text(encoding="utf-8")
CLASSES = {"[Documented]", "[Application or framework]", "[Measured]"}
RETIRED = ("128 MB", "8192 characters", "10,000", "30–90 days", "30-90 days", "[Requires verification]")


def tables(markdown):
    """Yield (header_cells, rows) for each pipe table, ignoring fenced code."""
    in_fence, block = False, []
    for line in markdown.splitlines() + [""]:
        if line.strip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and line.startswith("|"):
            block.append([cell.strip() for cell in line.strip().strip("|").split("|")])
            continue
        if len(block) >= 3:
            yield block[0], block[2:]
        block = []


def body_without_retirement_note(text):
    return re.sub(r"Earlier revisions of this page showed.*?\n", "", text)


class PlatformLimitsValueTests(unittest.TestCase):
    def test_no_retired_universal_number_is_published(self):
        text = body_without_retirement_note(PAGE)
        for value in RETIRED:
            with self.subTest(value=value):
                self.assertNotIn(value, text)

    def test_every_value_table_row_declares_a_known_class(self):
        seen = 0
        for header, rows in tables(PAGE):
            if "Class" not in header:
                continue
            column = header.index("Class")
            for row in rows:
                seen += 1
                with self.subTest(row=row[0]):
                    self.assertIn(row[column], CLASSES)
        self.assertGreaterEqual(seen, 10)

    def test_every_documented_row_cites_microsoft_learn(self):
        for header, rows in tables(PAGE):
            if "Class" not in header:
                continue
            column, source = header.index("Class"), header.index("Source")
            for row in rows:
                if row[column] == "[Documented]":
                    with self.subTest(row=row[0]):
                        self.assertIn("https://learn.microsoft.com/", row[source])

    def test_tier_maxima_match_the_documented_table(self):
        plan = next(rows for header, rows in tables(PAGE) if "Max instances" in header)
        by_tier = {re.sub(r"[*_`]", "", row[0]).split()[0]: row for row in plan}
        self.assertTrue(by_tier["Free"][1].startswith("1"))
        self.assertTrue(by_tier["Basic"][1].startswith("3"))
        self.assertTrue(by_tier["Standard"][1].startswith("10"))
        # Premium: 30 for v2/v3/v4 and 20 for v1 (not "30+").
        self.assertIn("30", by_tier["Premium"][1])
        self.assertIn("20 for Premium v1", by_tier["Premium"][1])
        self.assertNotIn("30+", by_tier["Premium"][1])

    def test_unpublished_values_are_named_and_not_numbered(self):
        section = PAGE.split("## Values this guide does not publish")[1].split("\n## ")[0]
        section = body_without_retirement_note(section).lower()
        for topic in ("request body", "url length", "app settings", "log retention"):
            with self.subTest(topic=topic):
                self.assertIn(topic, section)
        self.assertNotRegex(section, r"\b\d{3,}\b")


if __name__ == "__main__":
    unittest.main()
