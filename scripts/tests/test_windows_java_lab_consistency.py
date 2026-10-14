from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUIDE = Path(
    os.environ.get(
        "WINDOWS_JAVA_GUIDE",
        str(ROOT / "docs/troubleshooting/lab-guides/windows-java-httpplatformhandler-timeout.md"),
    )
)
LAB_ROOT = ROOT / "labs/windows-java-httpplatformhandler-timeout"
LAB_2 = LAB_ROOT / "lab-2-loopback-saturation"
DEPLOY = LAB_2 / "deploy.sh"


def bash_fences(markdown: str) -> tuple[str, ...]:
    return tuple(re.findall(r"```bash\n(.*?)```", markdown, flags=re.DOTALL))


def referenced_lab_scripts(markdown: str) -> set[Path]:
    """Return every `.sh` file the guide mentions, in fences or prose.

    A token with a slash is repository-relative; a bare name must exist
    somewhere under the Windows Java lab directory.
    """
    references: set[Path] = set()
    for token in re.findall(r"(?<![A-Za-z0-9_.-])[A-Za-z0-9_./-]+\.sh\b", markdown):
        if "/" in token:
            references.add(ROOT / token.removeprefix("./"))
            continue
        matches = sorted(LAB_ROOT.rglob(token))
        references.add(matches[0] if matches else LAB_2 / token)
    return references


class WindowsJavaLabConsistencyTests(unittest.TestCase):
    def test_lab_2_bash_fences_reference_existing_scripts(self) -> None:
        # Given the published Lab 2 guide, including fences and prose
        guide = GUIDE.read_text(encoding="utf-8")

        # When repository-qualified and Lab 2-local script references are resolved
        missing = sorted(
            path.relative_to(ROOT).as_posix()
            for path in referenced_lab_scripts(guide)
            if not path.is_file()
        )

        # Then every documented script is present in the repository
        self.assertEqual([], missing)

    def test_missing_script_references_are_detected_in_fences_and_prose(self) -> None:
        # Given references to nonexistent scripts in each documented form
        mutated = (
            "```bash\nbash run-nonexistent-fence.sh --rate 1\n```\n"
            "Prose mentions nonexistent-prose.sh here and "
            "labs/windows-java-httpplatformhandler-timeout/lab-2-loopback-saturation/nonexistent-path.sh.\n"
        )

        # When the references are resolved
        missing = {
            path.name for path in referenced_lab_scripts(mutated) if not path.is_file()
        }

        # Then each class of reference is reported as missing
        self.assertEqual(
            {"run-nonexistent-fence.sh", "nonexistent-prose.sh", "nonexistent-path.sh"},
            missing,
        )

    def test_guide_uses_stage_zero_jar_source_from_deploy_script(self) -> None:
        # Given the published guide and retained Lab 2 deployment script
        guide = GUIDE.read_text(encoding="utf-8")
        deploy = DEPLOY.read_text(encoding="utf-8")
        jar_directory = re.search(r'JAR_DIR="\$\{SCRIPT_DIR}/(?P<path>[^"\n]+)"', deploy)
        self.assertIsNotNone(jar_directory)

        # When their application source paths are compared
        expected_source = "stage-0-config-discovery/app"

        # Then the guide builds the same Stage 0 application that Lab 2 deploys
        self.assertIn(expected_source, jar_directory.group("path"))
        self.assertIn(expected_source, guide)
        self.assertNotRegex(
            guide,
            r'cd\s+["\']?labs/windows-java-httpplatformhandler-timeout/lab-2-loopback-saturation/app',
        )

    def test_guide_and_script_deploy_jar_with_jar_type(self) -> None:
        # Given deployment commands in the guide and retained script
        guide = GUIDE.read_text(encoding="utf-8")
        deploy = DEPLOY.read_text(encoding="utf-8")
        guide_deploy = re.search(
            r"az webapp deploy \\\n(?P<command>(?:.*\n){1,8}?)```",
            guide,
        )
        script_deploy = re.search(
            r"az webapp deploy \\\n(?P<command>(?:.*\n){1,8}?)\s*echo",
            deploy,
        )
        self.assertIsNotNone(guide_deploy)
        self.assertIsNotNone(script_deploy)

        # When deployment types are compared
        guide_command = guide_deploy.group("command")
        script_command = script_deploy.group("command")

        # Then both select OneDeploy's JAR mode rather than ZIP extraction
        self.assertIn("--type jar", guide_command)
        self.assertIn("--type jar", script_command)
        self.assertNotIn("--type zip", guide_command)


if __name__ == "__main__":
    unittest.main()
