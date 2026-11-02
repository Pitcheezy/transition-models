"""Loopback-only manifest-allowlisted server with byte ranges for local video."""
import argparse
import functools
import json
import re
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

DEFAULT_PORT = 8741
# Fixed table for the only extensions the allowlist serves. mimetypes is not used:
# on Windows it reads HKCR and a '.js => text/plain' value plus nosniff would stop the player.
CONTENT_TYPES = {'.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
                 '.js': 'text/javascript; charset=utf-8', '.json': 'application/json', '.mp4': 'video/mp4'}


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


def content_type(name):
    return CONTENT_TYPES.get(PurePosixPath(name).suffix.lower())


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
        if name not in self.files or '\\' in name or content_type(name) is None:
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
        self.send_header('Content-Type', content_type(name))
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


class Server(ThreadingHTTPServer):
    # Windows: SO_REUSEADDR would let a fixed port bind over a server already listening there, so bind exclusively.
    # macOS/Linux: SO_REUSEADDR never allows that, and without it an immediate restart loses the port to TIME_WAIT.
    allow_reuse_address = not hasattr(socket, 'SO_EXCLUSIVEADDRUSE')

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def create_server(root, port=DEFAULT_PORT):
    manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
    allowed = {r['path'] for r in manifest['files'] if r['path'] in {'index.html', 'player.css', 'core.js', 'player.js', 'registry.json'} or r['path'].startswith('clips/')}
    return Server(('127.0.0.1', port), functools.partial(Handler, root=root, files=allowed))


def start_server(root, port, explicit):
    """Bind the requested port; a busy default port falls back to a free one with a message. An explicit --port never falls back."""
    try:
        return create_server(root, port), None
    except OSError as error:
        if explicit or port == 0:
            raise OSError(f'port {port} is already in use (another serve.py or program). Close it or omit --port.') from error
        server = create_server(root, 0)
        return server, (f'Port {port} is busy (another serve.py or program is using it); using port {server.server_port} instead. '
                        'Tabs and bookmarks that still point at the old port must be reopened with the address below.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=None, help=f'fixed port (default {DEFAULT_PORT}; 0 = any free port)')
    args = parser.parse_args()
    requested = DEFAULT_PORT if args.port is None else args.port
    if not 0 <= requested <= 65535:
        parser.error('port must be 0..65535')
    try:
        server, message = start_server(Path(__file__).resolve().parent, requested, args.port is not None)
    except OSError as error:
        raise SystemExit(str(error)) from error
    if message:
        print(message, flush=True)
    print(f"Open http://127.0.0.1:{server.server_port}/ in this computer's browser. Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
