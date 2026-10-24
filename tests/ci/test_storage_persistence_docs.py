"""Offline guard: /home persistence is stated per hosting model, never as one universal rule.

Issue #255. A static check of the guide's own text; it reads no Azure resource and
proves no persistence behavior.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
LIMITS = (ROOT / "docs/reference/platform-limits.md").read_text(encoding="utf-8")
SECTION = LIMITS.split("## Storage and File System")[1].split("\n## ")[0]
MODELS = (
    "Windows, code (built-in)", "Linux, built-in runtime", "Windows custom container",
    "Linux custom container", "Run From Package", "Mounted Azure Storage (BYOS)",
)


def rows(section):
    out = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) == 5 and cells[0].startswith("**"):
            out[re.sub(r"[*]", "", cells[0])] = cells
    return out


class StoragePersistenceDocsTests(unittest.TestCase):
    def test_every_hosting_model_has_its_own_row_with_a_learn_source(self):
        table = rows(SECTION)
        for model in MODELS:
            with self.subTest(model=model):
                self.assertIn(model, table)
                self.assertIn("https://learn.microsoft.com/", table[model][4])

    def test_the_old_universal_rows_are_gone(self):
        self.assertNotIn("| **`/home`** | Persistent | Survives restarts and redeployments |", LIMITS)
        self.assertNotIn("Survives restarts and redeployments", LIMITS)

    def test_linux_custom_container_persistence_depends_on_the_setting_and_is_off_by_default(self):
        row = " ".join(rows(SECTION)["Linux custom container"])
        self.assertIn("WEBSITES_ENABLE_APP_SERVICE_STORAGE", row)
        self.assertIn("disabled by default", row)
        self.assertIn("count toward the plan's storage quota", row)

    def test_windows_custom_container_is_enabled_by_default_and_can_be_disabled(self):
        row = " ".join(rows(SECTION)["Windows custom container"])
        self.assertIn("enabled by default", row)
        self.assertIn("`false`", row)

    def test_run_from_package_is_read_only_and_byos_is_not_mounted_at_home(self):
        table = rows(SECTION)
        self.assertIn("read-only", " ".join(table["Run From Package"]))
        self.assertIn("`/home`", " ".join(table["Mounted Azure Storage (BYOS)"]))
        self.assertIn("not backed up", " ".join(table["Mounted Azure Storage (BYOS)"]))

    def test_restart_persistence_is_not_presented_as_a_retention_guarantee(self):
        self.assertIn("not a retention guarantee", SECTION)
        self.assertIn("[Not Proven]", SECTION)
        self.assertIn("Proof condition for your own app", SECTION)

    def test_existing_recipes_are_linked_not_duplicated(self):
        for target in (
            "../platform/run-from-package.md",
            "../language-guides/python/recipes/bring-your-own-storage.md",
            "../language-guides/nodejs/recipes/bring-your-own-storage.md",
        ):
            with self.subTest(target=target):
                self.assertIn(f"]({target})", SECTION)
                self.assertTrue((ROOT / "docs/reference" / target).resolve().is_file())

    def test_the_python_runtime_page_no_longer_claims_universal_persistence(self):
        text = (ROOT / "docs/language-guides/python/python-runtime.md").read_text(encoding="utf-8")
        self.assertNotIn("`/home` persists across restarts and deployments.", text)
        self.assertIn("WEBSITES_ENABLE_APP_SERVICE_STORAGE", text.split("## File System and Persistence")[1].split("\n## ")[0])


if __name__ == "__main__":
    unittest.main()
