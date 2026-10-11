"use strict";
// Local file inspection only; imports the same contract as the browser.
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { validate } = require("../web/pitch-studio/receiver-contract.js");
const args = process.argv.slice(2);
if (args.length !== 1 || args[0] === "--help") {
  console.log("Usage: node scripts/check_pitch_receiver.cjs FILE.json\nReads only. Validates our transfer envelope, not source authenticity or model quality.");
  process.exit(args[0] === "--help" ? 0 : 2);
}
try {
  const file = path.resolve(args[0]);
  if (fs.statSync(file).size > 5 * 1024 * 1024) throw new Error("Maximum input size: 5MB");
  const bytes = fs.readFileSync(file);
  const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  const data = validate(JSON.parse(text));
  console.log(JSON.stringify({
    status: "structure_and_binding_checks_passed",
    source_authenticated: false,
    live_model_connected: false,
    sha256: crypto.createHash("sha256").update(bytes).digest("hex"),
    source_kind: data.source.kind,
    declared_model_id: data.source.model_id,
    game_pk: data.game.game_pk,
    at_bat_number: data.at_bat_number,
    decisions: data.decisions.length,
    reveals: data.decisions.length,
    cv_video_identity_verified: false,
  }, null, 2));
} catch (error) {
  console.error(`Invalid response package: ${error.message}`);
  process.exitCode = 1;
}
