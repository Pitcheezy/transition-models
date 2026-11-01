'use strict';
// Stage3 user-run CLI: fixed target, one publisher-secret PUT, optional one fixed version GET.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {makeGuard} = require('./exhibit_stage2_cli_guard.cjs');
const HASH = /^[a-f0-9]{64}$/;
const UUID = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

async function publisherBody(body) {
  const input = typeof body === 'string' || Buffer.isBuffer(body) || body instanceof Uint8Array ? [body] : body;
  if (!input || (!input[Symbol.asyncIterator] && !input[Symbol.iterator])) throw new Error('invalid body');
  const chunks = [];
  let size = 0;
  for await (const chunk of input) {
    if (typeof chunk !== 'string' && !Buffer.isBuffer(chunk) && !(chunk instanceof Uint8Array)) throw new Error('invalid body');
    const bytes = Buffer.from(chunk);
    size += bytes.length;
    if (size > 512) throw new Error('invalid body');
    chunks.push(bytes);
  }
  const bytes = Buffer.concat(chunks);
  const obj = JSON.parse(new TextDecoder('utf-8', {fatal:true}).decode(bytes));
  if (!obj || Array.isArray(obj) || Object.keys(obj).sort().join(',') !== 'name,text,type' ||
      obj.name !== 'PUBLISH_TOKEN_SHA256' || obj.type !== 'secret_text' || !HASH.test(obj.text)) throw new Error('invalid body');
  return bytes;
}

function makePublisherGuard(delegate, account, worker, versionId = null, allowPut = false) {
  if (versionId !== null && !UUID.test(versionId)) throw new Error('invalid version');
  const inner = makeGuard(delegate, account, worker);
  const prefix = `/client/v4/accounts/${account}/workers/scripts/${worker}`;
  let putClaimed = false, versionRead = false;
  return {
    dispatch(opts, handler) {
      if (opts.origin === 'https://api.cloudflare.com' && opts.method === 'GET' &&
          versionId !== null && opts.path === `${prefix}/versions/${versionId}` && !versionRead) {
        versionRead = true;
        return delegate.dispatch(opts, handler);
      }
      if (opts.method === 'PUT') {
        if (!allowPut || putClaimed || opts.origin !== 'https://api.cloudflare.com' || opts.path !== `${prefix}/secrets`) {
          handler.onError(new Error('stage3 guard blocked request'));
          return false;
        }
        putClaimed = true;
        let timer;
        const timeout = new Promise((_, reject) => {timer = setTimeout(() => reject(new Error('timeout')), 5000);});
        Promise.race([publisherBody(opts.body), timeout]).then(bytes => {
          clearTimeout(timer);
          try { inner.dispatch({...opts, body:bytes}, handler); }
          catch (_) { handler.onError(new Error('stage3 guard blocked request')); }
        }, () => {clearTimeout(timer); handler.onError(new Error('stage3 guard blocked request'));});
        return true;
      }
      return inner.dispatch(opts, handler);
    }
  };
}

function install() {
  try {
    if (process.env.WRANGLER_WRITE_LOGS !== 'false') throw new Error();
    const bytes = fs.readFileSync(process.env.PITCHEEZY_STAGE3_MANIFEST);
    const expected = process.env.PITCHEEZY_STAGE3_MANIFEST_SHA256;
    if (!HASH.test(expected || '') || sha(bytes) !== expected) throw new Error();
    const m = JSON.parse(new TextDecoder('utf-8', {fatal:true}).decode(bytes));
    if (m.schema !== 'pitcheezy-stage3-publisher-registration-v1' || !['initial','rotate'].includes(m.phase)) throw new Error();
    const configBytes = fs.readFileSync(m.configuration_file);
    const config = JSON.parse(configBytes);
    if (sha(configBytes) !== m.configuration_sha256 || config.name !== m.worker_name || config.vars.UPLOAD_ENABLED !== 'false') throw new Error();
    const base = path.join(m.repository_root, 'scripts/exhibit_stage2_cli_guard.cjs');
    const cli = path.join(m.repository_root, 'ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js');
    if (sha(fs.readFileSync(__filename)) !== m.guard_sha256 || sha(fs.readFileSync(base)) !== m.base_guard_sha256 || sha(fs.readFileSync(cli)) !== m.wrangler_sha256) throw new Error();
    if (JSON.parse(fs.readFileSync(path.join(path.dirname(cli), '../package.json'))).version !== '4.151.0') throw new Error();
    if (path.resolve(process.argv[1]) !== path.resolve(cli) || fs.readFileSync(m.empty_env_file).length !== 0) throw new Error();
    const args = process.argv.slice(2), tail = ['--config',m.configuration_file,'--env-file',m.empty_env_file];
    let prefix, versionId = null, allowPut = false;
    if (args[0] === 'deployments' && args[1] === 'list') prefix = ['deployments','list','--json'];
    else if (args[0] === 'secret' && args[1] === 'list') prefix = ['secret','list','--format','json'];
    else if (args[0] === 'secret' && args[1] === 'put') {prefix = ['secret','put','PUBLISH_TOKEN_SHA256']; allowPut = true;}
    else if (args[0] === 'versions' && args[1] === 'view' && UUID.test(args[2] || '')) {versionId=args[2]; prefix=['versions','view',versionId,'--json'];}
    else throw new Error();
    if (JSON.stringify(args) !== JSON.stringify([...prefix,...tail])) throw new Error();
    const undici = require(path.join(m.repository_root, 'ops/public-host-tooling/node_modules/undici'));
    undici.setGlobalDispatcher(makePublisherGuard(undici.getGlobalDispatcher(),m.account_id,m.worker_name,versionId,allowPut));
  } catch (_) {throw new Error('stage3 guard initialization failed');}
}

module.exports = {makePublisherGuard};
if (module.parent && module.parent.id === 'internal/preload') install();
