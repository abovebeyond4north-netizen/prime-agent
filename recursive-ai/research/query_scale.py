"""Frozen 24-rule extension of the cheap public boundary-query comparison."""
import argparse
import json
import random
from pathlib import Path

from autonomy.procedure import propose
from autonomy.search import BOUND
from autonomy.tasks import Task
from autonomy.verifier import TaskVerifier
from core.rollback import VersionController
from memory.skill_store import MemoryEngine
from research.mixed_features import MixedTask, construct
from research.mixed_lifecycle import fresh_replay, record
from research.public_queries import acquire, sampled_rules, universe

from sandbox.runner import SandboxRunner


def rule_partition(shard):
    if type(shard) is not int or not 0 <= shard < 4:
        raise ValueError('shard must be 0..3')
    excluded = set(sampled_rules(620016)[:6]+sampled_rules(620017)[:6])
    population = [rule for rule in universe() if rule not in excluded]
    rules = random.Random(620018).sample(population,24)
    return rules[6*shard:6*(shard+1)]+[(5,1,1,1,1),(3,5,1,1,1)]


def lifecycle(state, active, manifest, seed):
    memory, versions = MemoryEngine(state), VersionController(state)
    base = versions.snapshot(active)
    extended = versions.snapshot(manifest,parent=base)
    memory.activate(extended)
    memory.db.close()
    first = fresh_replay(state,seed)
    memory = MemoryEngine(state)
    memory.activate(base)
    memory.db.close()
    rollback = fresh_replay(state,seed)
    assert set(rollback['outputs']) == set(active)
    assert all(first['outputs'][key] == value for key,value in rollback['outputs'].items())
    memory = MemoryEngine(state)
    memory.activate(extended)
    memory.db.close()
    restored = fresh_replay(state,seed)
    assert restored['outputs'] == first['outputs']
    return {'restart':first,'rollback':rollback,'restored':restored,
            'containers':sum(r['containers'] for r in (first,rollback,restored))}


def study(root, seed, shard):
    rules = rule_partition(shard)
    if root.exists():
        raise ValueError('new state directory required')
    root.mkdir(parents=True)
    training_runner = SandboxRunner()
    donor, training = Task('lower_bound'), Task('integer_sqrt')
    report = TaskVerifier(training_runner).verify(BOUND,donor,{})
    assert report['passed']
    active = {donor.key:record(donor,BOUND,report)}
    source, model, discovery = propose(training_runner,training,active)
    report = TaskVerifier(training_runner).verify(source,training,active)
    assert report['passed']
    active[training.key] = record(training,source,report)
    configuration = dict(model['configuration'])
    arms = {}
    order = ('fixed','random') if seed % 2 else ('random','fixed')
    for mode in order:
        rows, manifest = [], dict(active)
        for index,parameters in enumerate(rules):
            degree,p,r,q,d = parameters
            task = MixedTask(degree=degree,p=p,r=r,q=q,d=d)
            task_seed = seed+shard*100+index
            selection = acquire(lambda n:task.expected([(n,)])[0],mode,task_seed)
            row = {'parameters':parameters,'selection':selection,'certified':False,
                   'containers':0,'shifted_cases':0}
            if selection['hypothesis']['status'] == 'unique':
                candidate = construct(task.family,selection['hypothesis'],configuration)
                runner = SandboxRunner()
                runner.max_container_runs = 20
                report = TaskVerifier(runner).verify(candidate,task,active)
                row['report'] = report
                if report['passed']:
                    cases = task.samples(128,seed=task_seed+2000,audit=True)
                    try:
                        for offset in range(0,len(cases),32):
                            batch = cases[offset:offset+32]
                            result = TaskVerifier(runner).check(candidate,task,batch)
                            for (n,),k in zip(batch,result['outputs']):
                                if not task.value(k) <= task.d*n < task.value(k+1):
                                    raise ValueError('floor inequality failed')
                        row['certified'],row['shifted_cases'] = True,len(cases)
                        manifest[task.key] = record(task,candidate,report,
                                                    selection['hypothesis'],configuration)
                    except (ValueError,RuntimeError) as error:
                        row['audit_error'] = type(error).__name__
                row['containers'] = runner.container_runs
            rows.append(row)
        replays = lifecycle(root/mode,active,manifest,seed+shard*100+3000)
        retention = SandboxRunner()
        retention.max_container_runs = 40
        retained = [TaskVerifier(retention).verify(active[t.key]['source'],t,{})
                    for t in (donor,training)]
        assert all(r['passed'] for r in retained)
        arms[mode] = {'rows':rows,'in_grammar_certified':sum(r['certified'] for r in rows[:6]),
                      'lifecycle':replays,'retention':retained,
                      'retention_containers':retention.container_runs}
    return {'seed':seed,'shard':shard,'sampling_seed':620018,'sample_size':24,
            'query_ceiling':64,'receiving_container_ceiling':20,'order':order,
            'training_containers':training_runner.container_runs,'discovery':discovery,'arms':arms,
            'all_emitted_passed':all(r['certified'] for a in arms.values() for r in a['rows']
                                     if r['selection']['hypothesis']['status'] == 'unique'),
            'production_promotion':False,
            'limits':['24 unfiltered rules sampled after excluding both earlier six-rule sets.',
                      'Four disjoint shards; each repeats the same two out-of-grammar controls.',
                      'Same frozen cheap query policy and emission grammar; no tuning on this sample.',
                      'Exactly 64 labels and identical resource ceilings; consumed work differs.',
                      'Internal evaluator and same operator/environment class; no external replication.',
                      'Research checkpoint switches are not autonomous distribution-shift recovery.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,required=True)
    parser.add_argument('--shard',type=int,required=True)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = study(args.state,args.seed,args.shard)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print('QUERY_SCALE_RESULT '+json.dumps(result,sort_keys=True),flush=True)
