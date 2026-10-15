import copy
import json
import pathlib
import sqlite3
import unittest
from summarize import build

HERE = pathlib.Path(__file__).resolve().parent

class PublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = [json.loads(x) for x in (HERE / 'raw.jsonl').read_text().splitlines()]

    def test_raw_rebuild_matches_published(self):
        self.assertEqual(build(copy.deepcopy(self.rows)), json.loads((HERE / 'summary.json').read_text()))

    def test_missing_run_is_rejected(self):
        rows = copy.deepcopy(self.rows)
        rows.pop(next(i for i, r in enumerate(rows) if r['kind'] == 'sample' and not r['warmup']))
        with self.assertRaises(AssertionError): build(rows)

    def test_wrong_output_is_rejected(self):
        rows = copy.deepcopy(self.rows)
        next(r for r in rows if r['kind'] == 'sample' and not r['warmup'])['outputSha256'] = 'wrong'
        with self.assertRaises(AssertionError): build(rows)

    def test_tampered_runtime_data_not_confused_with_version_comparison(self):
        result = build(copy.deepcopy(self.rows))
        self.assertEqual(result['environment']['phpVersion'], '8.4.26')
        self.assertEqual(result['environment']['sqliteVersion'], '3.46.1')
        self.assertIn('not a PHP/DB version comparison', result['environment']['scope'])

    def test_security_controls_include_authorization_failure(self):
        result = build(copy.deepcopy(self.rows))
        summary = result['security']['summary']
        self.assertEqual(summary['prepared-only-control']['adversarialPassed'], 2)
        self.assertEqual(summary['prepared-and-scoped']['passed'], 6)
        self.assertEqual(summary['legacy-concatenation']['adversarialPassed'], 0)

    def test_security_replay_with_independent_driver(self):
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE invoices(id INTEGER PRIMARY KEY, tenant_id INTEGER, reference TEXT)')
        for tenant in (1, 2):
            for n in range(1, 6):
                db.execute('INSERT INTO invoices VALUES(?,?,?)', ((tenant - 1) * 6 + n, tenant, f'T{tenant}-{n:03d}'))
            db.execute('INSERT INTO invoices VALUES(?,?,?)', (tenant * 6, tenant, f"T{tenant}-O'Brian"))
        raw = next(r for r in self.rows if r['kind'] == 'security')
        for case in raw['cases']:
            for arm, observed in case['arms'].items():
                error = False
                result = []
                try:
                    if arm == 'legacy-concatenation':
                        result = db.execute("SELECT id, tenant_id FROM invoices WHERE reference='" + case['input'] + "' ORDER BY id").fetchall()
                    elif arm == 'prepared-only-control':
                        result = db.execute('SELECT id, tenant_id FROM invoices WHERE reference=? ORDER BY id', (case['input'],)).fetchall()
                    else:
                        result = db.execute('SELECT id, tenant_id FROM invoices WHERE tenant_id=? AND reference=? ORDER BY id', (1, case['input'])).fetchall()
                except sqlite3.OperationalError:
                    error = True
                self.assertEqual(error, observed['queryError'], (case['id'], arm))
                self.assertEqual([r[0] for r in result], observed['rowIds'], (case['id'], arm))
                self.assertEqual(sum(r[1] != 1 for r in result), observed['otherTenantRows'], (case['id'], arm))
        db.close()

if __name__ == '__main__': unittest.main()
