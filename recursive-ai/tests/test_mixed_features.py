import unittest
from autonomy.search import expand_inverse_grammar
from core.ast_validator import parse, validate
from research.mixed_features import MixedTask, construct, infer

class MixedFeatureTests(unittest.TestCase):
    def test_public_rules_are_identified_outside_frozen_grammar(self):
        configuration={'upper':'n + 1','direction':'forward','comparison':'<=','result':'low - 1'}
        for task in (MixedTask(degree=3,p=1,r=1,q=0,d=1),
                     MixedTask(degree=3,p=1,r=1,q=1,d=2),
                     MixedTask(degree=4,p=1,r=1,q=2,d=3)):
            public=task.public()
            examples=[(c[0],v) for c,v in zip(public,task.expected(public))]
            self.assertEqual(expand_inverse_grammar(examples)['status'],'expansion_budget_exhausted')
            hypothesis=infer(examples)
            self.assertEqual(hypothesis['rule'],(task.p,task.r,task.q,task.d))
            self.assertEqual(hypothesis['degree'],task.degree)
            validate(parse(construct('anonymous_inverse',hypothesis,configuration)))

    def test_ambiguity_and_invalid_examples_fail_closed(self):
        hypothesis=infer([(0,0)])
        self.assertEqual(hypothesis['status'],'ambiguous')
        with self.assertRaises(ValueError):
            construct('inverse',hypothesis,{})
        with self.assertRaises(ValueError):
            infer([(0,1)])

if __name__ == '__main__':
    unittest.main()
