"""Finite symbolic search and data-derived sequence compression; no eval/exec."""
from collections import Counter, deque

PRIMITIVES = ('increment', 'double', 'negate')


def run(program, value):
    if type(value) is not int:
        raise ValueError('invalid input')
    if not isinstance(program, tuple) or len(program) > 32:
        raise ValueError('invalid program')
    for operation in program:
        if operation == 'increment':
            value += 1
        elif operation == 'double':
            value *= 2
        elif operation == 'negate':
            value = -value
        else:
            raise ValueError('unknown primitive')
    return value


def compress(programs):
    """Select a repeated contiguous abstraction by net token saving.

    Return a flat primitive sequence, never an executable callable or source.
    Count non-overlapping occurrences, including the definition's token cost.
    """
    candidates = set()
    for program in programs:
        run(program, 0)
        for size in range(2, min(8, len(program))+1):
            candidates.update(program[i:i+size] for i in range(len(program)-size+1))
    gains = Counter()
    for candidate in candidates:
        count = 0
        for program in programs:
            index = 0
            while index <= len(program)-len(candidate):
                if program[index:index+len(candidate)] == candidate:
                    count += 1
                    index += len(candidate)
                else:
                    index += 1
        gains[candidate] = count*(len(candidate)-1)-len(candidate)-1
    if not gains:
        return None
    best = min(gains, key=lambda candidate: (-gains[candidate], len(candidate), candidate))
    return best if gains[best] > 0 else None


def search(examples, budget=1000, macro=None):
    """BFS with public semantic deduplication and primitive-operation budget.

    Macro execution pays for every expanded primitive on every public input.
    Public equivalence does not certify unseen inputs.
    """
    if type(budget) is not int or not 0 <= budget <= 100000:
        raise ValueError('invalid budget')
    if not examples or len(examples) > 32:
        raise ValueError('invalid examples')
    for row in examples:
        if len(row) != 2 or any(type(x) is not int or abs(x) > 10**12 for x in row):
            raise ValueError('invalid observation')
    operations = [(p,) for p in PRIMITIVES]
    if macro is not None:
        run(macro, 0)
        if not 2 <= len(macro) <= 8:
            raise ValueError('invalid abstraction')
        operations.insert(0, macro)
    initial = tuple(x for x, _ in examples)
    target = tuple(y for _, y in examples)
    queue = deque([((), initial)])
    seen = {initial}
    spent = 0
    while queue:
        program, values = queue.popleft()
        if values == target:
            return {'program': program, 'cost': spent, 'status': 'candidate'}
        for operation in operations:
            if len(program)+len(operation) > 32:
                continue
            cost = len(operation)*len(values)
            if spent+cost > budget:
                return {'program': None, 'cost': spent, 'status': 'exhausted'}
            spent += cost
            output = tuple(run(operation, value) for value in values)
            if output not in seen:
                seen.add(output)
                queue.append((program+operation, output))
    return {'program': None, 'cost': spent, 'status': 'exhausted'}
