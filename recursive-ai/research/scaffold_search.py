"""Research-only scaffold configuration search; no supplied donor program."""
import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

from autonomy.procedure import build_candidate, configurations, discover
from autonomy.search import expand_inverse_grammar
from autonomy.tasks import Task
from autonomy.verifier import TaskVerifier
from research.grammar_expansion import PowerTask
from sandbox.runner import SandboxRunner



def replay(model_path, n):
    model = json.loads(model_path.read_text())
    source = build_candidate(model['entrypoint'], model['rule'], model['degree'], model['configuration'])
    runner = SandboxRunner()
    runner.boot()
    return runner.execute(source, [(n,)], entrypoint=model['entrypoint'])


def study(seed, model_path):
    training = Task('integer_sqrt')
    cases = training.public()
    examples = [(case[0], value) for case, value in zip(cases, training.expected(cases))]
    screening = SandboxRunner()
    screening.boot()
    discovery = discover(screening, training.family, examples)
    assert discovery['status'] == 'unique'
    model = discovery['model']
    model_path.write_text(json.dumps(model, indent=2) + '\n')
    restored = json.loads(model_path.read_text())
    assert restored['configuration'] == model['configuration']
    source = build_candidate(training.family, restored['rule'], restored['degree'], restored['configuration'])
    training_runner = SandboxRunner()
    training_report = TaskVerifier(training_runner).verify(source, training, {})
    assert training_report['passed']
    n = 2**255 - 1
    answer = json.loads(subprocess.check_output([sys.executable, '-m', 'research.scaffold_search',
                       '--replay-model', str(model_path), '--input', str(n)], text=True))
    assert answer['outputs'] == [math.isqrt(n)]
    rows = []
    for parameters in ((3, 1, 0, 1), (3, 2, 1, 1), (4, 1, 1, 2)):
        task = PowerTask(*parameters)
        public = task.public()
        labels = [(case[0], value) for case, value in zip(public, task.expected(public))]
        expansion = expand_inverse_grammar(labels)
        assert expansion['status'] == 'unique'
        # Freeze the learned procedure configuration before exposing the new predicates.
        candidate = build_candidate(task.family, expansion['rule'], expansion['degree'], restored['configuration'])
        control = build_candidate(task.family, expansion['rule'], expansion['degree'], configurations()[0])
        reports = {}
        for mode, program in [('learned', candidate), ('frozen_control', control)]:
            runner = SandboxRunner()
            reports[mode] = TaskVerifier(runner).verify(program, task, {})
            reports[mode]['containers'] = runner.container_runs
        assert reports['learned']['passed'] and not reports['frozen_control']['passed']
        evaluator = SandboxRunner()
        evaluator.boot()
        shifted = task.samples(1024, seed=seed, audit=True)
        for offset in range(0, len(shifted), 64):
            batch = shifted[offset:offset + 64]
            result = TaskVerifier(evaluator).check(candidate, task, batch)
            for (n,), k in zip(batch, result['outputs']):
                assert task.p * k**task.degree + task.q * k <= task.d * n
                assert task.p * (k + 1)**task.degree + task.q * (k + 1) > task.d * n
        rows.append({'parameters': parameters, 'expansion': expansion, 'reports': reports,
                     'shifted_cases_passed': len(shifted), 'shifted_containers': evaluator.container_runs,
                     'source': candidate, 'source_sha256': hashlib.sha256(candidate.encode()).hexdigest()})
    return {'seed': seed, 'discovery': discovery, 'screening_containers': screening.container_runs,
            'training_report': training_report, 'training_containers': training_runner.container_runs,
            'fresh_process_replay_passed': True, 'replay_containers': 2, 'rows': rows,
            'donor_program_supplied': False, 'automatic_promotion': False,
            'limitations': ['Sixteen procedure configurations and loop grammar are developer-defined.',
                            'Learns boundary, branch, comparison and result choices, not arbitrary control flow.',
                            'Research-only model; no production promotion or external evaluator.',
                            'One operator and environment class, finite public/shifted distributions.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--replay-model', type=Path)
    parser.add_argument('--input', type=int)
    args = parser.parse_args()
    if args.replay_model is not None:
        if args.input is None or not 0 <= args.input < 2**256:
            parser.error('replay input must be a nonnegative 256-bit integer')
        print(json.dumps(replay(args.replay_model, args.input)))
    else:
        if args.seed is None or args.output is None:
            parser.error('--seed and --output are required')
        result = study(args.seed, args.output.with_suffix('.model.json'))
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        print('SCAFFOLD_SEARCH_RESULT ' + json.dumps(result, sort_keys=True), flush=True)
