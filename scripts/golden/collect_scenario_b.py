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
    for name in ("baseline", "load", "recovery"):
        capture = _read(run_dir / name / "probes.json", required=False)
        if capture is None:
            phases[name] = None
            continue
        if not isinstance(capture, list):
            raise CollectionError(f"{name}/probes.json is not a list of probe records")
        phases[name] = count_outcomes(capture, classifier)

    health = _read(run_dir / "destination-health.json", required=False)

    baseline = phases["baseline"]
    load = phases["load"]
    recovery = phases["recovery"]

    observations = {
        "baseline_success_count": None if baseline is None else baseline[classifier.SUCCESS],
        "load_transport_failure_count": (
            None if load is None else load[classifier.TRANSPORT_FAILURE]),
        "load_http_error_count": None if load is None else load[classifier.FAILURE],
        "recovery_success_count": None if recovery is None else recovery[classifier.SUCCESS],
        # The discriminating observation. Without it, transport failures are
        # equally consistent with the destination itself being down, and the
        # hypothesis cannot be separated from that explanation.
        "destination_health_status": None if health is None else health.get("status"),
    }

    incomplete = sorted(key for key, value in observations.items() if value is None)
    for key in incomplete:
        del observations[key]

    return {
        "run_id": run["run_id"],
        "captured_at": run["started_at"],
        "observations": observations,
        "collector": "scripts/golden/collect_scenario_b.py",
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
