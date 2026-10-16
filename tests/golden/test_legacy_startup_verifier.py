from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "labs/deployment-succeeded-startup-failed/verify.sh"


class LegacyStartupVerifierTests(unittest.TestCase):
    def test_missing_evidence_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fake_az = Path(temporary) / "az"
            fake_az.write_text(
                textwrap.dedent(
                    """\
                    #!/bin/bash
                    if [[ "$*" == *"workspace list"* ]]; then
                        printf 'workspace-id\\n'
                    elif [[ "$*" == *"tables[0].rows[0][0]"* ]]; then
                        printf '0\\n'
                    else
                        printf '[]\\n'
                    fi
                    """
                ),
                encoding="utf-8",
            )
            fake_az.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = f"{temporary}:{env['PATH']}"

            result = subprocess.run(
                ["bash", str(VERIFIER), "rg-fixture"],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No startup-failure evidence", result.stdout)


if __name__ == "__main__":
    unittest.main()
