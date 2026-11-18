"""Equal-budget comparison of a learned procedure and supplied scaffold on new rules."""
import argparse
import json
from pathlib import Path

from autonomy.procedure import propose
from autonomy.search import BOUND, adapt_inverse_scaffold, expand_inverse_grammar, normalized_digest
from autonomy.tasks import Task
from autonomy.verifier import TaskVerifier
from research.grammar_expansion import PowerTask
from sandbox.runner import SandboxRunner

PARAMETERS = ((2, 2, 3, 2), (3, 3, 4, 2), (4, 3, 2, 2))
ARM_BUDGET = 40


def supplied(task, active):
    public = task.public()
    expansion = expand_inverse_grammar([(case[0], value) for case, value in zip(public, task.expected(public))])
    if expansion['status'] != 'unique':
        raise ValueError('predicate is not uniquely identified')
    return adapt_inverse_scaffold(task.family, active, expansion['rule'], expansion['degree'])


def classify(left, right):
    if not left['passed'] or not right['passed']:
        return 'certification_failure'
    if left['normalized_source'] != right['normalized_source']:
        return 'different_programs'
    delta = right['containers'] - left['containers']
    return 'reuse_advantage' if delta > 0 else 'tie' if delta == 0 else 'scaffold_advantage'


def study(seed):
    runner = SandboxRunner()
    donor = Task('lower_bound')
    donor_report = TaskVerifier(runner).verify(BOUND, donor, {})
    assert donor_report['passed']
    donor_containers = runner.container_runs
    active = {donor.key: {'source': BOUND, 'report': donor_report}}
    training = Task('integer_sqrt')
    source, model, discovery = propose(runner, training, active)
    report = TaskVerifier(runner).verify(source, training, active)
    assert report['passed']
    active[training.key] = {'source': source, 'report': report, 'procedure_model': model}
    frozen_configuration = dict(model['configuration'])
    rows = []
    order = ('reuse', 'supplied') if seed % 2 else ('supplied', 'reuse')
    for parameters in PARAMETERS:
        task = PowerTask(*parameters)
        arms = {}
        for mode in order:
            evaluator = SandboxRunner()
            evaluator.max_container_runs = ARM_BUDGET
            if mode == 'reuse':
                candidate, transferred, evidence = propose(evaluator, task, active)
                assert transferred['configuration'] == frozen_configuration
                assert evidence['status'] == 'reused'
            else:
                candidate = supplied(task, active)
                evidence = {'status': 'supplied_scaffold'}
            assert candidate is not None
            certification = TaskVerifier(evaluator).verify(candidate, task, active)
            assert certification['passed'], certification
            cases = task.samples(512, seed=seed, audit=True)
            for offset in range(0, len(cases), 32):
                batch = cases[offset:offset + 32]
                result = TaskVerifier(evaluator).check(candidate, task, batch)
                for (n,), k in zip(batch, result['outputs']):
                    assert task.p*k**task.degree + task.q*k <= task.d*n
                    assert task.p*(k+1)**task.degree + task.q*(k+1) > task.d*n
            arms[mode] = {'passed': True, 'report': certification, 'shifted_cases': len(cases),
                          'containers': evaluator.container_runs, 'normalized_source': normalized_digest(candidate),
                          'source': candidate, 'proposal_evidence': evidence}
        outcome = classify(arms['reuse'], arms['supplied'])
        assert outcome != 'certification_failure'
        rows.append({'parameters': parameters, 'arms': arms, 'outcome': outcome})
    # This public-ambiguous task is a predeclared abstention check, not a filtered gain trial.
    ambiguous = PowerTask(4, 2, 3, 4)
    abstentions = {}
    for mode in order:
        check = SandboxRunner()
        try:
            propose(check, ambiguous, active) if mode == 'reuse' else supplied(ambiguous, active)
        except ValueError:
            abstentions[mode] = {'abstained': True, 'containers': check.container_runs}
        else:
            raise AssertionError('ambiguous public evidence must not produce a candidate')
        assert check.container_runs == 0
    return {'seed': seed, 'arm_budget': ARM_BUDGET, 'order': order,
            'training_containers': runner.container_runs, 'donor_certification_containers': donor_containers,
            'additional_model_learning_containers': runner.container_runs - donor_containers, 'training_discovery': discovery,
            'frozen_configuration': frozen_configuration, 'rows': rows, 'abstentions': abstentions,
            'limits': ['Rules and budgets fixed before Docker comparisons; public identifiability was checked during fixture design.',
                       'New receiving predicates, but same designed grammar and evaluator; not external held-out domains.',
                       'Learning setup cost is shared and reported separately; supplied adapter does not require a learned model.',
                       'Container counts do not establish CPU or wall-time superiority.',
                       'Same operator and environment class; no automatic promotion.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = study(args.seed)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('SCAFFOLD_BASELINE_RESULT ' + json.dumps(result, sort_keys=True), flush=True)
