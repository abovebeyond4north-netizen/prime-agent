import math
from autonomy.tasks import DEPENDENCIES, SUITE_VERSION, Task, task_from_key, suite_digest


def certified(active):
    return {key: value for key, value in active.items()
            if value.get("report", {}).get("suite_version") == SUITE_VERSION
            and value["report"].get("suite_digest") == suite_digest()
            and value["report"].get("task") == key
            and value["report"].get("passed") is True
            and [gate.get("number") for gate in value["report"].get("gates", [])] == list(range(1, 11))
            and all(gate.get("passed") is True for gate in value["report"]["gates"])}


def coverage(contract, active):
    verified = certified(active)
    return min(1.0, math.fsum(weight for key, weight in contract["weights"].items() if key in verified))


def next_task(contract, active, attempts):
    verified = certified(active)
    eligible = []
    for descriptor in contract["tasks"]:
        task = task_from_key(descriptor["key"])
        if task.key in verified:
            continue
        if task.tier > 1 and Task(task.family, task.tier - 1).key not in verified:
            continue
        if any(Task(dependency, 1).key not in verified for dependency in DEPENDENCIES.get(task.family, ())):
            continue
        eligible.append(task)
    if not eligible:
        return None
    # Breadth and prerequisites before difficulty escalation; rotate after failed attempts.
    return min(eligible, key=lambda task: (task.tier, attempts.get(task.key, 0), task.key))
