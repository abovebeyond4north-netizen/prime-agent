"""Public-driven mixed-polynomial inference, outside the frozen inverse grammar."""
import argparse
import ast
import json
import math
from dataclasses import dataclass
from pathlib import Path

from autonomy.procedure import build_candidate, propose
from autonomy.search import BOUND, _validate_inverse_examples, expand_inverse_grammar
from autonomy.tasks import Task
from autonomy.verifier import TaskVerifier
from research.grammar_expansion import PowerTask
from sandbox.runner import SandboxRunner


@dataclass(frozen=True)
class MixedTask(PowerTask):
    r: int = 1

    @property
    def family(self):
        return f'mixed_inverse_{self.degree}_{self.p}_{self.r}_{self.q}_{self.d}'

    def value(self, k):
        return self.p*k**self.degree + self.r*k*k + self.q*k

    def expected(self, cases):
        answers = []
        for (n,) in cases:
            target, value = self.d*n, 0
            for bit in reversed(range(target.bit_length()+1)):
                trial = value | (1 << bit)
                if self.value(trial) <= target:
                    value = trial
            answers.append(value)
        return answers

    def properties(self):
        boundaries = [(self.value(k)+self.d-1)//self.d for k in (1,2,3,100,10**12)]
        return [(max(0,n+offset),) for n in boundaries for offset in (-1,0,1)]


def infer(examples):
    _validate_inverse_examples(examples)
    stages = []
    compatible = []
    for degree in (3,4):
        fits = []
        for p in range(1,5):
            for r in range(1,5):
                for q in range(5):
                    for d in range(1,5):
                        if math.gcd(math.gcd(p,r),math.gcd(q,d)) != 1 or p+r+q < d:
                            continue
                        if all(p*k**degree+r*k*k+q*k <= d*n < p*(k+1)**degree+r*(k+1)**2+q*(k+1)
                               for n,k in examples):
                            fits.append((p,r,q,d))
        stages.append({'degree':degree,'raw_hypotheses':320,'compatible':len(fits)})
        compatible.extend((degree,rule) for rule in fits)
    if compatible:
        unique = len(compatible) == 1
        return {'status':'unique' if unique else 'ambiguous',
                'degree':compatible[0][0] if unique else None,
                'rule':compatible[0][1] if unique else None,'stages':stages}
    return {'status':'no_fit','rule':None,'degree':None,'stages':stages}


def construct(name, hypothesis, configuration):
    degree, rule = hypothesis['degree'], hypothesis['rule']
    if hypothesis['status'] != 'unique' or degree not in (3,4) or not isinstance(rule,(list,tuple)) or len(rule)!=4:
        raise ValueError('unique bounded rule required')
    p,r,q,d = rule
    if any(type(v) is not int for v in rule) or not (1<=p<=4 and 1<=r<=4 and 0<=q<=4 and 1<=d<=4 and p+r+q>=d):
        raise ValueError('rule outside grammar')
    tree = ast.parse(build_candidate(name,(1,0,1),degree,configuration))
    branch = tree.body[0].body[2].body[1]
    feature = ' * '.join(['mid']*degree)
    branch.test.left = ast.parse(f'{p} * {feature} + {r} * mid * mid + {q} * mid',mode='eval').body
    branch.test.comparators[0] = ast.parse(f'{d} * n',mode='eval').body
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'


def study(seed):
    training_runner = SandboxRunner()
    donor, training = Task('lower_bound'), Task('integer_sqrt')
    report = TaskVerifier(training_runner).verify(BOUND,donor,{})
    assert report['passed']
    active = {donor.key:{'source':BOUND,'report':report}}
    source, model, discovery = propose(training_runner,training,active)
    report = TaskVerifier(training_runner).verify(source,training,active)
    assert report['passed']
    active[training.key] = {'source':source,'report':report,'procedure_model':model}
    frozen = dict(model['configuration'])
    rows = []
    for task in (MixedTask(degree=3,p=1,r=1,q=0,d=1),
                 MixedTask(degree=3,p=1,r=1,q=1,d=2),
                 MixedTask(degree=4,p=1,r=1,q=2,d=3)):
        public = task.public()
        examples = [(case[0],value) for case,value in zip(public,task.expected(public))]
        baseline, hypothesis = expand_inverse_grammar(examples), infer(examples)
        assert baseline['status'] == 'expansion_budget_exhausted', baseline
        assert hypothesis['status'] == 'unique', hypothesis
        candidate = construct(task.family,hypothesis,frozen)
        runner = SandboxRunner()
        runner.max_container_runs = 40
        verification = TaskVerifier(runner).verify(candidate,task,active)
        assert verification['passed'], verification
        cases = task.samples(512,seed=seed,audit=True)
        for offset in range(0,len(cases),32):
            batch = cases[offset:offset+32]
            result = TaskVerifier(runner).check(candidate,task,batch)
            for (n,),k in zip(batch,result['outputs']):
                assert task.value(k) <= task.d*n < task.value(k+1)
        rows.append({'parameters':[task.degree,task.p,task.r,task.q,task.d],
                     'public_examples':examples,'baseline':baseline,'hypothesis':hypothesis,
                     'report':verification,'source':candidate,'containers':runner.container_runs,
                     'shifted_cases':len(cases),'baseline_emits_candidate':False})
    return {'seed':seed,'training_containers':training_runner.container_runs,'discovery':discovery,
            'configuration':frozen,'rows':rows,'arm_budget':40,'automatic_promotion':False,
            'limits':['Mixed quadratic feature and search bounds are developer-defined.',
                      'Fixtures selected for unique identifiability from public labels, not a random task sample.',
                      'Hypothesis selection uses public labels only; configuration frozen before new rules.',
                      'Baseline has the same resource ceiling but no representational fit; consumed work differs.',
                      'Same evaluator/operator/environment class; no external or open-world claim.']}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=study(args.seed)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print('MIXED_FEATURE_RESULT '+json.dumps(result,sort_keys=True),flush=True)
