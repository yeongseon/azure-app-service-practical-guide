#!/usr/bin/env python3
"""Validate every Golden document against the schema it claims to follow.

The Golden job previously called `json.load` on these files, which proves
they are JSON and nothing else. That is not schema validation, and the gap
was not theoretical: the manifest templates carried `hypothesis` and
`notes` under a schema declaring `additionalProperties: false`, and the
evaluator accepted an execution status no schema listed. The runtime model
and its published contracts had drifted apart with nothing to notice.

Validation is local. The schemas carry `$id` URLs on the documentation
host, but nothing should reach the network to check a file in this
repository, so `$ref` between schemas is resolved from disk.

Usage:
    python3 scripts/golden/validate_schemas.py [--verbose]

Exit codes: 0 every document conforms, 1 at least one does not,
2 the check could not run.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "schemas" / "golden"


def _registry():
    """A resolver that serves the sibling schemas from disk."""
    from referencing import Registry, Resource

    registry = Registry()
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        schema = json.loads(path.read_text())
        resource = Resource.from_contents(schema)
        registry = registry.with_resource(uri=schema["$id"], resource=resource)
    return registry


def documents():
    """(document_path, schema_name) pairs this repository must honour."""
    pairs = []
    for manifest in sorted((ROOT / "labs").glob("*/golden/manifest.template.json")):
        pairs.append((manifest, "manifest.schema.json"))
    for record in sorted((ROOT / "evidence" / "reproductions").glob("*.json")):
        pairs.append((record, "reproduction.schema.json"))
    runs = ROOT / "evidence" / "runs"
    if runs.is_dir():
        for run in sorted(runs.iterdir()):
            for name, schema in (("manifest.json", "manifest.schema.json"),
                                 ("evidence.json", "evidence.schema.json"),
                                 ("result.json", "result.schema.json")):
                if (run / name).is_file():
                    pairs.append((run / name, schema))
    return pairs


def validate(verbose: bool = False) -> list[str]:
    """Return one message per non-conforming document."""
    import jsonschema

    registry = _registry()
    failures = []
    checked = 0
    for path, schema_name in documents():
        schema = json.loads((SCHEMA_DIR / schema_name).read_text())
        validator = jsonschema.Draft202012Validator(schema, registry=registry)
        document = json.loads(path.read_text())
        errors = sorted(validator.iter_errors(document), key=lambda e: list(e.path))
        checked += 1
        if not errors:
            if verbose:
                print(f"ok   {path.relative_to(ROOT)} -> {schema_name}")
            continue
        for error in errors:
            location = "/".join(str(part) for part in error.path) or "(root)"
            failures.append(
                f"{path.relative_to(ROOT)}: {location}: {error.message} "
                f"[{schema_name}]")
    if verbose:
        print(f"checked {checked} document(s) against {len(list(SCHEMA_DIR.glob('*.json')))} schema(s)")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    try:
        failures = validate(args.verbose)
    except ImportError as exc:
        print(f"error: schema validation needs jsonschema and referencing: {exc}",
              file=sys.stderr)
        return 2
    for failure in failures:
        print(f"error: {failure}", file=sys.stderr)
    if failures:
        print(f"\n{len(failures)} document(s) do not conform to their schema",
              file=sys.stderr)
        return 1
    print("every Golden document conforms to its schema")
    return 0


if __name__ == "__main__":
    sys.exit(main())
