import contextlib
import io
import tempfile
import unittest
from unittest.mock import patch

from autonomy.controller import execute_goal
from autonomy.curriculum import next_task
from autonomy.memory import ResearchMemory
from autonomy.tasks import Task, goal_contract
from tests.test_autonomy import ContractRunner, certification


class PublicFailureCurriculumTests(unittest.TestCase):
    def test_priority_uses_only_latest_public_failure_in_this_goal(self):
        with tempfile.TemporaryDirectory() as root:
            memory = ResearchMemory(root)
            for goal, key, gate in [('g', 'gcd:tier1', 'public'),
                                    ('g', 'fibonacci:tier1', 'holdout'),
                                    ('other', 'upper_bound:tier1', 'public')]:
                memory.event({'goal_id': goal, 'attempt': 1, 'task': {'key': key}, 'failed_gate': gate})
            self.assertEqual(memory.public_repair_tasks('g'), {'gcd:tier1'})
            memory.event({'goal_id': 'g', 'attempt': 2, 'task': {'key': 'gcd:tier1'}, 'failed_gate': None})
            self.assertEqual(memory.public_repair_tasks('g'), set())
            memory.db.close()

    def test_repair_priority_preserves_prerequisites_and_tiers(self):
        contract = goal_contract('algorithms toolkit', tier=2)
        attempts = {'gcd:tier1': 1}
        self.assertEqual(next_task(contract, {}, attempts).key, 'fibonacci:tier1')
        self.assertEqual(next_task(contract, {}, attempts, priority_keys={'gcd:tier1'}).key,
                         'gcd:tier1')
        # Neither unadmitted tasks nor unresolved higher-tier dependencies become eligible.
        picked = next_task(contract, {}, attempts, priority_keys={'binary_search:tier2', 'outside'})
        self.assertEqual(picked.key, 'fibonacci:tier1')
        active = {'gcd:tier1': certification(Task('gcd'))}
        picked = next_task(contract, active, attempts, priority_keys={'gcd:tier2'})
        self.assertEqual(picked.tier, 1)

    def test_resume_does_not_reuse_summary_from_other_curriculum_mode(self):
        with tempfile.TemporaryDirectory() as root, patch('autonomy.controller.SandboxRunner', ContractRunner), contextlib.redirect_stdout(io.StringIO()):
            baseline = execute_goal(root, description='gcd', tier=1, max_model_calls=0)
            focused = execute_goal(root, description='gcd', tier=1, max_model_calls=0,
                                   repair_public_failures=True)
            self.assertFalse(baseline['repair_public_failures'])
            self.assertTrue(focused['repair_public_failures'])
            self.assertTrue(focused['audit']['passed'])
            self.assertEqual(focused['coverage'], baseline['coverage'])
            self.assertEqual(focused['session_attempts'], 0)

    def test_invalid_mode_fails_before_creating_state(self):
        with self.assertRaises(ValueError):
            execute_goal('unused', repair_public_failures='yes')
