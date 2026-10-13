import contextlib
import io
import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from autonomy.controller import execute_goal
from autonomy.procedure import build_candidate, propose
from autonomy.tasks import Task
from core.rollback import VersionController
from main import rollback
from tests.test_autonomy import ContractRunner

CONFIGURATION = {'upper': 'n + 1', 'direction': 'forward', 'comparison': '<=', 'result': 'low - 1'}
MODEL = {'entrypoint': 'integer_sqrt', 'rule': [1, 0, 1], 'degree': 2, 'configuration': CONFIGURATION}

class ProcedureControllerTests(unittest.TestCase):
    def test_reuse_reconstructs_and_reinduces_without_screening(self):
        active = {'integer_sqrt:tier1': {'source': build_candidate(**MODEL), 'procedure_model': MODEL}}
        candidate, model, evidence = propose(None, Task('triangular_inverse'), active)
        self.assertEqual(model['rule'], (1, 1, 2))
        self.assertEqual(model['configuration'], CONFIGURATION)
        self.assertEqual(evidence['status'], 'reused')
        self.assertIn('1 * mid * mid + 1 * mid <= 2 * n', candidate)

    def test_corrupt_model_fails_closed(self):
        active = {'integer_sqrt:tier1': {'source': 'different source', 'procedure_model': MODEL}}
        with self.assertRaisesRegex(ValueError, 'reconstruct'):
            propose(None, Task('triangular_inverse'), active)

    def test_invalid_modes_do_not_create_state(self):
        with tempfile.TemporaryDirectory() as root:
            state = Path(root) / 'state'
            for options in ({'learn_inverse_procedure': 1}, {'learn_inverse_procedure': True, 'provider': 'api'}):
                with self.assertRaises(ValueError):
                    execute_goal(state, **options)
                self.assertFalse(state.exists())

    def test_failed_certification_does_not_persist_model(self):
        with tempfile.TemporaryDirectory() as root, contextlib.redirect_stdout(io.StringIO()), \
                patch('autonomy.controller.SandboxRunner', ContractRunner), \
                patch('autonomy.controller.next_task', return_value=Task('integer_sqrt')), \
                patch('autonomy.controller.propose_procedure', return_value=(build_candidate(**MODEL), MODEL, {'status': 'unique'})), \
                patch('autonomy.controller.TaskVerifier.verify', return_value={'passed': False, 'gates': []}):
            result = execute_goal(root, tier=1, max_attempts=1, learn_inverse_procedure=True)
            self.assertIsNone(result['checkpoint'])
            self.assertEqual(result['coverage'], 0)

    @unittest.skipUnless(shutil.which('docker'), 'Docker is required for controller integration')
    def test_docker_acquisition_restart_transfer_and_rollback(self):
        with tempfile.TemporaryDirectory() as root, contextlib.redirect_stdout(io.StringIO()):
            options = dict(description='numeric inverses', tier=1, max_seconds=600, max_model_calls=0, learn_inverse_procedure=True)
            base = execute_goal(root, max_attempts=2, **options)
            self.assertEqual(base['certified_tasks'], ['lower_bound:tier1'], base)
            learned = execute_goal(root, max_attempts=3, **options)
            manifest = VersionController(root).read(learned['checkpoint'])
            self.assertIn('procedure_model', manifest['integer_sqrt:tier1'])
            self.assertNotIn('triangular_inverse:tier1', manifest)
            subprocess.check_output([sys.executable, 'main.py', 'autonomous', '--state', root, '--goal', 'numeric inverses', '--tier', '1', '--max-attempts', '6', '--max-model-calls', '0', '--learn-inverse-procedure'], text=True)
            complete = execute_goal(root, max_attempts=6, **options)
            self.assertEqual(complete['status'], 'goal_reached', complete)
            self.assertTrue(complete['audit']['passed'])
            final = VersionController(root).read(complete['checkpoint'])
            self.assertEqual(final['triangular_inverse:tier1']['procedure_model']['configuration'], CONFIGURATION)
            command = [sys.executable, 'main.py', 'solve', '--state', root, '--skill', 'integer_sqrt', '--arguments', json.dumps([2**255 - 1])]
            answer = json.loads(subprocess.check_output(command, text=True))
            self.assertEqual(answer['output'], math.isqrt(2**255 - 1))
            rollback(root, base['checkpoint'])
            self.assertFalse(any('procedure_model' in skill for skill in VersionController(root).read(base['checkpoint']).values()))
            rejected = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn('no current certification', rejected.stderr)
            rollback(root, complete['checkpoint'])
            self.assertEqual(json.loads(subprocess.check_output(command, text=True))['output'], answer['output'])
            print('PROCEDURE_CONTROLLER_RESULT ' + json.dumps(complete, sort_keys=True), file=sys.__stdout__, flush=True)

if __name__ == '__main__':
    unittest.main()
