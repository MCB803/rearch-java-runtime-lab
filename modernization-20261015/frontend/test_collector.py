#!/usr/bin/env python3
"""The local benchmark collector must reject cross-origin writes and path input."""
from pathlib import Path
from http.client import HTTPConnection
from http.server import HTTPServer
from tempfile import TemporaryDirectory
from threading import Thread
import importlib.util
import json
import unittest

spec = importlib.util.spec_from_file_location('frontend_collector', Path(__file__).with_name('serve.py'))
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)

class CollectorTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name) / 'evidence'
        self.root.mkdir()
        (self.root / 'benchmark.html').write_text('<title>Synthetic fixture</title>')
        collector.ROOT = self.root
        self.server = HTTPServer(('127.0.0.1', 0), collector.Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, body=None, headers=None, method='POST'):
        connection = HTTPConnection('127.0.0.1', self.port, timeout=3)
        values = {'Host': f'127.0.0.1:{self.port}', 'Origin': f'http://127.0.0.1:{self.port}', 'Content-Type': 'application/json'}
        values.update(headers or {})
        payload = json.dumps(body) if isinstance(body, (dict, list)) else body
        connection.request(method, '/' if method == 'GET' else '/result', payload, values)
        response = connection.getresponse()
        status = response.status
        response.read()
        connection.close()
        return status

    def evidence(self, started='../escaped'):
        return {'manifest': {'protocol': 'invoice-dom-v1', 'status': 'completed', 'startedAt': started}, 'samples': []}

    def test_manifest_cannot_control_filename_or_overwrite_first_result(self):
        self.assertEqual(self.request(self.evidence('first')), 201)
        original = (self.root / 'completed.json').read_bytes()
        self.assertEqual(self.request(self.evidence('../../escaped')), 201)
        files = sorted(self.root.glob('*.json'))
        self.assertEqual(len(files), 2)
        self.assertEqual((self.root / 'completed.json').read_bytes(), original)
        self.assertTrue(any(path.name.startswith('run-') for path in files))
        self.assertFalse((Path(self.temp.name) / 'escaped-completed.json').exists())

    def test_rejects_foreign_origin_and_rebinding_host(self):
        for headers in [{'Origin': 'https://attacker.invalid'}, {'Origin': 'null'}, {'Origin': ''}, {'Host': f'attacker.invalid:{self.port}'}]:
            with self.subTest(headers=headers):
                self.assertEqual(self.request(self.evidence(), headers), 403)
        self.assertEqual(list(self.root.glob('*.json')), [])

    def test_rejects_non_json_bad_json_and_oversized_body(self):
        self.assertEqual(self.request(self.evidence(), {'Content-Type': 'text/plain'}), 415)
        self.assertEqual(self.request('{'), 400)
        self.assertEqual(self.request('[]'), 400)
        self.assertEqual(self.request('{}', {'Content-Length': '2000001'}), 400)
        self.assertEqual(list(self.root.glob('*.json')), [])

    def test_rejects_invalid_protocol_or_status(self):
        for field, value in [('protocol', 'unknown'), ('status', '../../escape')]:
            body = self.evidence()
            body['manifest'][field] = value
            self.assertEqual(self.request(body), 400)

    def test_get_is_limited_to_loopback_host(self):
        self.assertEqual(self.request(method='GET'), 200)
        self.assertEqual(self.request(headers={'Host': 'attacker.invalid'}, method='GET'), 403)

if __name__ == '__main__':
    unittest.main()
