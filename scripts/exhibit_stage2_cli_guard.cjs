'use strict';

const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');
const MANIFEST_SHA = '2f8ae745122b04e2d6eef025db0841de46f6f672407a0d8b6c00b85b502f5e6b';
const CONFIG_SHA = 'a7c4464ed07c29830a508b612c45baf00eb9faf60e4806d76fc50d35c5097b77';

function makeGuard(delegate, account, worker) {
  if (!/^[a-f0-9]{32}$/i.test(account) || !/^[a-z0-9][a-z0-9-]*$/.test(worker)) throw new Error('guard configuration invalid');
  const prefix = `/client/v4/accounts/${account}/workers/scripts/${worker}`;
  let putCount = 0;
  return {
    dispatch(opts, handler) {
      const target = opts.path;
      const noQuery = target === `${prefix}/deployments` || target === `${prefix}/secrets`;
      const limitQuery = new RegExp(`^${prefix}/(?:deployments|secrets)\\?limit=[0-9]+$`).test(target);
      const allowedGet = opts.method === 'GET' && (noQuery || limitQuery);
      const allowedPut = opts.method === 'PUT' && target === `${prefix}/secrets` && putCount === 0;
      if (opts.origin !== 'https://api.cloudflare.com' || !(allowedGet || allowedPut)) {
        handler.onError(new Error('guard blocked request'));
        return false;
      }
      if (allowedPut) putCount++;
      return delegate.dispatch(opts, handler);
    }
  };
}

function install() {
  try {
    if (process.env.WRANGLER_WRITE_LOGS !== 'false') throw new Error();
    const bytes = fs.readFileSync(process.env.PITCHEEZY_STAGE2_MANIFEST);
    if (crypto.createHash('sha256').update(bytes).digest('hex') !== MANIFEST_SHA) throw new Error();
    const manifest = JSON.parse(bytes.toString('utf8').replace(/^\uFEFF/, ''));
    const config = fs.readFileSync(manifest.configuration_file);
    if (crypto.createHash('sha256').update(config).digest('hex') !== CONFIG_SHA || JSON.parse(config).name !== manifest.worker_name) throw new Error();
    const undici = require(path.join(manifest.repository_root, 'ops/public-host-tooling/node_modules/undici'));
    undici.setGlobalDispatcher(makeGuard(undici.getGlobalDispatcher(), manifest.account_id, manifest.worker_name));
  } catch (_) {
    throw new Error('stage2 guard initialization failed');
  }
}

module.exports = { makeGuard };
if (module.parent && module.parent.id === 'internal/preload') install();
