"""Non-promoting Docker experiment; never used by the production controller."""
import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

from autonomy.search import SKETCHES
from autonomy.tasks import Task
from autonomy.verifier import TaskVerifier
from sandbox.runner import SandboxRunner


class OracleAblatedVerifier(TaskVerifier):
    def check(self, source, task, cases):
        return self.runner.execute(source, cases, entrypoint=task.family)


def candidates():
    correct = SKETCHES['lower_bound']
    tail = correct.replace('def lower_bound(values, target):',
                           'def lower_bound(values, target):\n    if len(values) > 8:\n        return 0')
    return [
        ('correct', correct, False),
        ('constant_output', 'def lower_bound(values, target):\n    return 0\n', True),
        ('long_input_corruption', tail, True),
        ('linear_work', 'def lower_bound(values, target):\n    for index in range(len(values)):\n        if values[index] >= target:\n            return index\n    return len(values)\n', True),
    ]


def acceptance(rows):
    expected = {name for name, _, _ in candidates()}
    if len(rows) != len(expected) or {row['name'] for row in rows} != expected:
        raise ValueError('missing or duplicate candidate evidence')
    return {
        'intact_rejects_all_designated_faults': all(
            not r['intact']['passed'] for r in rows if r['designated_fault']),
        'correct_reference_passes_both': all(
            r['intact']['passed'] and r['oracle_ablated']['passed']
            and r['separate_audit']['outputs_correct']
            for r in rows if not r['designated_fault']),
        'ablation_exposes_semantic_faults': all(
            r['oracle_ablated']['passed'] and not r['separate_audit']['outputs_correct']
            for r in rows if r['name'] in ('constant_output', 'long_input_corruption')),
        'work_budget_still_rejects_linear_program': all(
            not r['oracle_ablated']['passed']
            and r['oracle_ablated']['gates'][-1]['name'] == 'performance'
            for r in rows if r['name'] == 'linear_work'),
    }


def run_study():
    task = Task('lower_bound')
    audit_cases = task.samples(64, seed=880301, audit=True)
    rows = []
    for name, source, fault in candidates():
        reports = {}
        for mode, verifier in (('intact', TaskVerifier), ('oracle_ablated', OracleAblatedVerifier)):
            runner = SandboxRunner()
            start = time.monotonic()
            reports[mode] = verifier(runner).verify(source, task, {})
            reports[mode]['container_runs'] = runner.container_runs
            reports[mode]['wall_seconds'] = time.monotonic() - start
        audit_runner = SandboxRunner()
        audit_runner.boot()
        audit = audit_runner.execute(source, audit_cases, entrypoint=task.family)
        rows.append({
            'name': name, 'designated_fault': fault,
            'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
            'source': source, **reports,
            'separate_audit': {'cases': len(audit_cases),
                               'outputs_correct': audit['outputs'] == task.expected(audit_cases),
                               'container_runs': audit_runner.container_runs},
        })
    checks = acceptance(rows)
    return {'protocol': 'oracle-ablation-v1', 'rows': rows, 'checks': checks,
            'accepted': all(checks.values()), 'automatic_promotion': False,
            'python': platform.python_version(),
            'limitations': ['Developer-designed faults and audit, not independent third-party evaluation.',
                            'Audit inputs are deterministic regression cases, not secret future holdouts.',
                            'Oracle ablation removes output comparisons across all gates together.',
                            'Containment is held intact; this does not measure sandbox escape resistance.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_study()
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('ABLATION_RESULT ' + json.dumps(result, sort_keys=True))
    if not result['accepted']:
        raise SystemExit('ablation acceptance failed; evidence preserved')
