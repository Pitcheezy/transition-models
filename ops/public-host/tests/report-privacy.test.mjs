import test from "node:test";
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { readFile, writeFile, readdir } from "node:fs/promises";
import { join } from "node:path";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { buildReport } from "../report.mjs";
import { createTestDirectory } from "./helpers/owned-temp.mjs";

const NOW = Date.parse("2026-10-20T01:00:00Z");
const base = () => ({
  schema: "pitcheezy-game-report-input-v1", game_pk: 123, evidence: "synthetic",
  window: { from: "2026-10-19T00:00:00Z", to: "2026-10-19T23:59:59Z" },
  collection: { telemetry_enabled: false, feedback_enabled: false, consent_note: "합성 검사", retain_days: null },
  usage_summary: null, monitor_state: null, notice_audit: null, alert_state: null, actions: [],
  sources: { host_commit: "a".repeat(40), frontend_commit: "b".repeat(40),
    contract_version: "public-file-v1-draft-v0", release_manifest_sha256: "c".repeat(64) },
  commands: [], unmeasured: [], notes: "",
});
const build = input => buildReport(input, { now: NOW });
const privateShapes = {
  email: "reviewer+trial@example.invalid",
  uppercase_email: "Reviewer@Example.INVALID",
  ipv4: "192.0.2.1",
  ipv4_port: "192.0.2.1:8771",
  ipv6: "2001:db8::1",
  ipv6_port: "[2001:db8::1]:8771",
  ipv6_loopback: "[::1]:8771",
  ipv6_zone: "[fe80::1%eth0]:8771",
  windows: String.raw`C:\Users\Example\private\notes.json`,
  windows_slashes: "C:/Users/Example/private/notes.json",
  unc: String.raw`\\device\private\notes.json`,
  unc_slashes: "//device/private/notes.json",
  mac_home: "/Users/example/private/notes.json",
  linux_home: "/home/example/private/notes.json",
  root_home: "/root/private/notes.json",
  shell_home: "~/private/notes.json",
  named_shell_home: "~example/private/notes.json",
  ssh_url: "ssh://example.invalid:22",
  file_url: "file:///private/notes.json",
};

for (const [kind, value] of Object.entries(privateShapes)) {
  test(`report refuses ${kind} before constructing public output`, () => {
    assert.throws(() => build({ ...base(), notes: "합성 입력 " + value }),
      { code: "secret_or_address_like_content" });
  });
}

test("privacy check covers every unconstrained text destination that reaches the draft", () => {
  const value = privateShapes.email;
  const audit = { schema: "pitcheezy-notice-audit-v1", at: "2026-10-19T10:00:00Z",
    active: true, message_id: "maintenance", operator: "ops", reason: "synthetic" };
  const changes = [
    input => { input.notes = value; },
    input => { input.commands = ["notify " + value]; },
    input => { input.actions = [{ at: "2026-10-19T10:00:00Z", by: "ops", what: value }]; },
    input => { input.collection.consent_note = value; },
    input => { input.unmeasured = [value]; },
    input => { input.sources.contract_version = value; },
    ...["operator", "reason", "message_id"].map(field => input => {
      input.notice_audit = [{ ...audit, [field]: value }];
    }),
  ];
  for (const change of changes) {
    const input = base(); change(input);
    assert.throws(() => build(input), { code: "secret_or_address_like_content" });
  }
});

test("normal commands, API routes, Korean notes, measurements and fixed source hashes remain usable", () => {
  const input = base();
  input.commands = ["node ops/public-host/report-cli.mjs --input ./input.json --output-dir .cache/reports",
    String.raw`python scripts\check_project.py --cpu-only`, "node -e 'console.log(123)'", "git show 0123456789abcdef"];
  input.notes = "합성 결과: 97.8%, 0.13초, 2.53px. Node v24.1.0, 예시 버전 v1.2.3.4, 12:34:56. " +
    "GET /v1/health.json 및 ../docs/WS_OPERATIONS_HANDOFF.md를 확인. 999.999.999.999는 IP가 아닌 합성 문자열.";
  const result = build(input);
  assert.equal(result.json.sources.host_commit, input.sources.host_commit);
  assert.equal(result.json.sources.release_manifest_sha256, input.sources.release_manifest_sha256);
  assert.match(result.markdown, /97\.8%/);
  assert.match(result.markdown, /report-cli\.mjs/);
  assert.equal(result.json.usage.status, "collection_off");
});

test("CLI refuses identifying input without creating report, lock or temporary output", async t => {
  const dir = await createTestDirectory(t);
  const path = join(dir, "input.json");
  const source = JSON.stringify({ ...base(), notes: privateShapes.email });
  await writeFile(path, source, { flag: "wx" });
  const script = fileURLToPath(new URL("../report-cli.mjs", import.meta.url));
  await assert.rejects(promisify(execFile)(process.execPath, [script, "--input", path, "--output-dir", dir]), error => {
    assert.equal(error.code, 2);
    assert.equal(error.stdout, "");
    assert.equal(JSON.parse(error.stderr).code, "secret_or_address_like_content");
    assert.equal(error.stderr.includes(privateShapes.email), false);
    return true;
  });
  assert.deepEqual(await readdir(dir), ["input.json"]);
  assert.equal(await readFile(path, "utf8"), source);
});
