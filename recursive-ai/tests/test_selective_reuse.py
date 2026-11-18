from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.composition_contract import activate, learn
from research.composition_search import run
from research.selective_reuse import _plan, solve_batch
from tests.test_composition_contract import A, B, problems


def example(a, b):
    return [(x, a*x+b) for x in (-2, 0, 3)]


class SelectiveReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'state'
        self.first = learn(self.root, problems(A))
        self.second = learn(self.root, problems(B))

    def test_composes_learned_macros_without_forward_search(self):
        with patch('research.selective_reuse.search', side_effect=AssertionError('forward search')):
            batch = solve_batch(self.root, [example(4, 4)])
        result, = batch['results']
        self.assertEqual(result['route'], 'planned')
        self.assertEqual(result['cost'], len(result['program'])*3)
        for x in range(-30, 31):
            self.assertEqual(run(result['program'], x), 4*x+4)

    def test_fallback_preserves_full_primitive_budget(self):
        batch = [example(-4, -3)]
        expected = solve_batch(None, batch, mode='primitive', budget=500)
        actual = solve_batch(self.root, batch, budget=500)
        self.assertEqual(actual['results'][0]['route'], 'fallback')
        for field in ('program', 'cost', 'status'):
            self.assertEqual(actual['results'][0][field], expected['results'][0][field])

    def test_planner_budget_and_unaffordable_plan(self):
        result = solve_batch(self.root, [example(4, 4)], budget=1)['results'][0]
        self.assertEqual(result['status'], 'exhausted')
        self.assertLessEqual(result['cost'], 1)
        self.assertLessEqual(result['planner_states'], 128)
        result = solve_batch(self.root, [example(4, 4)], planner_states=0)['results'][0]
        self.assertEqual(result['planner_states'], 0)
        self.assertEqual(result['route'], 'fallback')

    def test_backward_primitive_ablation_needs_no_state(self):
        batch = solve_batch(None, [example(2, -1)], mode='backward_primitive')
        self.assertEqual(batch['results'][0]['route'], 'planned')
        self.assertIsNone(batch['checkpoint'])
        self.assertEqual(run(batch['results'][0]['program'], 5), 9)

    def test_macro_rollback_changes_routing_and_restoration_recovers(self):
        task = [example(2, 2)]
        self.assertEqual(solve_batch(self.root, task)['results'][0]['route'], 'planned')
        activate(self.root, self.first['checkpoint'])
        self.assertEqual(solve_batch(self.root, task)['results'][0]['route'], 'fallback')
        activate(self.root, self.second['checkpoint'])
        self.assertEqual(solve_batch(self.root, task)['results'][0]['route'], 'planned')

    def test_stop_and_stale_library_block_reuse(self):
        (self.root/'STOP').touch()
        with self.assertRaisesRegex(RuntimeError, 'operator stop'):
            solve_batch(self.root, [example(4, 4)])
        (self.root/'STOP').unlink()
        with patch('research.composition_contract.adapter_digest', return_value='stale'):
            with self.assertRaisesRegex(ValueError, 'stale'):
                solve_batch(self.root, [example(4, 4)])

    def test_planner_cycles_and_length_are_bounded(self):
        operators = [(('negate', 'negate'), (1, 0))]
        program, states, edges = _plan((2, 1), operators, 128)
        self.assertIsNone(program)
        self.assertEqual((states, edges), (1, 1))
        program, states, _ = _plan((2**20, 2**20-1), [(('double', 'increment'), (2, 1))], 128)
        self.assertIsNone(program)
        self.assertLessEqual(states, 128)

    def test_planner_recognizes_match_at_exact_state_cap(self):
        operators = [(('increment',), (1, 1)), (('double', 'increment'), (2, 1))]
        program, states, _ = _plan((2, 1), operators, 1)
        self.assertEqual(program, ('double', 'increment'))
        self.assertEqual(states, 1)

    def test_invalid_configuration_has_no_new_state(self):
        fresh = Path(self.temp.name)/'fresh'
        for options in ({'budget': True}, {'planner_states': -1}, {'planner_states': 129},
                        {'mode': 'unknown'}):
            with self.assertRaises(ValueError):
                solve_batch(fresh, [example(2, 1)], **options)
        self.assertFalse(fresh.exists())


if __name__ == '__main__':
    unittest.main()
