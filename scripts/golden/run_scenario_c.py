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
#: Seconds to let a swap settle before reading /config. A swap returns as
#: soon as the routing change is accepted; the worker may answer briefly
#: from the previous process.
SETTLE_SECONDS = 25


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


def execute(resource_group: str, app: str, output: pathlib.Path) -> pathlib.Path:
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
    time.sleep(SETTLE_SECONDS)

    (directory / "prod-after.json").write_text(json.dumps(fetch_config(production_url), indent=2))
    (directory / "staging-after.json").write_text(json.dumps(fetch_config(staging_url), indent=2))

    # The step trigger.sh never performed. Without it the rollback
    # assertion cannot be satisfied by any run, only left absent.
    if swapped["exit_code"] == 0:
        swap(resource_group, app, directory, "swap-back", SLOT, "production")
        time.sleep(SETTLE_SECONDS)
        (directory / "prod-after-rollback.json").write_text(
            json.dumps(fetch_config(production_url), indent=2))

    (directory / "run-complete.json").write_text(json.dumps({"ended_at": now()}, indent=2))
    return directory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource_group")
    parser.add_argument("app")
    parser.add_argument("--output", required=True,
                        help="Private evidence directory outside the repository")
    args = parser.parse_args()
    try:
        directory = execute(args.resource_group, args.app, pathlib.Path(args.output))
    except (RunError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"RUN_DIR={directory}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
