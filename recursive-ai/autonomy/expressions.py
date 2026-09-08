"""Bounded declarative tasks; their trusted interpreter never executes source."""
import hashlib
import json
import math
import random
import secrets
from dataclasses import dataclass

OPERATORS = {"add": 2, "sub": 2, "mul": 2, "gcd": 2, "min": 2, "max": 2, "abs": 1}
COMMUTATIVE = {"add", "mul", "gcd", "min", "max"}
PROBES = [(a, b) for a in (-7, -2, 0, 3, 11) for b in (-7, -2, 0, 3, 11)]


def canonical(expression):
    count = 0

    def visit(node, depth):
        nonlocal count
        count += 1
        if depth > 5 or count > 31:
            raise ValueError("expression exceeds structural budget")
        if type(node) is int and -9 <= node <= 9:
            return node
        if type(node) is str and node in ("a", "b"):
            return node
        if type(node) is not list or not node or type(node[0]) is not str or node[0] not in OPERATORS:
            raise ValueError("invalid expression node")
        op = node[0]
        if len(node) != OPERATORS[op] + 1:
            raise ValueError("invalid operator arity")
        children = [visit(child, depth + 1) for child in node[1:]]
        if op in COMMUTATIVE:
            children.sort(key=lambda child: json.dumps(child, separators=(",", ":")))
        return [op, *children]

    return json.dumps(visit(expression, 0), separators=(",", ":"))


def interpret(expression, a, b):
    if type(expression) is int:
        return expression
    if type(expression) is str:
        return a if expression == "a" else b
    op = expression[0]
    values = [interpret(child, a, b) for child in expression[1:]]
    if op == "add":
        return values[0] + values[1]
    if op == "sub":
        return values[0] - values[1]
    if op == "mul":
        return values[0] * values[1]
    if op == "gcd":
        return math.gcd(*values)
    if op == "min":
        return min(values)
    if op == "max":
        return max(values)
    if op == "abs":
        return abs(values[0])
    raise ValueError("unknown operator")


@dataclass(frozen=True)
class ExpressionTask:
    expression_json: str
    tier: int = 1

    def __post_init__(self):
        if type(self.tier) is not int or not 1 <= self.tier <= 3:
            raise ValueError("invalid tier")
        if type(self.expression_json) is not str or len(self.expression_json) > 1024:
            raise ValueError("invalid expression encoding")
        try:
            normalized = canonical(json.loads(self.expression_json))
        except (RecursionError, json.JSONDecodeError) as error:
            raise ValueError("invalid expression encoding") from error
        if normalized != self.expression_json:
            raise ValueError("expression must use canonical encoding")

    @property
    def expression(self):
        return json.loads(self.expression_json)

    @property
    def family(self):
        return "compound_" + hashlib.sha256(self.expression_json.encode()).hexdigest()[:16]

    @property
    def key(self):
        return "expression:" + self.expression_json.encode().hex() + f":tier{self.tier}"

    @property
    def prerequisites(self):
        return ("gcd",) if '"gcd"' in self.expression_json else ()

    @property
    def performance_step_limit(self):
        return 10000

    @property
    def spec(self):
        return (f"{self.family}(a, b): evaluate the prefix expression {self.expression_json}. "
                "add/sub/mul are integer arithmetic; gcd is nonnegative greatest common divisor; "
                "abs/min/max have integer semantics. Return an integer without modifying inputs. "
                "Pure functions only; no imports, attributes, annotations or defaults.")

    def with_tier(self, tier):
        return ExpressionTask(self.expression_json, tier)

    def public(self):
        return [(0, 0), (-12, 18), (7, 0), (0, -7), (3, 11)]

    def expected(self, cases):
        expression = self.expression
        return [interpret(expression, *case) for case in cases]

    def samples(self, count, seed=None, audit=False):
        rng = random.Random(secrets.randbits(128) if seed is None else seed)
        bound = 10 ** (3 * self.tier + (3 if audit else 0))
        return [(rng.randint(-bound, bound), rng.randint(-bound, bound)) for _ in range(count)]

    def properties(self):
        return PROBES + [(10**40, -10**40), (-(10**40), 0), (1, 10**40)]

    def performance(self):
        return [(10**100 - 1, 10**80 - 1), (-(10**100), 10**99), (0, 10**100)]

    def descriptor(self):
        return {"key": self.key, "family": self.family, "tier": self.tier,
                "instruction": self.spec, "expression": self.expression, "grammar": "integer-expression-1"}

    @classmethod
    def from_key(cls, key):
        if type(key) is not str or len(key) > 2080 or not key.startswith("expression:"):
            raise ValueError("invalid expression task key")
        try:
            payload, tier = key[len("expression:"):].rsplit(":tier", 1)
            task = cls(bytes.fromhex(payload).decode("utf-8"), int(tier))
        except (ValueError, UnicodeError) as error:
            raise ValueError("invalid expression task key") from error
        if task.key != key:
            raise ValueError("noncanonical task key")
        return task


def generate_tasks(seed=0, count=6):
    if type(seed) is not int or not 0 <= seed < 2**32 or type(count) is not int or not 1 <= count <= 12:
        raise ValueError("task seed must be uint32; count must be 1..12")
    rng = random.Random(seed)
    tasks, seen = [], set()
    for _ in range(1000):
        # A verified primitive is a prerequisite; surrounding expressions vary by seed.
        left = [rng.choice(("add", "sub", "mul")), "a", rng.choice((-7, -3, 2, 5, 9))]
        right = [rng.choice(("add", "sub", "mul")), "b", rng.choice((-5, -2, 3, 7))]
        expression = [rng.choice(("add", "sub", "mul", "max", "min")), ["gcd", left, right],
                      [rng.choice(("add", "sub", "mul")), "a", "b"]]
        task = ExpressionTask(canonical(expression))
        fingerprint = tuple(task.expected(PROBES))
        # Finite behavioral novelty is a heuristic, never a claim of mathematical novelty.
        depends_a = any(fingerprint[i * 5 + j] != fingerprint[j] for i in range(1, 5) for j in range(5))
        depends_b = any(fingerprint[i * 5 + j] != fingerprint[i * 5] for i in range(5) for j in range(1, 5))
        if fingerprint in seen or not depends_a or not depends_b or len(set(fingerprint)) < 5:
            continue
        seen.add(fingerprint)
        tasks.append(task)
        if len(tasks) == count:
            return tasks
    raise ValueError("task admission budget exhausted")
