"""Loopback-only manifest-allowlisted server with byte ranges for local video."""
import argparse
import functools
import json
import mimetypes
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


def parse_range(value, size):
    if value is None:
        return 0, size - 1, False
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', value)
    if not match or not size or not any(match.groups()):
        raise ValueError('unsatisfiable range')
    start, end = match.groups()
    if not start:
        length = int(end)
        if length <= 0:
            raise ValueError('unsatisfiable suffix')
        return max(0, size - length), size - 1, True
    start = int(start)
    end = min(int(end), size - 1) if end else size - 1
    if start >= size or end < start:
        raise ValueError('unsatisfiable range')
    return start, end, True


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def __init__(self, *args, root, files, **kwargs):
        self.root, self.files = root, files
        super().__init__(*args, **kwargs)

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, ConnectionAbortedError):
            # A browser may close keep-alive reads during seeks or tab shutdown.
            self.close_connection = True

    def log_message(self, *_):
        pass

    def do_HEAD(self):
        self.respond(False)

    def do_GET(self):
        self.respond(True)

    def respond(self, body):
        name = unquote(urlsplit(self.path).path).lstrip('/') or 'index.html'
        if name not in self.files or '\\' in name:
            self.send_error(404)
            return
        path = self.root / name
        if not path.resolve().is_relative_to(self.root.resolve()) or path.is_symlink() or not path.is_file():
            self.send_error(404)
            return
        size = path.stat().st_size
        try:
            start, end, partial = parse_range(self.headers.get('Range'), size)
        except ValueError:
            self.send_response(416)
            self.send_header('Content-Range', f'bytes */{size}')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        self.send_response(206 if partial else 200)
        self.send_header('Content-Type', mimetypes.guess_type(name)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(max(0, end - start + 1)))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if partial:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        if body:
            try:
                with path.open('rb') as stream:
                    stream.seek(start)
                    remaining = end - start + 1
                    while remaining > 0:
                        data = stream.read(min(1024 * 1024, remaining))
                        if not data:
                            break
                        self.wfile.write(data)
                        remaining -= len(data)
            except (BrokenPipeError, ConnectionResetError):
                pass


def create_server(root, port=0):
    manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
    allowed = {r['path'] for r in manifest['files'] if r['path'] in {'index.html', 'player.css', 'core.js', 'player.js', 'registry.json'} or r['path'].startswith('clips/')}
    return ThreadingHTTPServer(('127.0.0.1', port), functools.partial(Handler, root=root, files=allowed))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('port must be 0..65535')
    server = create_server(Path(__file__).resolve().parent, args.port)
    print(f"Open http://127.0.0.1:{server.server_port}/ in this computer's browser. Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
