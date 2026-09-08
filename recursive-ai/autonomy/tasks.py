"""Trusted task families. Generated task descriptions never supply their own oracle."""
import hashlib
import json
import math
import random
import secrets
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SUITE_VERSION = "autonomy-1"
FAMILIES = ("lower_bound", "upper_bound", "binary_search", "count_occurrences", "gcd", "fibonacci")
DEPENDENCIES = {"binary_search": ("lower_bound",), "count_occurrences": ("lower_bound", "upper_bound")}
SPECS = {
    "lower_bound": "lower_bound(values, target): sorted integer list; return first index whose value >= target, or len(values).",
    "upper_bound": "upper_bound(values, target): sorted integer list; return first index whose value > target, or len(values).",
    "binary_search": "binary_search(values, target): sorted integer list; return FIRST matching index, or -1.",
    "count_occurrences": "count_occurrences(values, target): sorted integer list; return the number of entries equal to target.",
    "gcd": "gcd(a, b): two integers; return nonnegative greatest common divisor; gcd(0, 0) is 0.",
    "fibonacci": "fibonacci(n): nonnegative integer; return F(n), where F(0)=0 and F(1)=1.",
}


@lru_cache(maxsize=1)
def suite_digest():
    root = Path(__file__).resolve().parents[1]
    paths = ("autonomy/tasks.py", "autonomy/verifier.py", "core/ast_validator.py", "sandbox/runner_harness.py")
    return hashlib.sha256(b"".join((root / path).read_bytes() for path in paths)).hexdigest()


@dataclass(frozen=True)
class Task:
    family: str
    tier: int = 1

    def __post_init__(self):
        if self.family not in FAMILIES or type(self.tier) is not int or not 1 <= self.tier <= 3:
            raise ValueError("unsupported task family or tier")

    @property
    def key(self):
        return f"{self.family}:tier{self.tier}"

    @property
    def spec(self):
        return SPECS[self.family] + f" Difficulty tier {self.tier}. Return an integer, do not mutate inputs. Pure functions only; no imports, attributes, annotations, defaults or I/O."

    def public(self):
        if self.family == "gcd":
            return [(0, 0), (12, 18), (-12, 18), (7, 0), (17, 13)]
        if self.family == "fibonacci":
            return [(0,), (1,), (2,), (10,), (20,)]
        return [([], 0), ([1], 1), ([1], 0), ([1, 2, 2, 3], 2), ([-5, -1, 0], -1)]

    def expected(self, cases):
        def answer(args):
            if self.family == "gcd":
                return math.gcd(*args)
            if self.family == "fibonacci":
                a, b = 0, 1
                for _ in range(args[0]):
                    a, b = b, a + b
                return a
            values, target = args
            if self.family == "count_occurrences":
                return sum(value == target for value in values)
            for index, value in enumerate(values):
                if ((self.family == "lower_bound" and value >= target)
                    or (self.family == "upper_bound" and value > target)
                    or (self.family == "binary_search" and value == target)):
                    return index
            return -1 if self.family == "binary_search" else len(values)
        return [answer(case) for case in cases]

    def samples(self, count, seed=None, audit=False):
        rng = random.Random(secrets.randbits(128) if seed is None else seed)
        if self.family == "gcd":
            bound = 10 ** (3 * self.tier + (3 if audit else 0))
            return [(rng.randint(-bound, bound), rng.randint(-bound, bound)) for _ in range(count)]
        if self.family == "fibonacci":
            bound = 40 * self.tier + (80 if audit else 0)
            return [(rng.randrange(bound + 1),) for _ in range(count)]
        max_size = (32, 128, 256)[self.tier - 1]
        bound = 10 ** (self.tier + 1)
        cases = []
        for _ in range(count):
            # Audit deliberately stresses duplicates and tails beyond the search distribution.
            values = sorted(rng.randint(-bound, bound) for _ in range(rng.randrange(max_size)))
            if audit:
                values = sorted((values[:16] * 4) + [-10**20, 10**20])
            target = rng.choice(values) if values and rng.random() < 0.65 else rng.randint(-bound, bound)
            cases.append((values, target))
        return cases

    def properties(self):
        if self.family == "gcd":
            return [(a * k, b * k) for a, b in self.public() for k in (-3, 1, 7)] + [(10**50, 10**25)]
        if self.family == "fibonacci":
            return [(n,) for n in (0, 1, 2, 3, 30, 50, 100, 200)]
        cases = []
        for values, target in self.public() + [([0] * 80, 0), ([-10**100, 0, 10**100], 10**100)]:
            cases.extend([(values, target), ([x + 137 for x in values], target + 137),
                          ([x * 3 for x in values], target * 3), (sorted(-x for x in values), -target)])
        return cases

    def performance(self):
        if self.family == "gcd":
            return [(10**100 - 1, 10**80 - 1)] * 4
        if self.family == "fibonacci":
            return [(200,), (400,), (800,)]
        return [(list(range(10000)), target) for target in (0, 5000, 9999, 10000)]

    def descriptor(self):
        return {"key": self.key, "family": self.family, "tier": self.tier,
                "instruction": self.spec, "suite_version": SUITE_VERSION}


def task_from_key(key):
    family, tier = key.rsplit(":tier", 1)
    return Task(family, int(tier))


def goal_contract(description="algorithms toolkit", tier=2, target=1.0):
    text = description.lower().strip()
    if text in ("algorithms toolkit", "build a reliable algorithms toolkit"):
        families = list(FAMILIES)
    elif text in ("sorted search", "search toolkit"):
        families = list(FAMILIES[:4])
    elif text in ("number theory", "numeric toolkit"):
        families = list(FAMILIES[4:])
    else:
        families = [family for family in FAMILIES if family in text]
        if not families:
            raise ValueError("Unverifiable goal. Use 'algorithms toolkit', 'sorted search', 'number theory', or explicit supported function names.")
    for family in list(families):
        for dependency in DEPENDENCIES.get(family, ()):
            if dependency not in families:
                families.append(dependency)
    families = [family for family in FAMILIES if family in families]
    if type(tier) is not int or not 1 <= tier <= 3 or not math.isfinite(target) or not 0 < target <= 1:
        raise ValueError("tier must be 1..3 and target must be in (0,1]")
    tasks = [Task(family, level).descriptor() for level in range(1, tier + 1) for family in families]
    contract = {"description": description, "tasks": tasks, "target": target,
                "suite_version": SUITE_VERSION, "suite_digest": suite_digest(), "audit_lower_bound": 0.98, "weights": {task["key"]: 1 / len(tasks) for task in tasks}}
    contract["id"] = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()[:24]
    return contract
