import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SPEC = importlib.util.spec_from_file_location('predata', Path(__file__).parents[1] / 'scripts' / 'verify_exhibit_stage2_predata.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

@pytest.fixture
def setup(tmp_path, monkeypatch):
    public = tmp_path / 'public'
    (public / 'assets').mkdir(parents=True)
    index = b'x' * 659
    monkeypatch.setattr(m, 'INDEX_SHA', hashlib.sha256(index).hexdigest())
    for name, value in {'index.html': index, 'favicon.svg': b'icon', 'assets/index-a.js': b'js', 'assets/index-a.css': b'css', 'collection-settings.json': b'{}'}.items():
        (public / name).write_bytes(value)
    monkeypatch.setattr(m, 'STATIC_PINS', {('/' if p.name=='index.html' else '/'+p.relative_to(public).as_posix()): (len(p.read_bytes()), hashlib.sha256(p.read_bytes()).hexdigest()) for p in public.rglob('*') if p.is_file()})
    manifest = {'origin': 'https://test.example.com', 'public_directory': str(public), 'receipt_file': str(tmp_path / 'receipt.json'), 'expected_version': 'test-version', 'ready_confirmation': True}
    return manifest, public

class Fake:
    def __init__(self, public, failure=None):
        self.public = public
        self.failure = failure
        self.calls = []
    def request(self, scheme, host, method, path, headers, body, deadline):
        self.calls.append((scheme, method, path, headers, body))
        n = len(self.calls)
        if self.failure == ('timeout', n):
            raise TimeoutError()
        if self.failure == ('401', n):
            return 401, {}, b''
        if self.failure == ('redirect', n):
            return 302, {'location': 'https://elsewhere.example/'}, b''
        if n <= 3:
            return 401, {'x-pitcheezy-access': 'required'}, b''
        if n == 4:
            return 503, {}, b''
        if n == 5:
            return 200, {}, b'{"authenticated":false}'
        if n == 6:
            return 301, {'location': 'https://' + host + '/'}, b''
        if n == 7:
            return 200, {'set-cookie': '__Host-pz_viewer=v3.secret; Path=/; HttpOnly; Secure'}, b'{"authenticated":true}'
        if method == 'DELETE':
            return 204, {}, b''
        if n <= 12:
            p = self.public / ('index.html' if path == '/' else path[1:])
            return 200, {}, p.read_bytes()
        if n == 13:
            return 404, {}, b''
        return 401, {}, b''

def test_success_fifteen_and_no_secrets(setup):
    manifest, public = setup
    fake = Fake(public)
    result = m.run(manifest, 'secret-code', fake)
    assert result['passed'] and len(fake.calls) == 15
    assert fake.calls[5][:3] == ('http', 'GET', '/') and 'Cookie' not in fake.calls[5][3]
    assert fake.calls[-1][1:3] == ('DELETE', '/_access/v1/session')
    receipt = Path(manifest['receipt_file']).read_text()
    assert 'secret-code' not in receipt and 'v3.secret' not in receipt and 'test.example.com' not in receipt
    with pytest.raises(m.CheckError):
        m.run(manifest, 'secret-code', fake)
    assert len(fake.calls) == 15

def test_unexpected_status_stops(setup):
    manifest, public = setup
    fake = Fake(public, ('401', 4))
    assert not m.run(manifest, 'secret-code', fake)['passed']
    assert len(fake.calls) == 4

def test_after_login_failure_reserves_logout(setup):
    manifest, public = setup
    fake = Fake(public, ('401', 8))
    result = m.run(manifest, 'secret-code', fake)
    assert not result['passed'] and result['logout_status_ok']
    assert len(fake.calls) == 9 and fake.calls[-1][1] == 'DELETE'

def test_timeout_no_retry(setup):
    manifest, public = setup
    fake = Fake(public, ('timeout', 2))
    result = m.run(manifest, 'secret-code', fake)
    assert len(fake.calls) == 2 and len(result['requests']) == 2 and result['requests'][-1]['status'] is None

def test_redirect_not_followed(setup):
    manifest, public = setup
    fake = Fake(public, ('redirect', 8))
    assert not m.run(manifest, 'secret-code', fake)['passed']
    assert len(fake.calls) == 9 and fake.calls[-1][1] == 'DELETE'

def test_bad_pin_and_preflight_no_requests(setup):
    manifest, public = setup
    (public / 'index.html').write_bytes(b'bad')
    fake = Fake(public)
    with pytest.raises(m.CheckError):
        m.run(manifest, 'secret-code', fake)
    assert not fake.calls and not Path(manifest['receipt_file']).exists()

def test_no_execute_does_not_open_manifest(tmp_path):
    p = subprocess.run([sys.executable, str(SPEC.origin), '--manifest', str(tmp_path / 'nonexistent')], capture_output=True, text=True)
    assert p.returncode == 2 and 'No requests' in p.stdout



def test_other_asset_drift_stops_before_network(setup):
    manifest, public = setup
    (public / 'assets/index-a.js').write_bytes(b'changed')
    fake = Fake(public)
    with pytest.raises(m.CheckError, match='static_pin'):
        m.run(manifest, 'secret-code', fake)
    assert fake.calls == []


def test_partial_receipt_retains_attempts_without_secrets(setup):
    manifest, public = setup
    fake = Fake(public, ('timeout', 8))
    result = m.run(manifest, 'secret-code', fake)
    partial = Path(manifest['receipt_file'] + '.partial').read_text()
    assert len(json.loads(partial)['requests']) == 9
    assert all(value not in partial for value in ('secret-code', 'v3.secret', 'test.example.com'))
    assert not result['passed']


def test_existing_partial_receipt_refuses_run(setup):
    manifest, public = setup
    Path(manifest['receipt_file'] + '.partial').write_text('{}')
    fake = Fake(public)
    with pytest.raises(m.CheckError, match='already_started'):
        m.run(manifest, 'secret-code', fake)
    assert fake.calls == []


def test_login_receipt_write_failure_still_logs_out(setup, monkeypatch):
    manifest, public = setup
    original = Path.write_text
    writes = 0
    def fail_once(self, *args, **kwargs):
        nonlocal writes
        if self.name.endswith('.partial'):
            writes += 1
            if writes == 14:
                raise OSError('simulated persistence error after login')
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Path, 'write_text', fail_once)
    fake = Fake(public)
    report = m.run(manifest, 'secret-code', fake)
    assert not report['passed'] and report['error'] == 'receipt_write_failed'
    assert len(fake.calls) == 8 and fake.calls[-1][1] == 'DELETE'
