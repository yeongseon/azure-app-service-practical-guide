#!/usr/bin/env python3
"""Fixture tests for the diagram manifest coverage guard; run with python3 scripts/test_check_diagram_manifest_coverage.py."""

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable, Mapping

import yaml

import check_diagram_manifest_coverage as guard
import diagram_inventory as inventory

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / 'scripts/check_diagram_manifest_coverage.py'
FENCE = '<!-- diagram-id: {id} -->\n```mermaid\nflowchart LR\n{body}\n```\n'
Mutation = Callable[[inventory.Record], object]


def migration(state: str) -> inventory.Record:
    return {'state': state, 'exception': 'Owner deferred conversion' if state == 'exception' else None}


class GuardTests(unittest.TestCase):
    def __init__(self, methodName: str = 'runTest') -> None:
        super().__init__(methodName)
        self.root: Path = Path(tempfile.gettempdir())
        self.rules: inventory.Record = {}

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'scripts').mkdir()
        (self.root / 'docs/reference').mkdir(parents=True)
        for relative in (inventory.SCRIPT, inventory.SCHEMA):
            _ = shutil.copyfile(ROOT / relative, self.root / relative)
        self.rules = {'repository': 'fixture', 'batches': [{'issue': 1, 'title': 'Fixture', 'phase': 'P0', 'scope': 'Fixture diagrams', 'owns_diagrams': True}], 'ownership_rules': [{'id': 'fixture', 'paths': ['*.md', 'docs/**'], 'priority': 1, 'batch_issue': 1, 'rationale': 'Fixture scope'}], 'overrides': {}, 'occurrence_exclusions': [], 'asset_exclusions': [], 'visuals': []}
        _ = (self.root / inventory.RULES).write_text(inventory.encoded(self.rules))
        self.page()

    def page(self, name: str = 'x', body: str = 'A-->B', declared: bool = False) -> None:
        head = f'---\ncontent_sources:\n  diagrams: [{{id: {name}}}]\n---\n' if declared else ''
        _ = (self.root / f'docs/{name}.md').write_text(head + FENCE.format(id=name, body=body))

    def commit(self, mutate: Mutation | None = None) -> inventory.Record:
        manifest = inventory.build(self.root, self.rules, '0' * 40)
        if mutate is not None:
            _ = mutate(manifest)
        _ = (self.root / inventory.MANIFEST).write_text(inventory.encoded(manifest))
        return manifest

    def started(self, state: str = 'completed', target: Mapping[str, object] | None = None) -> inventory.Record:
        self.page(declared=True)
        manifest = inventory.build(self.root, self.rules, '0' * 40)
        manifest['diagrams'][0]['migration'] = migration(state)
        manifest['diagrams'][0]['target'].update(target or {})
        return manifest

    def spec(self, enrolled: str = 'docs/x.md#x') -> None:
        page, identifier = enrolled.split('#')
        spec = {'base': {'id': 'appservice'}, 'extensions': {'ingress-pe': {}, 'egress-vnet': {}}, 'overlays': {'egress-failure': {}},
                'diagrams': [{'id': identifier, 'page': page, 'base': 'appservice', 'extensions': ['ingress-pe'], 'overlay': None}]}
        _ = (self.root / guard.COMPOSITION).write_text(json.dumps(spec))

    def run_guard(self) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = guard.main(['--root', str(self.root)])
        return code, out.getvalue(), err.getvalue()

    def cli(self, script: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(script), '--root', str(self.root), *args], cwd=tempfile.gettempdir(),
                              capture_output=True, text=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})

    def test_a_manifest_that_covers_the_tree_passes(self):
        _ = self.commit()
        code, out, err = self.run_guard()
        self.assertEqual((code, err), (0, ''))
        self.assertIn('check passed (1 occurrences, 0 with a started migration)', out)

    def test_a_missing_manifest_key_fails_until_the_manifest_is_regenerated(self):
        _ = self.commit()
        self.page('new')
        failed = self.cli(GUARD)
        self.assertEqual(failed.returncode, 1, failed.stderr)
        self.assertIn('docs/new.md#new: Mermaid occurrence is not in the manifest', failed.stdout)
        self.assertIn(guard.REGENERATE, failed.stdout)
        self.assertEqual(self.cli(self.root / inventory.SCRIPT, '--write').returncode, 0)
        self.assertEqual(self.cli(GUARD).returncode, 0)

    def test_a_duplicate_manifest_key_fails_before_the_tree_is_compared(self):
        _ = self.commit(lambda m: m['diagrams'].append(copy.deepcopy(m['diagrams'][0])))
        code, out, _ = self.run_guard()
        self.assertEqual(code, 1)
        self.assertIn('diagrams: duplicate key', out)
        self.assertIn('not evaluated', out)

    def test_a_removed_or_renamed_occurrence_fails(self):
        _ = self.commit()
        page = self.root / 'docs/x.md'
        _ = page.write_text(page.read_text().replace('diagram-id: x', 'diagram-id: y'))
        self.assertIn('docs/x.md#x: now docs/x.md#y in the tree', self.run_guard()[1])
        page.unlink()
        self.assertIn('docs/x.md#x: manifest record has no Mermaid occurrence in the tree', self.run_guard()[1])

    def test_a_fence_the_scanner_cannot_recognize_is_not_covered(self):
        _ = self.commit()
        quoted = self.root / 'docs/quoted.md'
        _ = quoted.write_text('> ```mermaid\n> flowchart LR\n> A-->B\n> ```\n')
        code, out, _ = self.run_guard()
        self.assertEqual(code, 1)
        self.assertIn('docs/quoted.md:1: blockquote Mermaid fence cannot be recognized, so the manifest cannot cover it', out)
        self.assertNotIn('is not in the manifest', out)
        _ = quoted.write_text('text\n\n    ```mermaid\n    flowchart LR\n    A-->B\n    ```\n')
        self.assertEqual(self.run_guard()[0], 0)

    def test_edits_to_entries_that_have_not_started_stay_advisory(self):
        for state in ('not-started', 'exception'):
            with self.subTest(state=state):
                self.page()
                _ = self.commit(lambda m: m['diagrams'][0].update(migration=migration(state)))
                self.page(body='A[Changed label]-->B', declared=True)
                self.assertEqual(self.run_guard()[0], 0)
                page = self.root / 'docs/x.md'
                _ = page.write_text('\n\n' + page.read_text())
                self.assertEqual(self.run_guard()[0], 0)

    def test_a_started_entry_must_match_the_tree(self):
        for state in ('in-progress', 'completed'):
            with self.subTest(state=state):
                self.page(declared=True)
                _ = self.commit(lambda m: m['diagrams'][0].update(migration=migration(state)))
                self.assertEqual(self.run_guard()[0], 0)
                self.page(body='A[Changed label]-->B', declared=True)
                self.assertIn(f'docs/x.md#x: {state} entry: source differs from the manifest', self.run_guard()[1])
                self.page()
                self.assertIn(f'docs/x.md#x: {state} entry: provenance differs from the manifest', self.run_guard()[1])

    def test_a_started_entry_needs_a_stable_id_and_declared_provenance(self):
        for state in ('in-progress', 'completed'):
            manifest = self.started(state)
            self.assertEqual(guard.migration_problems(manifest), [])
            defects: list[tuple[str, Mutation, str]] = [
                ('no id', lambda m: m['diagrams'][0].update(diagram_id=None), 'requires a stable diagram-id comment'),
                ('provisional id', lambda m: m['diagrams'][0].update(id_provisional=True), 'requires a stable diagram-id comment'),
                ('missing provenance', lambda m: m['diagrams'][0]['provenance'].update(status='missing'), 'requires declared source provenance'),
                ('malformed provenance', lambda m: m['diagrams'][0]['provenance'].update(status='malformed'), 'requires declared source provenance')]
            for name, mutate, message in defects:
                with self.subTest(state=state, defect=name):
                    changed = copy.deepcopy(manifest)
                    _ = mutate(changed)
                    self.assertEqual(guard.migration_problems(changed), [f'docs/x.md#x: migration {state} {message}'])
        self.page()
        for state in ('not-started', 'exception'):
            with self.subTest(state=state):
                _ = self.commit(lambda m: m['diagrams'][0].update(migration=migration(state)))
                self.assertEqual(self.run_guard()[0], 0)
        _ = self.commit(lambda m: m['diagrams'][0].update(migration=migration('completed')))
        code, out, _ = self.run_guard()
        self.assertEqual(code, 1)
        self.assertIn('docs/x.md#x: migration completed requires declared source provenance', out)

    def test_composition_targets_resolve_against_the_spec(self):
        self.spec()
        enrolled = {'base': 'appservice', 'extensions': ['ingress-pe']}
        self.assertEqual(guard.composition_problems(self.root, self.started(target=enrolled)), [])
        defects: list[tuple[str, dict[str, object], str]] = [
            ('unknown base', {'base': 'other'}, "target.base 'other' is not the composition base 'appservice'"),
            ('unknown extension', {'extensions': ['ghost']}, 'unknown extension ghost'),
            ('unknown overlay', {'overlays': ['ghost']}, 'unknown overlay ghost'),
            ('another enrolled selection', {'extensions': ['egress-vnet']}, 'target differs from the enrolled composition'),
            ('no selection for an enrolled output', {'base': None, 'extensions': []}, 'target differs from the enrolled composition')]
        for name, change, message in defects:
            with self.subTest(defect=name):
                errors = guard.composition_problems(self.root, self.started(target={**enrolled, **change}))
                self.assertIn(f'docs/x.md#x: {message}', errors)

    def test_a_bad_composition_reference_fails_the_check(self):
        self.spec()
        self.page(declared=True)

        def mutate(manifest: inventory.Record) -> None:
            manifest['diagrams'][0]['migration'] = migration('in-progress')
            manifest['diagrams'][0]['target'].update(base='appservice', extensions=['ghost'])

        _ = self.commit(mutate)
        code, out, _ = self.run_guard()
        self.assertEqual(code, 1)
        self.assertIn('docs/x.md#x: unknown extension ghost', out)

    def test_a_target_needs_an_enrolled_composition_and_every_enrolled_output_needs_a_record(self):
        self.page('y')
        self.spec('docs/y.md#y')
        self.assertEqual(guard.composition_problems(self.root, self.started()), [])
        self.assertEqual(guard.composition_problems(self.root, self.started('not-started', {'base': 'ghost', 'extensions': ['ghost']})), [])
        self.assertEqual(guard.composition_problems(self.root, self.started(target={'base': 'appservice', 'extensions': ['ingress-pe']})),
                         ['docs/x.md#x: composition target is not enrolled in ' + guard.COMPOSITION])
        self.spec('docs/y.md#ghost')
        self.assertEqual(guard.composition_problems(self.root, self.started('not-started')),
                         ['docs/y.md#ghost: composition output is not in the manifest'])

    def test_the_composition_spec_is_optional(self):
        self.assertEqual(guard.composition_problems(self.root, self.started()), [])
        self.assertEqual(guard.composition_problems(self.root, self.started(target={'base': 'appservice'})),
                         ['docs/x.md#x: composition target requires ' + guard.COMPOSITION])
        for broken in ('{', '[]', '{"base": {}}'):
            with self.subTest(spec=broken):
                _ = (self.root / guard.COMPOSITION).write_text(broken)
                errors = guard.composition_problems(self.root, self.started())
                self.assertEqual(len(errors), 1)
                self.assertTrue(errors[0].startswith(guard.COMPOSITION + ': unreadable composition spec'), errors)

    def test_the_guard_reads_every_enrolled_selection_of_the_committed_spec(self):
        if not (ROOT / guard.COMPOSITION).exists():
            self.skipTest('the opt-in composition prototype is not present')
        spec: inventory.Record = json.loads((ROOT / guard.COMPOSITION).read_text())
        manifest: inventory.Record = json.loads((ROOT / inventory.MANIFEST).read_text())
        self.assertEqual(guard.composition_problems(ROOT, manifest), [])
        self.assertGreater(len(spec['diagrams']), 1)
        for entry in spec['diagrams']:
            key = f'{entry["page"]}#{entry["id"]}'
            with self.subTest(key=key):
                changed = copy.deepcopy(manifest)
                record = next(d for d in changed['diagrams'] if d['key'] == key)
                record['migration'] = migration('in-progress')
                record['target'].update(base=entry['base'], extensions=entry['extensions'], overlays=[entry['overlay']] if entry['overlay'] else [])
                self.assertEqual(guard.composition_problems(ROOT, changed), [])
                record['target']['extensions'] = [*entry['extensions'], 'ghost']
                self.assertIn(f'{key}: unknown extension ghost', guard.composition_problems(ROOT, changed))

    def test_the_content_sources_job_runs_the_guard_and_its_tests_as_blocking_steps(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/validate-content-sources.yml').read_text(encoding='utf-8'))
        job = workflow['jobs']['validate-content-sources']
        wanted = {'python scripts/test_check_diagram_manifest_coverage.py', 'python scripts/check_diagram_manifest_coverage.py'}
        steps = {' '.join(str(step.get('run', '')).split()): step for step in job['steps']}
        self.assertLessEqual(wanted, steps.keys())
        self.assertFalse(job.get('continue-on-error'))
        self.assertFalse([command for command in wanted if steps[command].get('continue-on-error')])

    def test_unusable_inputs_are_reported_without_a_traceback(self):
        missing = self.cli(GUARD)
        self.assertEqual(missing.returncode, 1)
        self.assertIn(f'{inventory.MANIFEST} is missing; run {guard.REGENERATE}', missing.stderr)
        _ = (self.root / inventory.MANIFEST).write_text('{')
        unreadable = self.cli(GUARD)
        self.assertEqual(unreadable.returncode, 1)
        self.assertTrue(unreadable.stderr.startswith('diagram manifest coverage: '), unreadable.stderr)
        self.assertNotIn('Traceback', unreadable.stderr)


if __name__ == '__main__':
    _ = unittest.main(verbosity=2)
