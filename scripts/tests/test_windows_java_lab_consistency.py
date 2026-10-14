from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "docs/troubleshooting/lab-guides/windows-java-httpplatformhandler-timeout.md"
DEPLOY = ROOT / "labs/windows-java-httpplatformhandler-timeout/lab-2-loopback-saturation/deploy.sh"


class WindowsJavaLabConsistencyTests(unittest.TestCase):
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
