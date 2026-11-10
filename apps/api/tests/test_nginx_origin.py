"""Exercise the shipped proxy with a real nginx binary (NGINX_BINARY)."""
import http.server
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.request

from starlette.requests import Request

from app.config import settings
from app.core.public_origin import public_origin


@unittest.skipUnless(os.environ.get('NGINX_BINARY') or shutil.which('nginx'), 'requires a local nginx binary')
class NginxOriginTests(unittest.TestCase):
    def test_proxy_preserves_allowed_authority_and_ignores_untrusted_hosts(self):
        class Upstream(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                request = Request({'type': 'http', 'scheme': 'http', 'server': ('127.0.0.1', 8000),
                                   'path': self.path, 'query_string': b'',
                                   'headers': [(k.lower().encode(), v.encode()) for k, v in self.headers.items()]})
                body = json.dumps({'host': self.headers.get('Host'), 'origin': public_origin(request)}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        binary = os.environ.get('NGINX_BINARY') or shutil.which('nginx')
        source = Path(__file__).resolve().parents[3] / 'docker/nginx/nginx.conf'
        upstream = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
        thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(upstream.server_close)
        self.addCleanup(upstream.shutdown)
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        with tempfile.TemporaryDirectory(prefix='ainadev-nginx-origin-') as directory:
            base = Path(directory).resolve()
            self.assertTrue(base.is_relative_to(Path(tempfile.gettempdir()).resolve()))
            (base / 'logs').mkdir()
            (base / 'temp').mkdir()
            config = source.read_text(encoding='utf-8-sig')
            config = config.replace('worker_processes auto;', 'worker_processes 1;')
            config = config.replace('include /etc/nginx/mime.types;', 'types { text/plain txt; }')
            config = config.replace('listen 80;', f'listen 127.0.0.1:{port};')
            config = config.replace('server web:3000;', f'server 127.0.0.1:{upstream.server_port};')
            config = config.replace('server api:8000;', f'server 127.0.0.1:{upstream.server_port};')
            (base / 'probe.conf').write_text('daemon off;\nmaster_process off;\n' + config, encoding='utf-8')
            prefix = base.as_posix() + '/'
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            process = subprocess.Popen([binary, '-p', prefix, '-c', 'probe.conf'], cwd=base,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
            try:
                deadline = time.monotonic() + 10
                while True:
                    try:
                        with socket.create_connection(('127.0.0.1', port), timeout=.2):
                            break
                    except OSError:
                        if process.poll() is not None or time.monotonic() > deadline:
                            self.fail((base / 'logs/error.log').read_text(errors='replace'))
                        time.sleep(.05)
                with patch.object(settings, 'public_base_url', 'http://primary.example'), \
                     patch.object(settings, 'public_allowed_origins', 'http://alt.example:8090'):
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    for path in ['/', '/api/origin-probe', '/mcp']:
                        request = urllib.request.Request(f'http://127.0.0.1:{port}{path}', headers={
                            'Host': 'alt.example:8090', 'X-Forwarded-Host': 'evil.example'})
                        with opener.open(request, timeout=5) as response:
                            value = json.load(response)
                        self.assertEqual(value, {'host': 'alt.example:8090', 'origin': 'http://alt.example:8090'})
                    request = urllib.request.Request(f'http://127.0.0.1:{port}/api/origin-probe', headers={'Host': 'evil.example:8090'})
                    with opener.open(request, timeout=5) as response:
                        self.assertEqual(json.load(response)['origin'], 'http://primary.example')
            finally:
                process.terminate()
                process.wait(timeout=5)
