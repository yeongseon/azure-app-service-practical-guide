#!/usr/bin/env python3
"""Execute Scenario C and capture what the Golden contract asserts on.

`trigger.sh` performs the swap and prints its findings as prose, which no
evaluator can read. It also never swaps back, so the one assertion about
rollback could never be satisfied by running it.

This runner performs the same swap, captures each observation as a file,
and then swaps back and captures again. It writes a run directory and
decides nothing: every verdict is left to `collect_scenario_c.py` and
`evaluate_run.py`. The run directory is written with exclusive-create
semantics so a second execution cannot overwrite an earlier one's
evidence.

Usage:
    python3 scripts/golden/run_scenario_c.py <resource_group> <app> \
        --output <dir outside the repository>

Exit codes: 0 captured, 2 the run could not be completed.
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.dont_write_bytecode = True

LAB = "slot-swap-config-drift"
SLOT = "staging"
#: How long to wait for a destination worker to restart after a swap.
#: A fixed sleep was tried first and produced a confident CONTRADICTED: at
#: 25 seconds the staging slot was still answering from the pre-swap
#: production process, whose environment describes the slot it came from.
#: Polling for the restart replaces guessing at the settle time.
RESTART_TIMEOUT_SECONDS = 240
RESTART_POLL_SECONDS = 10


class RunError(Exception):
    """The run could not be carried out."""


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def run_id() -> str:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{secrets.token_hex(6)}"


def command(directory: pathlib.Path, name: str, argv: list[str]) -> dict:
    """Run one command and persist its full invocation and result."""
    started = now()
    completed = subprocess.run(argv, capture_output=True, text=True)
    record = {
        "argv": argv,
        "started_at": started,
        "ended_at": now(),
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    (directory / f"{name}.json").write_text(json.dumps(record, indent=2))
    return record


def fetch_config(url: str) -> dict:
    """Read /config, recording a transport failure rather than raising.

    A slot that cannot be reached is a fact about the run, not a reason to
    abandon it; the collector treats an unusable capture as an absent
    observation and the evaluator answers INCONCLUSIVE.
    """
    try:
        with urllib.request.urlopen(f"{url}/config", timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return {"unreachable": str(exc)}


def await_restart(url: str, boundary: str, directory: pathlib.Path, name: str) -> dict:
    """Poll /config until the worker reports starting after `boundary`.

    Returns the last snapshot read, and a record of the wait, so a run
    that timed out is visible in the evidence rather than silently
    producing a stale observation. A timeout is not an error: the
    collector treats an unrestarted worker as unable to support the
    stickiness assertion, which is the honest outcome.
    """
    deadline = time.monotonic() + RESTART_TIMEOUT_SECONDS
    attempts = []
    snapshot = {}
    restarted = False
    while time.monotonic() < deadline:
        snapshot = fetch_config(url)
        start = snapshot.get("PROCESS_START_UTC")
        attempts.append({"at": now(), "process_start_utc": start})
        if start and boundary:
            try:
                if (datetime.datetime.fromisoformat(start)
                        > datetime.datetime.fromisoformat(boundary)):
                    restarted = True
                    break
            except ValueError:
                pass
        time.sleep(RESTART_POLL_SECONDS)
    (directory / f"{name}.json").write_text(json.dumps({
        "url": url,
        "boundary": boundary,
        "restarted": restarted,
        "attempts": attempts,
        "timeout_seconds": RESTART_TIMEOUT_SECONDS,
    }, indent=2))
    return snapshot


def collect_deployment_errors(resource_group: str, app: str, workspace: str,
                              directory: pathlib.Path) -> dict:
    """Query deployment error rows so the contract's last field is observable.

    Nothing queried these before, so deployment_error_count was absent on
    every run and the evaluation could never be better than INCONCLUSIVE.
    """
    query = (
        "AppServicePlatformLogs "
        "| where TimeGenerated > ago(1h) "
        "| where Level == 'Error' "
        "| project TimeGenerated, Level, Message "
        "| limit 100"
    )
    return command(directory, "console-query-0", [
        "az", "monitor", "log-analytics", "query",
        "--workspace", workspace,
        "--analytics-query", query,
        "--output", "json",
    ])


def swap(resource_group: str, app: str, directory: pathlib.Path, name: str,
         source: str, target: str) -> dict:
    return command(directory, name, [
        "az", "webapp", "deployment", "slot", "swap",
        "--resource-group", resource_group,
        "--name", app,
        "--slot", source,
        "--target-slot", target,
        "--output", "json",
    ])


def execute(resource_group: str, app: str, output: pathlib.Path,
            workspace: str | None = None) -> pathlib.Path:
    """Run the swap, the rollback, and capture both."""
    identifier = run_id()
    directory = output / identifier
    # Exclusive creation: a run may never write into an existing directory.
    directory.mkdir(parents=True, exist_ok=False)

    production_url = f"https://{app}.azurewebsites.net"
    staging_url = f"https://{app}-{SLOT}.azurewebsites.net"

    (directory / "run.json").write_text(json.dumps({
        "run_id": identifier,
        "started_at": now(),
        "resource_group": resource_group,
        "app": app,
        "scenario": LAB,
    }, indent=2))

    (directory / "prod-before.json").write_text(json.dumps(fetch_config(production_url), indent=2))
    (directory / "staging-before.json").write_text(json.dumps(fetch_config(staging_url), indent=2))

    swapped = swap(resource_group, app, directory, "swap", SLOT, "production")
    # The swap CLI returns after the platform has already recycled the
    # workers, so a worker that restarted as part of the swap started
    # BEFORE the command returned. Comparing against ended_at therefore
    # never matches and polls until timeout on a healthy run. The question
    # is whether the worker started after the swap began.
    boundary = swapped["started_at"]

    # Both sides must be read after their workers have restarted, or the
    # snapshot describes the slot the process came from.
    production_after = await_restart(production_url, boundary, directory, "prod-restart-wait")
    staging_after = await_restart(staging_url, boundary, directory, "staging-restart-wait")
    (directory / "prod-after.json").write_text(json.dumps(production_after, indent=2))
    (directory / "staging-after.json").write_text(json.dumps(staging_after, indent=2))

    # The step trigger.sh never performed. Without it the rollback
    # assertion cannot be satisfied by any run, only left absent.
    if swapped["exit_code"] == 0:
        rolled = swap(resource_group, app, directory, "swap-back", SLOT, "production")
        rollback_snapshot = await_restart(
            production_url, rolled["started_at"], directory, "rollback-restart-wait")
        (directory / "prod-after-rollback.json").write_text(
            json.dumps(rollback_snapshot, indent=2))

    if workspace:
        collect_deployment_errors(resource_group, app, workspace, directory)

    (directory / "run-complete.json").write_text(json.dumps({"ended_at": now()}, indent=2))
    return directory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource_group")
    parser.add_argument("app")
    parser.add_argument("--workspace", help="Log Analytics workspace GUID for the error query")
    parser.add_argument("--output", required=True,
                        help="Private evidence directory outside the repository")
    args = parser.parse_args()
    try:
        directory = execute(args.resource_group, args.app, pathlib.Path(args.output),
                            workspace=args.workspace)
    except (RunError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"RUN_DIR={directory}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
