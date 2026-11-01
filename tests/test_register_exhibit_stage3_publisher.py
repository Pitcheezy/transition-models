import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts import register_exhibit_stage3_publisher as op

V0 = '11111111-1111-1111-1111-111111111111'
V1 = '22222222-2222-2222-2222-222222222222'
sha = lambda b: hashlib.sha256(b).hexdigest()

@pytest.fixture
def fixture(tmp_path):
    root = tmp_path / 'root'
    (root / 'scripts').mkdir(parents=True)
    cli = root / 'ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js'
    cli.parent.mkdir(parents=True)
    cli.write_bytes(b'// mock CLI never executed')
    dist=cli.parent.parent/'wrangler-dist/cli.js';dist.parent.mkdir();dist.write_bytes(b'// mock CLI child never executed')
    (cli.parent.parent / 'package.json').write_text('{"version":"4.151.0"}')
    guard = root / 'scripts/exhibit_stage3_cli_guard.cjs'
    base = root / 'scripts/exhibit_stage2_cli_guard.cjs'
    guard.write_bytes(b'// mock stage3 guard')
    base.write_bytes(b'// mock base guard')
    cfg = {'name':'unit-worker','vars':{'UPLOAD_ENABLED':'false','ACCESS_GATE_ENABLED':'true'},'workers_dev':False,'preview_urls':False}
    config = tmp_path / 'config.json'; config.write_text(json.dumps(cfg))
    node = tmp_path / 'node.exe'; node.write_bytes(b'fake node')
    empty = tmp_path / 'empty'; empty.write_bytes(b'')
    token = tmp_path / 'token'; token.write_bytes(b'T'*43)
    m = {'schema':'pitcheezy-stage3-publisher-registration-v1','phase':'initial','repository_root':str(root),'configuration_file':str(config),'configuration_sha256':sha(config.read_bytes()),'node_executable':str(node),'node_sha256':sha(node.read_bytes()),'guard_sha256':sha(guard.read_bytes()),'base_guard_sha256':sha(base.read_bytes()),'wrangler_sha256':sha(cli.read_bytes()),'wrangler_dist_sha256':sha(dist.read_bytes()),'account_id':'a'*32,'worker_name':'unit-worker','expected_version':V0,'token_file':str(token),'token_sha256':sha(token.read_bytes()),'empty_env_file':str(empty),'output_directory':str(tmp_path/'out')}
    manifest = tmp_path / 'manifest.json'
    def pin():
        manifest.write_text(json.dumps(m), encoding='utf-8')
        return str(manifest), sha(manifest.read_bytes())
    return m, cfg, pin

class FakeCloud:
    def __init__(self, cfg, phase='initial'):
        self.cfg=cfg
        self.names=set(op.BASE_NAMES) | ({op.NAME} if phase=='rotate' else set())
        self.version=V0
        self.puts=[]
        self.calls=[]
        self.fail_after_put=False
        self.raw_echo='reflected-credential-must-not-survive'
    def __call__(self, command, **kwargs):
        args=command[4:]
        self.calls.append(args)
        assert command[1]=='--require'
        env=kwargs['env']
        for key in ['NODE_OPTIONS','CLOUDFLARE_API_TOKEN','HTTP_PROXY','HTTPS_PROXY','CLOUDFLARE_API_BASE_URL','CF_API_BASE_URL']:
            assert key not in env
        assert env['WRANGLER_WRITE_LOGS']=='false'
        assert env['WRANGLER_SEND_METRICS']=='false'
        if args[:2]==['deployments','list']:
            result=[{'created_on':'2026-11-02T00:00:00Z','versions':[{'version_id':self.version,'percentage':100}]}]
        elif args[:2]==['versions','view']:
            result={'id':self.version,'metadata':{'author_email':'do-not-copy'},'resources':{'bindings':[{'name':k,'type':'plain_text','text':v} for k,v in self.cfg['vars'].items()] + [{'name':n,'type':'secret_text'} for n in self.names]}}
        elif args[:2]==['secret','list']:
            result=[{'name':n,'type':'secret_text'} for n in sorted(self.names)]
        elif args[:2]==['secret','put']:
            assert args[2]==op.NAME
            digest=kwargs['input'].strip()
            assert digest not in command
            self.puts.append((op.NAME,digest))
            self.names.add(op.NAME)
            self.version=V1
            if self.fail_after_put:
                raise TimeoutError(self.raw_echo)
            return SimpleNamespace(returncode=0,stdout=self.raw_echo+digest,stderr=self.raw_echo)
        else:
            raise AssertionError('unexpected command')
        return SimpleNamespace(returncode=0,stdout=json.dumps(result),stderr='')

def test_initial_only_one_stdin_secret_and_no_sensitive_output(fixture,monkeypatch,capsys):
    m,cfg,pin=fixture
    for key in ['NODE_OPTIONS','CLOUDFLARE_API_TOKEN','HTTP_PROXY','HTTPS_PROXY','CLOUDFLARE_API_BASE_URL','CF_API_BASE_URL']:
        monkeypatch.setenv(key,'not-inherited')
    cloud=FakeCloud(cfg)
    path,digest=pin()
    state=op.register(path,digest,cloud)
    assert state['completed'] and state['pending'] is None and state['version']==V1
    assert cloud.puts==[(op.NAME,sha(b'T'*43))]
    persisted=''.join(f.read_text(encoding='utf-8') for f in Path(m['output_directory']).glob('*') if f.is_file())
    # Manifest contains the approved token FILE HASH, but never the token raw value or reflected CLI output.
    assert 'T'*43 not in persisted and cloud.raw_echo not in persisted and 'do-not-copy' not in persisted
    assert 'T'*43 not in capsys.readouterr().out
    assert json.loads((Path(m['output_directory'])/'manifest.private.json').read_text())==m
    with pytest.raises(RuntimeError,match='already_started'):
        op.register(path,digest,cloud)
    assert len(cloud.puts)==1

def test_rotate_generates_only_discarded_memory_secret(fixture,monkeypatch):
    m,cfg,pin=fixture
    m.update(phase='rotate',token_file=None,token_sha256=None)
    monkeypatch.setattr(op.secrets,'token_bytes',lambda n:b'X'*n)
    cloud=FakeCloud(cfg,'rotate')
    state=op.register(*pin(),cloud)
    assert state['phase']=='rotate' and state['completed']
    assert cloud.puts==[(op.NAME,sha(b'X'*32))]
    persisted=''.join(f.read_text() for f in Path(m['output_directory']).glob('*') if f.is_file())
    assert 'X'*32 not in persisted and sha(b'X'*32) not in persisted

def test_default_dryrun_and_cancel_do_not_call_network_or_create_output(fixture,monkeypatch,capsys):
    m,cfg,pin=fixture
    path,digest=pin()
    monkeypatch.setattr(op.subprocess,'run',lambda *a,**kw:pytest.fail('network command'))
    assert op.main(['--manifest',path,'--manifest-sha256',digest])==0
    assert not Path(m['output_directory']).exists()
    monkeypatch.setattr('builtins.input',lambda prompt:'q')
    assert op.main(['--manifest',path,'--manifest-sha256',digest,'--register'])==0
    assert not Path(m['output_directory']).exists()
    assert 'Dry-run passed' in capsys.readouterr().out

@pytest.mark.parametrize('changed',['manifest','configuration_file','node_executable','guard','base','cli','dist','empty_env_file'])
def test_local_pin_changes_stop_before_any_command(fixture,changed):
    m,cfg,pin=fixture
    path,digest=pin()
    targets={'manifest':Path(path),'configuration_file':Path(m['configuration_file']),'node_executable':Path(m['node_executable']),'guard':Path(m['repository_root'])/'scripts/exhibit_stage3_cli_guard.cjs','base':Path(m['repository_root'])/'scripts/exhibit_stage2_cli_guard.cjs','cli':Path(m['repository_root'])/'ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js','dist':Path(m['repository_root'])/'ops/public-host-tooling/node_modules/wrangler/wrangler-dist/cli.js','empty_env_file':Path(m['empty_env_file'])}
    targets[changed].write_bytes(b'changed')
    cloud=FakeCloud(cfg)
    with pytest.raises(RuntimeError):op.register(path,digest,cloud)
    assert cloud.calls==[]

def test_unexpected_names_stop_before_put(fixture):
    m,cfg,pin=fixture
    cloud=FakeCloud(cfg)
    cloud.names.add(op.NAME)
    with pytest.raises(RuntimeError,match='unexpected_secret'):op.register(*pin(),cloud)
    assert cloud.puts==[]

def test_changed_version_stops_before_put(fixture):
    m,cfg,pin=fixture
    cloud=FakeCloud(cfg);cloud.version=V1
    with pytest.raises(RuntimeError,match='active_version_changed'):op.register(*pin(),cloud)
    assert cloud.puts==[]

def test_remote_upload_on_or_other_variable_drift_stops_put(fixture):
    m,cfg,pin=fixture
    remote=json.loads(json.dumps(cfg));remote['vars']['UPLOAD_ENABLED']='true'
    cloud=FakeCloud(remote)
    with pytest.raises(RuntimeError,match='remote_version_or_vars_changed'):op.register(*pin(),cloud)
    assert cloud.puts==[]

def test_uncertain_put_preserves_pending_and_refuses_rerun(fixture):
    m,cfg,pin=fixture
    cloud=FakeCloud(cfg);cloud.fail_after_put=True
    path,digest=pin()
    with pytest.raises(RuntimeError,match='uncertain'):op.register(path,digest,cloud)
    state=json.loads((Path(m['output_directory'])/'registration.private.json').read_text())
    assert state['pending']==op.NAME and not state['completed']
    with pytest.raises(RuntimeError,match='already_started'):op.register(path,digest,cloud)
    assert len(cloud.puts)==1
    assert cloud.raw_echo not in ''.join(f.read_text() for f in Path(m['output_directory']).glob('*') if f.is_file())

def test_invalid_token_file_stops_before_put(fixture):
    m,cfg,pin=fixture
    path,digest=pin();Path(m['token_file']).write_bytes(b'changed')
    cloud=FakeCloud(cfg)
    with pytest.raises(RuntimeError,match='token_file_changed'):op.register(path,digest,cloud)
    assert cloud.puts==[]

def test_reflected_read_failure_output_discarded(fixture):
    m,cfg,pin=fixture
    def failure(*a,**kw):return SimpleNamespace(returncode=1,stdout='sensitive value',stderr='sensitive value')
    with pytest.raises(RuntimeError,match='command_failed'):op.register(*pin(),failure)
    assert 'sensitive value' not in ''.join(f.read_text() for f in Path(m['output_directory']).glob('*') if f.is_file())

def test_rotate_requires_null_token_fields(fixture):
    m,cfg,pin=fixture;m['phase']='rotate'
    cloud=FakeCloud(cfg)
    with pytest.raises(RuntimeError,match='rotation_has_token_file'):op.register(*pin(),cloud)
    assert cloud.calls==[]

def test_split_deployment_rejected():
    with pytest.raises(RuntimeError,match='split'):
        op.latest_version([{'created_on':'2026-11-02T00:00:00Z','versions':[{'version_id':V0,'percentage':50},{'version_id':V1,'percentage':50}]}])
