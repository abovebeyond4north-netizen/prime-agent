"""Public-only Boolean rule induction and bounded word-level code synthesis."""
import ast

MODES = ('lookup', 'linear', 'compositional')


def induce(examples, mode='compositional'):
    if mode not in MODES:
        raise ValueError('unknown induction mode')
    if not isinstance(examples, (list, tuple)) or len(examples) != 4:
        raise ValueError('four one-bit public examples required')
    table = {}
    for row in examples:
        if not isinstance(row, (list, tuple)) or len(row) != 4:
            raise ValueError('expected a, b, width, output')
        a, b, width, value = row
        if any(type(x) is not int for x in row) or width != 1 or any(x not in (0, 1) for x in (a, b, value)):
            raise ValueError('invalid one-bit observation')
        if (a, b) in table:
            raise ValueError('duplicate observation')
        table[a, b] = value
    c0 = table[0, 0]
    ca, cb = table[1, 0] ^ c0, table[0, 1] ^ c0
    cab = table[1, 1] ^ c0 ^ ca ^ cb
    if mode == 'linear' and cab:
        return {'status': 'abstained', 'reason': 'interaction_required', 'source': None}
    lines = ['def bit_transform(a, b, width):', '    mask = (1 << width) - 1',
             '    a = a & mask', '    b = b & mask']
    if mode == 'lookup':
        lines.append('    if width != 1:')
        lines.append('        return 0')
        expression = repr([[table[0, 0], table[0, 1]], [table[1, 0], table[1, 1]]])+'[a][b]'
    else:
        terms = [term for coefficient, term in ((c0, 'mask'), (ca, 'a'), (cb, 'b'), (cab, '(a & b)'))
                 if coefficient]
        expression = ' ^ '.join(terms) if terms else '0'
    lines.append('    return '+expression)
    source = '\n'.join(lines)+'\n'
    return {'status': 'candidate', 'source': source, 'coefficients': [c0, ca, cb, cab],
            'ast_nodes': sum(1 for _ in ast.walk(ast.parse(source))), 'public_labels': 4,
            'mode': mode}
