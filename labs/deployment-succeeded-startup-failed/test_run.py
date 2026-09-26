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
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.run = {'run_id': 'fixture', 'resource_id': '/subscriptions/example/resourceGroups/lab/providers/Microsoft.Web/sites/app',
                    'started_at': '2026-01-01T00:00:00+00:00', 'ended_at': '2026-01-01T00:04:00+00:00',
                    'fingerprints': pilot.fingerprints()}
        self.phases = {}
        for phase, minute, status in [('baseline', 0, 200), ('fault', 1, 503), ('recovery', 3, 200)]:
            self.phases[phase] = dict(run_id='fixture', resource_id=self.run['resource_id'],
                started_at=f'2026-01-01T00:0{minute}:00+00:00', ended_at=f'2026-01-01T00:0{minute}:30+00:00',
                status=status, startup=pilot.BAD if phase == 'fault' else pilot.GOOD,
                command_exit=0, probes=[{'status': status, 'exit_code': 0}])
        self.logs = [{'TimeGenerated': '2026-01-01T00:01:10+00:00', '_ResourceId': self.run['resource_id'],
                      'ResultDescription': "ModuleNotFoundError: No module named 'wrong_module'"}]

    def result(self):
        return pilot.evaluate(self.run, self.phases, self.logs)['evidence_validation']

    def hypothesis(self):
        return pilot.evaluate(self.run, self.phases, self.logs)['hypothesis_evaluation']

    def test_valid(self):
        self.assertEqual(self.result(), 'PASS')

    def test_valid_run_supports_the_hypothesis(self):
        self.assertEqual(self.hypothesis(), 'SUPPORTED')

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

        outcome = pilot.evaluate(self.run, self.phases, self.logs)
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
        axis stays PASS and only the hypothesis axis records REFUTED.
        Collapsing it into FAIL/INCONCLUSIVE would report a real refutation
        as a broken experiment.
        """
        for probe in self.phases['fault']['probes']:
            probe['status'] = 200
        self.phases['fault']['status'] = 200
        self.phases['fault']['intervention_activated'] = True
        self.logs = []

        outcome = pilot.evaluate(self.run, self.phases, self.logs)
        self.assertEqual(outcome['evidence_validation'], 'PASS')
        self.assertEqual(outcome['hypothesis_evaluation'], 'REFUTED')

    def test_refutation_is_not_reported_as_success(self):
        for probe in self.phases['fault']['probes']:
            probe['status'] = 200
        self.phases['fault']['status'] = 200
        self.phases['fault']['intervention_activated'] = True
        self.logs = []
        outcome = pilot.evaluate(self.run, self.phases, self.logs)
        self.assertNotEqual(
            pilot.exit_code_for(outcome),
            0,
            msg='a refuted hypothesis must not exit 0 and look like a confirmed reproduction',
        )

    def test_non_5xx_fault_response_refutes_rather_than_breaks_the_run(self):
        for probe in self.phases['fault']['probes']:
            probe['status'] = 404
        self.phases['fault']['status'] = 404
        self.phases['fault']['intervention_activated'] = True
        self.logs = []

        outcome = pilot.evaluate(self.run, self.phases, self.logs)
        self.assertEqual(outcome['evidence_validation'], 'PASS')
        self.assertEqual(outcome['hypothesis_evaluation'], 'REFUTED')
        self.assertTrue(any('404' in item for item in outcome['refutations']))

    def test_integrity_failure_outranks_refutation(self):
        for probe in self.phases['fault']['probes']:
            probe['status'] = 200
        self.phases['fault']['status'] = 200
        self.phases['fault']['intervention_activated'] = True
        self.phases['fault']['run_id'] = 'other'
        self.logs = []

        outcome = pilot.evaluate(self.run, self.phases, self.logs)
        self.assertEqual(outcome['evidence_validation'], 'FAIL')
        self.assertEqual(
            outcome['hypothesis_evaluation'],
            'INCONCLUSIVE',
            msg='a broken capture cannot refute anything; it can only fail to judge',
        )

    def test_exit_codes_separate_every_outcome(self):
        supported = pilot.evaluate(self.run, self.phases, self.logs)
        self.assertEqual(pilot.exit_code_for(supported), 0)

        self.logs = []
        inconclusive = pilot.evaluate(self.run, self.phases, self.logs)
        self.assertEqual(inconclusive['evidence_validation'], 'INCONCLUSIVE')
        self.assertEqual(pilot.exit_code_for(inconclusive), 2)

        for probe in self.phases['fault']['probes']:
            probe['status'] = 200
        self.phases['fault']['status'] = 200
        self.phases['fault']['intervention_activated'] = True
        refuted = pilot.evaluate(self.run, self.phases, self.logs)
        self.assertEqual(refuted['hypothesis_evaluation'], 'REFUTED')
        self.assertEqual(pilot.exit_code_for(refuted), 3)

        self.phases['fault']['run_id'] = 'other'
        failed = pilot.evaluate(self.run, self.phases, self.logs)
        self.assertEqual(pilot.exit_code_for(failed), 1)

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
        self.run['fingerprints']['main.bicep'] = 'stale'
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
        self.run['execution_status'] = 'COMPLETED'
        self.run['artifacts'] = {str(path.relative_to(folder)): {
            'size': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in folder.rglob('*.json')}
        pilot.write_json(folder / 'run.json', self.run)

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
                    self.assertEqual(pilot.evaluate_folder(folder), 1)

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
            self.run['execution_status'] = 'FAILED'
            (folder / 'run.json').write_text(json.dumps(self.run))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pilot.evaluate_folder(folder), 1)

    def test_fault_error_still_attempts_recovery_and_preserves_new_runs(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = SimpleNamespace(output=temporary, resource_group='lab', app='app')
            app = json.dumps({'id': self.run['resource_id'], 'defaultHostName': 'example.com'})
            for _ in range(2):
                with mock.patch.object(pilot, 'command', return_value='fixture-source'), \
                     mock.patch.object(pilot, 'azure', return_value=app), \
                     mock.patch.object(pilot, 'phase', side_effect=[{}, RuntimeError('fault failure'), {}]) as phase, \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(pilot.execute(args), 1)
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
                args = SimpleNamespace(run_dir=temporary, resource_group='lab')
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


if __name__ == '__main__':
    unittest.main()
