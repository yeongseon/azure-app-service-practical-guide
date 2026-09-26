#!/usr/bin/env python3
"""One App Service startup experiment. Offline evaluation needs no Azure credentials."""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
GOOD = 'gunicorn --bind=0.0.0.0:8000 --timeout=120 app:app'
BAD = GOOD.replace('app:app', 'wrong_module:app')


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def stamp(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timestamps require timezone')
    return parsed


def fingerprints():
    files = [ROOT / name for name in ('run.py', 'main.bicep', 'trigger.sh', 'verify.sh', 'contract.json')]
    files += sorted((ROOT / 'app').glob('*'))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files if p.is_file()}


def write_json(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, indent=2)
        handle.write('\n')


def evaluate(run, phases, logs):
    """Recompute from phase probes and resource/time-scoped raw console rows."""
    errors, gaps, refutations = [], [], []
    fault_showed_predicted_symptom = False
    try:
        if run['fingerprints'] != fingerprints():
            errors.append('Experiment files changed: old evidence requires review of its original source.')
        start, end = stamp(run['started_at']), stamp(run['ended_at'])
        previous = start
        for name in ('baseline', 'fault', 'recovery'):
            phase = phases[name]
            if phase['run_id'] != run['run_id'] or phase['resource_id'].lower() != run['resource_id'].lower():
                errors.append(f'{name}: mixed run/resource')
            a, b = stamp(phase['started_at']), stamp(phase['ended_at'])
            if not previous <= a <= b <= end:
                errors.append(f'{name}: phase order/window mismatch')
            previous = b
            if phase['command_exit'] != 0 or phase['startup'] != (BAD if name == 'fault' else GOOD):
                errors.append(f'{name}: command/configuration failed')
            probes = phase['probes']
            if not probes or phase['status'] != probes[-1]['status']:
                errors.append(f'{name}: raw probe/summary mismatch')
                continue
            final = probes[-1]
            if name == 'fault':
                # A response other than the predicted 5xx only refutes the
                # hypothesis if the intervention actually reached the running
                # worker. `az webapp config set` returning the requested
                # command proves the control plane accepted it, not that the
                # worker was recycled inside the probe window, so without
                # activation evidence a healthy app is ambiguous between "the
                # entrypoint does not matter" and "the change had not taken
                # effect yet". Only the first is a refutation.
                activated = phase.get('intervention_activated') is True
                if final['exit_code'] != 0 or final['status'] == 0:
                    gaps.append('Fault only produced a transport error, not an HTTP failure')
                elif 500 <= final['status'] <= 599:
                    fault_showed_predicted_symptom = True
                elif not activated:
                    gaps.append(
                        f'Fault returned HTTP {final["status"]} but the configuration was not '
                        'shown to take effect on the running worker, so this cannot be read '
                        'as a refutation'
                    )
                elif final['status'] == 200:
                    refutations.append('Fault configuration took effect but the app stayed healthy at HTTP 200')
                else:
                    refutations.append(f'Fault produced HTTP {final["status"]}, not the predicted 5xx')
            elif final['status'] != 200 or final['exit_code'] != 0:
                errors.append(f'{name}: health not verified')
        if not isinstance(logs, list):
            raise ValueError('console export must be a JSON array')
        fault = phases['fault']
        hits = 0
        for row in logs:
            if row['_ResourceId'].lower() != run['resource_id'].lower():
                errors.append('Console record belongs to another resource')
            if not stamp(fault['started_at']) <= stamp(row['TimeGenerated']) <= stamp(fault['ended_at']):
                errors.append('Console record outside fault window')
            message = row['ResultDescription']
            if 'ModuleNotFoundError' in message and 'wrong_module' in message:
                hits += 1
        # Absence of an import error is only a data gap when the app actually
        # failed. If the intervention never produced the predicted symptom,
        # having no import error is consistent with the refutation.
        if not hits and fault_showed_predicted_symptom:
            gaps.append('No matching runtime import error arrived within the collection deadline')
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        errors.append(f'Missing or invalid required evidence: {exc}')
        hits = 0
    verdict = 'FAIL' if errors else ('INCONCLUSIVE' if gaps else 'PASS')
    if errors:
        hypothesis = 'INCONCLUSIVE'
    elif refutations:
        hypothesis = 'REFUTED'
    elif gaps:
        hypothesis = 'INCONCLUSIVE'
    else:
        hypothesis = 'SUPPORTED'
    return {'run_id': run.get('run_id'), 'evaluated_at': now(),
            'evidence_validation': verdict,
            'hypothesis_evaluation': hypothesis,
            'independent_reproduction': 'NOT_RUN', 'matching_import_errors': hits,
            'errors': errors, 'refutations': refutations, 'limitations': gaps + [
                'Hashes detect content changes; they do not attest that Azure execution occurred.',
                'HTTP and import errors support this scoped intervention; other concurrent changes remain a limitation.',
                'A configuration readback plus an exhausted probe budget is the activation evidence used here; '
                'it does not positively prove the serving worker was recycled.']}


def exit_code_for(result):
    """Map a result onto a shell exit code.

    A refuted hypothesis must not share exit 0 with a supported one. Both are
    valid evidence, but exit 0 reads as "the reproduction worked", and the
    contract forbids presenting a refutation as a successful reproduction.
    """
    validation = result['evidence_validation']
    if validation == 'PASS' and result.get('hypothesis_evaluation') == 'REFUTED':
        return 3
    return {'PASS': 0, 'FAIL': 1, 'INCONCLUSIVE': 2}[validation]


def command(folder, label, argv, timeout=900):
    started = now()
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        code, out, err = result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as exc:
        code, out, err = 124, str(exc.stdout or ''), str(exc.stderr or '')
    write_json(folder / f'{label}.json', {'argv': argv, 'started_at': started,
               'ended_at': now(), 'exit_code': code, 'stdout': out, 'stderr': err})
    if code:
        raise RuntimeError(f'{label} failed ({code}); evidence preserved in {folder}')
    return out


def azure(folder, label, args):
    return command(folder, label, ['az', *args, '--output', 'json'])


def phase(folder, run, name, startup, hostname):
    target = folder / name
    target.mkdir()
    record = {'run_id': run['run_id'], 'resource_id': run['resource_id'],
              'started_at': now(), 'command_exit': 0, 'probes': []}
    try:
        config = json.loads(azure(target, 'configure', ['webapp', 'config', 'set', '--ids', run['resource_id'], '--startup-file', startup]))
        record['startup'] = config['appCommandLine']
        # Fixed bounded plan: at most 24 probes, each at most 20 seconds, 10s interval.
        for attempt in range(24):
            captured = now()
            result = subprocess.run(['curl', '--silent', '--show-error', '--output', '/dev/null',
                '--write-out', '%{http_code}', '--max-time', '20', f'https://{hostname}/health'],
                capture_output=True, text=True, timeout=25)
            status = int(result.stdout) if result.stdout.isdigit() else 0
            record['probes'].append({'captured_at': captured, 'status': status,
                                     'exit_code': result.returncode, 'stderr': result.stderr})
            if result.returncode == 0 and ((name == 'fault' and 500 <= status <= 599) or (name != 'fault' and status == 200)):
                break
            if attempt < 23:
                time.sleep(10)
        record['status'] = record['probes'][-1]['status']
        # Read the configuration back after probing. Combined with an
        # exhausted probe budget this is the strongest activation evidence
        # available without a worker-identity signal: the intended command is
        # still in place and the app was observed for the full window rather
        # than only across the first seconds of a rollout. It still does not
        # positively prove a worker recycle, which stays a stated limitation.
        readback = json.loads(azure(target, 'config-readback',
                                    ['webapp', 'config', 'show', '--ids', run['resource_id']]))
        record['config_readback'] = readback.get('appCommandLine')
        record['probe_budget_exhausted'] = len(record['probes']) >= 24
        record['intervention_activated'] = (
            record['config_readback'] == startup and record['probe_budget_exhausted']
        )
    except Exception:
        record['command_exit'] = 1
        raise
    finally:
        record['ended_at'] = now()
        write_json(target / 'phase.json', record)
    if name != 'fault' and record['status'] != 200:
        raise RuntimeError(f'{name} did not become healthy')
    return record


def collect(folder, run, fault):
    workspace = json.loads(azure(folder, 'workspace', ['monitor', 'log-analytics', 'workspace', 'list',
                                                '--resource-group', run['resource_group']]))
    if len(workspace) != 1:
        raise RuntimeError('Dedicated lab must contain exactly one workspace')
    query = ("AppServiceConsoleLogs\n| where _ResourceId =~ '" + run['resource_id'] + "'\n"
             "| where TimeGenerated between (datetime(" + fault['started_at'] + ") .. datetime(" + fault['ended_at'] + "))\n"
             "| project TimeGenerated, _ResourceId, ResultDescription")
    rows = []
    # Bounded ingestion wait: 6 requests, max 60 seconds each, 30s between attempts.
    for attempt in range(6):
        raw = command(folder, f'console-query-{attempt}', ['az', 'monitor', 'log-analytics', 'query',
            '--workspace', workspace[0]['customerId'], '--analytics-query', query, '--output', 'json'], timeout=60)
        rows = json.loads(raw)
        if not isinstance(rows, list):
            raise ValueError('Expected Azure CLI JSON row array')
        if any('ModuleNotFoundError' in row.get('ResultDescription', '') and
               'wrong_module' in row.get('ResultDescription', '') for row in rows):
            break
        if attempt < 5:
            time.sleep(30)
    write_json(folder / 'console.json', rows)


def execute(args):
    folder = pathlib.Path(args.output).resolve() / (dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:12])
    folder.mkdir(parents=True, exist_ok=False)
    print(f'RUN_DIR={folder}', flush=True)
    run = {'run_id': folder.name, 'started_at': now(), 'resource_group': args.resource_group,
           'fingerprints': fingerprints(), 'execution_status': 'RUNNING'}
    try:
        run['source_sha'] = command(folder, 'source-sha', ['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).strip()
        command(folder, 'azure-version', ['az', 'version'])
        command(folder, 'curl-version', ['curl', '--version'])
        run['python_version'] = sys.version
        app = json.loads(azure(folder, 'app', ['webapp', 'show', '--resource-group', args.resource_group, '--name', args.app]))
        run['resource_id'] = app['id']
        # Set a healthy entrypoint before package deployment, including on reused dedicated labs.
        azure(folder, 'initial-config', ['webapp', 'config', 'set', '--ids', app['id'], '--startup-file', GOOD])
        with tempfile.TemporaryDirectory() as temporary:
            package = pathlib.Path(temporary) / 'app.zip'
            with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as archive:
                for path in sorted((ROOT / 'app').glob('*')):
                    if path.is_file():
                        archive.write(path, path.name)
            azure(folder, 'deploy', ['webapp', 'deploy', '--resource-group', args.resource_group, '--name', args.app,
                                  '--src-path', str(package), '--type', 'zip'])
        phase(folder, run, 'baseline', GOOD, app['defaultHostName'])
        try:
            fault = phase(folder, run, 'fault', BAD, app['defaultHostName'])
        finally:
            # Attempt recovery even when fault probing or configuration fails.
            phase(folder, run, 'recovery', GOOD, app['defaultHostName'])
        collect(folder, run, fault)
        run['execution_status'] = 'COMPLETED'
    except Exception as exc:
        run['execution_status'] = 'FAILED'
        run['error'] = str(exc)
    finally:
        run['ended_at'] = now()
        run['cleanup_status'] = 'PENDING'
        run['artifacts'] = {str(path.relative_to(folder)): {'size': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in sorted(folder.rglob('*.json'))}
        write_json(folder / 'run.json', run)
    return evaluate_folder(folder)


def evaluate_folder(folder):
    try:
        run = json.loads((folder / 'run.json').read_text())
        for name, expected in run['artifacts'].items():
            path = (folder / name).resolve()
            if not path.is_relative_to(folder.resolve()):
                raise ValueError('Artifact outside run directory')
            data = path.read_bytes()
            if len(data) != expected['size'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
                raise ValueError(f'Artifact digest/size mismatch: {name}')
        required = ['console.json', *[f'{name}/phase.json' for name in ('baseline', 'fault', 'recovery')]]
        if any(name not in run['artifacts'] for name in required):
            raise ValueError('Required artifact missing from manifest')
        phases = {name: json.loads((folder / name / 'phase.json').read_text()) for name in ('baseline', 'fault', 'recovery')}
        logs = json.loads((folder / 'console.json').read_text())
        result = evaluate(run, phases, logs)
        if run.get('execution_status') != 'COMPLETED':
            result['evidence_validation'] = 'FAIL'
            result['hypothesis_evaluation'] = 'INCONCLUSIVE'
            result['errors'].append('Execution did not complete')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {'evaluated_at': now(), 'evidence_validation': 'FAIL',
                  'hypothesis_evaluation': 'INCONCLUSIVE', 'errors': [str(exc)]}
    # Every evaluation is separate; no prior collection/phase is overwritten.
    write_json(folder / f'evaluation-{uuid.uuid4().hex}.json', result)
    print(json.dumps(result, indent=2))
    return exit_code_for(result)


def cleanup(args):
    folder = pathlib.Path(args.run_dir).resolve()
    run = json.loads((folder / 'run.json').read_text())
    target = folder / ('cleanup-' + uuid.uuid4().hex)
    target.mkdir()
    result = {'run_id': run['run_id'], 'started_at': now(), 'cleanup_status': 'FAILED'}
    try:
        # Caller explicitly supplies the dedicated group, preventing accidental copied-path deletion.
        if args.resource_group != run['resource_group']:
            raise ValueError('Resource group does not match run')
        azure(target, 'delete', ['group', 'delete', '--name', args.resource_group, '--yes', '--no-wait'])
        for attempt in range(30):
            exists = json.loads(azure(target, f'exists-{attempt}', ['group', 'exists', '--name', args.resource_group]))
            if exists is False:
                result['cleanup_status'] = 'VERIFIED'
                break
            if attempt < 29:
                time.sleep(10)
    except Exception as exc:
        result['error'] = str(exc)
    result['ended_at'] = now()
    write_json(target / 'result.json', result)
    print(json.dumps(result, indent=2))
    return 0 if result['cleanup_status'] == 'VERIFIED' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    start = sub.add_parser('execute')
    start.add_argument('resource_group')
    start.add_argument('app')
    start.add_argument('--output', required=True, help='Private evidence directory outside the repository')
    check = sub.add_parser('evaluate')
    check.add_argument('run_dir')
    clean = sub.add_parser('cleanup')
    clean.add_argument('run_dir')
    clean.add_argument('resource_group')
    args = parser.parse_args()
    if args.action == 'execute':
        return execute(args)
    if args.action == 'cleanup':
        return cleanup(args)
    return evaluate_folder(pathlib.Path(args.run_dir))


if __name__ == '__main__':
    sys.exit(main())
