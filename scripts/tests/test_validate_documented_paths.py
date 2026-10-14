from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validate_documented_paths import PATH_EXCEPTIONS, validate_tree


class DocumentedPathValidationTests(unittest.TestCase):
    temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
    root: Path = Path()

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "docs").mkdir()

    def write_doc(self, body: str) -> None:
        _ = (self.root / "docs" / "guide.md").write_text(body, encoding="utf-8")

    def test_rejects_missing_inline_and_github_targets(self) -> None:
        # Given inline and main-branch links whose targets are absent
        self.write_doc(
            "\n".join(
                (
                    "[runner](../labs/example/run.py)",
                    "[file](https://github.com/yeongseon/azure-app-service-practical-guide/blob/main/labs/example/run.py)",
                    "[folder](https://github.com/yeongseon/azure-app-service-practical-guide/tree/main/labs/example)",
                    "",
                )
            )
        )

        # When the checkout is validated
        findings = validate_tree(self.root)

        # Then every missing target is reported according to its link form
        self.assertEqual(
            [finding.kind for finding in findings],
            ["relative-link", "github-main-link", "github-main-link"],
        )

    def test_rejects_missing_reference_style_target_at_definition_and_usage(self) -> None:
        # Given one used and one unused reference definition with missing targets
        self.write_doc(
            "\n".join(
                (
                    "Read the [runner][run-ref].",
                    "",
                    "[run-ref]: ../labs/example/run.py?mode=fast#usage",
                    "[unused-ref]: ../labs/example/unused.py",
                    "",
                )
            )
        )

        # When the checkout is validated
        findings = validate_tree(self.root)

        # Then the usage and both definitions are independently checked
        self.assertEqual(
            [(finding.line, finding.kind) for finding in findings],
            [
                (1, "reference-link"),
                (3, "reference-definition"),
                (4, "reference-definition"),
            ],
        )

    def test_rejects_undefined_reference_style_usage(self) -> None:
        # Given a reference-style usage with no definition
        self.write_doc("Read the [runner][missing-ref].\n")

        # When the checkout is validated
        findings = validate_tree(self.root)

        # Then the missing definition is reported
        self.assertEqual(
            [(finding.reference, finding.kind) for finding in findings],
            [("missing-ref", "reference-definition")],
        )

    def test_rejects_missing_local_html_href_and_src(self) -> None:
        # Given local HTML attributes pointing to absent repository files
        self.write_doc(
            "\n".join(
                (
                    '<a href="../labs/example/run.py?mode=fast#usage">runner</a>',
                    '<img src="../assets/missing.png#preview" alt="missing">',
                    "",
                )
            )
        )

        # When the checkout is validated
        findings = validate_tree(self.root)

        # Then both local HTML targets are rejected
        self.assertEqual(
            [(finding.reference, finding.kind) for finding in findings],
            [
                ("../labs/example/run.py?mode=fast#usage", "html-link"),
                ("../assets/missing.png#preview", "html-link"),
            ],
        )

    def test_rejects_missing_commands_only_in_executable_fences(self) -> None:
        # Given supported command forms in an executable shell fence
        self.write_doc(
            "\n".join(
                (
                    "```bash",
                    "python3 labs/example/run.py execute",
                    "./labs/example/trigger.sh",
                    "az deployment group create --template-file labs/example/main.bicep",
                    "```",
                    "",
                )
            )
        )

        # When the checkout is validated
        findings = validate_tree(self.root)

        # Then each missing command reference is rejected
        self.assertEqual(
            [finding.reference for finding in findings],
            [
                "labs/example/run.py",
                "labs/example/trigger.sh",
                "labs/example/main.bicep",
            ],
        )

    def test_ignores_links_in_all_fences_and_commands_in_non_executable_fences(self) -> None:
        # Given links in example fences and command-shaped lines in unsupported languages
        self.write_doc(
            "\n".join(
                (
                    "````markdown",
                    "[missing](../labs/nope/run.py)",
                    "````",
                    "~~~html",
                    '<a href="../labs/nope/run.py">missing</a>',
                    "~~~",
                    *(
                        line
                        for language in ("console", "shell", "zsh", "terminal", "kusto")
                        for line in (
                            f"```{language}",
                            "python3 labs/nope/run.py",
                            "```",
                        )
                    ),
                    "",
                )
            )
        )

        # When the checkout is validated
        findings = validate_tree(self.root)

        # Then examples and non-executable language content are ignored
        self.assertEqual(findings, ())

    def test_accepts_tables_and_query_or_anchor_suffixes_for_existing_targets(self) -> None:
        # Given existing targets linked from a Markdown table with URL suffixes
        lab = self.root / "labs" / "example"
        lab.mkdir(parents=True)
        (lab / "run.py").touch()
        self.write_doc(
            "\n".join(
                (
                    "| Form | Target |",
                    "|---|---|",
                    "| Inline | [runner](../labs/example/run.py?mode=fast#usage) |",
                    "| Reference | [runner][run-ref] |",
                    '| HTML | <a href="../labs/example/run.py?raw=1#L1">runner</a> |',
                    "",
                    "[run-ref]: ../labs/example/run.py?mode=slow#reference",
                    "",
                )
            )
        )

        # When the checkout is validated
        findings = validate_tree(self.root)

        # Then suffixes do not affect filesystem resolution and tables parse normally
        self.assertEqual(findings, ())

    def test_accepts_every_registered_exception(self) -> None:
        # Given one documented command path for every explicit exception
        body = "".join(
            f"```bash\npython3 {exception.example}\n```\n" for exception in PATH_EXCEPTIONS
        )
        self.write_doc(body)

        # When the checkout is validated
        findings = validate_tree(self.root)

        # Then every reviewed exception is honored
        self.assertEqual(findings, ())

    def test_rejects_neighboring_typo_and_unregistered_future_path(self) -> None:
        # Given paths close to registered generated, placeholder, and future exceptions
        self.write_doc(
            "\n".join(
                (
                    "```bash",
                    "python3 artifacts/rawish/evidence.json",
                    "python3 labs/missing/<app-nam>/run.py",
                    "python3 labs/windows-java-httpplatformhandler-timeout/artifacts-sanitized/stage-1/result.json",
                    "```",
                    "",
                )
            )
        )

        # When the checkout is validated
        findings = validate_tree(self.root)

        # Then exceptions do not hide neighboring or unregistered paths
        self.assertEqual(
            [finding.reference for finding in findings],
            [
                "artifacts/rawish/evidence.json",
                "labs/missing/<app-nam>/run.py",
                "labs/windows-java-httpplatformhandler-timeout/artifacts-sanitized/stage-1/result.json",
            ],
        )


if __name__ == "__main__":
    _ = unittest.main()
