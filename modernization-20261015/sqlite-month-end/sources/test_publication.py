import copy
import hashlib
import json
import os
import unittest
from pathlib import Path
from summarize import build

HERE=Path(__file__).resolve().parent
DATA=Path(os.environ.get('REARCH_SQLITE_MONTH_END_DATA',HERE.parents[3]/'public/labs/modernization-20261015/sqlite-month-end'))

class PublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=[json.loads(line) for line in (DATA/'raw.jsonl').read_text().splitlines()]
        cls.protocol=json.loads((HERE/'protocol.json').read_text())
    def test_summary_exact(self):
        self.assertEqual(build(self.raw,self.protocol),json.loads((DATA/'summary.json').read_text()))
    def test_missing_run_rejected(self):
        altered=copy.deepcopy(self.raw);altered.pop(next(i for i,r in enumerate(altered) if r['kind']=='sample'))
        with self.assertRaises(AssertionError):build(altered,self.protocol)
    def test_changed_row_rejected(self):
        altered=copy.deepcopy(self.raw);next(r for r in altered if r['kind']=='sample')['rows'][0][1]+=1
        with self.assertRaises(AssertionError):build(altered,self.protocol)
    def test_all_sources_and_raw_hashes(self):
        for name,digest in json.loads((DATA/'SHA256.json').read_text()).items():self.assertEqual(hashlib.sha256((DATA/name).read_bytes()).hexdigest(),digest,name)
        manifest=json.loads((DATA/'manifest.json').read_text());self.assertEqual(manifest['status'],'completed')
        for name,digest in manifest['sourceSha256'].items():self.assertEqual(hashlib.sha256((HERE/name).read_bytes()).hexdigest(),digest,name)
    def test_independent_python_business_oracle(self):
        # Recompute once in linear time, outside performance timings.
        for fixture in (r for r in self.raw if r['kind']=='fixture'):
            totals=[0]*500
            for i in range(fixture['size']):
                if (i+i//500)%4:totals[(i*73)%500]+=1000+(i*7919)%100000
            self.assertEqual([[i+1,v] for i,v in enumerate(totals)],fixture['expectedRows'])

if __name__=='__main__':unittest.main()
