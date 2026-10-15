#!/usr/bin/env python3
"""Portable reproduction must stay local and preserve published evidence."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent

class ReproductionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name).resolve()
        self.package = self.directory / 'standalone-clone' / 'frontend'
        self.package.mkdir(parents=True)
        for source in ROOT.iterdir():
            if source.is_file():
                shutil.copy2(source, self.package / source.name)
        self.before = {source.name: source.read_bytes() for source in self.package.iterdir()}

    def run_helper(self, *arguments):
        return subprocess.run([sys.executable, str(self.package / 'summarize.py'), *map(str, arguments)], cwd=self.directory, capture_output=True, text=True)

    def test_default_output_is_local_and_reproduces_frozen_evidence(self):
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        output = self.package / 'reproduced'
        self.assertEqual(Path(json.loads(result.stdout)['output']), output)
        for name in ['completed.json', 'summary.json', 'raw.csv', 'benchmark.html']:
            self.assertEqual((output / name).read_bytes(), self.before[name])
        hashes = json.loads((output / 'SHA256.json').read_text())
        self.assertEqual(set(hashes), {file.name for file in output.iterdir()} - {'SHA256.json'})
        for name, expected in hashes.items():
            self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), expected)
        for name, original in self.before.items():
            self.assertEqual((self.package / name).read_bytes(), original)
        self.assertEqual(set(self.directory.iterdir()), {self.package.parent})

    def test_input_selects_a_new_collector_run_without_overwriting_original(self):
        value = json.loads(self.before['completed.json'])
        value['manifest']['startedAt'] = 'local-reproduction-test'
        chosen = self.package / 'run-new-completed.json'
        chosen.write_text(json.dumps(value))
        output = self.directory / 'selected-run'
        result = self.run_helper('--input', chosen, '--output', output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((output / 'completed.json').read_bytes(), chosen.read_bytes())
        self.assertEqual(json.loads((output / 'summary.json').read_text())['manifest']['startedAt'], 'local-reproduction-test')
        self.assertEqual((self.package / 'completed.json').read_bytes(), self.before['completed.json'])

    def test_conflicting_output_is_rejected_before_any_file_is_written(self):
        output = self.directory / 'existing-output'
        output.mkdir()
        (output / 'summary.json').write_text('preserve this prior result')
        result = self.run_helper('--output', output)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((output / 'summary.json').read_text(), 'preserve this prior result')
        self.assertEqual([file.name for file in output.iterdir()], ['summary.json'])

    def test_invalid_measurement_creates_no_output(self):
        value = json.loads(self.before['completed.json'])
        value['samples'][0]['checksum'] = 'invalid'
        chosen = self.directory / 'invalid.json'
        chosen.write_text(json.dumps(value))
        output = self.directory / 'invalid-output'
        result = self.run_helper('--input', chosen, '--output', output)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

if __name__ == '__main__':
    unittest.main()
