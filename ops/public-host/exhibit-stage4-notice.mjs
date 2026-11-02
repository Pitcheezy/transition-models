/** One explicitly approved stage4 notice cycle; no deployment, uploads or credential changes. */
import { createStage4Transport } from './exhibit-stage4-transport.mjs';
import { executeNotice } from './notice-client.mjs';
const ROUTE = '/_notice/v1/state';
const fail = code => { throw new Error(code); };

async function auditCopy(response, signal) {
  const reader = response.body?.getReader();
  if (!reader) return { response, audit: [] };
  const chunks = []; let size = 0;
  try {
    while (true) {
      signal?.throwIfAborted();
      const { value, done } = await reader.read();
      if (done) break;
      size += value.length;
      if (size > 65536) { await reader.cancel(); fail('notice_body_limit'); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  const bytes = Buffer.concat(chunks);
  let audit = [];
  try { const v = JSON.parse(bytes.toString('utf8')); if (Array.isArray(v.audit)) audit = v.audit; } catch {}
  return { response: new Response(bytes, { status: response.status, headers: response.headers }), audit };
}

export async function runStage4Notice({ origin, token, outDir, versionPin, runId,
  onActive = async () => {}, onRestored = async () => {}, fetchImpl = fetch }) {
  if (!/^stage4-[a-z0-9-]{8,48}$/.test(runId || '')) fail('notice_run_id_invalid');
  const transport = await createStage4Transport({ origin, outDir, versionPin, limit: 8, reserve: 3,
    allowed: [{ method: 'GET', path: ROUTE }, { method: 'PUT', path: ROUTE }], fetchImpl });
  const reason = 'Approved exhibition acceptance ' + runId;
  const report = { schema: 'pitcheezy-stage4-notice-v1', passed: false, final_off_confirmed: false,
    initial_revision: null, expected_final_revision: null, operations: [], browser: null,
    cleanup: null, conflict: false, retries: 0, server_log_correlation: 'pending' };
  let initial = null, owned = null, onAttempted = false, onAck = false, normal = false, acknowledgedOnEtag = null;
  const owns = (state, audit, active, delta) => state && initial &&
    state.observed.revision === initial.observed.revision + delta && state.observed.active === active &&
    state.observed.message_id === 'maintenance' && !state.observed.audit_unavailable &&
    audit.some(a => a && a.schema === 'pitcheezy-notice-audit-v1' && a.operator === runId &&
      a.reason === reason && a.revision === state.observed.revision && a.active === active &&
      a.message_id === 'maintenance' && a.etag_after === state.condition.if_match);
  async function invoke(method, condition = null, active = null, cleanup = false) {
    let audit = [], responseEtag = null;
    const plan = { schema: 'pitcheezy-notice-plan-v1', origin, allow_loopback_http: false,
      method, condition, change: method === 'PUT' ? { active, operator: runId, reason, message_id: 'maintenance' } : null };
    const result = await executeNotice(plan, token, { timeoutMs: 15000, fetchImpl: async (url, init) => {
      const response = await (cleanup ? transport.cleanupFetch : transport.fetch)(url, init);
      responseEtag = response.headers.get('ETag');
      if (method !== 'GET' || response.status !== 200) return response;
      const copy = await auditCopy(response, init.signal); audit = copy.audit; return copy.response;
    } });
    report.operations.push({ ...result.receipt, cleanup });
    if (result.receipt.outcome === 'conflict') report.conflict = true;
    return { ...result, audit, responseEtag };
  }
  try {
    const before = await invoke('GET');
    if (before.receipt.outcome !== 'observed' || !before.snapshot || before.snapshot.observed.active) fail('initial_notice_not_confirmed_off');
    initial = before.snapshot;
    report.initial_revision = initial.observed.revision;
    report.expected_final_revision = initial.observed.revision + 2;
    onAttempted = true;
    const on = await invoke('PUT', initial.condition, true);
    if (['applied','applied_audit_missing'].includes(on.receipt.outcome) && on.receipt.revision === initial.observed.revision + 1) acknowledgedOnEtag = on.responseEtag;
    onAck = on.receipt.outcome === 'applied' && on.receipt.revision === initial.observed.revision + 1;
    if (!onAck) fail('notice_on_not_fully_acknowledged');
    const after = await invoke('GET');
    if (after.receipt.outcome !== 'observed' || !owns(after.snapshot, after.audit, true, 1)) fail('notice_on_ownership_not_confirmed');
    owned = after.snapshot;
    report.browser = await onActive();
    normal = true;
  } catch (error) {
    report.failure = /^[a-z_]{1,80}$/.test(error?.message || '') ? error.message : 'notice_observation_failed';
  } finally {
    if (onAttempted) {
      // A lost PUT acknowledgement is resolved by a read, never a repeated ON.
      if (!owned && !report.conflict) {
        const check = await invoke('GET', null, null, true);
        const ackOwned = acknowledgedOnEtag && check.snapshot?.condition.if_match === acknowledgedOnEtag &&
          check.snapshot.observed.active && check.snapshot.observed.revision === initial.observed.revision + 1;
        if (owns(check.snapshot, check.audit, true, 1) || ackOwned) owned = check.snapshot;
        else if (check.receipt.outcome === 'observed' && check.snapshot.observed.active === false &&
          check.snapshot.observed.revision === initial.observed.revision &&
          JSON.stringify(check.snapshot.condition) === JSON.stringify(initial.condition)) {
          report.final_off_confirmed = true; report.cleanup = 'unchanged_off';
        } else report.cleanup = 'ownership_unknown_stop';
      }
      if (owned && !report.conflict) {
        // Even after a browser error, turn off only the revision owned by this run.
        const off = await invoke('PUT', owned.condition, false, true);
        const final = await invoke('GET', null, null, true);
        report.final_off_confirmed = final.receipt.outcome === 'observed' && owns(final.snapshot, final.audit, false, 2);
        report.cleanup = report.final_off_confirmed ? 'own_revision_off_confirmed' : 'off_not_confirmed_stop';
        if (off.receipt.outcome !== 'applied') { normal = false; report.failure ??= 'notice_off_not_fully_acknowledged'; }
      }
      if (report.conflict) { normal = false; report.cleanup = 'conflict_no_overwrite'; }
    }
  }
  if (normal && report.final_off_confirmed) {
    try { report.restored = await onRestored(); }
    catch { normal = false; report.failure ??= 'browser_restore_failed'; }
  }
  report.transport = transport.summary();
  report.passed = normal && onAck && report.final_off_confirmed && !report.failure && !report.conflict;
  return report;
}
