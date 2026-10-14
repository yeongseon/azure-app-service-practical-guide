#!/usr/bin/env python3
"""Independent reproduction gate for Golden v1 scenarios.

A reproduction is independent when a second operator, given only the
repository, a target commit, the public documentation and an environment,
reaches the same verdict. The reviewer does not receive hidden steps,
undocumented workarounds, or any note stating the expected root cause.

This module records and checks that attempt. Two properties matter more
than a matching verdict.

A replay that reuses the original run is not a reproduction. It agrees by
construction, because it is the same evidence. The run identities and the
operators must differ.

Verdict agreement and documentation quality are separate results. A
reviewer who had to read source to fill a documentation gap has shown that
the code works and the documentation does not. The verdict may match while
the documentation reproduction FAILS, and recording only the verdict would
conceal exactly the defect this gate exists to surface. The same applies to
any deviation the reviewer had to invent: a step absent from the
documentation is a documentation gap, whatever the outcome.

Usage::

    python3 scripts/golden/check_reproduction.py <reproduction.json>

Exit codes: ``0`` both results REPRODUCED, ``1`` otherwise.
"""

from __future__ import annotations

import json
import pathlib
import sys
import datetime
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNS = ROOT / "evidence" / "runs"

HYPOTHESIS_STATUS = ("SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "NOT_TESTED")

REPRODUCTION_RESULT = ("REPRODUCED", "FAILED", "NOT_INDEPENDENT", "NOT_ATTEMPTED")
DOCUMENTATION_RESULT = ("REPRODUCED", "FAILED", "NOT_ATTEMPTED")

DEVIATION_KINDS = (
    "undocumented-step",
    "incorrect-step",
    "missing-prerequisite",
    "environment-difference",
)

REQUIRED_FIELDS = (
    "reviewer",
    "reviewer_kind",
    "original_operator",
    "original_operator_kind",
    "commit",
    "attempted_at",
    "scenario",
    "original_run_id",
    "original_hypothesis_status",
    "replay_hypothesis_status",
)


class ReproductionError(Exception):
    """Raised when a reproduction record does not conform to the schema."""


def _validate(record: dict) -> None:
    for field in REQUIRED_FIELDS:
        if field not in record:
            raise ReproductionError(f"reproduction record is missing: {field}")
    for field in ("original_hypothesis_status", "replay_hypothesis_status"):
        if record[field] not in HYPOTHESIS_STATUS:
            raise ReproductionError(f"unknown hypothesis status in {field}: {record[field]!r}")
    if not re.fullmatch(r"[0-9a-f]{40}", record["commit"]):
        if record.get("reviewer_kind") == "human" or record["commit"] == "deadbee":
            raise ReproductionError("commit must be a full 40-character lowercase Git SHA")
    try:
        attempted = datetime.datetime.fromisoformat(
            record["attempted_at"].replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ReproductionError("attempted_at must be an ISO date or date-time") from exc
    if attempted.tzinfo is None:
        attempted = attempted.replace(tzinfo=datetime.timezone.utc)
    if attempted > datetime.datetime.now(datetime.timezone.utc):
        raise ReproductionError("attempted_at cannot be in the future")
    for deviation in record.get("deviations") or []:
        kind = deviation.get("kind")
        if kind not in DEVIATION_KINDS:
            raise ReproductionError(
                f"deviation must declare a known kind, got {kind!r}; "
                f"expected one of {', '.join(DEVIATION_KINDS)}")


#: Statuses that mean the hypothesis was never put at risk.
UNTESTED_STATUS = ("NOT_TESTED", "NOT_RUN")


def classify_reproduction(record: dict) -> str:
    """Classify the replay attempt itself.

    >>> classify_reproduction({"replay_run_id": None, "original_run_id": "a",
    ...     "reviewer": "b", "original_operator": "c",
    ...     "original_hypothesis_status": "SUPPORTED",
    ...     "replay_hypothesis_status": "NOT_TESTED"})
    'NOT_ATTEMPTED'

    A replay carrying the original's run id is the same evidence:

    >>> classify_reproduction({"replay_run_id": "a", "original_run_id": "a",
    ...     "reviewer": "b", "original_operator": "c",
    ...     "original_hypothesis_status": "SUPPORTED",
    ...     "replay_hypothesis_status": "SUPPORTED"})
    'NOT_INDEPENDENT'

    >>> classify_reproduction({"replay_run_id": "z", "original_run_id": "a",
    ...     "reviewer": "b", "reviewer_kind": "human",
    ...     "original_operator": "c", "original_operator_kind": "human",
    ...     "original_hypothesis_status": "SUPPORTED",
    ...     "replay_hypothesis_status": "CONTRADICTED"})
    'FAILED'
    """
    if not record.get("replay_run_id"):
        return "NOT_ATTEMPTED"
    if record["replay_run_id"] == record["original_run_id"]:
        return "NOT_INDEPENDENT"
    if record["reviewer"] == record["original_operator"]:
        return "NOT_INDEPENDENT"
    if record["reviewer_kind"] != "human" or record["original_operator_kind"] != "human":
        return "NOT_INDEPENDENT"
    if record["replay_hypothesis_status"] != record["original_hypothesis_status"]:
        return "FAILED"
    # Equality alone is not reproduction. Two runs that never tested the
    # hypothesis hold equal statuses trivially, so NOT_TESTED on either side
    # would otherwise let a pair of non-runs reproduce each other.
    if record["replay_hypothesis_status"] in UNTESTED_STATUS:
        return "INCONCLUSIVE"
    return "REPRODUCED"


def _load_run(run_id: str) -> tuple[dict, dict, dict]:
    directory = RUNS / run_id
    try:
        manifest = json.loads((directory / "manifest.json").read_text())
        evidence = json.loads((directory / "evidence.json").read_text())
        result = json.loads((directory / "result.json").read_text())
    except FileNotFoundError as exc:
        raise ReproductionError(f"retained run not found: {run_id}") from exc
    if manifest.get("run_id") != run_id or evidence.get("run_id") != run_id or result.get("run_id") != run_id:
        raise ReproductionError(f"retained run identity mismatch: {run_id}")
    if manifest.get("execution_status") != "COMPLETE" or result.get("execution_status") != "COMPLETE":
        raise ReproductionError(f"retained run is not COMPLETE: {run_id}")
    if evidence.get("captured_at") != manifest.get("captured_at"):
        raise ReproductionError(f"retained run capture time mismatch: {run_id}")
    recovery_ids = [item["id"] for item in manifest.get("assertions", [])
                    if item.get("role") == "recovery"]
    if not recovery_ids or any(result.get("assertion_outcomes", {}).get(item) != "SUPPORTED"
                               for item in recovery_ids):
        raise ReproductionError(f"retained run has no verified recovery: {run_id}")
    return manifest, evidence, result


def classify_documentation(record: dict) -> str:
    """Classify whether the DOCUMENTATION reproduced, independent of the verdict.

    An attempt that never happened did not test the documentation either,
    so it does not earn a documentation pass:

    >>> classify_documentation({"replay_run_id": None})
    'NOT_ATTEMPTED'
    >>> classify_documentation({"replay_run_id": "z",
    ...     "consulted_source_to_fill_doc_gap": False, "deviations": []})
    'REPRODUCED'
    >>> classify_documentation({"replay_run_id": "z",
    ...     "consulted_source_to_fill_doc_gap": True, "deviations": []})
    'FAILED'
    >>> classify_documentation({"replay_run_id": "z",
    ...     "consulted_source_to_fill_doc_gap": False,
    ...     "deviations": [{"kind": "undocumented-step"}]})
    'FAILED'
    """
    if not record.get("replay_run_id"):
        return "NOT_ATTEMPTED"
    if record.get("consulted_source_to_fill_doc_gap"):
        return "FAILED"
    if record.get("deviations"):
        return "FAILED"
    return "REPRODUCED"


def check(path) -> dict:
    """Read and check one reproduction record."""
    path = pathlib.Path(path)
    try:
        record = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise ReproductionError(f"reproduction record not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReproductionError(f"malformed reproduction record: {exc}") from exc

    _validate(record)
    reproduction_result = classify_reproduction(record)
    if reproduction_result in ("REPRODUCED", "FAILED", "INCONCLUSIVE"):
        original_manifest, original_evidence, original_result = _load_run(record["original_run_id"])
        replay_manifest, replay_evidence, replay_result = _load_run(record["replay_run_id"])
        if original_manifest.get("resource_id") == replay_manifest.get("resource_id") and \
                original_evidence == replay_evidence:
            raise ReproductionError("replay reuses the original raw evidence")
        if replay_result.get("hypothesis_status") != record["replay_hypothesis_status"]:
            raise ReproductionError("replay status disagrees with the retained result")
        if original_result.get("hypothesis_status") != record["original_hypothesis_status"]:
            raise ReproductionError("original status disagrees with the retained result")
    documentation_result = classify_documentation(record)

    return {
        "scenario": record["scenario"],
        "commit": record["commit"],
        "reviewer": record["reviewer"],
        "attempted_at": record["attempted_at"],
        "original_hypothesis_status": record["original_hypothesis_status"],
        "replay_hypothesis_status": record["replay_hypothesis_status"],
        "reproduction_result": reproduction_result,
        "documentation_result": documentation_result,
        "deviations": list(record.get("deviations") or []),
        "passed": reproduction_result == "REPRODUCED"
        and documentation_result == "REPRODUCED",
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_reproduction.py <reproduction.json>", file=sys.stderr)
        return 1
    try:
        result = check(sys.argv[1])
    except ReproductionError as exc:
        print(f"reproduction record error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    if result["documentation_result"] == "FAILED":
        print(
            "documentation reproduction FAILED: the reviewer needed information "
            "the documentation did not provide",
            file=sys.stderr,
        )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
