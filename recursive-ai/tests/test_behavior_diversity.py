import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from research.behavior_diversity import observe_candidates, read_archive


class ProbeRunner:
    def __init__(self):
        self.container_runs = 0

    def boot(self):
        self.container_runs += 1

    def execute(self, source, cases, entrypoint):
        self.container_runs += 1
        if source == 'error':
            raise RuntimeError('failed candidate')
        self.assert_public(cases)
        return {'outputs': [0, 6, 6, 7, 1], 'steps_per_case': [len(source)] * len(cases)}

    @staticmethod
    def assert_public(cases):
        if cases != [(0, 0), (12, 18), (-12, 18), (7, 0), (17, 13)]:
            raise AssertionError('non-public cases supplied')


class BehaviorDiversityTests(unittest.TestCase):
    def test_equivalent_outputs_distinct_work_and_unobserved(self):
        report = observe_candidates([('gcd:tier1', s) for s in ('a', 'bb', 'error')], ProbeRunner())
        result = report['by_task']['gcd:tier1']
        self.assertEqual(result['distinct_sources'], 3)
        self.assertEqual(result['distinct_outputs'], 1)
        self.assertEqual(result['distinct_work_traces'], 2)
        self.assertEqual(result['unobserved'], 1)
        self.assertFalse(report['automatic_promotion'])
        self.assertEqual(report['container_runs'], 4)

    def test_archive_read_does_not_change_database(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, 'memory.sqlite3')
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE candidate_archive(family,digest,source,report)')
                db.execute('INSERT INTO candidate_archive VALUES (?,?,?,?)',
                           ('gcd', 'hash', 'a', json.dumps({'task': 'gcd:tier1'})))
            before = path.read_bytes()
            self.assertEqual(read_archive(root), ([('gcd:tier1', 'a')], 0))
            self.assertEqual(path.read_bytes(), before)
        with self.assertRaises(ValueError):
            read_archive('unused', limit=65)
