import unittest
from autonomy.tasks import Task
from core.ast_validator import parse, validate
from research.scaffold_search import build_candidate, configurations, discover


class ScaffoldSearchTests(unittest.TestCase):
    def test_all_candidates_are_valid_and_distinct(self):
        sources = [build_candidate('inverse', (1, 0, 1), 2, c) for c in configurations()]
        self.assertEqual(len(set(sources)), 16)
        for source in sources:
            validate(parse(source))

    def test_bad_model_parameters_are_rejected(self):
        for name, rule, degree, config in [('_hidden', (1, 0, 1), 2, configurations()[0]),
                                         ('inverse', (0, 0, 1), 2, configurations()[0]),
                                         ('inverse', (1, 0, 1), 5, configurations()[0]),
                                         ('inverse', (1, 0, 1), 2, {'upper': 'import os'})]:
            with self.assertRaises(ValueError):
                build_candidate(name, rule, degree, config)

    def test_ambiguity_does_not_execute_candidates(self):
        class ForbiddenRunner:
            def execute(self, *args, **kwargs):
                raise AssertionError('ambiguous examples cannot trigger candidate execution')
        result = discover(ForbiddenRunner(), 'inverse', [(0, 0)])
        self.assertEqual(result['status'], 'ambiguous')
        self.assertIsNone(result['model'])

    def test_budget_exhaustion_is_not_ignored(self):
        class ExhaustedRunner:
            def execute(self, *args, **kwargs):
                raise RuntimeError('container budget exhausted')
        task = Task('integer_sqrt')
        cases = task.public()
        with self.assertRaisesRegex(RuntimeError, 'budget exhausted'):
            discover(ExhaustedRunner(), task.family,
                     [(case[0], value) for case, value in zip(cases, task.expected(cases))])


if __name__ == '__main__':
    unittest.main()
