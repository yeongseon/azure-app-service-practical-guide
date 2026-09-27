#!/usr/bin/env python3
"""Emit Golden-model evidence for Scenario C from captured slot configs.

`trigger.sh` already computes most of what this contract asserts on. It
prints the results as prose -- "Non-sticky FEATURE_FLAG swapped with code:
True" -- which no evaluator can read and no assertion can be checked
against. The computation was never the problem; the destination was.

This collector reads the same captures and emits them as named
observations, leaving every verdict to `evaluate_run.py`. It decides
nothing about whether a swap behaved correctly: it reports what the four
config snapshots show, and what they do not show it omits.

Expected run directory, all files as captured by the trigger:

    prod-before.json       production /config before the swap
    staging-before.json    staging /config before the swap
    prod-after.json        production /config after the swap
    staging-after.json     staging /config after the swap
    swap.json              the `az webapp deployment slot swap` invocation
    prod-after-rollback.json   optional, production /config after swapping back
    console-query-0.json       optional, deployment error rows

A capture that is absent leaves its field absent and named in
`incomplete_fields`, so the evaluator answers INCONCLUSIVE rather than
reading a fabricated value as a refutation. Two runs are needed to claim
`post_rollback_matches_pre_swap`; a run that never swapped back simply
does not support that assertion.

Usage:
    python3 scripts/golden/collect_scenario_c.py <run_dir> [--output PATH]

Exit codes: 0 evidence written, 2 the run directory is unusable.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.dont_write_bytecode = True

#: The lab this collector serves, declared so the alignment check can
#: associate the two without depending on this file's name.
LAB = "slot-swap-config-drift"

#: Settings the platform swaps with the code unless marked sticky.
NON_STICKY = "FEATURE_FLAG"
#: Settings marked slot-sticky, which stay with the slot across a swap.
STICKY = "DB_CONNECTION_STRING"


class CollectionError(Exception):
    """The run directory cannot support a Golden evidence document."""


def _read(path: pathlib.Path, required: bool = True):
    if not path.is_file():
        if required:
            raise CollectionError(f"required capture missing: {path.name}")
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise CollectionError(f"malformed capture {path.name}: {exc}") from exc


def swapped_with_code(prod_before, staging_before, prod_after, staging_after, key) -> bool:
    """True when a setting moved with the code in both directions.

    Both halves are required. A one-sided move means something other than
    a swap changed the value, so it is not evidence that the swap carried
    the setting.

    >>> swapped_with_code({"F": "a"}, {"F": "b"}, {"F": "b"}, {"F": "a"}, "F")
    True
    >>> swapped_with_code({"F": "a"}, {"F": "b"}, {"F": "b"}, {"F": "b"}, "F")
    False
    """
    return (prod_after.get(key) == staging_before.get(key)
            and staging_after.get(key) == prod_before.get(key))


def remained_with_slot(prod_before, staging_before, prod_after, staging_after, key) -> bool:
    """True when a setting stayed put on both slots across the swap.

    >>> remained_with_slot({"D": "p"}, {"D": "s"}, {"D": "p"}, {"D": "s"}, "D")
    True
    >>> remained_with_slot({"D": "p"}, {"D": "s"}, {"D": "s"}, {"D": "p"}, "D")
    False
    """
    return (prod_after.get(key) == prod_before.get(key)
            and staging_after.get(key) == staging_before.get(key))


def error_row_count(console) -> int:
    """Count deployment-error rows in a raw log query result.

    >>> error_row_count(None) is None
    True
    >>> error_row_count({"stdout": "[]"})
    0
    >>> error_row_count({"stdout": '[{"Level": "Error"}]'})
    1
    """
    if console is None:
        return None
    try:
        rows = json.loads(console.get("stdout") or "[]")
    except json.JSONDecodeError:
        return 0
    if not isinstance(rows, list):
        return 0
    return sum(1 for row in rows if "error" in json.dumps(row).lower())


def collect(run_dir) -> dict:
    """Build a Golden evidence document from one captured swap."""
    run_dir = pathlib.Path(run_dir)
    run = _read(run_dir / "run.json")

    prod_before = _read(run_dir / "prod-before.json")
    staging_before = _read(run_dir / "staging-before.json")
    prod_after = _read(run_dir / "prod-after.json")
    staging_after = _read(run_dir / "staging-after.json")
    swap = _read(run_dir / "swap.json")
    rollback = _read(run_dir / "prod-after-rollback.json", required=False)
    console = _read(run_dir / "console-query-0.json", required=False)

    start_before = prod_before.get("PROCESS_START_UTC")
    start_after = prod_after.get("PROCESS_START_UTC")
    restart_observed = (
        None if start_before is None or start_after is None
        else start_before != start_after)

    observations = {
        "swap_exit_code": swap.get("exit_code"),
        "production_restart_observed": restart_observed,
        "non_sticky_feature_flag_swapped": swapped_with_code(
            prod_before, staging_before, prod_after, staging_after, NON_STICKY),
        "sticky_db_connection_remained": remained_with_slot(
            prod_before, staging_before, prod_after, staging_after, STICKY),
        "production_config_changed": prod_after != prod_before,
        "deployment_error_count": error_row_count(console),
        # A rollback that never happened cannot match anything. Claiming
        # otherwise would turn an unperformed step into supporting evidence.
        "post_rollback_matches_pre_swap": (
            None if rollback is None else rollback == prod_before),
    }

    incomplete = sorted(key for key, value in observations.items() if value is None)
    for key in incomplete:
        del observations[key]

    return {
        "run_id": run["run_id"],
        "captured_at": run["started_at"],
        "observations": observations,
        "collector": "scripts/golden/collect_scenario_c.py",
        "trust": "derived",
        "incomplete_fields": incomplete,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir")
    parser.add_argument("--output", help="Where to write evidence.json")
    args = parser.parse_args()
    try:
        evidence = collect(args.run_dir)
    except CollectionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(evidence, indent=2) + "\n"
    if args.output:
        pathlib.Path(args.output).write_text(text)
        print(f"evidence written to {args.output}")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
