"""Frozen sampled-rule study of fixed, random-boundary and scored public queries."""
import argparse
import json
from pathlib import Path

from autonomy.procedure import propose
from autonomy.search import BOUND
from autonomy.tasks import Task
from autonomy.verifier import TaskVerifier
from core.rollback import VersionController
from memory.skill_store import MemoryEngine
from research.mixed_features import MixedTask, construct
from research.mixed_lifecycle import fresh_replay, record
from research.public_queries import acquire, sampled_rules
from sandbox.runner import SandboxRunner


def study(root, seed):
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
    order = ('fixed','random','active') if seed % 2 else ('active','random','fixed')
    arms = {}
    for mode in order:
        rows, manifest = [], dict(active)
        for index,(degree,p,r,q,d) in enumerate(sampled_rules(620017)):
            task = MixedTask(degree=degree,p=p,r=r,q=q,d=d)
            selection = acquire(lambda n:task.expected([(n,)])[0],mode,seed+index)
            row = {'parameters':[degree,p,r,q,d], 'selection':selection,
                   'certified':False, 'containers':0, 'shifted_cases':0}
            if selection['hypothesis']['status'] == 'unique':
                candidate = construct(task.family,selection['hypothesis'],configuration)
                runner = SandboxRunner()
                runner.max_container_runs = 20
                verification = TaskVerifier(runner).verify(candidate,task,active)
                row['report'] = verification
                if verification['passed']:
                    cases = task.samples(128,seed=seed+2000+index,audit=True)
                    try:
                        for offset in range(0,len(cases),32):
                            batch = cases[offset:offset+32]
                            result = TaskVerifier(runner).check(candidate,task,batch)
                            for (n,),k in zip(batch,result['outputs']):
                                if not task.value(k) <= task.d*n < task.value(k+1):
                                    raise ValueError('floor inequality failed')
                        row['certified'], row['shifted_cases'] = True, len(cases)
                        manifest[task.key] = record(task,candidate,verification,
                                                    selection['hypothesis'],configuration)
                    except (ValueError,RuntimeError) as error:
                        row['audit_error'] = type(error).__name__
                row['containers'] = runner.container_runs
            rows.append(row)
        state = root/mode
        memory, versions = MemoryEngine(state), VersionController(state)
        base = versions.snapshot(active)
        checkpoint = versions.snapshot(manifest,parent=base)
        memory.activate(checkpoint)
        memory.db.close()
        restarted = fresh_replay(state,seed+3000)
        memory = MemoryEngine(state)
        memory.activate(base)
        memory.db.close()
        rollback = fresh_replay(state,seed+3000)
        assert set(rollback['outputs']) == set(active)
        assert all(restarted['outputs'][key] == value for key,value in rollback['outputs'].items())
        memory = MemoryEngine(state)
        memory.activate(checkpoint)
        memory.db.close()
        restored = fresh_replay(state,seed+3000)
        assert restored['outputs'] == restarted['outputs']
        retention = SandboxRunner()
        retention.max_container_runs = 40
        retained = [TaskVerifier(retention).verify(active[t.key]['source'],t,{})
                    for t in (donor,training)]
        assert all(item['passed'] for item in retained)
        arms[mode] = {'rows':rows, 'certified':sum(row['certified'] for row in rows),
                      'restart':restarted,'rollback':rollback,'restored':restored,
                      'retention':retained,'retention_containers':retention.container_runs,
                      'lifecycle_containers':sum(r['containers'] for r in (restarted,rollback,restored))}
    all_emitted_passed = all(row['certified'] for arm in arms.values() for row in arm['rows']
                             if row['selection']['hypothesis']['status'] == 'unique')
    return {'seed':seed,'sampling_seed':620017,'development_sampling_seed':620016,
            'query_ceiling':64,'receiving_container_ceiling':20,
            'training_containers':training_runner.container_runs,'discovery':discovery,
            'order':order,'arms':arms,'all_emitted_passed':all_emitted_passed,
            'boundary_gain':arms['random']['certified']-arms['fixed']['certified'],
            'ranking_gain':arms['active']['certified']-arms['random']['certified'],
            'production_promotion':False,
            'limits':['Six unfiltered seeded in-grammar samples and two declared out-of-grammar controls.',
                      'Public-only preflight replaced a coarse pool with exact surviving-hypothesis boundaries.',
                      'Random/scored policies share a dynamic pool and first sixteen labels; fixed uses original public set.',
                      'Identical query counts and resource ceilings; consumed prediction work and containers differ.',
                      'Developer-defined grammar, internal evaluator, same operator/environment class.',
                      'Research checkpoint replay is not autonomous real-world rollback.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,required=True)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = study(args.state,args.seed)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print('QUERY_STUDY_RESULT '+json.dumps(result,sort_keys=True),flush=True)
