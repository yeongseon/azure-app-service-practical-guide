#!/usr/bin/env python3
"""Fail when the committed diagram manifest stops covering the tree or a started migration.

Usage: python3 scripts/check_diagram_manifest_coverage.py [--root DIR]
Repository-local companion of scripts/diagram_inventory.py. It imports the shared scanner
unchanged, so the scanner and its schema stay byte-identical with the sibling guides.
It renders nothing, verifies no provenance and requires no diagram to be migrated.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import diagram_inventory as inventory

COMPOSITION = 'scripts/diagram_composition.json'
REGENERATE = 'python scripts/diagram_inventory.py --write'
STARTED = frozenset(('in-progress', 'completed'))
Selection = tuple[str | None, tuple[str, ...], tuple[str, ...]]
UNSELECTED: Selection = (None, (), ())


def started(manifest: inventory.Record) -> list[inventory.Record]:
    return [d for d in manifest['diagrams'] if d['migration']['state'] in STARTED]


def selection(target: inventory.Record) -> Selection:
    return (target['base'], tuple(target['extensions']), tuple(target['overlays']))


def migration_problems(manifest: inventory.Record) -> list[str]:
    """An entry whose migration has started must be traceable to its page and its declared sources."""
    errors: list[str] = []
    for diagram in started(manifest):
        state = diagram['migration']['state']
        if diagram['diagram_id'] is None or diagram['id_provisional']:
            errors.append(f'{diagram["key"]}: migration {state} requires a stable diagram-id comment')
        if diagram['provenance']['status'] != 'declared':
            errors.append(f'{diagram["key"]}: migration {state} requires declared source provenance')
    return errors


def composition_problems(root: Path, manifest: inventory.Record) -> list[str]:
    """Resolve the composition targets of started migrations against the opt-in composition spec.

    The spec is read as plain JSON, so removing the prototype never breaks this check.
    """
    path = inventory.local(root, COMPOSITION)
    declared = {d['key']: selection(d['target']) for d in started(manifest)}
    if not path.exists():
        return [f'{key}: composition target requires {COMPOSITION}'
                for key, target in declared.items() if target != UNSELECTED]
    try:
        spec: inventory.Record = json.loads(path.read_text(encoding='utf-8'))
        base: str = spec['base']['id']
        extensions, overlays = set(spec['extensions']), set(spec['overlays'])
        enrolled: dict[str, Selection] = {
            f'{e["page"]}#{e["id"]}': (e['base'], tuple(e['extensions']), (e['overlay'],) if e['overlay'] else ())
            for e in spec['diagrams']}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return [f'{COMPOSITION}: unreadable composition spec: {error}']
    errors = [f'{key}: composition output is not in the manifest'
              for key in sorted(enrolled.keys() - {d['key'] for d in manifest['diagrams']})]
    for key, (target_base, target_extensions, target_overlays) in declared.items():
        if (target_base, target_extensions, target_overlays) == UNSELECTED and key not in enrolled:
            continue
        if target_base is not None and target_base != base:
            errors.append(f'{key}: target.base {target_base!r} is not the composition base {base!r}')
        errors += [f'{key}: unknown extension {name}' for name in target_extensions if name not in extensions]
        errors += [f'{key}: unknown overlay {name}' for name in target_overlays if name not in overlays]
        if key not in enrolled:
            errors.append(f'{key}: composition target is not enrolled in {COMPOSITION}')
        elif enrolled[key] != (target_base, target_extensions, target_overlays):
            errors.append(f'{key}: target differs from the enrolled composition')
    return errors


def coverage_problems(previous: inventory.Record, current: inventory.Record) -> list[str]:
    """Compare the committed manifest with a fresh scan of the tree.

    Every added, removed or moved key is a problem, and so is a fence that the scanner cannot recognize at
    all (blocking reasons only). A changed body or provenance is a problem only for an entry whose migration
    has started: edits to diagrams nobody has begun to migrate stay advisory.
    """
    difference = inventory.drift(previous, current)
    errors = [f'{key}: Mermaid occurrence is not in the manifest' for key in difference['added']]
    errors += [f'{key}: manifest record has no Mermaid occurrence in the tree' for key in difference['removed']]
    errors += [f'{move["from"]}: now {move["to"]} in the tree' for move in difference['moved']]
    errors += [f'{item["page"]}:{item["line"]}: {item["reason"]} Mermaid fence cannot be recognized, so the manifest cannot cover it; '
               'move the fence to the top level with at most 3 spaces of indentation, or show it inside a longer outer fence'
               for item in current['exceptions']['unrecognized_mermaid_fences'] if item['reason'] in inventory.BLOCKING_REASONS]
    states = {d['key']: d['migration']['state'] for d in previous['diagrams']}
    for category, subject in (('changed', 'source'), ('provenance', 'provenance')):
        errors += [f'{key}: {states[key]} entry: {subject} differs from the manifest'
                   for key in difference[category] if states[key] in STARTED]
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    root: Path = parser.parse_args(argv).root.resolve()
    try:
        manifest_path = inventory.local(root, inventory.MANIFEST)
        if not manifest_path.exists():
            raise inventory.InventoryError(f'{inventory.MANIFEST} is missing; run {REGENERATE}')
        rules: inventory.Record = json.loads(inventory.local(root, inventory.RULES).read_text(encoding='utf-8'))
        manifest: inventory.Record = json.loads(manifest_path.read_text(encoding='utf-8'))
        errors = inventory.check(root, manifest, rules)
        if errors:
            print('\n'.join(errors))
            print('diagram manifest coverage: not evaluated, because python scripts/diagram_inventory.py --check fails')
            return 1
        errors = migration_problems(manifest) + composition_problems(root, manifest)
        errors += coverage_problems(manifest, inventory.build(root, rules, manifest['baseline']['base_commit']))
    except (inventory.InventoryError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'diagram manifest coverage: {error}', file=sys.stderr)
        return 1
    if errors:
        print('\n'.join(errors))
        print(f'diagram manifest coverage: {len(errors)} problem(s); fix the page, the manifest planning fields or {COMPOSITION}. '
              f'After adding, removing or renaming a Mermaid fence, run {REGENERATE} and commit the manifest')
        return 1
    print(f'diagram manifest coverage: check passed ({len(manifest["diagrams"])} occurrences, {len(started(manifest))} with a started migration)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
