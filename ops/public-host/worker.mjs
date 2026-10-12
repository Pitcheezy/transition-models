import gateway from "./gateway.mjs";
import { cleanupTelemetry } from "./telemetry.mjs";
export default {
  fetch: gateway.fetch,
  async scheduled(_event, env) {
    try { await cleanupTelemetry(env); }
    catch { throw new Error("telemetry_cleanup_failed"); }
  },
};
