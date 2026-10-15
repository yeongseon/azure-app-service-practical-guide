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
    python3 scripts/golden/check_reproduction.py <reproduction.json> \
        --verifier package.module:callable

Exit codes: ``0`` both results REPRODUCED, ``1`` otherwise.
"""

from __future__ import annotations

import json
import pathlib
import sys
import datetime
import re
import hashlib
import importlib.util
from collections.abc import Callable

import jsonschema
from referencing import Registry, Resource

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNS = ROOT / "evidence" / "runs"
SCHEMAS = ROOT / "schemas" / "golden"
_EVALUATOR_SPEC = importlib.util.spec_from_file_location(
    "golden_evaluator", ROOT / "scripts/golden/evaluate_run.py")
evaluator = importlib.util.module_from_spec(_EVALUATOR_SPEC)
_EVALUATOR_SPEC.loader.exec_module(evaluator)

HYPOTHESIS_STATUS = ("SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "NOT_TESTED")

REPRODUCTION_RESULT = (
    "REPRODUCED",
    "FAILED",
    "INCONCLUSIVE",
    "NOT_INDEPENDENT",
    "ATTESTATION_UNVERIFIED",
    "NOT_ATTEMPTED",
)
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
    "consulted_source_to_fill_doc_gap",
    "deviations",
)


class ReproductionError(Exception):
    """Raised when a reproduction record does not conform to the schema."""


def _read_json(path: pathlib.Path) -> dict:
    try:
        return json.loads(path.read_text(), object_pairs_hook=evaluator._unique_object)
    except FileNotFoundError as exc:
        raise ReproductionError(f"required file not found: {path}") from exc
    except (json.JSONDecodeError, evaluator.ModelError) as exc:
        raise ReproductionError(f"invalid JSON in {path.name}: {exc}") from exc


def _schema_validator(name: str) -> jsonschema.Draft202012Validator:
    registry = Registry()
    for path in SCHEMAS.glob("*.schema.json"):
        schema = _read_json(path)
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    format_checker = jsonschema.FormatChecker()

    @format_checker.checks("date-time", raises=(TypeError, ValueError))
    def valid_date_time(value):
        if not isinstance(value, str):
            return True
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return "T" in value and parsed.tzinfo is not None

    @format_checker.checks("date", raises=(TypeError, ValueError))
    def valid_date(value):
        if not isinstance(value, str):
            return True
        return datetime.date.fromisoformat(value).isoformat() == value

    return jsonschema.Draft202012Validator(
        _read_json(SCHEMAS / name), registry=registry, format_checker=format_checker)


def _validate_schema(document: dict, name: str) -> None:
    errors = sorted(_schema_validator(name).iter_errors(document), key=lambda error: list(error.path))
    if errors:
        location = "/".join(str(part) for part in errors[0].path) or "(root)"
        raise ReproductionError(f"{name} {location}: {errors[0].message}")


def valid_digest(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def resources_are_independent(original: dict, replay: dict) -> bool:
    original_environment = original.get("environment") or {}
    replay_environment = replay.get("environment") or {}
    return all(original_environment.get(key)
               and replay_environment.get(key)
               and original_environment[key].casefold() != replay_environment[key].casefold()
               for key in ("resource_group", "app_name"))


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


def classify_reproduction(
        record: dict,
        attestation_verifier: Callable[[dict], bool] | None = None) -> str:
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
    attestation = record.get("attestation")
    if not isinstance(attestation, dict):
        return "NOT_INDEPENDENT"
    identities = (
        attestation.get("reviewer_login"),
        attestation.get("original_operator_login"),
        attestation.get("pr_author_login"),
    )
    if not all(isinstance(value, str) and value for value in identities):
        return "NOT_INDEPENDENT"
    if len({value.casefold() for value in identities}) != len(identities):
        return "NOT_INDEPENDENT"
    if attestation_verifier is None or not attestation_verifier(attestation):
        return "ATTESTATION_UNVERIFIED"
    # Equality alone is not reproduction. Two runs that never tested the
    # hypothesis hold equal statuses trivially, so NOT_TESTED on either side
    # would otherwise let a pair of non-runs reproduce each other.
    if record["replay_hypothesis_status"] in UNTESTED_STATUS:
        return "INCONCLUSIVE"
    return "REPRODUCED"


def _load_run(run_id: str) -> tuple[dict, dict, dict]:
    directory = RUNS / run_id
    if directory.is_symlink():
        raise ReproductionError(f"retained run directory must not be a symlink: {run_id}")
    manifest = _read_json(directory / "manifest.json")
    evidence = _read_json(directory / "evidence.json")
    result = _read_json(directory / "result.json")
    provenance = _read_json(directory / "provenance.json")
    for document, schema_name in ((manifest, "manifest.schema.json"),
                                  (evidence, "evidence.schema.json"),
                                  (result, "result.schema.json")):
        _validate_schema(document, schema_name)
    if manifest.get("run_id") != run_id or evidence.get("run_id") != run_id or result.get("run_id") != run_id:
        raise ReproductionError(f"retained run identity mismatch: {run_id}")
    if manifest.get("execution_status") != "COMPLETE" or result.get("execution_status") != "COMPLETE":
        raise ReproductionError(f"retained run is not COMPLETE: {run_id}")
    if evidence.get("captured_at") != manifest.get("captured_at"):
        raise ReproductionError(f"retained run capture time mismatch: {run_id}")
    recomputed = evaluator.evaluate(directory)
    if recomputed["generated_verdict_rejected"]:
        raise ReproductionError(f"retained result disagrees with raw evidence: {run_id}")
    recovery_ids = [item["id"] for item in manifest.get("assertions", [])
                     if item.get("role") == "recovery"]
    if not recovery_ids or any(recomputed.get("assertion_outcomes", {}).get(item) != "SUPPORTED"
                                for item in recovery_ids):
        raise ReproductionError(f"retained run has no verified recovery: {run_id}")
    if provenance.get("scenario") is None or provenance.get("cleanup_verified") is not True:
        raise ReproductionError(f"retained run lacks cleanup provenance: {run_id}")
    digests = provenance.get("digests")
    if not isinstance(digests, dict):
        raise ReproductionError(f"retained run lacks artifact digests: {run_id}")
    for name in ("manifest.json", "evidence.json", "result.json"):
        expected = digests.get(name)
        actual = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        if not valid_digest(expected) or expected != actual:
            raise ReproductionError(f"retained run digest mismatch for {name}: {run_id}")
    return manifest, evidence, recomputed | {"scenario": provenance["scenario"]}


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


def check(path, attestation_verifier: Callable[[dict], bool] | None = None) -> dict:
    """Read and check one reproduction record."""
    path = pathlib.Path(path)
    record = _read_json(path)
    _validate_schema(record, "reproduction.schema.json")

    _validate(record)
    reproduction_result = classify_reproduction(record, attestation_verifier)
    replay_id = record.get("replay_run_id")
    validates_run_packages = (
        isinstance(replay_id, str)
        and replay_id != record["original_run_id"]
        and record["reviewer"] != record["original_operator"]
        and record["reviewer_kind"] == "human"
        and record["original_operator_kind"] == "human"
    )
    if validates_run_packages:
        original_manifest, original_evidence, original_result = _load_run(record["original_run_id"])
        replay_manifest, replay_evidence, replay_result = _load_run(record["replay_run_id"])
        if original_result["scenario"] != record["scenario"] or replay_result["scenario"] != record["scenario"]:
            raise ReproductionError("reproduction scenario disagrees with retained run provenance")
        if not resources_are_independent(original_manifest, replay_manifest):
            raise ReproductionError("runs are not resource-independent")
        if original_evidence == replay_evidence:
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
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record")
    parser.add_argument("--verifier", help="External attestation verifier as MODULE:CALLABLE")
    args = parser.parse_args()
    verifier = None
    try:
        if args.verifier:
            module_name, callable_name = args.verifier.split(":", 1)
            spec = importlib.util.find_spec(module_name)
            if spec is None or spec.loader is None:
                raise ReproductionError(f"verifier module not found: {module_name}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            candidate = getattr(module, callable_name, None)
            if not callable(candidate):
                raise ReproductionError(f"verifier callable not found: {args.verifier}")
            verifier = candidate
    except (ValueError, ReproductionError) as exc:
        print(f"reproduction record error: {exc}", file=sys.stderr)
        return 1
    try:
        result = check(args.record, verifier)
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
