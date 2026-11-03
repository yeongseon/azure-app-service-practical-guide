#!/usr/bin/env python3
"""Fail when the committed diagram manifest stops covering the tree or a started migration.

Usage: python3 scripts/check_diagram_manifest_coverage.py [--root DIR]
Repository-local companion of scripts/diagram_inventory.py. It imports the shared scanner unchanged,
so that no repository-specific logic enters the scanner or its schema, whose updates the composition
ADR requires to be coordinated byte-identically with the sibling guides.
It renders nothing, verifies no provenance and requires no diagram to be migrated.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import NamedTuple

import diagram_inventory as inventory

COMPOSITION = 'scripts/diagram_composition.json'
REGENERATE = 'python scripts/diagram_inventory.py --write'
STARTED = frozenset(('in-progress', 'completed'))
Selection = tuple[str | None, tuple[str, ...], tuple[str, ...]]
UNSELECTED: Selection = (None, (), ())


class Composition(NamedTuple):
    """The part of the composition spec that the targets of started migrations are resolved against."""
    base: str
    extensions: frozenset[str]
    overlays: frozenset[str]
    enrolled: dict[str, Selection]


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


def one_line(message: str) -> str:
    """Escape every character that is not printable, so a finding stays on one line whatever text it quotes."""
    return ''.join(char if char.isprintable() else char.encode('unicode_escape').decode() for char in message)


def unique(pairs: list[tuple[str, object]]) -> inventory.Record:
    """Reject a repeated object key, as the composer does, instead of reading the last value."""
    result: inventory.Record = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate key {key!r}')
        result[key] = value
    return result


def mapping(value: object, what: str) -> inventory.Record:
    if not isinstance(value, dict):
        raise ValueError(f'{what} must be an object')
    return value


def text(value: object, what: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f'{what} must be text')
    return value


def texts(value: object, what: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f'{what} must be a list of text')
    return tuple(value)


def enrollment(root: Path, position: int, value: object) -> tuple[str, Selection]:
    """The manifest key and the selection of one enrolled diagram, with its page spelled as the scanner spells it."""
    label = f'diagrams[{position}]'
    entry = mapping(value, label)
    page = PurePosixPath(text(entry['page'], label + '.page')).as_posix()
    try:
        _ = inventory.local(root, page)
    except inventory.InventoryError:
        raise ValueError(label + '.page leaves the repository') from None
    overlay = entry['overlay']
    return (f'{page}#{text(entry["id"], label + ".id")}',
            (text(entry['base'], label + '.base'), texts(entry['extensions'], label + '.extensions'),
             () if overlay is None else (text(overlay, label + '.overlay'),)))


def read_composition(root: Path, path: Path) -> Composition:
    """Read the fields of the composition spec that this guard resolves references against.

    The spec is plain JSON, so removing the prototype never breaks this check. Every field read is checked
    for its type, because a string would otherwise be read as a set of characters; the rest of the spec is
    for the composer to validate. A page is compared as pathlib spells it, so `docs/./x.md` is `docs/x.md`.
    """
    spec = mapping(json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique), 'the spec')
    diagrams = spec['diagrams']
    if not isinstance(diagrams, list):
        raise ValueError('diagrams must be a list')
    return Composition(text(mapping(spec['base'], 'base')['id'], 'base.id'),
                       frozenset(mapping(spec['extensions'], 'extensions')),
                       frozenset(mapping(spec['overlays'], 'overlays')),
                       dict(enrollment(root, position, value) for position, value in enumerate(diagrams)))


def composition_problems(root: Path, manifest: inventory.Record) -> list[str]:
    """Resolve the composition targets of started migrations against the opt-in composition spec."""
    declared = {d['key']: selection(d['target']) for d in started(manifest)}
    try:
        path = inventory.local(root, COMPOSITION)
        if not (path.exists() or path.is_symlink()):
            return [f'{key}: composition target requires {COMPOSITION}'
                    for key, target in declared.items() if target != UNSELECTED]
        spec = read_composition(root, path)
    except KeyError as error:
        return [f'{COMPOSITION}: unreadable composition spec: missing key {error}']
    except (inventory.InventoryError, OSError, ValueError, RuntimeError) as error:  # RuntimeError: a symlink loop before Python 3.13, or RecursionError
        return [f'{COMPOSITION}: unreadable composition spec: {error}']
    errors = [f'{key}: composition output is not in the manifest'
              for key in sorted(spec.enrolled.keys() - {d['key'] for d in manifest['diagrams']})]
    for key, target in declared.items():
        if target == UNSELECTED and key not in spec.enrolled:
            continue
        target_base, target_extensions, target_overlays = target
        if target_base is not None and target_base != spec.base:
            errors.append(f'{key}: target.base {target_base!r} is not the composition base {spec.base!r}')
        errors += [f'{key}: unknown extension {name}' for name in target_extensions if name not in spec.extensions]
        errors += [f'{key}: unknown overlay {name}' for name in target_overlays if name not in spec.overlays]
        if key not in spec.enrolled:
            errors.append(f'{key}: composition target is not enrolled in {COMPOSITION}')
        elif spec.enrolled[key] != target:
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
    arguments = parser.parse_args(argv)
    try:
        root: Path = arguments.root.resolve()
        manifest_path = inventory.local(root, inventory.MANIFEST)
        if not manifest_path.exists():
            raise inventory.InventoryError(f'{inventory.MANIFEST} is missing; run {REGENERATE}')
        rules: inventory.Record = json.loads(inventory.local(root, inventory.RULES).read_text(encoding='utf-8'))
        manifest: inventory.Record = json.loads(manifest_path.read_text(encoding='utf-8'))
        errors = inventory.check(root, manifest, rules)
        if errors:
            print('\n'.join(map(one_line, errors)))
            print('diagram manifest coverage: not evaluated, because python scripts/diagram_inventory.py --check fails')
            return 1
        errors = migration_problems(manifest) + composition_problems(root, manifest)
        errors += coverage_problems(manifest, inventory.build(root, rules, manifest['baseline']['base_commit']))
    except (inventory.InventoryError, OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'diagram manifest coverage: {one_line(str(error))}', file=sys.stderr)
        return 1
    if errors:
        print('\n'.join(map(one_line, errors)))
        print(f'diagram manifest coverage: {len(errors)} problem(s); correct the page, the manifest planning fields or {COMPOSITION}. '
              f'If a Mermaid fence was added, removed or moved, or its page or diagram-id renamed, run {REGENERATE} and commit the manifest')
        return 1
    print(f'diagram manifest coverage: check passed ({len(manifest["diagrams"])} occurrences, {len(started(manifest))} with a started migration)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
