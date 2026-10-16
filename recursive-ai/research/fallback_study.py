"""Fresh disjoint comparison using the unchanged certification/lifecycle harness."""
import argparse
import json
import random
from pathlib import Path
from unittest.mock import patch

from research.public_queries import sampled_rules, universe
from research.query_fallback import acquire_fallback
from research.query_scale import rule_partition as previous_partition, study as paired_study


def rule_partition(shard):
    if type(shard) is not int or not 0 <= shard < 4:
        raise ValueError('shard must be 0..3')
    excluded = set(sampled_rules(620016)[:6]+sampled_rules(620017)[:6])
    excluded.update(rule for index in range(4) for rule in previous_partition(index)[:6])
    rules = random.Random(620019).sample([r for r in universe() if r not in excluded],24)
    return rules[6*shard:6*(shard+1)]+[(5,1,1,1,1),(3,5,1,1,1)]


def selector(label, mode, seed):
    return acquire_fallback(label,{'fixed':'extended_fixed','random':'boundary_fallback'}[mode],seed)


def study(root, seed, shard):
    # Substitute only the public rule supplier and query policy, never the verifier.
    with patch('research.query_scale.rule_partition',rule_partition), \
            patch('research.query_scale.acquire',selector):
        result = paired_study(root,seed,shard)
    names = {'fixed':'extended_fixed','random':'boundary_fallback'}
    result['arms'] = {names[key]:value for key,value in result['arms'].items()}
    result['order'] = [names[key] for key in result['order']]
    result.update({'sampling_seed':620019,'query_ceiling':128,'baseline_query_count':64})
    for arm in result['arms'].values():
        arm['baseline64_certified'] = sum(row['certified'] and
            row['selection']['baseline_hypothesis']['status'] == 'unique' for row in arm['rows'][:6])
        arm['total_label_queries'] = sum(row['selection']['label_queries'] for row in arm['rows'])
    result['all_baseline_preserved'] = all(
        row['selection']['baseline_hypothesis']['status'] != 'unique' or
        (row['selection']['hypothesis'] == row['selection']['baseline_hypothesis'] and row['certified'])
        for arm in result['arms'].values() for row in arm['rows'])
    result['limits'] = [
        'Fresh 24-rule sample excludes all earlier 36 public-query development/test rules.',
        'Both policies preserve the complete original 64 labels and every unique baseline hypothesis.',
        'Only ambiguous cases can request up to 64 additional labels; no-fit stops at 64.',
        'Extended fixed inputs control for additional labels; actual query counts may differ.',
        'Baseline64 certifications reuse checks of identical preserved programs, not a third execution arm.',
        'Only public supplier/selector substituted in the existing paired harness; evaluator unchanged.',
        'Same internal grammar/evaluator/operator class; not independent or real-world recovery.']
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,required=True)
    parser.add_argument('--shard',type=int,required=True)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = study(args.state,args.seed,args.shard)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print('FALLBACK_STUDY_RESULT '+json.dumps(result,sort_keys=True),flush=True)
    assert result['all_baseline_preserved'] and result['all_emitted_passed']
