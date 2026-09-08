"""Finite program sketches plus optional model proposals and reusable archived programs."""
import ast
import hashlib
from synthesizer.generator import CandidateSynthesizer
from synthesizer.mutator import mutate_ast
from synthesizer.recombinator import recombine_ast


BOUND = """def lower_bound(values, target):
    low = 0
    high = len(values)
    while low < high:
        mid = (low + high) // 2
        if values[mid] < target:
            low = mid + 1
        else:
            high = mid
    return low
"""
UPPER = BOUND.replace("lower_bound", "upper_bound").replace("values[mid] < target", "values[mid] <= target")
SKETCHES = {
    "lower_bound": BOUND,
    "upper_bound": UPPER,
    "binary_search": BOUND + """
def binary_search(values, target):
    index = lower_bound(values, target)
    if index < len(values) and values[index] == target:
        return index
    return -1
""",
    "count_occurrences": BOUND + UPPER + """
def count_occurrences(values, target):
    return upper_bound(values, target) - lower_bound(values, target)
""",
    "gcd": """def gcd(a, b):
    a = abs(a)
    b = abs(b)
    while b:
        a, b = b, a % b
    return a
""",
    "fibonacci": """def fibonacci(n):
    a = 0
    b = 1
    for index in range(n):
        a, b = b, a + b
    return a
""",
}


def normalized_digest(source):
    return hashlib.sha256(ast.dump(ast.parse(source), include_attributes=False).encode()).hexdigest()


def transfer(task, active):
    if task.family not in ("binary_search", "count_occurrences"):
        return None
    helpers = {}
    for skill in active.values():
        for node in ast.parse(skill["source"]).body:
            if isinstance(node, ast.FunctionDef) and node.name in ("lower_bound", "upper_bound"):
                helpers[node.name] = ast.unparse(node) + "\n"
    required = ("lower_bound",) if task.family == "binary_search" else ("lower_bound", "upper_bound")
    if not all(name in helpers for name in required):
        return None
    target = ast.parse(SKETCHES[task.family]).body[-1]
    return "\n".join(helpers[name] for name in required) + "\n" + ast.unparse(target) + "\n"


class SearchEngine:
    def __init__(self, provider="search", model_calls=0, max_model_calls=12):
        self.provider = provider
        self.model_calls = model_calls
        self.max_model_calls = max_model_calls
        self.model = CandidateSynthesizer("api")

    def propose(self, task, operator, parents, active, attempt, remaining_seconds):
        self.model.last_usage = None
        reused = [value for key, value in active.items() if key.startswith(task.family + ":tier")]
        if reused:
            return reused[-1]["source"], "curriculum_transfer"
        sources = [parent["source"] for parent in parents]
        if self.provider == "api" and operator in ("direct", "repair"):
            if self.model_calls >= self.max_model_calls:
                raise RuntimeError("model call budget exhausted")
            self.model_calls += 1
            self.model.timeout = min(60, max(0.1, remaining_seconds))
            context = {"specification": task.spec, "public_cases": task.public(),
                       "sources": sources[:3], "prerequisite_sources": [value["source"] for value in active.values()][:4],
                       "recent_failed_gates": [parent.get("quality", 0) for parent in parents[:3]]}
            return self.model.generate(operator, context, attempt), "model"
        if operator == "repair" and sources:
            tree = ast.parse(sources[0])
            for node in ast.walk(tree):
                if isinstance(node, ast.Return) and isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Add) and isinstance(node.value.right, ast.Constant) and node.value.right.value == 1:
                    node.value = node.value.left
                    return ast.unparse(ast.fix_missing_locations(tree)) + "\n", "archive_return_repair"
        if operator == "mutation" and sources:
            return mutate_ast(sources[0], attempt), "ast_mutation"
        if operator == "crossover" and len(sources) > 1:
            return recombine_ast(sources[0], sources[1], attempt) or sources[0], "ast_crossover"
        composed = transfer(task, active)
        if composed:
            return composed, "skill_composition"
        # Search starts from an imperfect sketch and repairs from executable feedback.
        # The finite sketch space is disclosed; this is not novel algorithm discovery.
        source = SKETCHES[task.family]
        if operator == "direct" and attempt == 1:
            tree = ast.parse(source)
            function = tree.body[-1]
            final_return = function.body[-1]
            if isinstance(final_return, ast.Return):
                final_return.value = ast.BinOp(left=final_return.value, op=ast.Add(), right=ast.Constant(value=1))
            source = ast.unparse(ast.fix_missing_locations(tree)) + "\n"
        return source, "sketch_search"
