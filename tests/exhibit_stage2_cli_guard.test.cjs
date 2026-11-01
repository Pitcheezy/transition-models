'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { Readable } = require('node:stream');
const { makeGuard } = require('../scripts/exhibit_stage2_cli_guard.cjs');
const account = 'a'.repeat(32), worker = 'unit-test-worker';
const prefix = `/client/v4/accounts/${account}/workers/scripts/${worker}`;

function refresh(g, body, origin='https://dash.cloudflare.com', p='/oauth2/token') {
  return new Promise(resolve => {
    g.dispatch({origin, path:p, method:'POST', body}, {onError:() => resolve('blocked')});
  });
}

test('refresh accepts exactly one valid streamed form and preserves bytes', async () => {
  let count = 0;
  const original = 'grant_type=refresh_token&refresh_token=example%2Bvalue&client_id=example';
  let done;
  const accepted = new Promise(resolve => { done = resolve; });
  const g = makeGuard({dispatch(o) { count++; done(o.body); return true; }}, account, worker);
  g.dispatch({origin:'https://dash.cloudflare.com', path:'/oauth2/token', method:'POST', body:Readable.from([original.slice(0, 9), original.slice(9)])}, {onError:()=>done(null)});
  assert.equal((await accepted).toString(), original);
  assert.equal(await refresh(g, original), 'blocked');
  assert.equal(count, 1);
});

test('refresh rejects incorrect forms, endpoints and size', async () => {
  const forms = [
    'grant_type=authorization_code&refresh_token=x&client_id=y',
    'grant_type=refresh_token&grant_type=refresh_token&refresh_token=x&client_id=y',
    'grant_type=refresh_token&refresh_token=&client_id=y',
    'grant_type=refresh_token&refresh_token=%zz&client_id=y',
    'grant_type=refresh_token&refresh_token=x&client_id=y&other=z',
    'grant_type=refresh_token&refresh_token=' + 'x'.repeat(16384) + '&client_id=y'
  ];
  for (const form of forms) {
    let calls = 0;
    const g = makeGuard({dispatch() {calls++;}}, account, worker);
    assert.equal(await refresh(g, Readable.from([form])), 'blocked');
    assert.equal(calls, 0);
  }
  for (const [origin, p] of [['https://other.example','/oauth2/token'], ['https://dash.cloudflare.com','/oauth2/token?redirect=1']]) {
    const g = makeGuard({dispatch() {assert.fail('unexpected dispatch');}}, account, worker);
    assert.equal(await refresh(g, 'grant_type=refresh_token&refresh_token=x&client_id=y', origin, p), 'blocked');
  }
});

test('stalled refresh stream times out and cannot dispatch later', async () => {
  let finish, calls = 0;
  const body = (async function* () { await new Promise(resolve => {finish = resolve;}); yield 'grant_type=refresh_token&refresh_token=x&client_id=y'; })();
  const g = makeGuard({dispatch() {calls++;}}, account, worker);
  assert.equal(await refresh(g, body), 'blocked');
  finish();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls, 0);
});

test('real Wrangler refreshes only through the guarded fake dispatcher', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'stage2-guard-test-'));
  try {
    const root = path.resolve(__dirname, '..');
    const config = path.join(tmp, 'wrangler.json'), envFile = path.join(tmp, 'empty');
    const wrapper = path.join(tmp, 'wrapper.cjs'), trace = path.join(tmp, 'trace');
    const authDir = path.join(tmp, '.wrangler', 'config');
    fs.mkdirSync(authDir, {recursive:true});
    fs.writeFileSync(path.join(authDir, 'default.toml'), 'oauth_token = "dummy-expired"\nrefresh_token = "dummy-refresh"\nexpiration_time = "2000-01-01T00:00:00.000Z"\n');
    fs.writeFileSync(config, JSON.stringify({name:worker, compatibility_date:'2026-01-01', workers_dev:false}));
    fs.writeFileSync(envFile, '');
    const undici = path.join(root, 'ops/public-host-tooling/node_modules/undici');
    const guard = path.join(root, 'scripts/exhibit_stage2_cli_guard.cjs');
    const cli = path.join(root, 'ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js');
    fs.writeFileSync(wrapper, `
      const fs = require('node:fs'); const u = require(${JSON.stringify(undici)});
      const {makeGuard} = require(${JSON.stringify(guard)});
      const fake = {dispatch(o,h) {
        fs.appendFileSync(${JSON.stringify(trace)}, o.method + ' ' + o.origin + o.path + '\\n');
        let result;
        if (o.origin === 'https://dash.cloudflare.com') result = {access_token:'dummy-access', refresh_token:'dummy-next', expires_in:3600, scope:''};
        else result = {success:true, errors:[], messages:[], result:{deployments:[]}};
        h.onConnect(() => {}); h.onHeaders(200, [Buffer.from('content-type'),Buffer.from('application/json')], () => {}, 'OK');
        h.onData(Buffer.from(JSON.stringify(result))); h.onComplete([]); return true;
      }};
      u.setGlobalDispatcher(makeGuard(fake, ${JSON.stringify(account)}, ${JSON.stringify(worker)}));
    `);
    const env = {SYSTEMROOT:process.env.SYSTEMROOT, WINDIR:process.env.WINDIR, USERPROFILE:tmp, APPDATA:tmp, LOCALAPPDATA:tmp, TEMP:tmp, TMP:tmp,
      PATH:process.env.PATH, CLOUDFLARE_ACCOUNT_ID:account, CI:'true', WRANGLER_WRITE_LOGS:'false', WRANGLER_SEND_METRICS:'false', WRANGLER_SEND_ERROR_REPORTS:'false', WRANGLER_LOG:'log', WRANGLER_LOG_SANITIZE:'true', NO_COLOR:'1'};
    const child = spawnSync(process.execPath, ['--require', wrapper, cli, 'deployments', 'list', '--json', '--config', config, '--env-file', envFile], {cwd:tmp, encoding:'utf8', timeout:30000, env});
    assert.equal(child.status, 0, child.stderr);
    assert.deepEqual(JSON.parse(child.stdout), []);
    const lines = fs.readFileSync(trace, 'utf8');
    assert.match(lines, /POST https:\/\/dash\.cloudflare\.com\/oauth2\/token/);
    assert.match(lines, /GET https:\/\/api\.cloudflare\.com.*\/deployments/);
    assert.doesNotMatch(lines + child.stdout + child.stderr, /dummy-(refresh|access|next|expired)/);
  } finally {
    assert.equal(path.dirname(path.resolve(tmp)), path.resolve(os.tmpdir()));
    assert.ok(path.basename(tmp).startsWith('stage2-guard-test-'));
    fs.rmSync(tmp, {recursive:true, force:true});
  }
});

test('exact origin and paths, one PUT, no worker creation or redirects', () => {
  const seen = [], errors = [];
  const g = makeGuard({dispatch(o) { seen.push(o); return true; }}, account, worker);
  const send = (method, p, origin='https://api.cloudflare.com') => g.dispatch({ method, path:p, origin }, {onError(e) { errors.push(e.message); }});
  send('GET', `${prefix}/deployments`);
  send('GET', `${prefix}/secrets?limit=20`);
  send('PUT', `${prefix}/secrets`);
  send('PUT', `${prefix}/secrets`);
  send('PUT', prefix);
  send('GET', `${prefix}/secrets?limit=20&other=x`);
  send('GET', `${prefix}/secrets`, 'https://other.example');
  assert.equal(seen.length, 3);
  assert.equal(errors.length, 4);
});

test('real Wrangler missing-worker fallback is blocked without network or logs', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'stage2-guard-test-'));
  try {
    const root = path.resolve(__dirname, '..');
    const config = path.join(tmp, 'wrangler.json');
    const envFile = path.join(tmp, 'empty');
    const trace = path.join(tmp, 'trace');
    const wrapper = path.join(tmp, 'wrapper.cjs');
    fs.writeFileSync(config, JSON.stringify({name:worker, compatibility_date:'2026-01-01', workers_dev:false}));
    fs.writeFileSync(envFile, '');
    const undici = path.join(root, 'ops/public-host-tooling/node_modules/undici');
    const guard = path.join(root, 'scripts/exhibit_stage2_cli_guard.cjs');
    const cli = path.join(root, 'ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js');
    fs.writeFileSync(wrapper, `
      const fs = require('node:fs');
      const u = require(${JSON.stringify(undici)});
      const {makeGuard} = require(${JSON.stringify(guard)});
      const fake = { dispatch(opts, h) {
        fs.appendFileSync(${JSON.stringify(trace)}, opts.method + ' ' + opts.path + '\\n');
        const body = Buffer.from(JSON.stringify({success:false, errors:[{code:10007,message:Buffer.from('ZmFrZS1zZWNyZXQtdmFsdWU=', 'base64').toString()}],messages:[],result:null}));
        h.onConnect(() => {});
        h.onHeaders(404, [Buffer.from('content-type'),Buffer.from('application/json')], () => {}, 'Not Found');
        h.onData(body); h.onComplete([]); return true;
      }};
      const inner = makeGuard(fake, ${JSON.stringify(account)}, ${JSON.stringify(worker)});
      u.setGlobalDispatcher({dispatch(o,h) { if (o.method === 'PUT' && o.path === ${JSON.stringify(prefix)}) fs.appendFileSync(${JSON.stringify(trace)}, 'BLOCKED worker PUT\\n'); return inner.dispatch(o,h); }});
    `);
    const child = spawnSync(process.execPath, ['--require', wrapper, cli, 'secret', 'put', 'ACCESS_CODE_SHA256', '--config', config, '--env-file', envFile], {
      cwd:tmp, input:'fake-secret-value\n', encoding:'utf8', timeout:30000,
      env:{...process.env, CLOUDFLARE_API_TOKEN:'fake-token', CLOUDFLARE_ACCOUNT_ID:account, CI:'true', WRANGLER_WRITE_LOGS:'false', WRANGLER_SEND_METRICS:'false', WRANGLER_SEND_ERROR_REPORTS:'false', WRANGLER_LOG:'warn', WRANGLER_LOG_SANITIZE:'true', NO_COLOR:'1'}
    });
    assert.notEqual(child.status, 0, child.stdout + child.stderr);
    const lines = fs.readFileSync(trace, 'utf8');
    assert.match(lines, /PUT .*\/secrets/);
    assert.match(lines, /BLOCKED worker PUT/);
    assert.doesNotMatch(lines, /fake-secret-value|fake-token/);
    for (const entry of fs.readdirSync(tmp)) assert.doesNotMatch(fs.readFileSync(path.join(tmp, entry), 'utf8'), /fake-secret-value|fake-token/);
  } finally {
    assert.equal(path.dirname(path.resolve(tmp)), path.resolve(os.tmpdir()));
    assert.ok(path.basename(tmp).startsWith("stage2-guard-test-"));
    fs.rmSync(tmp, {recursive:true, force:true});
  }
});

test('production preload fails closed without its pinned manifest', () => {
  const guard = path.resolve(__dirname, '../scripts/exhibit_stage2_cli_guard.cjs');
  const child = spawnSync(process.execPath, ['--require', guard, '-e', 'process.stdout.write("unexpected")'], {
    encoding:'utf8', env:{...process.env, WRANGLER_WRITE_LOGS:'false', PITCHEEZY_STAGE2_MANIFEST:path.join(os.tmpdir(), 'nonexistent-stage2-manifest')}
  });
  assert.notEqual(child.status, 0);
  assert.doesNotMatch(child.stdout, /unexpected/);
  assert.match(child.stderr, /stage2 guard initialization failed/);
});
