import contextlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from autonomy.verifier import TaskVerifier
from autonomy.tasks import SUITE_VERSION, suite_digest
from core.rollback import VersionController
from memory.skill_store import MemoryEngine
from research.mixed_features import MixedTask
from research.query_fallback import acquire_fallback
from research.skill_contract import acquire, activate, invoke, task_contract

CONFIG = {'upper': 'n + 1', 'direction': 'forward', 'comparison': '<=', 'result': 'low - 1'}
A = {'degree': 4, 'p': 3, 'r': 3, 'q': 0, 'd': 1}
B = {'degree': 3, 'p': 4, 'r': 3, 'q': 1, 'd': 2}


def public(descriptor):
    task = task_contract(descriptor)
    return lambda n: task.expected([(n,)])[0]


def selector(label, mode, seed, **kwargs):
    return acquire_fallback(label, mode, seed)


class OracleRunner:
    """Controller orchestration fake; never evaluates candidate source."""
    def __init__(self, image):
        self.container_runs, self.max_container_runs = 0, 128
        self.deadline = self.stop_file = None

    def boot(self):
        if self.container_runs >= self.max_container_runs:
            raise RuntimeError('container budget exhausted')
        self.container_runs += 1

    def execute(self, source, cases, entrypoint, **kwargs):
        self.boot()
        values = list(map(int, entrypoint.split('_')[2:]))
        task = task_contract(dict(zip(('degree', 'p', 'r', 'q', 'd'), values)))
        return {'outputs': task.expected(cases), 'cpu_seconds': 0.001,
                'peak_bytes': 1000, 'steps_per_case': [10]*len(cases)}


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'state'
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('research.skill_contract.acquire_via_process', side_effect=selector))
        self.stack.enter_context(patch('research.skill_contract.SandboxRunner', OracleRunner))

    def learn(self, descriptor=A):
        return acquire(self.root, descriptor, public(descriptor), CONFIG, seed=920022)

    def current(self):
        memory = MemoryEngine(self.root)
        try:
            return memory.current()
        finally:
            memory.db.close()

    def test_invalid_contract_has_no_state_side_effect(self):
        for descriptor in ({'degree': True}, dict(A, p=True), dict(A, degree=100)):
            with self.assertRaises(ValueError):
                acquire(self.root, descriptor, lambda n: 0, CONFIG)
            self.assertFalse(self.root.exists())

    def test_production_state_cannot_be_mixed_in(self):
        self.root.mkdir()
        sentinel = self.root/'memory.sqlite3'
        sentinel.write_text('production sentinel')
        with self.assertRaisesRegex(ValueError, 'dedicated empty'):
            self.learn()
        self.assertEqual(sentinel.read_text(), 'production sentinel')

    def test_reuse_and_checkpoint_switching(self):
        first, second = self.learn(), self.learn(B)
        self.assertEqual(first['status'], 'certified')
        self.assertIn(task_contract(A).key, second['retention'])
        repeat = acquire(self.root, B, lambda n: self.fail('reacquired labels'), CONFIG)
        self.assertEqual((repeat['label_queries'], repeat['containers']), (0, 0))
        activate(self.root, first['checkpoint'])
        with self.assertRaisesRegex(ValueError, 'no current contract certification'):
            invoke(self.root, task_contract(B).key, 100)
        activate(self.root, second['checkpoint'])
        self.assertEqual(invoke(self.root, task_contract(B).key, 100)['output'], public(B)(100))
        with self.assertRaises(ValueError):
            activate(self.root, '0'*40)

    def test_failed_gate_and_duplicate_gates_never_promote_or_requery(self):
        task = task_contract(A)
        for gates in ([], [{'number': 1, 'passed': True}]*10):
            with tempfile.TemporaryDirectory() as root, \
                    patch('research.skill_contract.TaskVerifier.verify', return_value={
                        'passed': True, 'task': task.key, 'suite_version': SUITE_VERSION,
                        'suite_digest': suite_digest(), 'gates': gates}):
                result = acquire(root, A, public(A), CONFIG)
                self.assertEqual(result['status'], 'certification_failed')
                self.assertIsNone(result['checkpoint'])
                with self.assertRaisesRegex(ValueError, 'already attempted'):
                    acquire(root, A, lambda n: self.fail('reacquired after protected failure'), CONFIG)

    def test_retention_failure_preserves_active_checkpoint(self):
        base = self.learn()
        original = TaskVerifier.verify
        def verify(verifier, source, task, active):
            if task.key == task_contract(A).key:
                return {'passed': False, 'gates': []}
            return original(verifier, source, task, active)
        with patch('research.skill_contract.TaskVerifier.verify', verify):
            result = self.learn(B)
        self.assertEqual(result['status'], 'retention_failed')
        self.assertEqual(self.current(), base['checkpoint'])

    def test_shifted_audit_failure_preserves_active_checkpoint(self):
        base = self.learn()
        original = TaskVerifier.check
        def check(verifier, source, task, cases):
            if len(cases) == 32:
                raise ValueError('injected shifted audit failure')
            return original(verifier, source, task, cases)
        with patch('research.skill_contract.TaskVerifier.check', check):
            result = self.learn(B)
        self.assertEqual(result['status'], 'audit_failed')
        self.assertEqual(self.current(), base['checkpoint'])

    def test_tampered_model_rejected_before_invocation(self):
        result = self.learn()
        versions = VersionController(self.root)
        manifest = versions.read(result['checkpoint'])
        manifest['skills'][task_contract(A).key]['source'] = 'tampered'
        bad = versions.snapshot(manifest, result['checkpoint'])
        memory = MemoryEngine(self.root)
        memory.activate(bad)
        memory.db.close()
        with self.assertRaises(ValueError), patch('research.skill_contract.SandboxRunner') as runner:
            invoke(self.root, task_contract(A).key, 100)
        runner.assert_not_called()

    def test_stop_during_public_acquisition_prevents_further_labels(self):
        calls = []
        def label(n):
            calls.append(n)
            (self.root/'STOP').touch()
            return public(A)(n)
        with self.assertRaisesRegex(RuntimeError, 'operator stop'):
            acquire(self.root, A, label, CONFIG)
        self.assertEqual(len(calls), 1)
        self.assertIsNone(self.current())

    def test_container_budget_failure_does_not_promote(self):
        result = acquire(self.root, A, public(A), CONFIG, max_containers=2)
        self.assertEqual(result['status'], 'certification_failed')
        self.assertLessEqual(result['containers'], 2)
        self.assertIsNone(self.current())

    def test_activation_failure_rolls_back_active_pointer(self):
        first = self.learn()
        with patch('research.skill_contract.MemoryEngine.activate', side_effect=RuntimeError('injected activation failure')):
            with self.assertRaisesRegex(RuntimeError, 'activation failure'):
                self.learn(B)
        self.assertEqual(self.current(), first['checkpoint'])

    def test_stale_adapter_fails_before_requesting_labels(self):
        self.learn()
        with patch('research.skill_contract.adapter_digest', return_value='different'):
            with self.assertRaisesRegex(ValueError, 'stale'):
                acquire(self.root, B, lambda n: self.fail('queried with stale state'), CONFIG)

    def test_stop_prevents_persisted_skill_invocation(self):
        self.learn()
        (self.root/'STOP').touch()
        with patch('research.skill_contract.SandboxRunner') as runner:
            with self.assertRaisesRegex(RuntimeError, 'operator stop'):
                invoke(self.root, task_contract(A).key, 100)
            runner.assert_not_called()


@unittest.skipUnless(shutil.which('docker'), 'Docker required for actual contract service integration')
class ContractDockerTests(unittest.TestCase):
    def test_acquisition_restart_invocation_retention_and_rollback(self):
        output = os.environ.get('CONTRACT_EVIDENCE_DIR')
        context = contextlib.nullcontext(output) if output else tempfile.TemporaryDirectory()
        with context as directory:
            root = Path(directory)
            root.mkdir(parents=True, exist_ok=True)
            state = root/'state'
            seed = int(os.environ.get('CONTRACT_SEED', '920022'))
            runner = os.environ.get('CONTRACT_RUNNER_IMAGE', 'recursive-ai-runner:local')
            options = {'seed': seed, 'image': runner,
                       'selector_image': os.environ.get('RECURSIVE_SELECTOR_IMAGE', 'recursive-ai-selector:local')}
            first = acquire(state, A, public(A), CONFIG, **options)
            second = acquire(state, B, public(B), CONFIG, **options)
            self.assertEqual(first['status'], 'certified', first)
            self.assertEqual(second['status'], 'certified', second)
            self.assertTrue(second['retention'][task_contract(A).key]['passed'])
            self.assertLessEqual(first['label_queries'], 128)
            self.assertLessEqual(second['label_queries'], 128)
            self.assertLessEqual(first['candidate_containers'], 20)
            self.assertLessEqual(second['candidate_containers'], 20)
            def cli(command, *arguments, check=True):
                return subprocess.run([sys.executable, '-m', 'research.skill_contract', command,
                    '--state', str(state), *arguments], text=True, capture_output=True, timeout=60, check=check)
            n, invocations = 2**255-1, []
            def call(descriptor):
                result = json.loads(cli('invoke', '--key', task_contract(descriptor).key,
                                        '--input', str(n), '--image', runner).stdout)
                self.assertEqual(result['output'], public(descriptor)(n))
                invocations.append(result)
                return result
            before = call(B)
            call(A)
            reused = acquire(state, B, lambda n: self.fail('labels requested after restart'), CONFIG, **options)
            self.assertEqual((reused['label_queries'], reused['containers']), (0, 0))
            cli('activate', '--checkpoint', first['checkpoint'])
            missing = cli('invoke', '--key', task_contract(B).key, '--input', str(n), '--image', runner, check=False)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn('no current contract certification', missing.stderr)
            call(A)
            cli('activate', '--checkpoint', second['checkpoint'])
            restored = call(B)
            self.assertEqual((restored['checkpoint'], restored['output']), (before['checkpoint'], before['output']))
            stop = state/'STOP'
            stop.touch()
            stopped = cli('invoke', '--key', task_contract(B).key, '--input', str(n), '--image', runner, check=False)
            self.assertNotEqual(stopped.returncode, 0)
            self.assertIn('operator stop', stopped.stderr)
            stop.unlink()
            mismatch = {'degree': 3, 'p': 1, 'r': 1, 'q': 0, 'd': 1}
            rejected = acquire(state, mismatch, public(B), CONFIG, **options)
            self.assertEqual(rejected['status'], 'certification_failed')
            self.assertEqual(rejected['checkpoint'], second['checkpoint'])
            with self.assertRaisesRegex(ValueError, 'already attempted'):
                acquire(state, mismatch, lambda n: self.fail('retried protected failure'), CONFIG, **options)
            result = {'seed': seed, 'first': first, 'second': second, 'reused': reused,
                      'invocations': invocations, 'rejected': rejected, 'rollback_removed_skill': True,
                      'restoration_reproduced_output': True, 'runner_image': runner,
                      'operator_stop_prevented_invocation': True,
                      'selector_image': options['selector_image'], 'configuration_origin': 'caller_supplied',
                      'production_integration': False, 'independent_evaluation': False}
            (root/'result.json').write_text(json.dumps(result, indent=2)+'\n')
            print('SKILL_CONTRACT_RESULT '+json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    unittest.main()
