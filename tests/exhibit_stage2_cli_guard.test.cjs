'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { makeGuard } = require('../scripts/exhibit_stage2_cli_guard.cjs');
const account = 'a'.repeat(32), worker = 'unit-test-worker';
const prefix = `/client/v4/accounts/${account}/workers/scripts/${worker}`;

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
