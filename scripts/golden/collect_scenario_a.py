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

The one derived field is `fault_status_class`, which buckets an observed
status code into `2xx`/`4xx`/`5xx`. That is a restatement of the observed
code, not an inference about why it occurred.

Usage:
    python3 scripts/golden/collect_scenario_a.py <run_dir> [--output PATH]

Exit codes: 0 evidence written, 2 the run directory is unusable.
"""

from __future__ import annotations

import argparse
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


def status_class(status) -> str:
    """Bucket an observed HTTP status into its class.

    A restatement of what was observed, not a judgement about it.

    >>> status_class(503)
    '5xx'
    >>> status_class(200)
    '2xx'
    >>> status_class(None) is None
    True
    """
    if not isinstance(status, int):
        return None
    return f"{status // 100}xx"


def import_error_hits(console: dict) -> int:
    """Count console rows naming a Python import failure.

    Counted from the raw query output rather than from any summary, so a
    console file that recorded nothing yields 0 and not a missing field.

    >>> import_error_hits({"stdout": "[]"})
    0
    >>> import_error_hits({"stdout": '[{"Msg": "ModuleNotFoundError: x"}]'})
    1
    """
    raw = console.get("stdout") or "[]"
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        rows = []
    if not isinstance(rows, list):
        return 0
    needles = ("modulenotfounderror", "importerror", "no module named")
    count = 0
    for row in rows:
        text = json.dumps(row).lower() if not isinstance(row, str) else row.lower()
        if any(needle in text for needle in needles):
            count += 1
    return count


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

    observations = {
        "baseline_status": phases["baseline"].get("status"),
        "deploy_exit_code": _read(run_dir / "deploy.json").get("exit_code"),
        "fault_startup_command": fault.get("startup"),
        "fault_config_readback": fault.get("config_readback"),
        "fault_status_class": status_class(fault.get("status")),
        "fault_import_error_hits": import_error_hits(console),
        "recovery_status": phases["recovery"].get("status"),
    }

    # A field the run genuinely failed to capture stays absent rather than
    # becoming a zero, so the evaluator answers INCONCLUSIVE instead of
    # reading a fabricated value as a refutation.
    incomplete = sorted(k for k, v in observations.items() if v is None)
    for key in incomplete:
        del observations[key]

    return {
        "run_id": run["run_id"],
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
