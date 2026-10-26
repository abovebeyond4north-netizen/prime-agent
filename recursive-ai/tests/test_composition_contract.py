import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from core.rollback import VersionController
from memory.skill_store import MemoryEngine
from research.composition_contract import activate, digest, invoke, learn, state_session

A = ((2, 1), (4, 2), (4, 3), (8, 4), (8, 6), (8, 7))
B = ((2, 2), (4, 4), (4, 6), (8, 8), (8, 12), (8, 14))


def problems(tasks):
    return [[(x, a*x+b) for x in (-2, 0, 3)] for a, b in tasks]


class CompositionContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'compositions'

    def current(self):
        memory = MemoryEngine(self.root)
        try:
            return memory.current()
        finally:
            memory.db.close()

    def cli(self, command, *options):
        return subprocess.run([sys.executable, '-m', 'research.composition_contract', command,
                               '--state', str(self.root), *options], text=True,
                              capture_output=True, timeout=30)

    def test_learning_restart_invocation_rollback_and_restoration(self):
        first = learn(self.root, problems(A))
        second = learn(self.root, problems(B))
        self.assertEqual(first['status'], 'stored')
        self.assertEqual(second['status'], 'stored')
        old_key = first['macros'][0]
        new_key, = set(second['macros'])-set(first['macros'])
        for key, intercept in ((old_key, 1), (new_key, 2)):
            for value in (-2**255+1, 0, 2**255-1):
                result = self.cli('invoke', '--macro', key, '--input', str(value))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)['output'], 2*value+intercept)
        result = self.cli('activate', '--checkpoint', first['checkpoint'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.cli('invoke', '--macro', new_key, '--input', '7').returncode, 1)
        self.assertEqual(invoke(self.root, old_key, 7)['output'], 15)
        self.assertEqual(self.cli('activate', '--checkpoint', second['checkpoint']).returncode, 0)
        self.assertEqual(invoke(self.root, new_key, 7)['output'], 16)

    def test_cached_learning_never_searches_again(self):
        first = learn(self.root, problems(A))
        with patch('research.composition_contract.search', side_effect=AssertionError('retrained')):
            repeated = learn(self.root, list(reversed(problems(A))))
        self.assertEqual(repeated['status'], 'already_stored')
        self.assertEqual(repeated['checkpoint'], first['checkpoint'])
        self.assertEqual(repeated['cost'], 0)

    def test_invalid_public_data_has_no_state_side_effect(self):
        bad = ([], [[[0, 0]]], [[[0, 0], [0, 1]]], [[[0, True], [1, 1]]],
               [[[0, 0], [2, 1]]], [[[0, 0], [1, 1], [2, 5]]])
        for batch in bad:
            with self.assertRaises(ValueError):
                learn(self.root, batch)
            self.assertFalse(self.root.exists())

    def test_production_state_is_not_mixed_in(self):
        self.root.mkdir()
        sentinel = self.root/'memory.sqlite3'
        sentinel.write_text('production sentinel')
        with self.assertRaisesRegex(ValueError, 'dedicated empty'):
            learn(self.root, problems(A))
        self.assertEqual(sentinel.read_text(), 'production sentinel')

    def test_exhaustion_or_no_compression_preserves_checkpoint(self):
        first = learn(self.root, problems(A))
        failed = learn(self.root, problems(B), max_evaluations=1)
        self.assertEqual(failed['status'], 'exhausted')
        self.assertLessEqual(failed['cost'], 1)
        self.assertEqual(self.current(), first['checkpoint'])
        empty = Path(self.temp.name)/'empty'
        self.assertEqual(learn(empty, problems(A[:1]))['status'], 'no_compression')
        memory = MemoryEngine(empty)
        try:
            self.assertIsNone(memory.current())
        finally:
            memory.db.close()

    def test_stale_binding_fails_before_training_or_invocation(self):
        first = learn(self.root, problems(A))
        with patch('research.composition_contract.adapter_digest', return_value='stale'), \
                patch('research.composition_contract.search') as search:
            with self.assertRaisesRegex(ValueError, 'stale'):
                learn(self.root, problems(B))
            with self.assertRaisesRegex(ValueError, 'stale'):
                invoke(self.root, first['macros'][0], 1)
        search.assert_not_called()

    def test_unregistered_checkpoint_cannot_be_activated(self):
        first = learn(self.root, problems(A))
        versions = VersionController(self.root)
        other = versions.snapshot(versions.read(first['checkpoint']), first['checkpoint'])
        with self.assertRaisesRegex(ValueError, 'not registered'):
            activate(self.root, other)
        self.assertEqual(self.current(), first['checkpoint'])

    def test_tampered_proof_and_provenance_fail_closed(self):
        first = learn(self.root, problems(A))
        versions = VersionController(self.root)
        for mutation in ('proof', 'training', 'program'):
            manifest = versions.read(first['checkpoint'])
            record = manifest['macros'][first['macros'][0]]
            if mutation == 'proof':
                record['coefficients'][1] += 1
            elif mutation == 'training':
                record['training_ids'] = record['training_ids'][:1]
            else:
                record['program'] = ['import', 'double']
            bad = versions.snapshot(manifest, first['checkpoint'])
            memory = MemoryEngine(self.root)
            memory.activate(bad)
            memory.db.close()
            with self.assertRaises(ValueError):
                invoke(self.root, first['macros'][0], 7)
        activate(self.root, first['checkpoint'])
        self.assertEqual(invoke(self.root, first['macros'][0], 7)['output'], 15)

    def test_retained_problem_is_rechecked(self):
        first = learn(self.root, problems(A))
        versions = VersionController(self.root)
        manifest = versions.read(first['checkpoint'])
        manifest['problems'][digest(problems(A)[0])]['program'] = ['increment']
        bad = versions.snapshot(manifest, first['checkpoint'])
        memory = MemoryEngine(self.root)
        memory.activate(bad)
        memory.db.close()
        with self.assertRaisesRegex(ValueError, 'certificate mismatch'), \
                patch('research.composition_contract.search') as search:
            learn(self.root, problems(B))
        search.assert_not_called()

    def test_stop_blocks_learning_and_invocation_but_allows_recovery(self):
        first = learn(self.root, problems(A))
        second = learn(self.root, problems(B))
        (self.root/'STOP').touch()
        with self.assertRaisesRegex(RuntimeError, 'operator stop'):
            learn(self.root, problems(B))
        with self.assertRaisesRegex(RuntimeError, 'operator stop'):
            invoke(self.root, first['macros'][0], 7)
        activate(self.root, first['checkpoint'])
        (self.root/'STOP').unlink()
        self.assertEqual(invoke(self.root, first['macros'][0], 7)['checkpoint'], first['checkpoint'])
        self.assertNotEqual(first['checkpoint'], second['checkpoint'])

    def test_stop_after_snapshot_prevents_activation(self):
        first = learn(self.root, problems(A))
        snapshot = VersionController.snapshot
        def interrupted(versions, *args):
            result = snapshot(versions, *args)
            (self.root/'STOP').touch()
            return result
        with patch('research.composition_contract.VersionController.snapshot', interrupted):
            with self.assertRaisesRegex(RuntimeError, 'operator stop'):
                learn(self.root, problems(B))
        self.assertEqual(self.current(), first['checkpoint'])

    def test_activation_event_failure_rolls_back_transaction(self):
        first = learn(self.root, problems(A))
        with patch('research.composition_contract.MemoryEngine.event', side_effect=RuntimeError('injected')):
            with self.assertRaisesRegex(RuntimeError, 'injected'):
                learn(self.root, problems(B))
        self.assertEqual(self.current(), first['checkpoint'])

    def test_process_crash_rolls_back_uncommitted_activation(self):
        first = learn(self.root, problems(A))
        code = ('import os,sys; from unittest.mock import patch; '
                'from research.composition_contract import learn; '
                'from tests.test_composition_contract import B,problems; '
                'p=patch("research.composition_contract.MemoryEngine.event",side_effect=lambda *a: os._exit(73)); '
                'p.start(); learn(sys.argv[1],problems(B))')
        child = subprocess.run([sys.executable, '-c', code, str(self.root)],
                               capture_output=True, text=True, timeout=30)
        self.assertEqual(child.returncode, 73, child.stderr)
        self.assertEqual(self.current(), first['checkpoint'])
        self.assertEqual(invoke(self.root, first['macros'][0], 7)['output'], 15)

    def test_exclusive_state_lock_rejects_second_writer(self):
        with state_session(self.root), (self.root/'composition.lock').open('a') as other:
            with self.assertRaises(BlockingIOError):
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_invocation_bounds_and_budget_validation(self):
        for value in (True, 2**256, -2**256):
            with self.assertRaises(ValueError):
                invoke(self.root, 'unused', value)
        for budget in (True, -1, 100001):
            with self.assertRaises(ValueError):
                learn(self.root, problems(A), max_evaluations=budget)
        self.assertFalse(self.root.exists())


if __name__ == '__main__':
    unittest.main()
