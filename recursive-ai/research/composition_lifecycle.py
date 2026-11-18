"""Reproduce real Git/SQLite composition storage and fresh-process rollback."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

from research.composition_contract import adapter_digest, invoke, learn

FIRST = ((2, 1), (4, 2), (4, 3), (8, 4), (8, 6), (8, 7))
SECOND = ((2, 2), (4, 4), (4, 6), (8, 8), (8, 12), (8, 14))


def study(root):
    root = Path(root).resolve()
    if root.exists():
        raise ValueError('lifecycle state must be a new directory')
    problems = lambda tasks: [[(x, a*x+b) for x in (-2, 0, 3)] for a, b in tasks]
    first = learn(root, problems(FIRST))
    second = learn(root, problems(SECOND))
    if first['status'] != 'stored' or second['status'] != 'stored':
        raise ValueError('composition learning failed')
    old_key, = first['macros']
    new_key, = set(second['macros'])-set(first['macros'])
    invocations = []

    def cli(command, *arguments):
        return subprocess.run([sys.executable, '-m', 'research.composition_contract', command,
                               '--state', str(root), *arguments], text=True,
                              capture_output=True, timeout=30)

    def call(key, value, intercept):
        child = cli('invoke', '--macro', key, '--input', str(value))
        if child.returncode:
            raise ValueError(child.stderr)
        receipt = json.loads(child.stdout)
        if receipt['output'] != 2*value+intercept:
            raise ValueError('fresh-process output mismatch')
        invocations.append(dict(receipt, input=value))

    for key, intercept in ((old_key, 1), (new_key, 2)):
        for value in (-2**255+1, -1, 0, 1, 2**255-1):
            call(key, value, intercept)
    repeated = learn(root, problems(SECOND))
    if repeated['status'] != 'already_stored' or repeated['cost'] != 0:
        raise ValueError('cached learning repeated search')
    rollback = cli('activate', '--checkpoint', first['checkpoint'])
    if rollback.returncode:
        raise ValueError(rollback.stderr)
    removed = cli('invoke', '--macro', new_key, '--input', '7')
    if removed.returncode == 0 or 'macro is not active' not in removed.stderr:
        raise ValueError('rollback did not remove later macro')
    call(old_key, 7, 1)
    if cli('activate', '--checkpoint', second['checkpoint']).returncode:
        raise ValueError('restoration failed')
    call(new_key, 7, 2)
    stop = root/'STOP'
    stop.touch()
    blocked = cli('invoke', '--macro', new_key, '--input', '7')
    if blocked.returncode == 0 or 'operator stop' not in blocked.stderr:
        raise ValueError('STOP did not prevent invocation')
    stop.unlink()
    if invoke(root, new_key, 7)['output'] != 16:
        raise ValueError('state changed during STOP')
    return {'protocol': 'composition-lifecycle-1', 'code_commit': os.environ.get('GITHUB_SHA'),
            'adapter_digest': adapter_digest(), 'python': platform.python_version(),
            'first': first, 'second': second, 'cached': repeated, 'invocations': invocations,
            'rollback_removed_later_macro': True, 'restoration_reproduced_output': True,
            'stop_prevented_invocation': True, 'production_defaults_changed': False,
            'limits': ['Finite supplied primitive interpreter, not generated Python or new primitive invention.',
                       'Exact affine certificates assume affine task semantics; not arbitrary hidden functions.',
                       'Lifecycle verification does not establish search efficiency or independent evaluation.',
                       'State integrity checks are not authentication against an operator replacing Git and SQLite.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = study(args.state)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print('COMPOSITION_LIFECYCLE_RESULT '+json.dumps(result, sort_keys=True), flush=True)
