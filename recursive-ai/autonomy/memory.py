import ast
import hashlib
import json
from collections import Counter
from memory.skill_store import MemoryEngine

OPERATORS = ("direct", "repair", "mutation", "crossover")


def _structure_profile(source):
    """Normalized AST-node histogram used only for archive diversity ranking."""
    counts = Counter(type(node).__name__ for node in ast.walk(ast.parse(source)))
    total = sum(counts.values()) or 1
    return {name: count / total for name, count in counts.items()}


def _structure_distance(left, right):
    keys = set(left) | set(right)
    # L1 distance between normalized histograms is in [0,2].
    return 0.5 * sum(abs(left.get(key, 0.0) - right.get(key, 0.0)) for key in keys)


class ResearchMemory(MemoryEngine):
    def __init__(self, root):
        super().__init__(root)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS research_goals(id TEXT PRIMARY KEY, contract TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'pending', summary TEXT);
            CREATE TABLE IF NOT EXISTS candidate_archive(family TEXT, digest TEXT, source TEXT NOT NULL, quality REAL NOT NULL, report TEXT NOT NULL, parent TEXT, PRIMARY KEY(family,digest));
            CREATE TABLE IF NOT EXISTS candidate_lineage(
                family TEXT NOT NULL,
                child_digest TEXT NOT NULL,
                parent_digest TEXT NOT NULL,
                operator TEXT NOT NULL,
                origin TEXT NOT NULL,
                PRIMARY KEY(child_digest,parent_digest,operator,origin)
            );
            CREATE TABLE IF NOT EXISTS operator_evidence(family TEXT, operator TEXT, attempts INTEGER NOT NULL, reward REAL NOT NULL, seconds REAL NOT NULL, PRIMARY KEY(family,operator));
            CREATE TABLE IF NOT EXISTS learning_policies(id INTEGER PRIMARY KEY, digest TEXT NOT NULL, source TEXT NOT NULL, evidence TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS model_reservations(id INTEGER PRIMARY KEY, goal TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS task_attempts(goal TEXT, task TEXT, attempts INTEGER NOT NULL, PRIMARY KEY(goal,task));
        """)

    def register(self, contract):
        self.db.execute("INSERT OR IGNORE INTO research_goals(id,contract) VALUES (?,?)", (contract["id"], json.dumps(contract, sort_keys=True)))

    def reserve_attempt(self, goal_id, task_key, limit):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            cursor = self.db.execute("UPDATE research_goals SET attempts=attempts+1,status='running' WHERE id=? AND attempts<?", (goal_id, limit))
            if cursor.rowcount != 1:
                raise RuntimeError("attempt budget exhausted")
            self.db.execute("INSERT INTO task_attempts VALUES (?,?,1) ON CONFLICT(goal,task) DO UPDATE SET attempts=attempts+1", (goal_id, task_key))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        return self.db.execute("SELECT attempts FROM research_goals WHERE id=?", (goal_id,)).fetchone()[0]

    def attempts(self, goal_id):
        return dict(self.db.execute("SELECT task,attempts FROM task_attempts WHERE goal=?", (goal_id,)))

    def operators(self, family):
        evidence = {op: (n, reward, seconds) for op, n, reward, seconds in self.db.execute("SELECT operator,attempts,reward,seconds FROM operator_evidence WHERE family=?", (family,))}
        return [evidence.get(operator, (0, 0.0, 0.0)) for operator in OPERATORS]

    def global_operators(self):
        """Aggregate learned operator outcomes without exporting skills, source, or checkpoints."""
        evidence = {
            op: (attempts, reward, seconds)
            for op, attempts, reward, seconds in self.db.execute(
                "SELECT operator,sum(attempts),sum(reward),sum(seconds) FROM operator_evidence GROUP BY operator"
            )
        }
        return [evidence.get(operator, (0, 0.0, 0.0)) for operator in OPERATORS]

    def archive(self, task, source, report, parent, operator, reward, seconds,
                candidate_parents=(), origin="unknown"):
        digest = hashlib.sha256(source.encode()).hexdigest()
        quality = sum(gate["passed"] for gate in report.get("gates", [])) / 10
        self.db.execute(
            "INSERT INTO candidate_archive VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(family,digest) DO UPDATE SET quality=excluded.quality,report=excluded.report",
            (task.family, digest, source, quality, json.dumps(report), parent),
        )
        self.db.execute(
            "INSERT INTO operator_evidence VALUES (?,?,1,?,?) "
            "ON CONFLICT(family,operator) DO UPDATE SET attempts=attempts+1,reward=reward+excluded.reward,seconds=seconds+excluded.seconds",
            (task.family, operator, reward, seconds),
        )
        for parent_digest in dict.fromkeys(candidate_parents or ()):
            if isinstance(parent_digest, str) and parent_digest and parent_digest != digest:
                self.db.execute(
                    "INSERT OR IGNORE INTO candidate_lineage VALUES (?,?,?,?,?)",
                    (task.family, digest, parent_digest, str(operator), str(origin)),
                )
        return digest

    def parents(self, family, limit=8):
        """Select high-quality parents while retaining structural diversity.

        The archive is bounded to the 64 best stored candidates before diversity
        scoring, keeping selection deterministic and cheap. Candidate code is
        parsed but never executed on the host.
        """
        if type(limit) is not int or not 1 <= limit <= 16:
            raise ValueError("parent limit must be in [1,16]")
        rows = self.db.execute(
            "SELECT digest,source,quality FROM candidate_archive "
            "WHERE family=? ORDER BY quality DESC,length(source),digest LIMIT 64",
            (family,),
        ).fetchall()
        if not rows:
            return []

        pool = []
        for digest, source, quality in rows:
            try:
                profile = _structure_profile(source)
            except SyntaxError:
                # Keep malformed attempts in the archive for failure memory, but
                # never feed unparsable code back into mutation or crossover.
                continue
            pool.append({
                "digest": digest,
                "source": source,
                "quality": float(quality),
                "_profile": profile,
            })

        selected = [pool.pop(0)]
        while pool and len(selected) < limit:
            def score(candidate):
                novelty = min(
                    _structure_distance(candidate["_profile"], item["_profile"])
                    for item in selected
                )
                size_score = 1.0 / (1.0 + len(candidate["source"]) / 1000.0)
                combined = 0.70 * candidate["quality"] + 0.25 * novelty + 0.05 * size_score
                return (combined, candidate["quality"], -len(candidate["source"]), candidate["digest"])

            choice = max(pool, key=score)
            pool.remove(choice)
            selected.append(choice)

        return [
            {"digest": item["digest"], "source": item["source"], "quality": item["quality"]}
            for item in selected
        ]

    def lineage(self, family=None):
        if family is None:
            rows = self.db.execute(
                "SELECT family,child_digest,parent_digest,operator,origin "
                "FROM candidate_lineage ORDER BY family,child_digest,parent_digest"
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT family,child_digest,parent_digest,operator,origin "
                "FROM candidate_lineage WHERE family=? ORDER BY child_digest,parent_digest",
                (family,),
            ).fetchall()
        return [
            {
                "family": row[0],
                "child_digest": row[1],
                "parent_digest": row[2],
                "operator": row[3],
                "origin": row[4],
            }
            for row in rows
        ]

    def save_policy(self, source, evidence):
        digest = hashlib.sha256(source.encode()).hexdigest()
        self.db.execute("INSERT INTO learning_policies(digest,source,evidence) VALUES (?,?,?)", (digest, source, json.dumps(evidence)))
        return digest

    def finish(self, goal_id, summary):
        self.db.execute("UPDATE research_goals SET status=?,summary=? WHERE id=?", (summary["status"], json.dumps(summary, sort_keys=True), goal_id))
        self.event({"goal_id": goal_id, "summary": summary})

    def reserve_model_call(self, goal_id, limit):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            count = self.db.execute("SELECT count(*) FROM model_reservations WHERE goal=?", (goal_id,)).fetchone()[0]
            if count >= limit:
                raise RuntimeError("model call budget exhausted")
            self.db.execute("INSERT INTO model_reservations(goal) VALUES (?)", (goal_id,))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
