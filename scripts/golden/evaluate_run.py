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
import os
import subprocess
import hashlib

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
RUN_DECLARATIONS = ROOT / "evidence/run-declarations.json"
SCENARIO_A_RECIPE = ROOT / "scripts/golden/scenario-a-recipe.json"
SCENARIO_B_RECIPE = ROOT / "scripts/golden/scenario-b-recipe.json"
REQUIRED_ENVIRONMENT_FIELDS = ("subscription_kind", "region", "runtime", "sku")
PLACEHOLDERS = {"", "unknown", "none", "null", "na", "tbd", "placeholder", "notavailable"}
FROZEN_HISTORICAL_RUN_IDS = {
    "20260927T104304Z-aba0d3a9daa7",
    "20260927T114621Z-04c6c02c9ae1",
}


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
    def scalar(value) -> bool:
        return value is None or isinstance(value, (str, int, float, bool))

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
        if (not scalar(observed) or observed is None or not isinstance(choices, list)
                or not choices or any(not scalar(expected) or expected is None for expected in choices)
                or any(type(expected) is not type(choices[0]) for expected in choices)
                or any(not compatible(expected) for expected in choices)):
            return "CONTRADICTED"
        return "SUPPORTED" if observed in choices else "CONTRADICTED"
    if "not_in" in assertion:
        choices = assertion["not_in"]
        if (not scalar(observed) or observed is None or not isinstance(choices, list)
                or not choices or any(not scalar(expected) or expected is None for expected in choices)
                or any(type(expected) is not type(choices[0]) for expected in choices)
                or any(not compatible(expected) for expected in choices)):
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


def _historical_run_ids(base_ref: str | None = None) -> set[str]:
    base_ref = base_ref or os.environ.get("GOLDEN_BASE_REF")
    if not base_ref:
        return set(FROZEN_HISTORICAL_RUN_IDS)
    try:
        text = subprocess.run(
            ["git", "show", f"{base_ref}:evidence/retained-digests.json"],
            cwd=ROOT, text=True, capture_output=True, check=True,
        ).stdout
        document = json.loads(text, object_pairs_hook=_unique_object)
    except (subprocess.CalledProcessError, json.JSONDecodeError, ModelError):
        return set(FROZEN_HISTORICAL_RUN_IDS)
    packages = document.get("packages") or {}
    return {
        run_id for run_id, package in packages.items()
        if isinstance(package, dict) and package.get("historical") is True
    }


def _declared_run_ids() -> set[str]:
    if not RUN_DECLARATIONS.is_file():
        return set()
    document = _read_json(RUN_DECLARATIONS)
    runs = document.get("runs") or {}
    return set(runs) if isinstance(runs, dict) else set()


def _git_bytes(commit: str, path: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True, check=False)
    if completed.returncode != 0:
        subprocess.run(
            ["git", "fetch", "--no-tags", "origin", commit], cwd=ROOT,
            capture_output=True, check=False)
        completed = subprocess.run(
            ["git", "show", f"{commit}:{path}"], cwd=ROOT,
            capture_output=True, check=False)
    if completed.returncode != 0:
        raise ModelError(f"source_commit does not contain provenance input: {path}")
    return completed.stdout


def _verify_provenance_digests(manifest: dict) -> None:
    if manifest.get("run_id") not in _declared_run_ids():
        return
    source_commit = manifest["source_commit"]
    recipe_paths = manifest.get("recipe_paths")
    declaration = _read_json(RUN_DECLARATIONS)["runs"][manifest["run_id"]]
    definition_path = (SCENARIO_B_RECIPE if declaration["scenario"] == "snat-exhaustion"
                       else SCENARIO_A_RECIPE)
    definition = _read_json(definition_path)
    if recipe_paths != definition.get("recipe_paths"):
        raise ModelError("recipe_paths does not match the versioned recipe definition")
    if (not isinstance(recipe_paths, list) or not recipe_paths
            or any(not isinstance(path, str) or not path for path in recipe_paths)):
        raise ModelError("recipe_paths is required for a declared COMPLETE run")
    common = pathlib.PurePosixPath(os.path.commonpath(recipe_paths)).as_posix()
    prefix = common.rstrip("/") + "/"
    fingerprints = {
        path.removeprefix(prefix): hashlib.sha256(_git_bytes(source_commit, path)).hexdigest()
        for path in sorted(recipe_paths)
    }
    canonical = json.dumps(fingerprints, sort_keys=True, separators=(",", ":")).encode()
    recipe = hashlib.sha256(canonical).hexdigest()
    if manifest["recipe_digest"] != f"sha256:{recipe}":
        raise ModelError("recipe_digest does not match canonical source fingerprints")


def _verify_derivation(provenance: dict, manifest: dict, evidence: dict) -> None:
    derivation = provenance.get("derivation")
    if not isinstance(derivation, dict) or derivation.get("derived_offline") is not True:
        raise ModelError("offline derivation metadata is required")
    collector_commit = derivation.get("collector_commit")
    collector_path = derivation.get("collector_path")
    collector_digest = derivation.get("collector_digest")
    if (not isinstance(collector_commit, str)
            or re.fullmatch(r"[0-9a-f]{40}", collector_commit) is None
            or not isinstance(collector_path, str)):
        raise ModelError("derivation collector commit/path is invalid")
    definition_path = (SCENARIO_B_RECIPE if provenance.get("scenario") == "snat-exhaustion"
                       else SCENARIO_A_RECIPE)
    definition = _read_json(definition_path)
    if (collector_commit != definition.get("derivation_collector_commit")
            or collector_path != definition.get("collector_path")):
        raise ModelError("derivation collector does not match the versioned recipe definition")
    expected_digest = definition.get("derivation_collector_digest")
    if collector_digest != expected_digest:
        raise ModelError("derivation collector digest does not match the versioned recipe definition")
    try:
        collector_bytes = _git_bytes(collector_commit, collector_path)
    except ModelError:
        local_collector = ROOT / collector_path
        if not local_collector.is_file():
            raise ModelError(
                "derivation collector is unavailable from both Git and the checkout") from None
        collector_bytes = local_collector.read_bytes()
    actual = hashlib.sha256(collector_bytes).hexdigest()
    if expected_digest != f"sha256:{actual}":
        raise ModelError("derivation collector_digest does not match collector_commit bytes")
    derived_at = _timestamp(derivation.get("derived_at"), "derivation derived_at")
    captured_at = _timestamp(manifest["captured_at"], "manifest captured_at")
    if derived_at < captured_at:
        raise ModelError("derivation derived_at is earlier than captured_at")
    if derived_at > datetime.datetime.now(datetime.timezone.utc):
        raise ModelError("derivation derived_at is in the future")
    raw_input = derivation.get("raw_input")
    integrity = evidence.get("phase_capture_integrity")
    if (not isinstance(raw_input, dict) or raw_input.get("run_id") != manifest["run_id"]
            or raw_input.get("phase_capture_integrity") != {
                phase: anchor["sha256"] for phase, anchor in integrity.items()
            }):
        raise ModelError("derivation raw_input does not match phase capture anchors")
    required_shape = ({"phase_windows", "phase_probes", "destination_health",
                       "destination_binding", "snat_port_pressure"}
                      if provenance.get("scenario") == "snat-exhaustion"
                      else {"fault_status", "fault_console_rows", "phase_windows",
                            "baseline_probes", "fault_probes", "recovery_probes"})
    if not required_shape <= set(evidence):
        raise ModelError("derivation collector output shape is incomplete")


def _verify_source_commit(manifest: dict, evidence: dict) -> None:
    source_commit = manifest["source_commit"]
    if evidence.get("runner_source_commit") != source_commit:
        raise ModelError("source_commit does not match the runner-captured source SHA")
    completed = subprocess.run(
        ["git", "show", "-s", "--format=%cI", source_commit],
        cwd=ROOT, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise ModelError("source_commit date cannot be resolved")
    committed_at = _timestamp(completed.stdout.strip(), "source_commit committed_at")
    captured_at = _timestamp(manifest["captured_at"], "manifest captured_at")
    if committed_at > captured_at:
        raise ModelError("source_commit is later than captured_at")


def _placeholder(value: str) -> bool:
    normalized = re.sub(r"[\s./\\_-]+", "", value).casefold()
    return (normalized in PLACEHOLDERS or normalized.startswith("<")
            or len(set(normalized.replace("sha256:", ""))) <= 1)


def _validate_new_run_provenance(
        manifest: dict, skip_source_commit_resolution: bool = False,
        base_ref: str | None = None) -> str | None:
    if manifest.get("execution_status") != "COMPLETE" or not manifest.get("hypothesis"):
        return None
    if manifest.get("run_id") in _historical_run_ids(base_ref):
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
    for field in ("recipe_digest",):
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


def _derive_scenario_a(observations: dict, manifest: dict, provenance: dict) -> dict:
    required = {"phase_windows", "baseline_probes", "fault_probes", "recovery_probes",
                "fault_console_rows"}
    if not required <= set(observations):
        return observations
    capture = manifest.get("capture_window")
    if not isinstance(capture, dict):
        raise ModelError("raw Scenario A evidence requires a capture_window")
    capture_start = _timestamp(capture.get("started_at"), "capture_window started_at")
    capture_end = _timestamp(capture.get("ended_at"), "capture_window ended_at")
    windows = observations["phase_windows"]
    if not isinstance(windows, dict):
        raise ModelError("phase_windows must be an object")
    parsed = {}
    for phase in ("baseline", "fault", "recovery"):
        window = windows.get(phase)
        if not isinstance(window, dict):
            raise ModelError(f"{phase} window is missing")
        start = _timestamp(window.get("started_at"), f"{phase} started_at")
        end = _timestamp(window.get("ended_at"), f"{phase} ended_at")
        if not capture_start <= start <= end <= capture_end:
            raise ModelError(f"{phase} window falls outside the capture window")
        parsed[phase] = (start, end)
    ordered = (parsed["baseline"][1] < parsed["fault"][0]
               and parsed["fault"][1] < parsed["recovery"][0])
    if not ordered:
        raise ModelError("phase windows are not strictly ordered")
    statuses = {}
    integrity = observations.get("phase_capture_integrity")
    provenance_integrity = provenance.get("phase_capture_integrity")
    if not isinstance(integrity, dict) or integrity != provenance_integrity:
        raise ModelError("phase capture integrity anchors are missing or disagree")
    for phase in ("baseline", "fault", "recovery"):
        probes = observations[f"{phase}_probes"]
        if not isinstance(probes, list) or not probes:
            raise ModelError(f"{phase}_probes must be a non-empty array")
        statuses[phase] = []
        anchor = integrity.get(phase)
        if (not isinstance(anchor, dict) or anchor.get("probe_count") != len(probes)
                or not re.fullmatch(r"[0-9a-f]{64}", str(anchor.get("sha256", "")))):
            raise ModelError(f"{phase} probes do not match the raw phase capture anchor")
        seen = set()
        for probe in probes:
            if not isinstance(probe, dict):
                raise ModelError(f"{phase} probe must be an object")
            captured = _timestamp(probe.get("captured_at"), f"{phase} probe captured_at")
            normalized = captured.astimezone(datetime.timezone.utc)
            if normalized in seen:
                raise ModelError(f"{phase} probes contain duplicate normalized timestamps")
            seen.add(normalized)
            if not parsed[phase][0] <= captured <= parsed[phase][1]:
                raise ModelError(f"{phase} probe falls outside its phase window")
            statuses[phase].append(probe.get("status"))
    signature = "ModuleNotFoundError: No module named 'wrong_module'"
    rows = observations["fault_console_rows"]
    if not isinstance(rows, list) or not rows:
        raise ModelError("fault_console_rows must contain an exact wrong_module row")
    for row in rows:
        if not isinstance(row, dict) or row.get("signature") != signature:
            raise ModelError("fault console row has an unrelated signature")
        captured = _timestamp(row.get("timestamp"), "fault console timestamp")
        if not parsed["fault"][0] <= captured <= parsed["fault"][1]:
            raise ModelError("fault console row falls outside the fault window")
    derived = {
        "baseline_status": 200 if 200 in statuses["baseline"] else None,
        "fault_status": 503 if 503 in statuses["fault"] else None,
        "recovery_status": 200 if 200 in statuses["recovery"] else None,
        "fault_import_error_signature": signature,
        "phase_order_valid": ordered,
    }
    for field, value in derived.items():
        if observations.get(field) != value:
            raise ModelError(f"summary field disagrees with raw evidence: {field}")
    return {**observations, **derived}


def _derive_scenario_b(observations: dict, manifest: dict) -> dict:
    required = {"phase_windows", "phase_probes", "destination_health",
                "destination_binding", "snat_port_pressure"}
    if not required <= set(observations):
        return observations
    capture = manifest.get("capture_window")
    if not isinstance(capture, dict):
        raise ModelError("raw Scenario B evidence requires a capture_window")
    capture_start = _timestamp(capture.get("started_at"), "capture_window started_at")
    capture_end = _timestamp(capture.get("ended_at"), "capture_window ended_at")
    windows = observations["phase_windows"]
    probes_by_phase = observations["phase_probes"]
    if not isinstance(windows, dict) or not isinstance(probes_by_phase, dict):
        raise ModelError("Scenario B phase windows and probes must be objects")
    parsed = {}
    totals = {}
    for phase in ("baseline", "load", "recovery"):
        window = windows.get(phase)
        probes = probes_by_phase.get(phase)
        if not isinstance(window, dict) or not isinstance(probes, list) or not probes:
            raise ModelError(f"{phase} raw capture is missing")
        start = _timestamp(window.get("started_at"), f"{phase} started_at")
        end = _timestamp(window.get("ended_at"), f"{phase} ended_at")
        if not capture_start <= start <= end <= capture_end:
            raise ModelError(f"{phase} window falls outside the capture window")
        parsed[phase] = (start, end)
        totals[phase] = {"success": 0, "failure": 0, "transport_failure": 0}
        for probe in probes:
            if not isinstance(probe, dict):
                raise ModelError(f"{phase} probe must be an object")
            if probe.get("run_id", manifest["run_id"]) != manifest["run_id"]:
                raise ModelError(f"{phase} probe belongs to another run")
            captured = _timestamp(probe.get("captured_at"), f"{phase} probe captured_at")
            if not start <= captured <= end:
                raise ModelError(f"{phase} probe falls outside its phase window")
            inner = probe.get("inner")
            if not isinstance(inner, dict):
                raise ModelError(f"{phase} probe has no retained inner outcomes")
            for outcome in totals[phase]:
                value = inner.get(outcome)
                if not isinstance(value, int) or value < 0:
                    raise ModelError(f"{phase} probe has invalid {outcome} count")
                totals[phase][outcome] += value
    if not (parsed["baseline"][1] < parsed["load"][0]
            and parsed["load"][1] < parsed["recovery"][0]):
        raise ModelError("Scenario B phase windows are not strictly ordered")
    if observations["destination_binding"] is not True:
        raise ModelError("Scenario B destination is not bound to the workload target")
    health = observations["destination_health"]
    if not isinstance(health, dict):
        raise ModelError("Scenario B destination health capture is invalid")
    health_at = _timestamp(health.get("captured_at"), "destination health captured_at")
    if not parsed["load"][0] <= health_at <= capture_end:
        raise ModelError("destination health is not contemporaneous with the load phase")
    derived = {
        "baseline_success_count": len(probes_by_phase["baseline"])
        if totals["baseline"]["failure"] == totals["baseline"]["transport_failure"] == 0 else 0,
        "load_transport_failure_count": sum(
            1 for probe in probes_by_phase["load"]
            if probe["inner"]["transport_failure"] > 0),
        "load_http_error_count": sum(
            1 for probe in probes_by_phase["load"] if probe["inner"]["failure"] > 0),
        "recovery_success_count": len(probes_by_phase["recovery"])
        if totals["recovery"]["failure"] == totals["recovery"]["transport_failure"] == 0 else 0,
        "destination_health_status": health.get("status"),
        "destination_binding": True,
        "snat_port_pressure": observations["snat_port_pressure"],
    }
    for field, value in derived.items():
        if field in observations and observations[field] != value:
            raise ModelError(f"summary field disagrees with raw evidence: {field}")
    return {**observations, **derived}


def evaluate(run_dir, *, skip_source_commit_resolution: bool = False,
             base_ref: str | None = None) -> dict:
    """Evaluate one run directory and return a result record."""
    run_dir = pathlib.Path(run_dir)
    manifest = _read_json(run_dir / "manifest.json")
    identity_bound = (manifest.get("run_id") in _declared_run_ids()
                      or manifest.get("run_id") in _historical_run_ids(base_ref))
    if identity_bound and run_dir.name != manifest.get("run_id"):
        raise ModelError("package directory name does not match manifest run_id")

    execution_status = manifest.get("execution_status")
    if execution_status not in EXECUTION_STATUS:
        raise ModelError(f"unknown execution status: {execution_status!r}")
    for key in ("run_id", "captured_at"):
        if not manifest.get(key):
            raise ModelError(f"manifest is missing run identity field: {key}")
    _timestamp(manifest["captured_at"], "manifest captured_at")
    source_commit_resolution = _validate_new_run_provenance(
        manifest, skip_source_commit_resolution, base_ref)
    if source_commit_resolution != "SKIPPED_EXPLICITLY":
        _verify_provenance_digests(manifest)

    claim_level = manifest.get("hypothesis_claim_level")
    historical_run = manifest.get("run_id") in _historical_run_ids(base_ref)
    if (execution_status == "COMPLETE" and manifest.get("hypothesis")
            and not historical_run and claim_level not in CLAIM_LEVELS):
        raise ModelError("causal hypothesis must declare an allowed hypothesis_claim_level")

    assertions = manifest.get("assertions") or []
    evidence_doc = (
        _read_json(run_dir / "evidence.json")
        if (run_dir / "evidence.json").is_file() else {}
    )
    evidence, evidence_identity = _bind_evidence(evidence_doc, manifest)
    provenance = _read_json(run_dir / "provenance.json") if (run_dir / "provenance.json").is_file() else {}
    if manifest.get("run_id") in _declared_run_ids():
        _verify_source_commit(manifest, evidence_doc)
        _verify_derivation(provenance, manifest, evidence)
        evidence = _derive_scenario_a(evidence, manifest, provenance)
        if provenance.get("scenario") == "snat-exhaustion":
            evidence = _derive_scenario_b(evidence, manifest)

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
        if identity_bound and stored.get("run_id") != run_dir.name:
            raise ModelError("result run_id does not match package directory")
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
