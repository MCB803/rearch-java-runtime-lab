#!/usr/bin/env python3
"""Serve only this synthetic fixture; record its visible Run-button result locally."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from datetime import datetime, timezone
import json
import uuid

ROOT = Path(__file__).resolve().parent

class Handler(BaseHTTPRequestHandler):
    def local_request(self):
        port = self.server.server_address[1]
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        if self.headers.get('Host') not in hosts:
            self.send_error(403, 'Loopback host required')
            return False
        origin = self.headers.get('Origin')
        if (self.command == 'POST' or origin is not None) and origin != f'http://{self.headers.get("Host")}':
            self.send_error(403, 'Same-origin loopback request required')
            return False
        return True

    def do_GET(self):
        if not self.local_request():
            return
        if self.path != '/':
            self.send_error(404)
            return
        content = (ROOT / 'benchmark.html').read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        if not self.local_request():
            return
        if self.path != '/result':
            self.send_error(404)
            return
        if self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
            self.send_error(415, 'JSON content type required')
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
        except ValueError:
            self.send_error(400, 'Invalid body length')
            return
        if not 0 < length < 2_000_000:
            self.send_error(400)
            return
        try:
            value = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            self.send_error(400, 'Invalid JSON')
            return
        if not isinstance(value, dict) or not isinstance(value.get('manifest'), dict) or value['manifest'].get('protocol') != 'invoice-dom-v1' or value['manifest'].get('status') not in {'completed', 'failed'} or not isinstance(value.get('samples'), list):
            self.send_error(400)
            return
        name = 'completed.json' if value['manifest']['status'] == 'completed' else 'failed.json'
        root = ROOT.resolve()
        path = root / name
        if path.exists():
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            name = f'run-{timestamp}-{uuid.uuid4().hex}-{name}'
            path = root / name
        if path.resolve().parent != root:
            self.send_error(400, 'Invalid evidence destination')
            return
        try:
            with path.open('x', encoding='utf-8') as handle:
                handle.write(json.dumps(value, indent=2) + '\n')
        except FileExistsError:
            self.send_error(409, 'Evidence destination already exists')
            return
        print(f'Saved {name}: {len(value["samples"])} samples', flush=True)
        self.send_response(201)
        self.end_headers()
        self.wfile.write(b'OK')

if __name__ == '__main__':
    HTTPServer(('127.0.0.1', 4387), Handler).serve_forever()
