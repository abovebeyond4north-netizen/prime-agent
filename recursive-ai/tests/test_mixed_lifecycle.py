import tempfile
import unittest
from unittest.mock import patch

from autonomy.search import expand_inverse_grammar
from core.rollback import VersionController
from memory.skill_store import MemoryEngine
from research.mixed_features import MixedTask, construct, infer
from research.mixed_lifecycle import PARAMETERS, SUPPLIED, record, replay


class MixedLifecycleTests(unittest.TestCase):
    def test_new_rules_are_identifiable_and_persisted(self):
        for degree,p,r,q,d in PARAMETERS:
            task = MixedTask(degree=degree,p=p,r=r,q=q,d=d)
            public = task.public()
            examples = [(c[0],v) for c,v in zip(public,task.expected(public))]
            hypothesis = infer(examples)
            self.assertEqual(hypothesis['rule'],(p,r,q,d))
            self.assertEqual(hypothesis['degree'],degree)
            self.assertEqual(expand_inverse_grammar(examples)['status'],'expansion_budget_exhausted')
            source = construct(task.family,hypothesis,SUPPLIED)
            with tempfile.TemporaryDirectory() as root:
                versions, memory = VersionController(root), MemoryEngine(root)
                base = versions.snapshot({})
                extended = versions.snapshot({task.key:record(task,source,{'passed':True},hypothesis,SUPPLIED)},base)
                memory.activate(extended)
                memory.db.close()
                restored = versions.read(extended)[task.key]
                self.assertEqual(construct(task.family,restored['hypothesis'],restored['configuration']),source)
                memory = MemoryEngine(root)
                self.assertEqual(memory.current(),extended)
                memory.activate(base)
                self.assertEqual(versions.read(memory.current()),{})
                memory.db.close()

    def test_corrupt_model_rejected_before_execution(self):
        task = MixedTask(degree=3,p=2,r=1,q=0,d=1)
        with tempfile.TemporaryDirectory() as root:
            versions, memory = VersionController(root), MemoryEngine(root)
            checkpoint = versions.snapshot({task.key:record(task,'def bad(n):\n return 0\n',{},
                {'status':'unique','degree':3,'rule':[2,1,0,1]},SUPPLIED)})
            memory.activate(checkpoint)
            memory.db.close()
            with patch('research.mixed_lifecycle.SandboxRunner') as runner:
                with self.assertRaises(ValueError):
                    replay(root,1)
                runner.return_value.execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
