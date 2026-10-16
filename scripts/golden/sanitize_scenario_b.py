#!/usr/bin/env python3
"""Deterministically remove Azure identifiers from Scenario B evidence."""

from __future__ import annotations

import argparse
import json
import pathlib

PUBLIC_DESTINATION = "https://target.example/health"


class SanitisationError(Exception):
    pass


def sanitise(document: dict) -> dict:
    observations = document.get("observations")
    if not isinstance(observations, dict):
        raise SanitisationError("evidence has no observations object")
    result = json.loads(json.dumps(document))
    result["resource_id"] = None
    public = result["observations"]
    public["destination"] = PUBLIC_DESTINATION
    for field in ("phase_probes", "pooled_phase_probes"):
        phases = public.get(field)
        if not isinstance(phases, dict):
            raise SanitisationError(f"evidence has no {field} object")
        for probes in phases.values():
            for probe in probes:
                probe["target"] = PUBLIC_DESTINATION
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("output")
    args = parser.parse_args()
    source = pathlib.Path(args.input)
    target = pathlib.Path(args.output)
    target.write_text(json.dumps(sanitise(json.loads(source.read_text())), indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
