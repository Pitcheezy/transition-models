import argparse
import datetime as dt
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import ssl
import time
from urllib.parse import urlsplit

STATIC_PINS = {
 '/': (659, '85616c4b2f49c5f9f0252bc9a687606fbbe6ce2e54253424bc956803db5a4289'),
 '/favicon.svg': (249, 'bbfd72e5d077bd545b2cf568e5267c6637598d5253746f5b395e0d5f3fb144d9'),
 '/assets/index-X1sSTTQ4.js': (300041, 'e46d431a7495bf58efd0084b20af87642fea8e6544cf3ac76ef278223621c30c'),
 '/assets/index-ks_hu7Ji.css': (118449, '292dd392a798d3ee52bd752857edeba50810f19eda4bbf234d4399b106e3bfc0'),
 '/collection-settings.json': (108, '90c09614d495e310c08ba9f7a5e89a32ff6542306ffdfd1e1b9acf1d9c2a7eb3'),
}
MAX_BODY = 1024 * 1024
INDEX_SHA = '85616c4b2f49c5f9f0252bc9a687606fbbe6ce2e54253424bc956803db5a4289'

class CheckError(Exception):
    pass

def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def prepare(manifest, code):
    if not isinstance(manifest, dict) or manifest.get('ready_confirmation') is not True:
        raise CheckError('not_ready')
    origin = manifest.get('origin')
    if not isinstance(origin, str):
        raise CheckError('origin')
    u = urlsplit(origin)
    if (u.scheme != 'https' or not u.hostname or u.netloc != u.hostname or u.path not in ('', '/')
            or u.query or u.fragment or len(u.hostname) > 253
            or not re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', u.hostname)):
        raise CheckError('origin')
    if not isinstance(code, str) or not code.strip() or len(code) > 1024:
        raise CheckError('code')
    if not isinstance(manifest.get('expected_version'), str) or not manifest['expected_version'].strip():
        raise CheckError('version')
    directory = Path(manifest['public_directory'])
    receipt = Path(manifest['receipt_file'])
    if not directory.is_absolute() or not receipt.is_absolute() or not receipt.parent.is_dir():
        raise CheckError('paths')
    marker = receipt.with_name(receipt.name + '.started')
    if receipt.exists() or marker.exists() or receipt.with_name(receipt.name + '.partial').exists():
        raise CheckError('already_started')
    js = list((directory / 'assets').glob('index-*.js'))
    css = list((directory / 'assets').glob('index-*.css'))
    files = [directory / 'index.html', directory / 'favicon.svg', *js, *css, directory / 'collection-settings.json']
    if len(js) != 1 or len(css) != 1 or any(p.is_symlink() or not p.is_file() for p in files):
        raise CheckError('artifacts')
    data = [p.read_bytes() for p in files]
    if any(len(b) > MAX_BODY for b in data) or len(data[0]) != 659 or hashlib.sha256(data[0]).hexdigest() != INDEX_SHA or b'cloudflareinsights' in data[0].lower():
        raise CheckError('artifact_pin')
    paths = ['/', '/favicon.svg', '/' + js[0].relative_to(directory).as_posix(), '/' + css[0].relative_to(directory).as_posix(), '/collection-settings.json']
    if any(not re.fullmatch(r'/[A-Za-z0-9_./-]*', p) for p in paths):
        raise CheckError('artifact_path')
    if set(paths) != set(STATIC_PINS) or any((len(b), hashlib.sha256(b).hexdigest()) != STATIC_PINS[p] for p, b in zip(paths, data)):
        raise CheckError('static_pin')
    return u.hostname, receipt, marker, list(zip(paths, data))

class Transport:
    def request(self, scheme, host, method, path, headers, body, deadline):
        deadline = min(deadline, time.monotonic() + 15)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        cls = http.client.HTTPSConnection if scheme == 'https' else http.client.HTTPConnection
        kw = {'timeout': min(15, remaining)}
        if scheme == 'https':
            kw['context'] = ssl.create_default_context()
        conn = cls(host, **kw)
        try:
            conn.request(method, path, body=body, headers=headers)
            response = conn.getresponse()
            chunks, total = [], 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                if conn.sock:
                    conn.sock.settimeout(min(15, remaining))
                chunk = response.read(min(65536, MAX_BODY + 1 - total))
                total += len(chunk)
                if total > MAX_BODY:
                    raise CheckError('body_limit')
                if not chunk:
                    break
                chunks.append(chunk)
            return response.status, dict((k.lower(), v) for k, v in response.getheaders()), b''.join(chunks)
        finally:
            conn.close()

def run(manifest, code, transport=None):
    host, receipt, marker, files = prepare(manifest, code)
    transport = transport or Transport()
    # O_EXCL persists even after an interrupted process; never auto-retry.
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    report = {'schema': 'pitcheezy-stage2-predata-v1', 'started_utc': stamp(), 'requests': [], 'passed': False,
              'expected_deployment_version': manifest['expected_version'],
              'version_basis': 'management_readback_before_run_not_http_proof',
              'request_limit': 15, 'source_files': [{'path': p, 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()} for p, b in files],
              'limitations': ['No browser, data upload, notice switching, or public app migration.',
                              'Socket timeouts do not independently bound OS DNS resolution.']}
    def persist_partial():
        receipt.with_name(receipt.name + '.partial').write_text(json.dumps(report, indent=2), encoding='utf-8')
    deadline = time.monotonic() + 300
    cookie = None
    attempted_logout = False
    def request(scheme, method, path, headers=None, body=None):
        if len(report['requests']) >= 15 or time.monotonic() >= deadline:
            raise CheckError('budget')
        row = {'method': method, 'path': path, 'started_utc': stamp(), 'status': None}
        report['requests'].append(row)
        try:
            persist_partial()
        except OSError:
            report['receipt_write_failed'] = True
            if method != 'DELETE':
                raise CheckError('receipt_write_failed') from None
        try:
            status, h, b = transport.request(scheme, host, method, path, headers or {}, body, deadline)
            row['status'] = status
            response_headers = {k.lower(): v for k, v in h.items()}
            ray = response_headers.get('cf-ray', '')
            row['ray'] = ray if re.fullmatch(r'[a-fA-F0-9]{16,32}-[A-Z]{3}', ray) else None
            row['response_bytes'] = len(b)
            row['response_sha256'] = hashlib.sha256(b).hexdigest() if method == 'GET' and path in STATIC_PINS and headers and 'Cookie' in headers else None
            return status, {k.lower(): v for k, v in h.items()}, b
        except Exception:
            raise CheckError('request_failed') from None
        finally:
            row['finished_utc'] = stamp()
            try:
                persist_partial()
            except OSError:
                report['receipt_write_failed'] = True
    def check(condition, label):
        if report.get('receipt_write_failed') and label != 'logout':
            raise CheckError('receipt_write_failed')
        if not condition:
            raise CheckError(label)
    def authvalue(b, expected):
        try:
            obj = json.loads(b)
            return isinstance(obj, dict) and obj.get('authenticated') is expected
        except (ValueError, UnicodeError):
            return False
    try:
        for path in ('/', '/favicon.svg', '/v1/manifest.json'):
            s, h, _ = request('https', 'GET', path)
            check(s == 401 and h.get('x-pitcheezy-access') == 'required', 'gate')
        s, _, _ = request('https', 'HEAD', '/_publish/v1/health.json')
        check(s == 503, 'publish_closed')
        s, _, b = request('https', 'GET', '/_access/v1/session')
        check(s == 200 and authvalue(b, False), 'session_closed')
        s, h, _ = request('http', 'GET', '/')
        check(s == 301 and h.get('location') == 'https://' + host + '/', 'https_redirect')
        payload = json.dumps({'code': code}).encode()
        s, h, b = request('https', 'POST', '/_access/v1/session', {'Content-Type': 'application/json'}, payload)
        raw = h.get('set-cookie', '')
        # Capture issued cookies even if another login assertion fails, so logout is reserved.
        match = re.match(r'(__Host-pz_viewer=v3\.[A-Za-z0-9._-]+)(?:;|$)', raw)
        if match:
            cookie = match.group(1)
        attrs = [part.strip().lower() for part in raw.split(';')[1:]]
        check(s == 200 and authvalue(b, True) and cookie is not None and 'secure' in attrs and 'httponly' in attrs and 'path=/' in attrs, 'login')
        for path, expected in files:
            s, _, b = request('https', 'GET', path, {'Cookie': cookie})
            check(s == 200 and b == expected and (path != '/' or b'cloudflareinsights' not in b.lower()), 'static')
        s, _, _ = request('https', 'GET', '/v1/manifest.json', {'Cookie': cookie})
        check(s == 404, 'manifest_absent')
        s, _, _ = request('https', 'GET', '/_notice/v1/state')
        check(s == 401, 'notice_gate')
        attempted_logout = True
        s, _, _ = request('https', 'DELETE', '/_access/v1/session', {'Cookie': cookie})
        check(s == 204, 'logout')
        report['passed'] = True
    except CheckError as exc:
        report['error'] = str(exc)
    finally:
        if cookie and not attempted_logout and len(report['requests']) < 15 and time.monotonic() < deadline:
            try:
                s, _, _ = request('https', 'DELETE', '/_access/v1/session', {'Cookie': cookie})
                report['logout_status_ok'] = s == 204
            except CheckError:
                report['logout_status_ok'] = False
        report['finished_utc'] = stamp()
        with receipt.open('x', encoding='utf-8') as out:
            json.dump(report, out, indent=2)
    return report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if not args.execute:
        print('No requests made; --execute is required.')
        return 2
    try:
        with open(args.manifest, encoding='utf-8') as src:
            manifest = json.load(src)
        result = run(manifest, os.environ.get('PITCHEEZY_ACCESS_CODE'))
        print('Passed.' if result['passed'] else 'Failed; see private receipt.')
        return 0 if result['passed'] else 1
    except (OSError, ValueError, TypeError, KeyError, CheckError):
        print('Stopped; inspect private receipt and started marker before any retry.')
        return 1

if __name__ == '__main__':
    raise SystemExit(main())




