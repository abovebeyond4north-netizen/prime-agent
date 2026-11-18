"""Matched empty-state acquisition cost of learned versus supplied inverse procedures."""
import argparse
import json
from pathlib import Path
from autonomy.controller import execute_goal
from autonomy.curriculum import certified
from autonomy.search import normalized_digest
from core.rollback import VersionController
from research.procedure_reuse import shifted_check

BUDGETS = {'max_attempts':16, 'max_containers':160, 'max_model_calls':0, 'max_seconds':600}


def compare(learned, supplied):
    for arm in (learned, supplied):
        summary = arm['summary']
        if summary['status'] != 'goal_reached' or not summary['audit']['passed'] or not arm['shifted']['passed']:
            raise ValueError('fresh acquisition or holdout verification failed')
    if learned['sources'] != supplied['sources']:
        raise ValueError('different certified programs')
    if learned['summary']['total_attempts'] != supplied['summary']['total_attempts']:
        raise ValueError('attempt counts differ')
    delta = learned['summary']['container_runs'] - supplied['summary']['container_runs']
    return {'verified':True, 'learned_extra_containers':delta,
            'outcome':'supplied_advantage' if delta > 0 else 'tie' if delta == 0 else 'learned_advantage'}


def study(root, seed):
    if root.exists():
        raise ValueError('study state must be a new directory')
    root.mkdir(parents=True)
    order = ('learned','supplied') if seed % 2 else ('supplied','learned')
    arms = {}
    for mode in order:
        state = root / mode
        summary = execute_goal(state,description='numeric inverses',tier=2,
                               learn_inverse_procedure=mode == 'learned',**BUDGETS)
        if summary['status'] != 'goal_reached':
            raise ValueError('acquisition failed under predeclared budget')
        manifest = certified(VersionController(state).read(summary['checkpoint']))
        arms[mode] = {'summary':summary,
                      'sources':{key:normalized_digest(skill['source']) for key,skill in manifest.items()},
                      'procedure_models':sum('procedure_model' in skill for skill in manifest.values()),
                      'shifted':shifted_check(state,summary['checkpoint'],seed)}
    return {'seed':seed,'order':order,'budgets':BUDGETS,'arms':arms,
            'comparison':compare(arms['learned'],arms['supplied']),
            'limits':['Both start empty; extra seeded validation is separate from acquisition cost.',
                      'Same designed tasks, evaluator and operator/environment class; no open-world claim.',
                      'Receiving tiers use the same task family; supplied arm starts with a correct designed scaffold.',
                      'Container cost does not establish CPU, wall-time or dollar-cost superiority.']}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,required=True)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=study(args.state,args.seed)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print('COLD_START_RESULT '+json.dumps(result,sort_keys=True),flush=True)
