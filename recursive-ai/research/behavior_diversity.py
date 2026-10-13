"""Read-only development-case diagnostics; no selection or promotion authority."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from autonomy.tasks import task_from_key
from sandbox.runner import SandboxRunner


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def observe_candidates(candidates, runner):
    runner.boot()
    rows = []
    for task_key, source in candidates:
        task = task_from_key(task_key)
        cases = task.public()
        row = {'task': task_key, 'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
               'development_cases_digest': digest(cases)}
        try:
            result = runner.execute(source, cases, entrypoint=task.family)
            row.update(status='observed', output_digest=digest([task_key, cases, result['outputs']]),
                       work_digest=digest([task_key, cases, result['steps_per_case']]),
                       public_correct=result['outputs'] == task.expected(cases))
        except Exception as error:
            row.update(status='unobserved', error_type=type(error).__name__)
        rows.append(row)
    summaries = {}
    for key in sorted({row['task'] for row in rows}):
        relevant = [r for r in rows if r['task'] == key]
        observed = [r for r in relevant if r['status'] == 'observed']
        summaries[key] = {
            'candidates': len(relevant), 'unobserved': len(relevant) - len(observed),
            'distinct_sources': len({r['source_sha256'] for r in relevant}),
            'distinct_outputs': len({r['output_digest'] for r in observed}),
            'distinct_work_traces': len({r['work_digest'] for r in observed}),
            'public_correct_sources': len({r['source_sha256'] for r in observed if r['public_correct']}),
            'distinct_correct_outputs': len({r['output_digest'] for r in observed if r['public_correct']}),
        }
    return {'protocol': 'public-behavior-diversity-v1', 'rows': rows, 'by_task': summaries,
            'container_runs': runner.container_runs, 'automatic_promotion': False,
            'limitations': ['Public cases only; no holdout or audit outcomes inform fingerprints.',
                            'Matching outputs on a finite probe set do not prove program equivalence.',
                            'Step traces distinguish work patterns, not algorithm identity.',
                            'Unobserved candidates are counted, never treated as duplicates.']}


def read_archive(root, limit=64):
    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError('candidate limit must be in 1..64')
    path = Path(root).resolve() / 'memory.sqlite3'
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as connection:
        # Only the bounded prefix is diagnosed; ordering is explicit and reproducible.
        entries = connection.execute(
            'SELECT source,report FROM candidate_archive ORDER BY family,digest LIMIT ?', (limit,)
        ).fetchall()
    candidates = []
    missing = 0
    for source, raw in entries:
        key = json.loads(raw).get('task')
        if key is None:
            missing += 1
        else:
            candidates.append((key, source))
    return candidates, missing


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=64)
    args = parser.parse_args()
    candidates, missing = read_archive(args.root, args.limit)
    report = observe_candidates(candidates, SandboxRunner())
    report['archive_entries_missing_task_identity'] = missing
    report['archive_limit'] = args.limit
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, sort_keys=True))
