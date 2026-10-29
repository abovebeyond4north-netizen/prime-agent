"""Research-only, version-bound storage of symbolically checked compositions."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path

from core.rollback import VersionController
from memory.skill_store import MemoryEngine
from research.composition_search import compress, run, search
from research.composition_validation import coefficients

FORMAT = 'composition-library-1'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def adapter_digest():
    root = Path(__file__).resolve().parents[1]
    paths = ('research/composition_contract.py', 'research/composition_search.py',
             'research/composition_validation.py', 'core/rollback.py',
             'memory/skill_store.py', 'core/ledger.py')
    return digest([(path, hashlib.sha256((root/path).read_bytes()).hexdigest()) for path in paths])


def observations(examples):
    if not isinstance(examples, (list, tuple)) or not 2 <= len(examples) <= 32:
        raise ValueError('two to 32 public observations required')
    rows = []
    for row in examples:
        if (not isinstance(row, (list, tuple)) or len(row) != 2 or
                any(type(v) is not int or abs(v) > 10**12 for v in row)):
            raise ValueError('invalid public observation')
        rows.append(list(row))
    rows.sort()
    if len({row[0] for row in rows}) != len(rows):
        raise ValueError('distinct public inputs required')
    (x0, y0), (x1, y1) = rows[:2]
    slope, remainder = divmod(y1-y0, x1-x0)
    intercept = y0-slope*x0
    if remainder or any(slope*x+intercept != y for x, y in rows):
        raise ValueError('observations do not fit an integer affine function')
    return rows, [slope, intercept]


def checked_program(program, proof, *, macro=False):
    if (not isinstance(program, (list, tuple)) or not (2 if macro else 0) <= len(program) <= (8 if macro else 32) or
            not isinstance(proof, (list, tuple)) or len(proof) != 2 or
            any(type(v) is not int for v in proof)):
        raise ValueError('invalid primitive sequence or affine certificate')
    program = tuple(program)
    run(program, 0)
    if list(coefficients(program)) != list(proof):
        raise ValueError('symbolic certificate mismatch')
    return program


def check_manifest(manifest):
    if (not isinstance(manifest, dict) or
            set(manifest) != {'format', 'adapter_digest', 'problems', 'macros'} or
            manifest['format'] != FORMAT or manifest['adapter_digest'] != adapter_digest()):
        raise ValueError('unsupported or stale composition checkpoint')
    problems, macros = manifest['problems'], manifest['macros']
    if (not isinstance(problems, dict) or not 1 <= len(problems) <= 32 or
            not isinstance(macros, dict) or not 1 <= len(macros) <= 8):
        raise ValueError('invalid composition library size')
    for key, record in problems.items():
        if not isinstance(record, dict) or set(record) != {'examples', 'program', 'coefficients'}:
            raise ValueError('invalid problem record')
        rows, proof = observations(record['examples'])
        if rows != record['examples'] or digest(rows) != key or proof != record['coefficients']:
            raise ValueError('problem provenance mismatch')
        checked_program(record['program'], record['coefficients'])
    for key, record in macros.items():
        if not isinstance(record, dict) or set(record) != {'program', 'coefficients', 'training_ids'}:
            raise ValueError('invalid macro record')
        program = checked_program(record['program'], record['coefficients'], macro=True)
        ids = record['training_ids']
        if (digest(program) != key or not isinstance(ids, list) or not 1 <= len(ids) <= 32 or
                any(type(item) is not str for item in ids) or len(set(ids)) != len(ids) or
                any(item not in problems for item in ids)):
            raise ValueError('macro provenance mismatch')
        if compress([tuple(problems[item]['program']) for item in ids]) != program:
            raise ValueError('macro does not reconstruct from solved programs')
    return manifest


@contextmanager
def state_session(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with (root/'composition.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        marker = root/'composition-format.json'
        if marker.exists():
            if json.loads(marker.read_text()) != FORMAT:
                raise ValueError('wrong composition state format')
        else:
            if any(path.name != 'composition.lock' for path in root.iterdir()):
                raise ValueError('dedicated empty state directory required')
            with marker.open('x') as stream:
                json.dump(FORMAT, stream)
        memory = MemoryEngine(root)
        try:
            yield memory, VersionController(root)
        finally:
            memory.db.close()


def stopped(root):
    if (Path(root)/'STOP').exists():
        raise RuntimeError('operator stop requested')


def load(memory, versions, checkpoint):
    if checkpoint is None:
        return {'format': FORMAT, 'adapter_digest': adapter_digest(), 'problems': {}, 'macros': {}}
    if memory.db.execute('SELECT 1 FROM checkpoints WHERE sha=?', (checkpoint,)).fetchone() is None:
        raise ValueError('checkpoint was not registered by this state')
    return check_manifest(versions.read(checkpoint))


def learn(root, problems, *, max_evaluations=100000):
    if not isinstance(problems, (list, tuple)) or not 1 <= len(problems) <= 16:
        raise ValueError('one to 16 public problems required')
    normalized = [observations(examples) for examples in problems]
    if type(max_evaluations) is not int or not 0 <= max_evaluations <= 100000:
        raise ValueError('invalid total evaluation budget')
    stopped(root)
    with state_session(root) as (memory, versions):
        parent = memory.current()
        manifest = load(memory, versions, parent)
        records = dict(manifest['problems'])
        spent, added = 0, 0
        for rows, proof in normalized:
            stopped(root)
            key = digest(rows)
            if key in records:
                continue
            if len(records) >= 32:
                raise ValueError('composition problem capacity exhausted')
            result = search(rows, max_evaluations-spent, eager=True)
            spent += result['cost']
            if result['program'] is None:
                return {'status': 'exhausted', 'checkpoint': parent, 'cost': spent}
            program = checked_program(result['program'], proof)
            records[key] = {'examples': rows, 'program': list(program), 'coefficients': proof}
            added += 1
        if not added:
            return {'status': 'already_stored', 'checkpoint': parent, 'cost': 0,
                    'macros': sorted(manifest['macros'])}
        macro = compress([tuple(record['program']) for record in records.values()])
        if macro is None:
            return {'status': 'no_compression', 'checkpoint': parent, 'cost': spent}
        macros = dict(manifest['macros'])
        macros[digest(macro)] = {'program': list(macro), 'coefficients': list(coefficients(macro)),
                                'training_ids': list(records)}
        updated = {'format': FORMAT, 'adapter_digest': adapter_digest(),
                   'problems': records, 'macros': macros}
        check_manifest(updated)
        stopped(root)
        memory.db.execute('BEGIN IMMEDIATE')
        try:
            checkpoint = versions.snapshot(updated, parent)
            stopped(root)
            memory.activate(checkpoint)
            memory.event({'composition_checkpoint': checkpoint, 'cost': spent,
                          'added_problems': added, 'macros': sorted(macros)})
            memory.db.execute('COMMIT')
        except Exception:
            memory.db.execute('ROLLBACK')
            raise
        return {'status': 'stored', 'checkpoint': checkpoint, 'cost': spent, 'macros': sorted(macros)}


def invoke(root, key, value):
    if type(value) is not int or abs(value).bit_length() > 256:
        raise ValueError('signed 256-bit integer required')
    stopped(root)
    with state_session(root) as (memory, versions):
        checkpoint = memory.current()
        manifest = load(memory, versions, checkpoint)
        if key not in manifest['macros']:
            raise ValueError('macro is not active')
        record = manifest['macros'][key]
        program = checked_program(record['program'], record['coefficients'], macro=True)
        output = run(program, value)
        a, b = record['coefficients']
        if output != a*value+b:
            raise ValueError('invocation violated affine certificate')
        stopped(root)
        return {'checkpoint': checkpoint, 'macro': key, 'output': output}


def activate(root, checkpoint):
    with state_session(root) as (memory, versions):
        if checkpoint is None:
            raise ValueError('registered checkpoint required')
        load(memory, versions, checkpoint)
        memory.db.execute('BEGIN IMMEDIATE')
        try:
            memory.activate(checkpoint)
            memory.event({'composition_checkpoint_activated': checkpoint})
            memory.db.execute('COMMIT')
        except Exception:
            memory.db.execute('ROLLBACK')
            raise
        return {'checkpoint': checkpoint}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('invoke', 'activate'))
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--macro')
    parser.add_argument('--input', type=int)
    parser.add_argument('--checkpoint')
    args = parser.parse_args()
    if args.command == 'invoke':
        receipt = invoke(args.state, args.macro, args.input)
    else:
        receipt = activate(args.state, args.checkpoint)
    print(json.dumps(receipt, sort_keys=True))
