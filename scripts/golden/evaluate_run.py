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
``3`` NOT_TESTED (execution did not complete).
"""

from __future__ import annotations

import json
import pathlib
import sys

CLAIM_LEVELS = ("Documented", "Observed", "Inferred", "Not Proven")
HYPOTHESIS_STATUS = ("SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "NOT_TESTED")
#: RUNNING was added after the pilot runner was found emitting it. A run
#: in flight is not PARTIAL, which means finished but incomplete, and the
#: model simply had no word for it. It can never produce a verdict:
#: evaluate() gates the hypothesis axis on COMPLETE, so RUNNING yields
#: NOT_TESTED like every other non-final state.
EXECUTION_STATUS = ("COMPLETE", "PARTIAL", "BLOCKED", "FAILED", "NOT_RUN", "RUNNING")
EVIDENCE_ROLES = ("symptom", "supporting", "discriminating", "control", "recovery")
EVIDENCE_TRUST = ("trusted-current", "trusted-historical", "unverified", "invalid")

EXIT_CODES = {"SUPPORTED": 0, "CONTRADICTED": 1, "INCONCLUSIVE": 2, "NOT_TESTED": 3}

# Observed outranks Inferred, so a claim may only ever move toward weaker.
_CLAIM_STRENGTH = {"Observed": 3, "Documented": 2, "Inferred": 1, "Not Proven": 0}


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


def _read_json(path: pathlib.Path):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise ModelError(f"required file missing: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise ModelError(f"malformed JSON in {path.name}: {exc}") from exc


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
    if field not in evidence:
        return "INCONCLUSIVE"
    observed = evidence[field]
    if "equals" in assertion:
        return "SUPPORTED" if observed == assertion["equals"] else "CONTRADICTED"
    if "in" in assertion:
        return "SUPPORTED" if observed in assertion["in"] else "CONTRADICTED"
    raise ModelError(f"assertion {assertion.get('id')!r} declares no comparison")


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


def _bind_evidence(document: dict, run_id: str):
    """Return (observations, identity_state) for one evidence document.

    Evidence that declares a run_id must agree with the manifest. Without
    this, a result could be assembled from another run's captures and
    nothing would object -- the wrong-run case the model names but the
    evaluator did not previously check.

    >>> _bind_evidence({"run_id": "r1", "observations": {"status": 503}}, "r1")
    ({'status': 503}, 'BOUND')
    >>> _bind_evidence({"status": 503}, "r1")
    ({'status': 503}, 'UNBOUND')
    >>> _bind_evidence({"run_id": "other", "observations": {}}, "r1")
    Traceback (most recent call last):
    evaluate_run.ModelError: evidence belongs to run 'other', not 'r1'
    """
    if not document:
        return {}, "ABSENT"
    declared = document.get("run_id")
    if declared is None:
        # Legacy flat evidence carries no identity. It is usable but the
        # result records that nothing tied it to this run.
        return document, "UNBOUND"
    if declared != run_id:
        raise ModelError(f"evidence belongs to run {declared!r}, not {run_id!r}")
    observations = document.get("observations")
    if not isinstance(observations, dict):
        raise ModelError("evidence declares a run_id but no observations object")
    return observations, "BOUND"


def evaluate(run_dir) -> dict:
    """Evaluate one run directory and return a result record."""
    run_dir = pathlib.Path(run_dir)
    manifest = _read_json(run_dir / "manifest.json")

    execution_status = manifest.get("execution_status")
    if execution_status not in EXECUTION_STATUS:
        raise ModelError(f"unknown execution status: {execution_status!r}")
    for key in ("run_id", "captured_at"):
        if not manifest.get(key):
            raise ModelError(f"manifest is missing run identity field: {key}")

    assertions = manifest.get("assertions") or []
    evidence_doc = (
        _read_json(run_dir / "evidence.json")
        if (run_dir / "evidence.json").is_file() else {}
    )
    evidence, evidence_identity = _bind_evidence(evidence_doc, manifest["run_id"])

    # Keying outcomes by a caller-supplied id let a later assertion overwrite
    # an earlier one, so a manifest declaring the same id twice could drop a
    # CONTRADICTED outcome and report SUPPORTED. Ids must be unique.
    per_assertion = {}
    for assertion in assertions:
        assertion_id = assertion.get("id")
        if assertion_id in per_assertion:
            raise ModelError(f"duplicate assertion id: {assertion_id!r}")
        per_assertion[assertion_id] = evaluate_assertion(assertion, evidence)

    # Execution status gates the hypothesis axis: a run that did not finish
    # has not tested anything, whatever its partial evidence happens to show.
    if execution_status != "COMPLETE":
        hypothesis_status = "NOT_TESTED"
    else:
        hypothesis_status = combine(per_assertion.values())

    # A generated verdict is recomputed and compared, never consumed.
    generated = run_dir / "result.json"
    generated_verdict_rejected = False
    generated_claimed = None
    if generated.is_file():
        try:
            generated_claimed = _read_json(generated).get("hypothesis_status")
        except ModelError:
            generated_claimed = None
        generated_verdict_rejected = generated_claimed != hypothesis_status

    return {
        "run_id": manifest["run_id"],
        "captured_at": manifest["captured_at"],
        "evaluated_at": manifest.get("evaluated_at"),
        "execution_status": execution_status,
        "evidence_identity": evidence_identity,
        "hypothesis_status": hypothesis_status,
        "assertion_outcomes": per_assertion,
        "generated_verdict_claimed": generated_claimed,
        "generated_verdict_rejected": generated_verdict_rejected,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        print("usage: evaluate_run.py <run-dir>", file=sys.stderr)
        return 2
    try:
        result = evaluate(sys.argv[1])
    except ModelError as exc:
        print(f"model error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    if result["generated_verdict_rejected"]:
        print(
            "generated result.json disagrees with the recomputation and was rejected",
            file=sys.stderr,
        )
    return EXIT_CODES[result["hypothesis_status"]]


if __name__ == "__main__":
    sys.exit(main())
