"""GEPA-inspired per-case Pareto survival for bounded policy experiments.

Development trials only. This is an adaptation of preserving complementary
specialists, not a reproduction of GEPA's reflective prompt optimizer.
"""


def pareto_order(records, generation):
    """Return fronts preserving per-seed coverage/resource tradeoffs.

    O(p^2*r) time and O(p*r+p^2) space for p policies and r paired trials.
    Caller breaks within-front ties with its existing quality-diversity rule.
    All policies must have exactly the same development trial identities.
    """
    vectors = []
    identities = None
    for record in records:
        rows = [row for row in record["development_rows"] if row.get("generation") == generation]
        rows.sort(key=lambda row: (row["goal"], row["seed"]))
        keys = [(row["goal"], row["seed"]) for row in rows]
        if not keys or len(set(keys)) != len(keys):
            raise ValueError("missing or duplicate development trial")
        if identities is None:
            identities = keys
        elif identities != keys:
            raise ValueError("Pareto selection requires matched development trials")
        # Correctness dominates resource savings, including cheap failed runs.
        correctness = tuple((bool(row["goal_reached"]), bool(row["audit_passed"]), row["coverage"]) for row in rows)
        resources = tuple(value for row in rows for value in (-row["attempts"], -row["container_runs"], -row["model_calls"]))
        vectors.append((correctness, resources))

    def dominates(a, b):
        ac, ar = vectors[a]
        bc, br = vectors[b]
        flat_a = tuple(value for row in ac for value in row)
        flat_b = tuple(value for row in bc for value in row)
        if flat_a != flat_b:
            return all(x >= y for x, y in zip(flat_a, flat_b)) and any(x > y for x, y in zip(flat_a, flat_b))
        return all(x >= y for x, y in zip(ar, br)) and any(x > y for x, y in zip(ar, br))

    edges = [[] for _ in records]
    counts = [0] * len(records)
    for a in range(len(records)):
        for b in range(len(records)):
            if a != b and dominates(a, b):
                edges[a].append(b)
                counts[b] += 1
    front = [i for i, count in enumerate(counts) if count == 0]
    fronts = []
    while front:
        fronts.append([records[i] for i in front])
        following = []
        for a in front:
            for b in edges[a]:
                counts[b] -= 1
                if counts[b] == 0:
                    following.append(b)
        front = following
    return fronts
