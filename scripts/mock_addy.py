#!/usr/bin/env python3
"""
Simple mock Addy HTTP server for local testing.
POST /v1/messages expects JSON {from,to,subject,html}
It writes the payload to data/addy_mock.json and returns 200.
"""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

DATA_DIR = Path('data')
DATA_DIR.mkdir(exist_ok=True)

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path.startswith('/v1/messages'):
            length = int(self.headers.get('content-length', '0'))
            body = self.rfile.read(length) if length else b''
            try:
                payload = json.loads(body.decode('utf8'))
            except Exception:
                payload = {'raw': body.decode('utf8', errors='replace')}
            (DATA_DIR / 'addy_mock.json').write_text(json.dumps({'path': self.path, 'headers': dict(self.headers), 'payload': payload}, indent=2), encoding='utf8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"ok":true}\n')
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', 8025), Handler)
    print('Mock Addy server running on http://127.0.0.1:8025')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
        print('Server stopped')
