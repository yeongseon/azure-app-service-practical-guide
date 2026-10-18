from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = ROOT / ".github/workflows/e2e-azure.yml"


class AzureE2EWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    def _job(self, name: str) -> str:
        marker = f"  {name}:\n"
        start = self.workflow_text.index(marker) + len(marker)
        lines = self.workflow_text[start:].splitlines(keepends=True)
        body: list[str] = []
        for line in lines:
            if line.startswith("  ") and not line.startswith("    "):
                break
            body.append(line)
        return "".join(body)

    def _step(self, job_name: str, step_name: str) -> str:
        job = self._job(job_name)
        marker = f"      - name: {step_name}\n"
        start = job.index(marker) + len(marker)
        return job[start:].split("      - name:", maxsplit=1)[0]

    def _run_ttl_sweep(self, gh_program: str, python_program: str) -> subprocess.CompletedProcess[str]:
        step = self._step("ttl-sweep", "Delete only owner-tagged groups with expired TTL")
        command = textwrap.dedent(step.split("        run: |\n", maxsplit=1)[1])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            for name, program in (("gh", gh_program), ("python3", python_program)):
                executable = bin_dir / name
                executable.write_text(program, encoding="utf-8")
                executable.chmod(0o755)
            environment = os.environ.copy()
            environment.update({
                "PATH": f"{bin_dir}:{environment['PATH']}",
                "RUNNER_TEMP": str(root),
                "GITHUB_REPOSITORY": "example/repository",
            })
            return subprocess.run(
                ["bash", "-c", command],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_first_job_restricts_ref_and_workflow_ref_to_main(self) -> None:
        jobs = self.workflow_text.split("jobs:\n", maxsplit=1)[1]
        self.assertTrue(jobs.startswith("  validate-context:\n"))
        context = self._job("validate-context")
        self.assertIn("github.ref == 'refs/heads/main'", context)
        self.assertIn("github.workflow_ref", context)
        self.assertIn("@refs/heads/main", context)

    def test_every_oidc_job_depends_on_context_validation(self) -> None:
        privileged = {name for name in ("scenario-a", "cleanup", "ttl-sweep") if "id-token: write" in self._job(name)}
        self.assertTrue(privileged)
        for name in privileged:
            self.assertIn("validate-context", self._job(name), msg=name)

    def test_ttl_is_validated_before_any_oidc_job(self) -> None:
        context = self._job("validate-context")
        self.assertIn("validate-ttl", context)
        self.assertIn("inputs.ttl_hours", context)

    def test_resource_group_name_is_derived_from_run_identity(self) -> None:
        inputs = self.workflow_text.split("    inputs:\n", maxsplit=1)[1].split("\npermissions:", maxsplit=1)[0]
        self.assertNotIn("resource_group:", inputs)
        self.assertIn("rg-golden-e2e-${{ github.run_id }}-${{ github.run_attempt }}", self.workflow_text)

    def test_cleanup_result_is_sanitized_and_uploaded(self) -> None:
        cleanup_text = self._job("cleanup")
        self.assertIn("cleanup-result.json", cleanup_text)
        self.assertIn("scan-sanitized", cleanup_text)
        self.assertIn("actions/upload-artifact", cleanup_text)
        self.assertIn("GITHUB_STEP_SUMMARY", cleanup_text)
        self.assertIn("id: cleanup-sanitize", cleanup_text)
        self.assertIn("id: cleanup-scan", cleanup_text)
        self.assertIn("steps.cleanup-sanitize.outcome == 'success'", cleanup_text)
        self.assertIn("steps.cleanup-scan.outcome == 'success'", cleanup_text)
        self.assertIn("Require sanitized cleanup artifact", cleanup_text)

        upload = self._step("cleanup", "Upload sanitized cleanup result")
        self.assertIn(
            "if: always() && steps.cleanup-sanitize.outcome == 'success' && steps.cleanup-scan.outcome == 'success'",
            upload,
        )
        fallback = self._step("cleanup", "Require sanitized cleanup artifact")
        self.assertIn(
            "if: always() && (steps.cleanup-sanitize.outcome != 'success' || steps.cleanup-scan.outcome != 'success')",
            fallback,
        )

    def test_target_validation_requires_helpers_before_oidc_jobs(self) -> None:
        validation = self._step(
            "validate-target", "Require an immutable commit on this repository main history"
        )

        self.assertTrue(validation.startswith("        id: target\n"))
        self.assertTrue(validation.endswith('          echo "sha=$sha" >> "$GITHUB_OUTPUT"\n\n'))

    def test_ttl_sweep_rechecks_transitioned_run_before_deletion(self) -> None:
        gh_program = """#!/usr/bin/env bash
set -euo pipefail
if [[ "$*" == *"/runs?per_page=100"* ]]; then
  printf '999-2\\n'
elif [[ "$*" == *"/runs/999/attempts/2"* ]]; then
  printf 'in_progress\\n'
else
  exit 99
fi
"""
        python_program = """#!/usr/bin/env bash
set -euo pipefail
if [[ "$*" == *" sweep "* ]]; then
  candidates="${@: -1}"
  printf 'rg-golden-e2e-999-2\\n' > "$candidates"
  exit 0
fi
printf 'delete-called\\n' >> "$RUNNER_TEMP/delete.log"
"""

        result = self._run_ttl_sweep(gh_program, python_program)

        self.assertNotEqual(result.returncode, 0)

    def test_ttl_sweep_inventory_includes_every_noncompleted_status(self) -> None:
        gh_program = """#!/usr/bin/env bash
set -euo pipefail
test "$3" = "/repos/example/repository/actions/workflows/e2e-azure.yml/runs?per_page=100"
test "$5" = '.workflow_runs[] | select(.status != "completed") | "\\(.id)-\\(.run_attempt)"'
declare -A runs=([101]=queued [102]=in_progress [103]=waiting [104]=pending [105]=requested)
for id in "${!runs[@]}"; do
  test "${runs[$id]}" != completed
done
printf '101-1\\n102-1\\n103-1\\n104-1\\n105-1\\n'
"""
        python_program = """#!/usr/bin/env bash
set -euo pipefail
active=''
candidates=''
while (($#)); do
  case "$1" in
    --active-run-ids-file) active="$2"; shift 2 ;;
    --candidates-file) candidates="$2"; shift 2 ;;
    *) shift ;;
  esac
done
diff -u <(printf '101-1\\n102-1\\n103-1\\n104-1\\n105-1\\n') "$active"
: > "$candidates"
"""

        result = self._run_ttl_sweep(gh_program, python_program)

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
