import hashlib
import json
from memory.skill_store import MemoryEngine

OPERATORS = ("direct", "repair", "mutation", "crossover")


class ResearchMemory(MemoryEngine):
    def __init__(self, root):
        super().__init__(root)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS research_goals(id TEXT PRIMARY KEY, contract TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'pending', summary TEXT);
            CREATE TABLE IF NOT EXISTS candidate_archive(family TEXT, digest TEXT, source TEXT NOT NULL, quality REAL NOT NULL, report TEXT NOT NULL, parent TEXT, PRIMARY KEY(family,digest));
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

    def archive(self, task, source, report, parent, operator, reward, seconds):
        digest = hashlib.sha256(source.encode()).hexdigest()
        quality = sum(gate["passed"] for gate in report.get("gates", [])) / 10
        self.db.execute("INSERT INTO candidate_archive VALUES (?,?,?,?,?,?) ON CONFLICT(family,digest) DO UPDATE SET quality=excluded.quality,report=excluded.report", (task.family, digest, source, quality, json.dumps(report), parent))
        self.db.execute("INSERT INTO operator_evidence VALUES (?,?,1,?,?) ON CONFLICT(family,operator) DO UPDATE SET attempts=attempts+1,reward=reward+excluded.reward,seconds=seconds+excluded.seconds", (task.family, operator, reward, seconds))
        return digest

    def parents(self, family):
        # Quality plus inverse size retains useful, cheap stepping stones.
        rows = self.db.execute("SELECT digest,source,quality FROM candidate_archive WHERE family=? ORDER BY quality DESC,length(source),digest LIMIT 8", (family,)).fetchall()
        return [{"digest": digest, "source": source, "quality": quality} for digest, source, quality in rows]

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
