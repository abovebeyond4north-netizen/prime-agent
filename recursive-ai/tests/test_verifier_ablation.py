import unittest
from autonomy.tasks import goal_contract, task_from_key
from core.ast_validator import parse, validate
from research.verifier_ablation import acceptance, candidates


class VerifierAblationTests(unittest.TestCase):
    def test_faults_are_valid_sandbox_programs(self):
        for name, source, _ in candidates():
            with self.subTest(name=name):
                validate(parse(source))
        tail = dict((name, source) for name, source, _ in candidates())['long_input_corruption']
        self.assertIn('if len(values) > 8:', tail)

    def test_missing_evidence_cannot_pass(self):
        with self.assertRaisesRegex(ValueError, 'missing or duplicate'):
            acceptance([])

    def test_all_accepting_verifier_fails_acceptance(self):
        rows = [{'name': name, 'designated_fault': fault,
                 'intact': {'passed': True},
                 'oracle_ablated': {'passed': True},
                 'separate_audit': {'outputs_correct': True}}
                for name, _, fault in candidates()]
        checks = acceptance(rows)
        self.assertFalse(checks['intact_rejects_all_designated_faults'])
        self.assertFalse(checks['ablation_exposes_semantic_faults'])
        self.assertFalse(checks['work_budget_still_rejects_linear_program'])

    def test_varied_holdouts_are_distinct_and_disjoint(self):
        training = goal_contract('sorted search', tier=1)
        families = {task_from_key(row['key']).family for row in training['tasks']}
        contracts = [goal_contract('compound arithmetic', tier=1, task_seed=seed,
                                   task_count=3)
                     for seed in (410003, 610007, 810009)]
        self.assertEqual(len({c['id'] for c in contracts}), 3)
        for contract in contracts:
            self.assertTrue(families.isdisjoint(
                {task_from_key(row['key']).family for row in contract['tasks']}))
