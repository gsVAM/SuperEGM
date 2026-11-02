"""AgentCore controller: launch a detached worker and keep its session busy."""
import json
import os
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from protocol import prefixes

WORKERS = {}
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def respond(self, code, value):
        data = json.dumps(value).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path != '/ping':
            return self.respond(404, {'error': 'not found'})
        with LOCK:
            busy = any(p.poll() is None for _, p in WORKERS.values())
        self.respond(200, {'status': 'HealthyBusy' if busy else 'Healthy'})

    def read_body(self):
        if self.headers.get('Transfer-Encoding', '').lower() != 'chunked':
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 8192:
                raise ValueError('Invalid request length')
            return self.rfile.read(length)
        data = bytearray()
        while True:
            size = int(self.rfile.readline(128).split(b';', 1)[0].strip(), 16)
            if size < 0 or len(data) + size > 8192:
                raise ValueError('Invalid request length')
            if not size:
                return data
            data.extend(self.rfile.read(size))
            if self.rfile.read(2) != b'\r\n':
                raise ValueError('Invalid chunk framing')

    def do_POST(self):
        if self.path != '/invocations':
            return self.respond(404, {'error': 'not found'})
        try:
            request = json.loads(self.read_body())
            if request.get('action') == 'probe':
                return self.respond(200, {'protocol': 'livebuilders-s3-v1', 'uid': os.getuid()})
            if request.get('action') != 'start':
                raise ValueError('Unknown action')
            owner, run_id, sha = request['owner'], request['run_id'], request['request_sha256']
            prefixes(owner, run_id)
            if not re.fullmatch('[0-9a-f]{64}', sha):
                raise ValueError('Invalid request hash')
            with LOCK:
                identity = (owner, run_id)
                if identity in WORKERS:
                    if WORKERS[identity][0] != sha:
                        raise ValueError('Run already bound to another request')
                    return self.respond(200, {'accepted': True, 'duplicate': True, 'run_id': run_id})
                root = Path('/mnt/workspace/livebuilders') / owner / run_id
                root.mkdir(parents=True, exist_ok=True, mode=0o700)
                with (root / 'worker.log').open('ab') as log:
                    process = subprocess.Popen(['python3', str(Path(__file__).with_name('worker.py')), '--bucket', os.environ['LB_BUCKET'], '--region', os.environ['AWS_REGION'], '--owner', owner, '--run-id', run_id, '--request-sha256', sha, '--root', str(root)], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                WORKERS[identity] = (sha, process)
            self.respond(202, {'accepted': True, 'duplicate': False, 'run_id': run_id})
        except (KeyError, TypeError, ValueError):
            self.respond(400, {'error': 'invalid request'})


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
