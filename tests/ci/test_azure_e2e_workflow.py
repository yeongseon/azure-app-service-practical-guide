from __future__ import annotations

import os
import re
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = ROOT / ".github/workflows/e2e-azure.yml"


class AzureE2EWorkflowTests(unittest.TestCase):
    workflow_text: str = ""

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
        self.assertIn('echo "sha=$sha" >> "$GITHUB_OUTPUT"', validation)

    def _git(self, cwd: Path, *args: str) -> str:
        environment = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
        return subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
            cwd=cwd, env=environment, check=True, capture_output=True, text=True,
        ).stdout.strip()

    def _checkout_like_validate_target(self, root: Path) -> tuple[Path, dict[str, str]]:
        upstream, work = root / "upstream.git", root / "work"
        self._git(root, "init", "--quiet", "--bare", "-b", "main", str(upstream))
        self._git(root, "init", "--quiet", "-b", "main", str(work))
        shas: dict[str, str] = {}

        def commit(name: str) -> None:
            (work / name).write_text(name, encoding="utf-8")
            self._git(work, "add", name)
            self._git(work, "commit", "--quiet", "-m", name)
            shas[name] = self._git(work, "rev-parse", "HEAD")

        commit("older")
        commit("newer")
        commit("tip")
        self._git(work, "checkout", "--quiet", "-b", "side", shas["older"])
        commit("side")
        self._git(work, "checkout", "--quiet", "main")
        self._git(work, "remote", "add", "origin", str(upstream))
        self._git(work, "push", "--quiet", "origin", "main", "side")
        checkout = self._job("validate-target").split("      - name:", maxsplit=1)[0]
        match = re.search(r"^\s+fetch-depth:\s*(\d+)\s*(?:#.*)?$", checkout, re.MULTILINE)
        depth = int(match.group(1)) if match else 1  # actions/checkout fetches one commit unless told otherwise
        clone = root / "clone"
        if depth:
            self._git(root, "clone", "--quiet", "--depth", str(depth), f"file://{upstream}", str(clone))
        else:
            self._git(root, "clone", "--quiet", str(upstream), str(clone))
        return clone, shas

    def _run_target_validation(self, clone: Path, target: str) -> tuple[subprocess.CompletedProcess[str], str]:
        step = self._step("validate-target", "Require an immutable commit on this repository main history")
        command = textwrap.dedent(step.split("        run: |\n", maxsplit=1)[1])
        bin_dir = clone.parent / "bin"
        bin_dir.mkdir(exist_ok=True)
        helper = bin_dir / "python3"
        helper.write_text('#!/bin/bash\n[ "$2" = validate-target ] && echo "$3"\nexit 0\n', encoding="utf-8")
        helper.chmod(0o755)
        output = clone.parent / "github-output"
        output.write_text("", encoding="utf-8")
        environment = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "TARGET_COMMIT": target,
            "GITHUB_OUTPUT": str(output),
        }
        result = subprocess.run(
            ["bash", "-c", command], cwd=clone, env=environment, capture_output=True, text=True, check=False,
        )
        return result, output.read_text(encoding="utf-8")

    def test_target_validation_accepts_a_reviewed_commit_older_than_the_tip(self) -> None:
        # Given: a checkout made the way the validate-target job makes it, and a commit that is on main but not its tip.
        with tempfile.TemporaryDirectory() as temporary:
            clone, shas = self._checkout_like_validate_target(Path(temporary))
            # When: the validation step runs for the older commit and for the tip.
            older, older_output = self._run_target_validation(clone, shas["older"])
            tip, tip_output = self._run_target_validation(clone, shas["tip"])
            # Then: both are accepted and published as the target.
            self.assertEqual(older.returncode, 0, msg=older.stderr)
            self.assertEqual(older_output, f"sha={shas['older']}\n")
            self.assertEqual(tip.returncode, 0, msg=tip.stderr)
            self.assertEqual(tip_output, f"sha={shas['tip']}\n")

    def test_target_validation_rejects_a_commit_that_is_not_on_main_history(self) -> None:
        # Given: a commit on a side branch that was never merged into main.
        with tempfile.TemporaryDirectory() as temporary:
            clone, shas = self._checkout_like_validate_target(Path(temporary))
            # When: the validation step runs for it.
            result, output = self._run_target_validation(clone, shas["side"])
            # Then: it fails and publishes no target.
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output, "")

    def test_missing_oidc_configuration_blocks_before_azure_login(self) -> None:
        job = self._job("scenario-a")
        self.assertLess(job.index("id: oidc-config"), job.index("uses: azure/login"))
        step = self._step("scenario-a", "Require Azure OIDC configuration")
        command = textwrap.dedent(step.split("        run: |\n", maxsplit=1)[1])
        names = ("AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID")
        for missing in (None, *names):
            with self.subTest(missing=missing):
                # Given: the three values that the secrets resolve to, one of them empty as an unset secret is.
                environment = {key: value for key, value in os.environ.items() if key not in names}
                environment.update({name: "" if name == missing else "value" for name in names})
                # When: the step runs.
                result = subprocess.run(
                    ["bash", "-c", command], env=environment, capture_output=True, text=True, check=False,
                )
                # Then: it blocks with exit code 3 unless every value is present.
                self.assertEqual(result.returncode, 0 if missing is None else 3, msg=result.stderr)
                if missing is not None:
                    self.assertIn("BLOCKED", result.stderr)

    def test_every_failure_stage_writes_an_allowlisted_record(self) -> None:
        for stage in (
            "oidc-config",
            "oidc-login",
            "target-validation",
            "provisioning",
            "deployment",
            "runner-start",
            "runner-crash",
            "evaluation",
            "sanitize",
        ):
            with self.subTest(stage=stage):
                self.assertIn(stage, self.workflow_text)
        self.assertIn("write-failure", self.workflow_text)
        self.assertIn("failure-record.json", self.workflow_text)
        self.assertIn("target-failure-${{ github.run_id }}-${{ github.run_attempt }}", self.workflow_text)
        self.assertIn("sanitizer-failure-${{ github.run_id }}-${{ github.run_attempt }}", self.workflow_text)

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

    def test_ttl_sweep_inventory_reads_successive_pages(self) -> None:
        gh_program = """#!/usr/bin/env bash
set -euo pipefail
test "$1" = api
test "$2" = --paginate
test "$3" = "/repos/example/repository/actions/workflows/e2e-azure.yml/runs?per_page=100"
test "$4" = --jq
for page in 1 2; do
  printf 'page=%s\n' "$page" >> "$RUNNER_TEMP/gh-pages.log"
  if [[ "$page" = 1 ]]; then
    printf '101-1\n'
  else
    printf '202-2\n'
  fi
done
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
diff -u <(printf '101-1\n202-2\n') "$active"
: > "$candidates"
"""

        result = self._run_ttl_sweep(gh_program, python_program)

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
