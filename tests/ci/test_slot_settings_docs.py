"""Offline guard for documented `az webapp config appsettings set --slot-settings` usage.

`--slot-settings` takes space-separated NAME=VALUE pairs (or an @file); a bare
name is rejected by the CLI and gives the reader a false belief that a setting
is sticky. This is a static syntax check of the documented examples. It does not
execute any command and says nothing about live Azure behavior.
"""
from pathlib import Path
import shlex
import unittest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
SET_COMMAND = ("az", "webapp", "config", "appsettings", "set")
CANONICAL = DOCS / "operations" / "deployment-slots.md"
COMPACT = DOCS / "operations" / "deployment" / "slots-and-swap.md"


def bash_fences(text):
    """Yield (first_line_number, joined_command_lines) for each bash fence."""
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        if lines[index].strip().startswith("```bash"):
            start = index + 2
            body = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                body.append(lines[index].strip())
                index += 1
            yield start, body
        index += 1


def commands(body):
    """Join backslash-continued shell lines into whole command strings."""
    command = ""
    for line in body:
        if line.endswith("\\"):
            command += line[:-1] + " "
            continue
        command += line
        yield command
        command = ""
    if command:
        yield command


def set_options(command):
    """Return {option: [tokens]} for an appsettings-set command, else None."""
    tokens = shlex.split(command)
    if tuple(tokens[:5]) != SET_COMMAND:
        return None
    options, current = {}, None
    for token in tokens[5:]:
        if token.startswith("--") and "=" in token and token.split("=", 1)[0] in ("--settings", "--slot-settings"):
            current, first = token.split("=", 1)
            options.setdefault(current, []).append(first)
        elif token.startswith("-") and not token.startswith("-@"):
            current = token
            options.setdefault(current, [])
        elif current is not None:
            options[current].append(token)
    return options


def invalid_slot_settings(text):
    """Return human-readable problems for slot-settings usage in one document."""
    problems = []
    for start, body in bash_fences(text):
        for command in commands(body):
            if "appsettings set" not in command:
                continue
            options = set_options(command)
            if options is None or "--slot-settings" not in options:
                continue
            sticky = options["--slot-settings"]
            if not sticky:
                problems.append(f"line {start}: --slot-settings has no NAME=VALUE pair")
            bare = [token for token in sticky if "=" not in token and not token.startswith("@")]
            if bare:
                problems.append(f"line {start}: bare names without =VALUE: {', '.join(bare)}")
            plain_names = {token.split("=", 1)[0] for token in options.get("--settings", []) if "=" in token}
            sticky_names = {token.split("=", 1)[0] for token in sticky if "=" in token}
            redundant = sorted(plain_names & sticky_names)
            if redundant:
                problems.append(f"line {start}: same name under --settings and --slot-settings: {', '.join(redundant)}")
    return problems


class SlotSettingsDocumentationTests(unittest.TestCase):
    def test_checker_flags_the_original_bare_key_example(self):
        # Given: the invalid example that previously shipped in slots-and-swap.md.
        broken = (
            "```bash\n"
            "az webapp config appsettings set \\\n"
            "  --slot staging \\\n"
            "  --settings APP_ENVIRONMENT=staging API_BASE_URL=https://x.example \\\n"
            "  --slot-settings APP_ENVIRONMENT API_BASE_URL \\\n"
            "  --output json\n"
            "```\n"
        )

        # When: the checker inspects it.
        problems = invalid_slot_settings(broken)

        # Then: the bare keys are reported.
        self.assertTrue(any("bare names" in problem for problem in problems), problems)

    def test_checker_flags_equals_form_and_duplicate_names(self):
        # Given: --slot-settings=NAME with no value, and a name repeated under --settings.
        bare = "```bash\naz webapp config appsettings set --slot-settings=APP_ENV\n```\n"
        dup = "```bash\naz webapp config appsettings set --settings A=1 --slot-settings A=1\n```\n"

        # When / Then: both are reported.
        self.assertTrue(invalid_slot_settings(bare))
        self.assertTrue(any("same name" in p for p in invalid_slot_settings(dup)))

    def test_checker_accepts_name_value_pairs_and_file_references(self):
        # Given: supported forms, including a quoted value and an @file reference.
        valid = (
            "```bash\n"
            "az webapp config appsettings set \\\n"
            "  --slot-settings APP_ENVIRONMENT=staging \"API_BASE_URL=https://x.example\" @more.json \\\n"
            "  --output none\n"
            "```\n"
        )

        # When / Then: nothing is reported.
        self.assertEqual(invalid_slot_settings(valid), [])

    def test_every_documented_slot_settings_example_uses_name_value_pairs(self):
        # Given: every Markdown page under docs/.
        checked = 0
        problems = []
        for path in sorted(DOCS.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            if "--slot-settings" not in text:
                continue
            checked += 1

            # When: its bash examples are inspected.
            problems.extend(f"{path.relative_to(ROOT)}: {problem}" for problem in invalid_slot_settings(text))

        # Then: the scan was not vacuous and no example uses a bare key.
        self.assertGreater(checked, 0)
        self.assertEqual(problems, [])

    def test_slot_pages_link_to_each_other_and_read_back_the_flag_without_values(self):
        # Given: the canonical operations page and the compact deployment page.
        canonical = CANONICAL.read_text(encoding="utf-8")
        compact = COMPACT.read_text(encoding="utf-8")

        # When / Then: they link both ways and both read back slotSetting.
        self.assertIn("deployment/slots-and-swap.md", canonical)
        self.assertIn("../deployment-slots.md#configure-slot-specific-settings", compact)
        for text in (canonical, compact):
            self.assertIn("slotSetting:slotSetting", text)
            self.assertNotIn("value:value", text)


if __name__ == "__main__":
    unittest.main()
