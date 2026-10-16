#!/usr/bin/env python3
"""Emit Golden-model evidence for Scenario B from captured probe results.

Scenario B is the comparative scenario: its verdict depends on two
transports agreeing about the same response. That agreement is only real
if one implementation classifies for both, which is why
``labs/snat-exhaustion/app/classification.py`` exists and why this
collector imports it rather than re-deriving the bands. A collector with
its own copy of the predicate would reintroduce exactly the confounder
that module was written to remove: the same HTTP response counted a
success on one side and a failure on the other.

`verify.sh` writes symptom counts under different names --
``console_snat_timeout_refused_hits`` and friends -- which are useful but
are not the fields this contract asserts on, and which explicitly carry
``causal_claim: null``. This collector reads the probe captures instead
and counts outcomes per phase under the declared names.

Expected run directory:

    run.json                 run_id and started_at
    baseline/probes.json     probe records before load
    load/probes.json         probe records under connection pressure
    recovery/probes.json     probe records after pressure is removed
    destination-health.json  the destination's own health, probed directly

Each probe record is either ``{"status": 200}`` for a completed round trip
or ``{"transport_error": "EADDRNOTAVAIL"}`` when no HTTP response was
obtained. The distinction is the whole experiment: port exhaustion
surfaces as connection-level failure, not as a status code.

A phase that was not captured leaves its fields absent and named in
``incomplete_fields``, so the evaluator answers INCONCLUSIVE rather than
reading a fabricated zero as a refutation.

Usage:
    python3 scripts/golden/collect_scenario_b.py <run_dir> [--output PATH]

Exit codes: 0 evidence written, 2 the run directory is unusable.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import hashlib
import pathlib
import sys

sys.dont_write_bytecode = True

#: The lab this collector serves, declared so the alignment check can
#: associate the two without depending on this file's name.
LAB = "snat-exhaustion"

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_CLASSIFIER = _ROOT / "labs" / LAB / "app" / "classification.py"


def _load_classifier():
    """Import the lab's shared classifier.

    Imported rather than reimplemented. Two copies of a predicate that
    agree when read side by side is precisely the failure this experiment
    already suffered once.
    """
    spec = importlib.util.spec_from_file_location("snat_classification", _CLASSIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def classify_probe(probe: dict, classifier) -> str:
    """Classify one captured probe through the lab's shared rules.

    A probe that reports neither a status nor a transport error is not
    classifiable and raises, because silently bucketing it would invent an
    outcome the capture does not contain.
    """
    if "transport_error" in probe and probe["transport_error"]:
        return classifier.TRANSPORT_FAILURE
    if "status" in probe and probe["status"] is not None:
        return classifier.classify_status(probe["status"])
    raise CollectionError(f"probe record has neither status nor transport_error: {probe}")


def count_outcomes(probes, classifier) -> dict:
    """Count each outcome across one phase's probes.

    Every outcome the classifier knows appears in the result, so a phase
    with no transport failures reports zero rather than omitting the key
    and making absence look like a missing capture.
    """
    counts = {outcome: 0 for outcome in classifier.OUTCOMES}
    for probe in probes:
        counts[classify_probe(probe, classifier)] += 1
    return counts


def collect(run_dir) -> dict:
    """Build a Golden evidence document from one captured run."""
    classifier = _load_classifier()
    run_dir = pathlib.Path(run_dir)
    run = _read(run_dir / "run.json")

    phases = {}
    phase_windows = {}
    integrity = {}
    for name in ("baseline", "load", "recovery"):
        phase_dir = run_dir / name
        phase = _read(phase_dir / "phase.json", required=False)
        unpooled = _read(phase_dir / "unpooled-probes.json", required=False)
        pooled = _read(phase_dir / "pooled-probes.json", required=False)
        legacy = _read(phase_dir / "probes.json", required=False)
        if unpooled is None and legacy is not None:
            unpooled = legacy
            pooled = legacy
            phase = {
                "run_id": run["run_id"],
                "started_at": run["started_at"],
                "ended_at": run["started_at"],
            }
        if phase is None or unpooled is None or pooled is None:
            phases[name] = None
            continue
        if (not isinstance(unpooled, list) or not isinstance(pooled, list)
                or phase.get("run_id") != run["run_id"]):
            raise CollectionError(f"{name} capture is malformed or belongs to another run")
        phase_windows[name] = {
            "started_at": phase["started_at"],
            "ended_at": phase["ended_at"],
        }
        def normalize(probes):
            normalized = []
            for probe in probes:
                if (probe.get("run_id") != run["run_id"]
                        or probe.get("target") != run.get("destination")):
                    raise CollectionError(
                        f"{name} probe identity or destination binding is invalid")
                inner = probe.get("inner")
                if not isinstance(inner, dict):
                    outcome = classify_probe(probe, classifier)
                    inner = {item: int(item == outcome) for item in classifier.OUTCOMES}
                normalized.append({
                    "run_id": probe["run_id"],
                    "captured_at": probe.get("at", run["started_at"]),
                    "status": probe.get("status"),
                    "inner": inner,
                    "target": probe["target"],
                })
            return normalized

        normalized = normalize(unpooled)
        normalized_pooled = normalize(pooled)
        phase_path = phase_dir / "phase.json"
        raw_files = {
            "phase.json": hashlib.sha256(phase_path.read_bytes()).hexdigest(),
            "unpooled-probes.json": hashlib.sha256(
                (phase_dir / "unpooled-probes.json").read_bytes()).hexdigest(),
            "pooled-probes.json": hashlib.sha256(
                (phase_dir / "pooled-probes.json").read_bytes()).hexdigest(),
        }
        integrity[name] = {
            "probe_count": len(normalized),
            "pooled_probe_count": len(normalized_pooled),
            "files": raw_files,
            "retained_rows_sha256": hashlib.sha256(json.dumps(
                {"unpooled": normalized, "pooled": normalized_pooled},
                sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        }
        phases[name] = {"unpooled": normalized, "pooled": normalized_pooled}

    health = _read(run_dir / "destination-health.json", required=False)
    pressure = _read(run_dir / "port-pressure.json", required=False)
    target = _read(run_dir / "app-target.json", required=False)

    observations = {
        "phase_windows": phase_windows,
        "phase_probes": {name: capture["unpooled"] for name, capture in phases.items()
                          if capture is not None},
        "pooled_phase_probes": {name: capture["pooled"] for name, capture in phases.items()
                                 if capture is not None},
        "destination": run.get("destination"),
        "phase_capture_integrity": integrity,
        "destination_health": None if health is None else {
            "captured_at": health.get("at", run["started_at"]),
            "status": health.get("status")},
        "destination_health_status": None if health is None else health.get("status"),
        "snat_port_pressure": None if pressure is None else pressure.get("status"),
        "destination_binding": (
            None if target is None else target.get("matches_requested_destination")),
        "pooling_reduces_transport_failures": None,
    }

    scalar_sources = {
        "baseline_success_count": ("baseline", classifier.SUCCESS),
        "load_transport_failure_count": ("load", classifier.TRANSPORT_FAILURE),
        "load_http_error_count": ("load", classifier.FAILURE),
        "recovery_success_count": ("recovery", classifier.SUCCESS),
    }
    for field, (phase_name, outcome) in scalar_sources.items():
        phase_capture = phases[phase_name]
        capture = None if phase_capture is None else phase_capture["unpooled"]
        observations[field] = (None if capture is None else sum(
            1 for probe in capture if probe["inner"][outcome] > 0))
    observations["destination_health_status"] = (
        None if health is None else health.get("status"))
    if phases["load"] is not None:
        unpooled_failures = sum(
            1 for probe in phases["load"]["unpooled"]
            if probe["inner"][classifier.TRANSPORT_FAILURE] > 0)
        pooled_failures = sum(
            1 for probe in phases["load"]["pooled"]
            if probe["inner"][classifier.TRANSPORT_FAILURE] > 0)
        observations["pooling_reduces_transport_failures"] = (
            unpooled_failures > pooled_failures)

    incomplete = sorted(key for key, value in observations.items() if value is None)
    for key in incomplete:
        del observations[key]

    return {
        "run_id": run["run_id"],
        "resource_id": run.get("resource_id"),
        "captured_at": run["started_at"],
        "observations": observations,
        "collector": "scripts/golden/collect_scenario_b.py",
        "capture_provenance": "derived",
        "runner_source_commit": run.get("runner_source_commit"),
        "phase_capture_integrity": integrity,
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
