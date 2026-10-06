"use strict";
// Usage: node build-first-pa.cjs <received JSON directory> <output JS file>
// Raw capture files remain outside the website. Export only the first PA's display fields.
const fs = require("node:fs"),
  path = require("node:path"),
  crypto = require("node:crypto");
const assert = require("node:assert/strict");
const [inputDir, outputFile] = process.argv.slice(2);
assert(inputDir && outputFile, "Provide an input directory and output JS file");
const read = (name) => fs.readFileSync(path.join(inputDir, name));
const json = (name) => JSON.parse(read(name));
const sha = (bytes) => crypto.createHash("sha256").update(bytes).digest("hex");
const manifest = json("manifest.json");
const names = [
  "watch-games.json",
  "watch-849843.json",
  "reveal-0.json",
  "reveal-1.json",
  "reveal-2.json",
];
const originals = names.map((name) => {
  const record = manifest.files.find((f) => f.file === name);
  const raw = read(name);
  assert(record && record.http_status === 200);
  assert.equal(raw.length, record.bytes, `${name}: byte count mismatch`);
  assert.equal(sha(raw), record.sha256, `${name}: SHA256 mismatch`);
  return { name, hash: record.sha256 };
});
const watch = json("watch-849843.json");
assert.equal(watch.game.game_pk, 849843);
assert.equal(watch.decisions.length, 262);
assert.equal(
  watch.decisions.filter((d) => d.pre.status === "ready").length,
  246,
);
const selected = watch.decisions.filter((d) => d.at_bat_number === 1);
assert.deepEqual(
  selected.map((d) => d.index),
  [0, 1, 2],
);
assert.deepEqual(
  selected.map((d) => `${d.pa_id}:${d.pitch_number}`),
  manifest.scope.first_pa_pitch_ids,
);
const pick = (object, keys) =>
  Object.fromEntries(
    keys.filter((k) => Object.hasOwn(object, k)).map((k) => [k, object[k]]),
  );
const timeline = {
  schema: watch.schema,
  game: pick(watch.game, [
    "game_pk",
    "date",
    "game_type",
    "away_team",
    "home_team",
  ]),
  decisions: selected.map((d) => ({
    ...pick(d, [
      "index",
      "pa_id",
      "at_bat_number",
      "pitch_number",
      "situation",
      "pitcher",
      "batter",
    ]),
    pre: {
      status: d.pre.status,
      reason: null,
      recommendation: {
        candidates: d.pre.recommendation.candidates.map((c) => ({
          ...pick(c, [
            "rank",
            "pitch_type",
            "pitch_label",
            "zone_id",
            "zone_label",
            "target",
          ]),
          detail: { probability: c.detail.probability },
        })),
      },
    },
  })),
};
const { assemble } = require(
  path.resolve(path.dirname(outputFile), "receiver-contract.js"),
);
const packet = assemble({
  timeline,
  at_bat_number: 1,
  source: {
    kind: "provided_export",
    revision: manifest.generated_result.generator_git_commit,
    model_id: manifest.generated_result.policy_name,
    exported_at: manifest.generated_result.generated_kst,
  },
  reveals: selected.map((d) => {
    const record = manifest.files.find(
      (f) => f.file === `reveal-${d.index}.json`,
    );
    const response = json(record.file);
    assert.equal(response.index, d.index);
    return {
      source_endpoint: new URL(record.url).pathname,
      response: {
        index: response.index,
        actual: pick(response.actual, [
          "pitch_type",
          "pitch_label",
          "description",
          "result_label",
          "event_label",
          "speed_mph",
          "x",
          "z",
        ]),
        we: response.we,
      },
    };
  }),
});
const value = {
  packet,
  originals,
  provenance: {
    capture_manifest_sha256: sha(read("manifest.json")),
    policy_identity_sha256: manifest.generated_result.policy_identity_sha256,
    loaded_backend_commit: manifest.service.loaded_backend_commit,
    scope:
      "First PA display fields only; original private bundle is not published.",
  },
};
const text = JSON.stringify(value, null, 2);
assert(
  !/100\.108\.|\/Users\/|serving_worktree|process_started|source_media|observer-zone-v1/.test(
    text,
  ),
);
fs.writeFileSync(
  outputFile,
  `/* Supplied model responses, display projection only. Not a live model call. */\n(function(root) {\nconst value = ${text};\nif(typeof module === "object" && module.exports) module.exports = value;\nelse root.PitchReceiverDemo849843 = value;\n})(typeof globalThis === "object" ? globalThis : this);\n`,
);
console.log(
  "Verified five original hashes; exported first PA only (3 decisions / 3 reveals).",
);
