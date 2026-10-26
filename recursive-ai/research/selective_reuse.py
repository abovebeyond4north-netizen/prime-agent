"""Bounded semantic routing of saved compositions, with primitive-search fallback."""
from collections import deque
from contextlib import nullcontext

from research.composition_contract import checked_program, load, observations, state_session, stopped
from research.composition_search import PRIMITIVES, run, search
from research.composition_validation import coefficients

MODES = ('primitive', 'backward_primitive', 'unconditional', 'selective')


def _plan(target, operators, limit):
    queue = deque([(tuple(target), ())])
    seen = {tuple(target)}
    states, edges = 0, 0
    while queue:
        (a, b), suffix = queue.popleft()
        if (a, b) == (1, 0):
            return suffix, states, edges
        if states == limit:
            break
        states += 1
        for program, (m, c) in operators:
            edges += 1
            if len(program)+len(suffix) > 32 or m == 0 or a % m or (b-c) % m:
                continue
            predecessor = (a//m, (b-c)//m)
            if predecessor == (1, 0):
                return program+suffix, states, edges
            if predecessor not in seen:
                seen.add(predecessor)
                queue.append((predecessor, program+suffix))
    return None, states, edges


def solve_batch(root, problems, *, mode='selective', budget=10000, planner_states=128):
    """Use only public examples and a frozen, checked library snapshot.

    Caps are separate: primitive evaluations and symbolic planning states.
    Routing, state loading and proof checks still cost time; no zero-overhead or
    equal-wall-budget guarantee is implied by a primitive-evaluation saving.
    """
    if mode not in MODES:
        raise ValueError('unknown reuse mode')
    if type(budget) is not int or not 0 <= budget <= 100000:
        raise ValueError('invalid primitive-evaluation budget')
    if type(planner_states) is not int or not 0 <= planner_states <= 128:
        raise ValueError('invalid planner-state budget')
    if not isinstance(problems, (list, tuple)) or not 1 <= len(problems) <= 128:
        raise ValueError('one to 128 public problems required')
    normalized = [observations(problem) for problem in problems]
    uses_memory = mode in ('selective', 'unconditional')
    if uses_memory and root is None:
        raise ValueError('composition state required')
    if uses_memory:
        stopped(root)
    session = state_session(root) if uses_memory else nullcontext(None)
    with session as state:
        checkpoint, operators = None, []
        if uses_memory:
            memory, versions = state
            checkpoint = memory.current()
            manifest = load(memory, versions, checkpoint)
            operators = [(tuple(record['program']), tuple(record['coefficients']))
                         for _, record in sorted(manifest['macros'].items())]
        elif mode == 'backward_primitive':
            operators = [((token,), coefficients((token,))) for token in PRIMITIVES]
        results = []
        for rows, proof in normalized:
            if uses_memory:
                stopped(root)
            program, states, edges = None, 0, 0
            if mode in ('selective', 'backward_primitive'):
                program, states, edges = _plan(proof, operators, planner_states)
            if program is not None and len(program)*len(rows) <= budget:
                checked_program(program, proof)
                if any(run(program, x) != y for x, y in rows):
                    raise ValueError('planned program failed public examples')
                result = {'program': program, 'cost': len(program)*len(rows),
                          'status': 'candidate', 'route': 'planned'}
            else:
                macro = operators[0][0] if mode == 'unconditional' and operators else None
                result = dict(search(rows, budget, macro, eager=True),
                              route='unconditional' if macro else 'fallback')
                if result['program'] is not None:
                    checked_program(result['program'], proof)
            results.append(dict(result, planner_states=states, planner_edges=edges))
        if uses_memory:
            stopped(root)
        return {'mode': mode, 'checkpoint': checkpoint, 'results': results}
