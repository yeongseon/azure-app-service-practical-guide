from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from validate_documented_paths import validate_tree


class DocumentedPathValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "docs").mkdir()

    def write_doc(self, body: str) -> None:
        (self.root / "docs" / "guide.md").write_text(body, encoding="utf-8")

    def test_rejects_missing_relative_link(self) -> None:
        # Given a documentation link to a repository-local file that is absent
        self.write_doc("[runner](../labs/example/run.py)\n")

        # When the checkout is validated
        findings = validate_tree(self.root)

        # Then the missing relative target is reported
        self.assertEqual([finding.kind for finding in findings], ["relative-link"])

    def test_rejects_missing_main_blob_and_tree_links(self) -> None:
        # Given main-branch links whose targets do not exist in this checkout
        self.write_doc(
            "[file](https://github.com/yeongseon/azure-app-service-practical-guide/blob/main/labs/example/run.py)\n"
            "[folder](https://github.com/yeongseon/azure-app-service-practical-guide/tree/main/labs/example)\n"
        )

        # When the checkout is validated
        findings = validate_tree(self.root)

        # Then both links are resolved against the working tree and rejected
        self.assertEqual(
            [finding.kind for finding in findings],
            ["github-main-link", "github-main-link"],
        )

    def test_rejects_missing_registered_command_paths(self) -> None:
        # Given supported command forms that name absent repository files
        self.write_doc(
            "```bash\n"
            "python3 labs/example/run.py execute\n"
            "./labs/example/trigger.sh\n"
            "az deployment group create --template-file labs/example/main.bicep\n"
            "```\n"
        )

        # When the checkout is validated
        findings = validate_tree(self.root)

        # Then each registered command reference is rejected
        self.assertEqual(
            [finding.reference for finding in findings],
            [
                "labs/example/run.py",
                "labs/example/trigger.sh",
                "labs/example/main.bicep",
            ],
        )

    def test_accepts_existing_targets_and_generated_artifacts(self) -> None:
        # Given existing link and command targets plus known generated outputs
        lab = self.root / "labs" / "example"
        lab.mkdir(parents=True)
        for name in ("run.py", "trigger.sh", "main.bicep"):
            (lab / name).touch()
        self.write_doc(
            "[runner](../labs/example/run.py)\n"
            "[lab](https://github.com/yeongseon/azure-app-service-practical-guide/tree/main/labs/example)\n"
            "```bash\n"
            "python3 labs/example/run.py --output artifacts/raw/evidence\n"
            "./labs/example/trigger.sh --env artifacts/.env\n"
            "az deployment group create --template-file labs/example/main.bicep\n"
            "```\n"
        )

        # When the checkout is validated
        findings = validate_tree(self.root)

        # Then checked-in targets pass and intentionally generated artifacts are ignored
        self.assertEqual(findings, ())

    def test_ignores_placeholders_and_external_or_anchor_links(self) -> None:
        # Given illustrative placeholders and links outside the repository
        self.write_doc(
            "[section](#next) [Learn](https://learn.microsoft.com/en-us/azure/app-service/)\n"
            "```bash\n"
            "az deployment group create --template-file labs/<name>/main.bicep\n"
            "```\n"
        )

        # When the checkout is validated
        findings = validate_tree(self.root)

        # Then non-concrete repository targets are outside this gate
        self.assertEqual(findings, ())


if __name__ == "__main__":
    unittest.main()
