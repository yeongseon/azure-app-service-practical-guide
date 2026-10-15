#!/usr/bin/env python3
"""Golden v1 reference evaluator: re-derive assertion outcomes from raw evidence.

This evaluator answers one question only: do the raw evidence files support
the assertions the run declared in advance? It does not diagnose, rank
causes, or name a root cause. Collectors collect facts; assertions are
declared before execution; this module decides nothing beyond whether each
declared assertion holds.

Two properties matter more than convenience:

Raw wins. If a run also carries a generated ``result.json``, that file is
NEVER read as input. It is recomputed and compared, and a disagreement is
reported rather than trusted. A verdict file that can decide its own
outcome is not evidence.

Absence is not refutation. Evidence that cannot decide an assertion yields
INCONCLUSIVE, never CONTRADICTED. Collapsing the two is how a missing field
becomes a false disproof.

Usage::

    python3 scripts/golden/evaluate_run.py <run-dir>

Exit codes: ``0`` SUPPORTED, ``1`` CONTRADICTED, ``2`` INCONCLUSIVE,
``3`` NOT_TESTED (execution did not complete), ``4`` stored generated verdict
rejected because it disagrees with raw evidence.
"""

from __future__ import annotations

import json
import pathlib
import sys
import datetime
import unicodedata
import re
import math
import subprocess

CLAIM_LEVELS = ("Documented", "Observed", "Inferred", "Not Proven")
HYPOTHESIS_STATUS = ("SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "NOT_TESTED")
EXECUTION_STATUS = ("COMPLETE", "PARTIAL", "BLOCKED", "FAILED", "NOT_RUN")
EVIDENCE_ROLES = ("symptom", "supporting", "discriminating", "control", "recovery")
EVIDENCE_TRUST = ("trusted-current", "trusted-historical", "unverified", "invalid")

EXIT_CODES = {"SUPPORTED": 0, "CONTRADICTED": 1, "INCONCLUSIVE": 2, "NOT_TESTED": 3}
GENERATED_VERDICT_REJECTED_EXIT = 4

# Observed outranks Inferred, so a claim may only ever move toward weaker.
_CLAIM_STRENGTH = {"Observed": 3, "Documented": 2, "Inferred": 1, "Not Proven": 0}
ROOT = pathlib.Path(__file__).resolve().parents[2]
RETAINED_DIGESTS = ROOT / "evidence/retained-digests.json"
REQUIRED_ENVIRONMENT_FIELDS = ("subscription_kind", "region", "runtime", "sku")
PLACEHOLDERS = {"", "unknown", "none", "null", "n/a", "na", "tbd", "placeholder"}


class ClaimPromotionError(Exception):
    """Raised when a claim is moved to a strictly stronger level."""


class ModelError(Exception):
    """Raised when a run does not conform to the Golden v1 model."""


def promote_claim(current: str, target: str) -> str:
    """Return ``target`` only if it does not strengthen ``current``.

    >>> promote_claim("Observed", "Inferred")
    'Inferred'
    >>> promote_claim("Inferred", "Observed")
    Traceback (most recent call last):
        ...
    evaluate_run.ClaimPromotionError: cannot promote 'Inferred' to 'Observed'
    """
    for level in (current, target):
        if level not in CLAIM_LEVELS:
            raise ModelError(f"unknown claim level: {level!r}")
    if _CLAIM_STRENGTH[target] > _CLAIM_STRENGTH[current]:
        raise ClaimPromotionError(f"cannot promote {current!r} to {target!r}")
    return target


def _unique_object(pairs):
    value = {}
    normalized = set()
    for key, item in pairs:
        folded = unicodedata.normalize("NFKC", key).casefold()
        if key in value:
            raise ModelError(f"duplicate JSON key: {key!r}")
        if folded in normalized:
            raise ModelError(f"look-alike JSON key: {key!r}")
        value[key] = item
        normalized.add(folded)
    return value


def _read_json(path: pathlib.Path):
    def reject_non_finite(value: str):
        raise ModelError(f"non-finite JSON number in {path.name}: {value}")

    try:
        return json.loads(
            path.read_text(),
            object_pairs_hook=_unique_object,
            parse_constant=reject_non_finite,
        )
    except FileNotFoundError as exc:
        raise ModelError(f"required file missing: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise ModelError(f"malformed JSON in {path.name}: {exc}") from exc


def _timestamp(value: str, field: str) -> datetime.datetime:
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ModelError(f"{field} is not a valid date-time: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ModelError(f"{field} must include a timezone")
    if parsed > datetime.datetime.now(datetime.timezone.utc):
        raise ModelError(f"{field} is in the future: {value!r}")
    return parsed


def evaluate_assertion(assertion: dict, evidence: dict) -> str:
    """Return SUPPORTED, CONTRADICTED or INCONCLUSIVE for one assertion.

    >>> evaluate_assertion({"field": "status", "equals": 503}, {"status": 503})
    'SUPPORTED'
    >>> evaluate_assertion({"field": "status", "equals": 503}, {"status": 200})
    'CONTRADICTED'
    >>> evaluate_assertion({"field": "status", "equals": 503}, {})
    'INCONCLUSIVE'
    """
    field = assertion.get("field")
    if field is None:
        raise ModelError(f"assertion {assertion.get('id')!r} declares no field")
    role = assertion.get("role")
    if role is not None and role not in EVIDENCE_ROLES:
        raise ModelError(f"unknown evidence role: {role!r}")
    if "exists" in assertion:
        return "SUPPORTED" if (field in evidence) == assertion["exists"] else "CONTRADICTED"
    if field not in evidence:
        return "INCONCLUSIVE"
    observed = evidence[field]
    if observed == "unavailable":
        return "INCONCLUSIVE"
    if isinstance(observed, dict) and {"numerator", "denominator", "ratio"} <= set(observed):
        numerator = observed["numerator"]
        denominator = observed["denominator"]
        per_file_limit = observed.get("per_file_limit")
        if (not isinstance(numerator, (int, float)) or isinstance(numerator, bool)
                or not isinstance(denominator, (int, float)) or isinstance(denominator, bool)
                or not math.isfinite(numerator) or not math.isfinite(denominator)
                or denominator <= 0 or not isinstance(per_file_limit, (int, float))
                or isinstance(per_file_limit, bool) or not math.isfinite(per_file_limit)
                or per_file_limit <= 0):
            return "INCONCLUSIVE"
        observed = numerator / denominator
    expected_numbers = []
    if "equals" in assertion:
        expected_numbers.append(assertion["equals"])
    if "in" in assertion:
        expected_numbers.extend(assertion["in"])
    if "not_in" in assertion:
        expected_numbers.extend(assertion["not_in"])
    numeric_comparison = any(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in expected_numbers
    ) or "range" in assertion
    if numeric_comparison:
        if (not isinstance(observed, (int, float)) or isinstance(observed, bool)
                or not math.isfinite(observed)):
            return "CONTRADICTED"
    def compatible(expected) -> bool:
        if isinstance(expected, bool) or isinstance(observed, bool):
            return isinstance(expected, bool) and isinstance(observed, bool)
        if isinstance(expected, (int, float)) or isinstance(observed, (int, float)):
            return (isinstance(expected, (int, float)) and not isinstance(expected, bool)
                    and isinstance(observed, (int, float)) and not isinstance(observed, bool))
        return type(expected) is type(observed)
    if "equals" in assertion:
        expected = assertion["equals"]
        return "SUPPORTED" if compatible(expected) and observed == expected else "CONTRADICTED"
    if "in" in assertion:
        choices = assertion["in"]
        if not choices or any(not compatible(expected) for expected in choices):
            return "CONTRADICTED"
        return "SUPPORTED" if observed in choices else "CONTRADICTED"
    if "not_in" in assertion:
        choices = assertion["not_in"]
        if not choices or any(not compatible(expected) for expected in choices):
            return "CONTRADICTED"
        return "SUPPORTED" if observed not in choices else "CONTRADICTED"
    if "range" in assertion:
        bounds = assertion["range"]
        if (not isinstance(observed, (int, float)) or isinstance(observed, bool)
                or not math.isfinite(observed)):
            return "CONTRADICTED"
        minimum = bounds.get("minimum")
        maximum = bounds.get("maximum")
        if minimum is not None and observed < minimum:
            return "CONTRADICTED"
        if maximum is not None and observed > maximum:
            return "CONTRADICTED"
        return "SUPPORTED"
    if "regex" in assertion:
        if not isinstance(observed, str):
            return "CONTRADICTED"
        try:
            return "SUPPORTED" if re.search(assertion["regex"], observed) else "CONTRADICTED"
        except re.error as exc:
            raise ModelError(f"assertion {assertion.get('id')!r} has invalid regex") from exc
    raise ModelError(f"assertion {assertion.get('id')!r} declares no comparison")


def _predicate_values(assertion: dict) -> set | None:
    if "equals" in assertion:
        return {assertion["equals"]}
    if "in" in assertion:
        return set(assertion["in"])
    return None


def _absorbed(discriminating: dict, other: dict) -> bool:
    strong_values = _predicate_values(discriminating)
    weak_values = _predicate_values(other)
    if strong_values is None or weak_values is None:
        return True
    return strong_values <= weak_values


def _historical_run_ids() -> set[str]:
    try:
        document = _read_json(RETAINED_DIGESTS)
    except ModelError:
        return set()
    packages = document.get("packages") or {}
    return {
        run_id for run_id, package in packages.items()
        if isinstance(package, dict) and package.get("historical") is True
    }


def _placeholder(value: str) -> bool:
    normalized = value.strip().casefold()
    return (normalized in PLACEHOLDERS or normalized.startswith("<")
            or len(set(normalized.replace("sha256:", ""))) <= 1)


def _validate_new_run_provenance(
        manifest: dict, skip_source_commit_resolution: bool = False) -> str | None:
    if manifest.get("execution_status") != "COMPLETE" or not manifest.get("hypothesis"):
        return None
    if manifest.get("run_id") in _historical_run_ids():
        return None
    source_commit = manifest.get("source_commit")
    if (not isinstance(source_commit, str)
            or re.fullmatch(r"[0-9a-f]{40}", source_commit) is None
            or _placeholder(source_commit)):
        raise ModelError("source_commit must be a full 40-character lowercase hex commit")
    environment = manifest.get("environment")
    if not isinstance(environment, dict):
        raise ModelError("environment must be an object with required provenance fields")
    for field in REQUIRED_ENVIRONMENT_FIELDS:
        value = environment.get(field)
        if not isinstance(value, str) or _placeholder(value):
            raise ModelError(f"environment.{field} must be a non-placeholder string")
    for field in ("recipe_digest", "collector_digest"):
        value = manifest.get(field)
        if (not isinstance(value, str)
                or re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None
                or _placeholder(value)):
            raise ModelError(f"{field} must be an exact sha256 digest")
    if skip_source_commit_resolution:
        return "SKIPPED_EXPLICITLY"
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{source_commit}^{{commit}}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ModelError("source_commit does not resolve to a commit in this repository")
    return "VERIFIED"


def _evaluation_time() -> str:
    value = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    return value.isoformat().replace("+00:00", "Z")


def combine(outcomes) -> str:
    """Fold per-assertion outcomes into one hypothesis status.

    A single refutation outranks any number of confirmations, and an
    unevaluable assertion prevents SUPPORTED without pretending to refute.

    >>> combine(["SUPPORTED", "SUPPORTED"])
    'SUPPORTED'
    >>> combine(["SUPPORTED", "INCONCLUSIVE"])
    'INCONCLUSIVE'
    >>> combine(["INCONCLUSIVE", "CONTRADICTED"])
    'CONTRADICTED'
    >>> combine([])
    'NOT_TESTED'
    """
    outcomes = list(outcomes)
    if not outcomes:
        return "NOT_TESTED"
    if "CONTRADICTED" in outcomes:
        return "CONTRADICTED"
    if "INCONCLUSIVE" in outcomes:
        return "INCONCLUSIVE"
    return "SUPPORTED"


def _bind_evidence(document: dict, manifest: dict):
    """Return (observations, identity_state) for one evidence document.

    Evidence that declares a run_id must agree with the manifest. Without
    this, a result could be assembled from another run's captures and
    nothing would object -- the wrong-run case the model names but the
    evaluator did not previously check.

    >>> _bind_evidence({"run_id": "r1", "captured_at": "2026-01-01T00:00:00Z", "observations": {"status": 503}}, {"run_id": "r1", "resource_id": None, "captured_at": "2026-01-01T00:00:00Z"})
    ({'status': 503}, 'BOUND')
    >>> _bind_evidence({"status": 503}, {"run_id": "r1", "resource_id": None, "captured_at": "2026-01-01T00:00:00Z"})
    ({'status': 503}, 'UNBOUND')
    >>> _bind_evidence({"run_id": "other", "observations": {}}, {"run_id": "r1", "resource_id": None, "captured_at": "2026-01-01T00:00:00Z"})
    Traceback (most recent call last):
    evaluate_run.ModelError: evidence belongs to run 'other', not 'r1'
    """
    if not document:
        return {}, "ABSENT"
    run_id = manifest["run_id"]
    declared = document.get("run_id")
    if declared is None:
        # Legacy flat evidence carries no identity. It is usable but the
        # result records that nothing tied it to this run.
        return document, "UNBOUND"
    if declared != run_id:
        raise ModelError(f"evidence belongs to run {declared!r}, not {run_id!r}")
    resource_id = manifest.get("resource_id")
    if resource_id is not None and document.get("resource_id") != resource_id:
        raise ModelError("evidence resource_id does not match the manifest")
    evidence_captured = _timestamp(document.get("captured_at"), "evidence captured_at")
    manifest_captured = _timestamp(manifest["captured_at"], "manifest captured_at")
    if evidence_captured != manifest_captured:
        raise ModelError("evidence captured_at does not match the manifest")
    window = manifest.get("capture_window")
    if window:
        started = _timestamp(window.get("started_at"), "capture_window started_at")
        ended = _timestamp(window.get("ended_at"), "capture_window ended_at")
        if started > ended:
            raise ModelError("capture window ends before it starts")
        if started > evidence_captured or evidence_captured > ended:
            raise ModelError("evidence captured_at falls outside the capture window")
    observations = document.get("observations")
    if not isinstance(observations, dict):
        raise ModelError("evidence declares a run_id but no observations object")
    return observations, "BOUND"


def evaluate(run_dir, *, skip_source_commit_resolution: bool = False) -> dict:
    """Evaluate one run directory and return a result record."""
    run_dir = pathlib.Path(run_dir)
    manifest = _read_json(run_dir / "manifest.json")

    execution_status = manifest.get("execution_status")
    if execution_status not in EXECUTION_STATUS:
        raise ModelError(f"unknown execution status: {execution_status!r}")
    for key in ("run_id", "captured_at"):
        if not manifest.get(key):
            raise ModelError(f"manifest is missing run identity field: {key}")
    _timestamp(manifest["captured_at"], "manifest captured_at")
    source_commit_resolution = _validate_new_run_provenance(
        manifest, skip_source_commit_resolution)

    claim_level = manifest.get("hypothesis_claim_level")
    historical_run = manifest.get("run_id") in _historical_run_ids()
    if (execution_status == "COMPLETE" and manifest.get("hypothesis")
            and not historical_run and claim_level not in CLAIM_LEVELS):
        raise ModelError("causal hypothesis must declare an allowed hypothesis_claim_level")

    assertions = manifest.get("assertions") or []
    evidence_doc = (
        _read_json(run_dir / "evidence.json")
        if (run_dir / "evidence.json").is_file() else {}
    )
    evidence, evidence_identity = _bind_evidence(evidence_doc, manifest)

    # Keying outcomes by a caller-supplied id let a later assertion overwrite
    # an earlier one, so a manifest declaring the same id twice could drop a
    # CONTRADICTED outcome and report SUPPORTED. Ids must be unique.
    per_assertion = {}
    for assertion in assertions:
        assertion_id = assertion.get("id")
        if assertion_id in per_assertion:
            raise ModelError(f"duplicate assertion id: {assertion_id!r}")
        outcome = evaluate_assertion(assertion, evidence)
        if assertion.get("claim_level") == "Not Proven" and outcome == "SUPPORTED":
            outcome = "INCONCLUSIVE"
        per_assertion[assertion_id] = outcome

    strong = [item for item in assertions if item.get("role") == "discriminating"]
    for item in strong:
        for weak in assertions:
            if weak is item or weak.get("field") != item.get("field"):
                continue
            if _absorbed(item, weak):
                raise ModelError(
                    f"discriminating assertion {item.get('id')!r} is absorbed by {weak.get('id')!r}")

    # Execution status gates the hypothesis axis: a run that did not finish
    # has not tested anything, whatever its partial evidence happens to show.
    if execution_status != "COMPLETE":
        hypothesis_status = "NOT_TESTED"
    else:
        hypothesis_status = combine(per_assertion.values())
        causal_claim = bool(manifest.get("hypothesis"))
        if hypothesis_status == "SUPPORTED" and causal_claim and (not strong or evidence_identity != "BOUND"):
            hypothesis_status = "INCONCLUSIVE"
        if hypothesis_status == "SUPPORTED" and claim_level == "Not Proven":
            hypothesis_status = "INCONCLUSIVE"

    # A generated verdict is recomputed and compared, never consumed.
    result = {
        "run_id": manifest["run_id"],
        "captured_at": manifest["captured_at"],
        "evaluated_at": _evaluation_time(),
        "execution_status": execution_status,
        "evidence_identity": evidence_identity,
        "hypothesis_status": hypothesis_status,
        "assertion_outcomes": per_assertion,
    }
    if source_commit_resolution == "SKIPPED_EXPLICITLY":
        result["source_commit_resolution"] = source_commit_resolution
    generated = run_dir / "result.json"
    generated_verdict_rejected = False
    generated_claimed = None
    if generated.is_file():
        stored = _read_json(generated)
        generated_claimed = stored.get("hypothesis_status")
        comparable = {key: stored.get(key) for key in result}
        comparable["evaluated_at"] = result["evaluated_at"]
        allowed = set(result) | {"generated_verdict_claimed", "generated_verdict_rejected"}
        generated_verdict_rejected = comparable != result or not set(stored) <= allowed
    result["generated_verdict_claimed"] = generated_claimed
    result["generated_verdict_rejected"] = generated_verdict_rejected
    return result


def main() -> int:
    skip_source_commit_resolution = False
    arguments = sys.argv[1:]
    if "--skip-source-commit-resolution" in arguments:
        arguments.remove("--skip-source-commit-resolution")
        skip_source_commit_resolution = True
    if len(arguments) != 1:
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        print(
            "usage: evaluate_run.py <run-dir> [--skip-source-commit-resolution]",
            file=sys.stderr,
        )
        return 2
    try:
        result = evaluate(
            arguments[0],
            skip_source_commit_resolution=skip_source_commit_resolution,
        )
    except ModelError as exc:
        print(f"model error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    if result["generated_verdict_rejected"]:
        print(
            "generated result.json disagrees with the recomputation and was rejected",
            file=sys.stderr,
        )
        return GENERATED_VERDICT_REJECTED_EXIT
    return EXIT_CODES[result["hypothesis_status"]]


if __name__ == "__main__":
    sys.exit(main())
