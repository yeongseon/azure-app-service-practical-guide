#!/usr/bin/env python3
"""Emit Golden-model evidence for Scenario A from a completed run directory.

Scenario A grew two contract systems. `run.py` fixes its criteria in
`contract.json` and evaluates against them, while the Golden manifest
asserts on seven field names `run.py` never writes. The scenario had
therefore executed against Azure while its Golden manifest had never been
exercised, and nothing said so.

This collector closes that gap without a second deployment: it reads a run
directory `run.py` already produced and re-expresses its raw captures under
the names the Golden manifest declares. It computes nothing about cause and
decides nothing about the hypothesis -- every value here is read from a
capture, and the verdict is left to `evaluate_run.py`.

The collector retains exact status codes, probe timestamps, phase windows,
and exact fault-window rows naming ``wrong_module``. The only derived field is
``phase_order_valid``, recomputed from the retained phase and capture windows.

Usage:
    python3 scripts/golden/collect_scenario_a.py <run_dir> [--output PATH]

Exit codes: 0 evidence written, 2 the run directory is unusable.
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

sys.dont_write_bytecode = True

#: The lab this collector serves. Declared rather than inferred from the
#: filename, so the alignment check can associate the two without a
#: naming convention that silently breaks when either is renamed.
LAB = "deployment-succeeded-startup-failed"

PHASES = ("baseline", "fault", "recovery")


class CollectionError(Exception):
    """The run directory cannot support a Golden evidence document."""


def _read(path: pathlib.Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise CollectionError(f"required capture missing: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise CollectionError(f"malformed capture {path.name}: {exc}") from exc


def _timestamp(value: str) -> datetime.datetime:
    parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise CollectionError("capture timestamp requires a timezone")
    return parsed


def exact_import_error_rows(console: dict, fault: dict) -> list[dict]:
    raw = console.get("stdout") or "[]"
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        rows = []
    if not isinstance(rows, list):
        return []
    signature = "ModuleNotFoundError: No module named 'wrong_module'"
    started = _timestamp(fault["started_at"])
    ended = _timestamp(fault["ended_at"])
    retained = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        message = row.get("ResultDescription") or row.get("Msg")
        captured_at = row.get("TimeGenerated")
        if message != signature or not isinstance(captured_at, str):
            continue
        if started <= _timestamp(captured_at) <= ended:
            retained.append({"timestamp": captured_at, "signature": signature})
    return retained


def _probes(phase: dict) -> list[dict]:
    probes = phase.get("probes")
    if not isinstance(probes, list):
        return []
    return [
        {key: probe.get(key) for key in ("captured_at", "status", "exit_code")}
        for probe in probes if isinstance(probe, dict)
    ]


def phases_are_ordered(run: dict, phases: dict) -> bool:
    try:
        values = [
            _timestamp(run["started_at"]),
            _timestamp(phases["baseline"]["started_at"]),
            _timestamp(phases["baseline"]["ended_at"]),
            _timestamp(phases["fault"]["started_at"]),
            _timestamp(phases["fault"]["ended_at"]),
            _timestamp(phases["recovery"]["started_at"]),
            _timestamp(phases["recovery"]["ended_at"]),
            _timestamp(run["ended_at"]),
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise CollectionError(f"invalid phase window: {exc}") from exc
    return values == sorted(values)


def collect(run_dir) -> dict:
    """Build a Golden evidence document from one completed run directory."""
    run_dir = pathlib.Path(run_dir)
    run = _read(run_dir / "run.json")

    phases = {}
    for name in PHASES:
        phase_file = run_dir / name / "phase.json"
        if not phase_file.is_file():
            raise CollectionError(f"run has no {name} phase; it did not complete")
        phases[name] = _read(phase_file)

    fault = phases["fault"]
    console_file = run_dir / "console-query-0.json"
    console = _read(console_file) if console_file.is_file() else {"stdout": "[]"}

    exact_rows = exact_import_error_rows(console, fault)
    observations = {
        "baseline_status": phases["baseline"].get("status"),
        "deploy_exit_code": _read(run_dir / "deploy.json").get("exit_code"),
        "fault_startup_command": fault.get("startup"),
        "fault_config_readback": fault.get("config_readback"),
        "fault_status": fault.get("status"),
        "fault_import_error_signature": (
            exact_rows[0]["signature"] if exact_rows else None),
        "phase_order_valid": phases_are_ordered(run, phases),
        "recovery_status": phases["recovery"].get("status"),
        "phase_windows": {
            name: {key: phases[name].get(key) for key in ("started_at", "ended_at")}
            for name in PHASES
        },
        "baseline_probes": _probes(phases["baseline"]),
        "fault_probes": _probes(fault),
        "recovery_probes": _probes(phases["recovery"]),
        "fault_console_rows": exact_rows,
    }

    # A field the run genuinely failed to capture stays absent rather than
    # becoming a zero, so the evaluator answers INCONCLUSIVE instead of
    # reading a fabricated value as a refutation.
    incomplete = sorted(k for k, v in observations.items() if v is None)
    for key in incomplete:
        del observations[key]

    return {
        "run_id": run["run_id"],
        "resource_id": run.get("resource_id"),
        "captured_at": run["started_at"],
        "observations": observations,
        "collector": "scripts/golden/collect_scenario_a.py",
        "capture_provenance": "derived",
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
