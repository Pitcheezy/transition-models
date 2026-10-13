/**
 * Optional session measurement. No persistent storage, URLs or page contents; the client never reads or
 * writes cookies. Collection requests omit credentials unless the deployment turns the viewer access gate
 * on (`accessGate`), because the gate protects these routes too; then only same-origin cookies travel
 * with the request and the server stores none of them.
 */
const RATINGS = new Set(["helpful", "unclear", "problem"]);
const REASONS = new Set(["none", "recommendation", "explanation", "delay", "display", "other"]);
const validGame = n => Number.isSafeInteger(n) && n >= 0 && n <= 999999999999;
/** Explicit deployment settings, not an approval or a server configuration probe. */
export function collectionSettings(options = {}) {
  const retainDays = Number.isInteger(options.retainDays) && options.retainDays >= 1 && options.retainDays <= 90 ? options.retainDays : null;
  return Object.freeze({ retainDays,
    telemetryEnabled: retainDays !== null && options.telemetryEnabled === true,
    feedbackEnabled: retainDays !== null && options.feedbackEnabled === true,
    // Must equal the server's ACCESS_GATE_ENABLED (enforced by the offline config check).
    accessGate: options.accessGate === true });
}
export function createUsageClient(options = {}) {
  const settings = collectionSettings(options);
  const fetchFn = options.fetchFn || globalThis.fetch.bind(globalThis);
  const now = options.now || (() => performance.now());
  const wall = options.wall || (() => Date.now());
  const visible = options.visible || (() => document.visibilityState === "visible");
  const optedOut = options.optedOut || (() => navigator.doNotTrack === "1" || navigator.globalPrivacyControl === true);
  const uuid = options.uuid || (() => crypto.randomUUID());
  const status = options.onStatus || (() => {});
  let game = options.gamePk ?? 0;
  if (!validGame(game)) throw new Error("invalid_game");
  let consent = false, session = null, feedback = null, destroyed = false, accessStopped = false;
  const day = () => new Date(wall()).toISOString().slice(0,10);
  const permitted = () => !destroyed && !optedOut();
  const allowedSession = () => settings.telemetryEnabled && permitted();
  const allowedFeedback = () => settings.feedbackEnabled && permitted();
  const abort = value => value?.controller?.abort();
  // The gate answers before collection runs, so this refusal is certain: nothing was stored.
  const accessRefused = response => response.status === 401 && response.headers?.get?.("X-Pitcheezy-Access") === "required";
  function freshSession() {
    abort(session);
    session = { id: uuid(), day: day(), game, sequence: 0, active: 0, started: false,
      last: now(), visible: visible(), pending: null, running: false, failures: 0, retryAt: 0, paused: false };
  }
  function sample() {
    if (!session) return;
    if (session.day !== day()) freshSession();
    const time = now();
    if (session.started && session.visible) {
      // Long sleep/throttling gaps cannot establish foreground time. Deliberately undercount.
      const delta = time-session.last;
      if (delta >= 0 && delta <= 60000) session.active = Math.min(28800000,session.active+delta);
    }
    session.last=time; session.visible=visible();
  }
  async function transmit(route, body, target) {
    const controller=new AbortController(); target.controller=controller;
    let rejectAbort;
    const aborted=new Promise((_,reject)=>{rejectAbort=()=>reject(new Error("request_aborted"));});
    controller.signal.addEventListener("abort",rejectAbort,{once:true});
    const timeout=setTimeout(()=>controller.abort(),5000);
    try {
      const response=await Promise.race([fetchFn(route,{method:"POST",headers:{"Content-Type":"application/json"},
        credentials:settings.accessGate?"same-origin":"omit",referrerPolicy:"no-referrer",cache:"no-store",redirect:"error",keepalive:true,
        body:JSON.stringify(body),signal:controller.signal}),aborted]);
      const ack=response.ok ? await Promise.race([response.json(),aborted]) : null;
      return {ok:response.ok,status:response.status,headers:response.headers,ack};
    } finally {
      clearTimeout(timeout);controller.signal.removeEventListener("abort",rejectAbort);
      if(target.controller===controller)target.controller=null;
    }
  }
  async function flush() {
    if (!consent || !allowedSession()) { if(consent) withdraw(); return false; }
    sample();
    const target=session;
    if (target.running || target.paused || now()<target.retryAt) return false;
    target.pending ||= {v:1,consent:true,session_id:target.id,game_pk:target.game,
      sequence:target.started ? target.sequence+1 : 0,active_ms:target.started ? Math.floor(target.active) : 0};
    const pending=target.pending; target.running=true;
    try {
      const response=await transmit("/_telemetry/session",pending,target);
      if (session!==target || !consent || !allowedSession()) return false;
      if (accessRefused(response)) {
        // Viewer session expired or missing: participation ends here. Consent is dropped (the widget unchecks the
        // box) so a game or UTC day change cannot restart sending; only a new explicit choice after re-entry does.
        consent=false; session=null; accessStopped=true; status("access_required"); return false;
      }
      if (!response.ok) {
        if ([400,403,409,413,415].includes(response.status)) target.paused=true;
        const retry=Number(response.headers.get("Retry-After"));
        target.retryAt=now()+Math.max(30000,Math.min(300000,Number.isFinite(retry)?retry*1000:30000));
        throw new Error("collection_failed");
      }
      const ack=response.ack;
      if (ack?.accepted!==true) throw new Error("invalid_ack");
      if (session!==target || !consent || !allowedSession()) return false;
      if (!target.started) { target.active=0; target.last=now(); target.visible=visible(); target.started=true; }
      target.sequence=pending.sequence; target.pending=null; target.failures=0;
      status("active"); return true;
    } catch {
      if(session===target && consent) {
        target.failures++; if(target.failures>=3) target.paused=true;
        status(target.paused?"paused":"retry");
      }
      return false;
    } finally { target.running=false; }
  }
  function grant() {
    if (!allowedSession()) { status("disabled"); return Promise.resolve(false); }
    if(consent) return flush();
    consent=true; accessStopped=false; freshSession(); status("starting"); return flush();
  }
  function withdraw() {
    consent=false; abort(session); session=null; status("off");
  }
  function setGame(gamePk) {
    if(!validGame(gamePk)) throw new Error("invalid_game");
    if(game===gamePk) return;
    // Abort pending work; already stored requests cannot be recalled. Never attach old game time to new game.
    game=gamePk; abort(feedback); feedback=null;
    if(consent) { freshSession(); void flush(); }
  }
  async function sendFeedback(rating, reason="none") {
    if(!allowedFeedback() || !RATINGS.has(rating) || !REASONS.has(reason)) return {ok:false,disabled:true};
    if(feedback?.running || feedback?.done) return {ok:feedback?.done===true,busy:feedback?.running===true};
    if(feedback && (feedback.body.rating!==rating || feedback.body.reason!==reason || feedback.day!==day())) {
      return {ok:false,uncertain:true}; // A lost acknowledgement must not create a second response.
    }
    feedback ||= {day:day(),body:{v:1,consent:true,feedback_id:uuid(),game_pk:game,rating,reason},running:false,done:false};
    const target=feedback; target.running=true;
    try {
      const response=await transmit("/_telemetry/feedback",target.body,target);
      if(accessRefused(response)) {
        // Certain only for THIS request. An earlier uncertain attempt of the same record may be stored, so keep
        // that record (same id and rating) rather than allowing a second response after re-entry.
        if(target.uncertain) return {ok:false,accessRequired:true,uncertain:true};
        if(feedback===target) feedback=null;
        return {ok:false,accessRequired:true};
      }
      if(!response.ok || response.ack?.accepted!==true) { target.uncertain=true; return {ok:false,uncertain:true}; }
      if(feedback!==target || !allowedFeedback()) { target.uncertain=true; return {ok:false,uncertain:true}; }
      target.done=true; return {ok:true};
    } catch { target.uncertain=true; return {ok:false,uncertain:true}; }
    finally {target.running=false;}
  }
  function destroy() {withdraw();destroyed=true;abort(feedback);feedback=null;}
  return {grant,withdraw,setGame,flush,sample,sendFeedback,destroy,
    get state(){return {telemetryEnabled:allowedSession(),feedbackEnabled:allowedFeedback(),retainDays:settings.retainDays,consent,gamePk:game,started:session?.started===true,
      accessGate:settings.accessGate,accessRequired:accessStopped};}};
}
