"""Offline synthetic fixtures; never Azure execution evidence."""
import contextlib
import hashlib
import io
import json
import importlib.util
import pathlib
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location('pilot', ROOT / 'run.py')
assert spec is not None and spec.loader is not None
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


class EvaluationTests(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super().__init__(methodName)
        self.capture = {'run_id': 'fixture', 'resource_id': '/subscriptions/example/resourceGroups/lab/providers/Microsoft.Web/sites/app',
                    'started_at': '2026-01-01T00:00:00+00:00', 'ended_at': '2026-01-01T00:04:00+00:00',
                    'fingerprints': pilot.fingerprints()}
        self.phases = {}
        for phase, minute, status in [('baseline', 0, 200), ('fault', 1, 503), ('recovery', 3, 200)]:
            self.phases[phase] = dict(run_id='fixture', resource_id=self.capture['resource_id'],
                started_at=f'2026-01-01T00:0{minute}:00+00:00', ended_at=f'2026-01-01T00:0{minute}:30+00:00',
                status=status, startup=pilot.BAD if phase == 'fault' else pilot.GOOD,
                command_exit=0, probes=[{'status': status, 'exit_code': 0}])
        self.logs = [{'TimeGenerated': '2026-01-01T00:01:10+00:00', '_ResourceId': self.capture['resource_id'],
                      'ResultDescription': "ModuleNotFoundError: No module named 'wrong_module'"}]

    def result(self):
        return pilot.evaluate(self.capture, self.phases, self.logs)['evidence_validation']

    def hypothesis(self):
        return pilot.evaluate(self.capture, self.phases, self.logs)['hypothesis_evaluation']

    def test_valid(self):
        self.assertEqual(self.result(), 'PASS')

    def test_valid_run_supports_the_hypothesis(self):
        self.assertEqual(self.hypothesis(), 'SUPPORTED')

    def test_forged_activation_flag_is_not_trusted(self):
        """The derived flag must be recomputed, never believed.

        `intervention_activated` is written by the runner. If the evaluator
        trusts it, a phase can assert its own activation without the
        readback or probe evidence that defines it - the same summary-over-raw
        inversion these gates exist to prevent.
        """
        for probe in self.phases['fault']['probes']:
            probe['status'] = 200
        self.phases['fault']['status'] = 200
        self.phases['fault']['intervention_activated'] = True
        self.phases['fault'].pop('config_readback', None)
        self.phases['fault'].pop('probe_budget_exhausted', None)
        self.logs = []

        outcome = pilot.evaluate(self.capture, self.phases, self.logs)
        self.assertNotEqual(
            outcome['hypothesis_evaluation'],
            'CONTRADICTED',
            msg='a self-asserted activation flag must not license a refutation',
        )

    def test_activation_requires_the_configuration_to_read_back_unchanged(self):
        for probe in self.phases['fault']['probes']:
            probe['status'] = 200
        self.phases['fault']['status'] = 200
        self.phases['fault']['probes'] = [{'status': 200, 'exit_code': 0} for _ in range(24)]
        self.phases['fault'].update(
            intervention_activated=True,
            config_readback=pilot.GOOD,
            probe_budget_exhausted=True,
        )
        self.logs = []

        outcome = pilot.evaluate(self.capture, self.phases, self.logs)
        self.assertNotEqual(outcome['hypothesis_evaluation'], 'CONTRADICTED')

    def test_healthy_fault_without_activation_proof_is_inconclusive(self):
        """A control-plane write is not proof the workload picked it up.

        ``az webapp config set`` returning the requested appCommandLine only
        shows the configuration was accepted. The worker may not have been
        recycled inside the bounded probe window, so a still-healthy app is
        ambiguous between "the entrypoint does not matter" and "the change
        had not taken effect yet". Only the first of those is a refutation.
        """
        for probe in self.phases['fault']['probes']:
            probe['status'] = 200
        self.phases['fault']['status'] = 200
        self.phases['fault'].pop('intervention_activated', None)
        self.logs = []

        outcome = pilot.evaluate(self.capture, self.phases, self.logs)
        self.assertEqual(outcome['hypothesis_evaluation'], 'INCONCLUSIVE')
        self.assertEqual(outcome['evidence_validation'], 'INCONCLUSIVE')
        self.assertTrue(
            any('take effect' in item or 'activation' in item for item in outcome['limitations']),
            msg='the run must say why a healthy fault was not treated as a refutation',
        )

    def test_clean_fault_that_stays_healthy_refutes_the_hypothesis(self):
        """A correctly applied fault that never breaks the app is a refutation.

        The contract predicts HTTP 5xx plus a matching import error. If the
        bad entrypoint is genuinely configured, every probe still answers
        200, and nothing about the capture is malformed, the prediction is
        contradicted. That is a valid experimental result, so the evidence
        axis stays PASS and only the hypothesis axis records CONTRADICTED.
        Collapsing it into FAIL/INCONCLUSIVE would report a real refutation
        as a broken experiment.
        """
        for probe in self.phases['fault']['probes']:
            probe['status'] = 200
        self.phases['fault']['status'] = 200
        self.phases['fault'].update(intervention_activated=True, config_readback=pilot.BAD, probe_budget_exhausted=True)
        self.phases['fault']['probes'] = [{'status': self.phases['fault']['status'], 'exit_code': 0} for _ in range(24)]
        self.logs = []

        outcome = pilot.evaluate(self.capture, self.phases, self.logs)
        self.assertEqual(outcome['evidence_validation'], 'PASS')
        self.assertEqual(outcome['hypothesis_evaluation'], 'CONTRADICTED')

    def test_refutation_is_not_reported_as_success(self):
        for probe in self.phases['fault']['probes']:
            probe['status'] = 200
        self.phases['fault']['status'] = 200
        self.phases['fault'].update(intervention_activated=True, config_readback=pilot.BAD, probe_budget_exhausted=True)
        self.phases['fault']['probes'] = [{'status': self.phases['fault']['status'], 'exit_code': 0} for _ in range(24)]
        self.logs = []
        outcome = pilot.evaluate(self.capture, self.phases, self.logs)
        self.assertNotEqual(
            pilot.exit_code_for(outcome),
            0,
            msg='a refuted hypothesis must not exit 0 and look like a confirmed reproduction',
        )

    def test_non_5xx_fault_response_refutes_rather_than_breaks_the_run(self):
        for probe in self.phases['fault']['probes']:
            probe['status'] = 404
        self.phases['fault']['status'] = 404
        self.phases['fault'].update(intervention_activated=True, config_readback=pilot.BAD, probe_budget_exhausted=True)
        self.phases['fault']['probes'] = [{'status': self.phases['fault']['status'], 'exit_code': 0} for _ in range(24)]
        self.logs = []

        outcome = pilot.evaluate(self.capture, self.phases, self.logs)
        self.assertEqual(outcome['evidence_validation'], 'PASS')
        self.assertEqual(outcome['hypothesis_evaluation'], 'CONTRADICTED')
        self.assertTrue(any('404' in item for item in outcome['refutations']))

    def test_integrity_failure_outranks_refutation(self):
        for probe in self.phases['fault']['probes']:
            probe['status'] = 200
        self.phases['fault']['status'] = 200
        self.phases['fault'].update(intervention_activated=True, config_readback=pilot.BAD, probe_budget_exhausted=True)
        self.phases['fault']['probes'] = [{'status': self.phases['fault']['status'], 'exit_code': 0} for _ in range(24)]
        self.phases['fault']['run_id'] = 'other'
        self.logs = []

        outcome = pilot.evaluate(self.capture, self.phases, self.logs)
        self.assertEqual(outcome['evidence_validation'], 'FAIL')
        self.assertEqual(
            outcome['hypothesis_evaluation'],
            'INCONCLUSIVE',
            msg='a broken capture cannot refute anything; it can only fail to judge',
        )

    def test_exit_codes_separate_every_outcome(self):
        supported = pilot.evaluate(self.capture, self.phases, self.logs)
        self.assertEqual(pilot.exit_code_for(supported), 0)

        self.logs = []
        inconclusive = pilot.evaluate(self.capture, self.phases, self.logs)
        self.assertEqual(inconclusive['evidence_validation'], 'INCONCLUSIVE')
        self.assertEqual(pilot.exit_code_for(inconclusive), 2)

        for probe in self.phases['fault']['probes']:
            probe['status'] = 200
        self.phases['fault']['status'] = 200
        self.phases['fault'].update(intervention_activated=True, config_readback=pilot.BAD, probe_budget_exhausted=True)
        self.phases['fault']['probes'] = [{'status': self.phases['fault']['status'], 'exit_code': 0} for _ in range(24)]
        refuted = pilot.evaluate(self.capture, self.phases, self.logs)
        self.assertEqual(refuted['hypothesis_evaluation'], 'CONTRADICTED')
        self.assertEqual(pilot.exit_code_for(refuted), 1)  # CONTRADICTED, matching evaluate_run.py

        self.phases['fault']['run_id'] = 'other'
        failed = pilot.evaluate(self.capture, self.phases, self.logs)
        # Evidence that failed validation supports no hypothesis verdict,
        # so it no longer borrows the code that now means CONTRADICTED.
        self.assertEqual(pilot.exit_code_for(failed), 4)

    def test_raw_contradiction_cannot_be_overridden(self):
        self.phases['fault']['status'] = 200
        self.phases['fault']['verdict'] = 'Overall: PASS'
        self.assertEqual(self.result(), 'FAIL')

    def test_missing_recovery(self):
        del self.phases['recovery']
        self.assertEqual(self.result(), 'FAIL')

    def test_mixed_run(self):
        self.phases['fault']['run_id'] = 'other'
        self.assertEqual(self.result(), 'FAIL')

    def test_other_resource(self):
        self.logs[0]['_ResourceId'] += '-other'
        self.assertEqual(self.result(), 'FAIL')

    def test_wrong_window(self):
        self.logs[0]['TimeGenerated'] = '2026-01-02T00:01:10+00:00'
        self.assertEqual(self.result(), 'FAIL')

    def test_no_logs_inconclusive(self):
        self.logs = []
        self.assertEqual(self.result(), 'INCONCLUSIVE')

    def test_transport_failure_not_fault_evidence(self):
        self.phases['fault']['status'] = 0
        self.phases['fault']['probes'] = [{'status': 0, 'exit_code': 28}]
        self.assertEqual(self.result(), 'INCONCLUSIVE')

    def test_source_changed(self):
        self.capture['fingerprints'] = dict(pilot.fingerprints(), **{'main.bicep': 'stale'})
        self.assertEqual(self.result(), 'FAIL')

    def test_probe_summary_mismatch(self):
        self.phases['recovery']['probes'][-1]['status'] = 503
        self.assertEqual(self.result(), 'FAIL')

    def test_recovery_failure(self):
        self.phases['recovery']['status'] = 503
        self.phases['recovery']['probes'][-1]['status'] = 503
        self.assertEqual(self.result(), 'FAIL')

    def fixture_folder(self, folder):
        for name, value in self.phases.items():
            (folder / name).mkdir()
            pilot.write_json(folder / name / 'phase.json', value)
        pilot.write_json(folder / 'console.json', self.logs)
        self.capture['execution_status'] = 'COMPLETE'
        self.capture['artifacts'] = {str(path.relative_to(folder)): {
            'size': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in folder.rglob('*.json')}
        pilot.write_json(folder / 'run.json', self.capture)

    def test_missing_empty_and_malformed_evidence(self):
        for content in (None, '', '{broken'):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as temporary:
                folder = pathlib.Path(temporary)
                self.fixture_folder(folder)
                target = folder / 'console.json'
                if content is None:
                    target.unlink()
                else:
                    target.write_text(content)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(pilot.evaluate_folder(folder), 4)  # evidence FAIL, not CONTRADICTED

    def test_repeated_evaluation_preserves_capture(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = pathlib.Path(temporary)
            self.fixture_folder(folder)
            before = (folder / 'run.json').read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pilot.evaluate_folder(folder), 0)
                self.assertEqual(pilot.evaluate_folder(folder), 0)
            self.assertEqual((folder / 'run.json').read_bytes(), before)
            self.assertEqual(len(list(folder.glob('evaluation-*.json'))), 2)

    def test_failed_execution_not_promoted(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = pathlib.Path(temporary)
            self.fixture_folder(folder)
            self.capture['execution_status'] = 'FAILED'
            (folder / 'run.json').write_text(json.dumps(self.capture))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pilot.evaluate_folder(folder), 4)  # evidence FAIL, not CONTRADICTED

    def test_fault_error_still_attempts_recovery_and_preserves_new_runs(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = SimpleNamespace(output=temporary, resource_group='lab', app='app')
            app = json.dumps({'id': self.capture['resource_id'], 'defaultHostName': 'example.com'})
            for _ in range(2):
                with mock.patch.object(pilot, 'command', return_value='fixture-source'), \
                     mock.patch.object(pilot, 'azure', return_value=app), \
                     mock.patch.object(pilot, 'phase', side_effect=[{}, RuntimeError('fault failure'), {}]) as phase, \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(pilot.execute(args), 4)  # evidence FAIL, not CONTRADICTED
                    self.assertEqual([call.args[2] for call in phase.call_args_list],
                                     ['baseline', 'fault', 'recovery'])
            captures = list(pathlib.Path(temporary).glob('*/run.json'))
            self.assertEqual(len(captures), 2)
            for capture in captures:
                self.assertEqual(json.loads(capture.read_text())['execution_status'], 'FAILED')

    def test_cleanup_only_verified_when_group_absent(self):
        for exists, expected in [('true', 1), ('false', 0)]:
            with self.subTest(exists=exists), tempfile.TemporaryDirectory() as temporary:
                folder = pathlib.Path(temporary)
                pilot.write_json(folder / 'run.json', {'run_id': 'fixture', 'resource_group': 'lab'})
                args = SimpleNamespace(run_dir=temporary, resource_group='lab', github_run_id=None)
                with mock.patch.object(pilot, 'azure', return_value=exists), \
                     mock.patch.object(pilot.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(pilot.cleanup(args), expected)

    def test_exclusive_write(self):
        with tempfile.TemporaryDirectory() as folder:
            target = pathlib.Path(folder) / 'phase.json'
            pilot.write_json(target, {'first': True})
            with self.assertRaises(FileExistsError):
                pilot.write_json(target, {'second': True})
            self.assertIn('first', target.read_text())


class CleanupTests(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super().__init__(methodName)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = pathlib.Path(self.temporary.name)
        self.group = 'rg-golden-e2e-12345-2'
        self.identity = '12345-2'
        self.tags = {'owner': 'golden-e2e',
                     'repository': 'yeongseon/azure-app-service-practical-guide',
                     'run-id': self.identity}
        self.args = SimpleNamespace(run_dir=str(self.folder), resource_group=self.group,
                                    github_run_id=self.identity)
        self.exists = [True, False]
        self.tag_response = None
        self.calls = []

    def command(self, folder, label, argv):
        self.calls.append(argv)
        if argv[1:3] == ['group', 'exists']:
            output = json.dumps(self.exists.pop(0))
        elif argv[1:3] == ['group', 'show']:
            if isinstance(self.tag_response, Exception):
                raise self.tag_response
            output = self.tag_response if self.tag_response is not None else json.dumps(self.tags)
        elif argv[1:3] == ['group', 'delete']:
            output = ''
        else:
            self.fail(f'Unexpected command: {argv}')
        pilot.write_json(folder / f'{label}.json', {'argv': argv, 'stdout': output, 'exit_code': 0})
        return output

    def cleanup(self):
        pilot.write_json(self.folder / 'run.json', {'run_id': 'fixture', 'resource_group': self.group})
        with mock.patch.object(pilot, 'command', side_effect=self.command), \
             mock.patch.object(pilot.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
            code = pilot.cleanup(self.args)
        result = json.loads(next(self.folder.glob('cleanup-*/result.json')).read_text())
        return code, result

    def assert_blocked(self, check):
        code, result = self.cleanup()
        self.assertEqual(code, 1)
        self.assertEqual(result['cleanup_status'], 'BLOCKED')
        self.assertEqual(result['error'], 'ownership-unproven')
        self.assertEqual(result['failed_check'], check)
        self.assertFalse(any(argv[1:3] == ['group', 'delete'] for argv in self.calls))

    def test_missing_operator_identity_blocks_even_with_matching_tags(self):
        self.args.github_run_id = None
        self.assert_blocked('github-run-id-required')

    def test_caller_group_must_match_recorded_group(self):
        self.args.resource_group = 'rg-golden-e2e-999-1'
        self.assert_blocked('recorded-group')
        self.assertEqual(self.calls, [])

    def test_wrong_owned_name_blocks(self):
        self.group = self.args.resource_group = 'foreign'
        self.assert_blocked('owned-name')

    def test_similar_foreign_group_name_blocks(self):
        self.group = self.args.resource_group = self.group + '-foreign'
        self.assert_blocked('owned-name')

    def test_timestamp_capture_identity_cannot_authorize_deletion(self):
        self.args.github_run_id = '20261105T000000Z-abcdef123456'
        self.assert_blocked('owned-name')

    def test_wrong_owner_blocks(self):
        self.tags['owner'] = 'foreign'
        self.assert_blocked('run-ownership')

    def test_missing_owner_blocks(self):
        del self.tags['owner']
        self.assert_blocked('run-ownership')

    def test_wrong_repository_blocks(self):
        self.tags['repository'] = 'example/foreign'
        self.assert_blocked('run-ownership')

    def test_missing_repository_blocks(self):
        del self.tags['repository']
        self.assert_blocked('run-ownership')

    def test_run_id_tag_mismatch_blocks(self):
        self.tags['run-id'] = '12345-1'
        self.assert_blocked('run-ownership')

    def test_missing_run_id_tag_blocks(self):
        del self.tags['run-id']
        self.assert_blocked('run-ownership')

    def test_tags_readback_failure_blocks(self):
        self.tag_response = RuntimeError('mock readback failed')
        self.assert_blocked('tags-readback')

    def test_malformed_tags_readback_blocks(self):
        self.tag_response = '{broken'
        self.assert_blocked('tags-readback')

    def test_null_tags_readback_blocks(self):
        self.tag_response = 'null'
        self.assert_blocked('tags-readback')

    def test_ambiguous_exists_readback_blocks(self):
        self.exists = [None]
        self.assert_blocked('group-exists-readback')

    def test_absent_group_is_verified_without_identity_or_deletion(self):
        self.exists = [False]
        self.args.github_run_id = None
        code, result = self.cleanup()
        self.assertEqual((code, result['cleanup_status']), (0, 'VERIFIED'))
        self.assertEqual(self.calls, [['az', 'group', 'exists', '--name', self.group, '--output', 'json']])
        self.assertFalse(any(argv[1:3] == ['group', 'delete'] for argv in self.calls))

    def test_owned_group_deletion_has_exact_argv_and_verified_absence(self):
        code, result = self.cleanup()
        self.assertEqual((code, result['cleanup_status']), (0, 'VERIFIED'))
        self.assertEqual(self.calls, [
            ['az', 'group', 'exists', '--name', self.group, '--output', 'json'],
            ['az', 'group', 'show', '--name', self.group, '--query', 'tags', '--output', 'json'],
            ['az', 'group', 'delete', '--name', self.group, '--yes', '--no-wait', '--output', 'json'],
            ['az', 'group', 'exists', '--name', self.group, '--output', 'json'],
        ])
        self.assertEqual(result['ownership_tags'], self.tags)
        self.assertEqual(len(list(self.folder.glob('cleanup-*/*.json'))), 5)

    def test_deletion_without_confirmed_absence_fails(self):
        self.exists = [True] * 31
        code, result = self.cleanup()
        self.assertEqual((code, result['cleanup_status']), (1, 'FAILED'))

    def test_copyable_guard_matches_shared_helper(self):
        shared_spec = importlib.util.spec_from_file_location(
            'shared_cleanup', ROOT.parents[1] / 'scripts/golden/azure_cleanup.py')
        assert shared_spec is not None and shared_spec.loader is not None
        shared = importlib.util.module_from_spec(shared_spec)
        shared_spec.loader.exec_module(shared)
        valid = {'owner': shared.OWNER, 'repository': shared.REPOSITORY, 'run-id': self.identity}
        for identity in (self.identity, '0-1', '123-01', '123-0', 'fixture', self.identity + '\n'):
            for name in (self.group, shared.GROUP_PREFIX + identity, self.group + '-foreign'):
                for tags in (valid, {}, dict(valid, owner='foreign'),
                             dict(valid, repository='foreign'), dict(valid, **{'run-id': '999-1'})):
                    with self.subTest(identity=identity, name=name, tags=tags):
                        try:
                            shared.require_owned_name(name, identity)
                            shared.require_run_ownership(tags, identity)
                        except shared.CleanupError:
                            with self.assertRaises(pilot.CleanupOwnershipError):
                                pilot.require_cleanup_ownership(name, tags, identity)
                        else:
                            pilot.require_cleanup_ownership(name, tags, identity)


if __name__ == '__main__':
    unittest.main()
