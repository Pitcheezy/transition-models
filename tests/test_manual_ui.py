"""Exercise the real manual UI with deferred requests and a minimal Node DOM."""

import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "src/web/static/app.js"
NODE = shutil.which("node")

HARNESS = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

class Element {
  constructor(name = "") {
    this.name = name;
    this.value = "";
    this.textContent = "";
    this.hidden = false;
    this.disabled = false;
    this.src = "";
    this.loadCount = 0;
    this.children = [];
    this.style = {};
    this.listeners = {};
    this.classes = new Set();
    this.classList = {toggle: (name, on) => {
      if (on) this.classes.add(name);
      else this.classes.delete(name);
    }};
  }
  set value(value) { this._value = String(value); }
  get value() { return this._value; }
  addEventListener(type, handler) { this.listeners[type] = handler; }
  emit(type) { return this.listeners[type]?.({preventDefault() {}}); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  removeAttribute(name) { if (name === "src") this.src = ""; }
  load() { this.loadCount++; }
}
const nodes = new Map();
const el = id => {
  if (!nodes.has(id)) nodes.set(id, new Element());
  return nodes.get(id);
};
const fields = Object.fromEntries(
  ["balls", "pitcher", "inning"].map(name => [name, new Element(name)])
);
fields.balls.value = "1";
fields.pitcher.value = "123";
fields.inning.value = "1";
el("state-form").elements = Object.values(fields);
el("prediction").hidden = true;
el("video").hidden = true;
const calls = [];
const context = vm.createContext({
  document: {
    querySelector: selector => el(selector.slice(1)),
    createElement: () => new Element(),
  },
  FormData: class {
    constructor(form) { this.form = form; }
    *[Symbol.iterator]() {
      for (const field of this.form.elements) yield [field.name, field.value];
    }
  },
  fetch: (url, options) => new Promise((resolve, reject) => {
    calls.push({url, options, resolve, reject});
  }),
});
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);
const flush = () => new Promise(setImmediate);
const matching = url => calls.filter(call => call.url === url);
const last = url => matching(url).at(-1);
const example = () => {
  el("example").emit("click");
  return last("/api/example");
};
const predict = () => {
  el("state-form").emit("submit");
  return last("/api/predict");
};
const edit = value => {
  fields.balls.value = value;
  el("state-form").emit("input");
};
const reply = async (call, body) => {
  assert.ok(call, "Expected a pending request");
  call.resolve({ok: true, json: async () => body});
  await flush();
};
const fail = async (call, message = "old request failed") => {
  call.reject(new Error(message));
  await flush();
};
const sample = (balls, video_url = null) => ({
  state: {balls, pitcher: 123, inning: 1}, video_url,
});
const output = (elapsed_ms = 1) => ({
  recommendation: "FF", empirical_recommendation: "FF", elapsed_ms, reason: null,
  candidates: [{action: "FF", supported: true, expected_cost: 0.1,
    display_probabilities: {hit: 0.2}, legacy_probabilities: {Ball: 0.8, Single: 0.2}}],
});
"""

SCENARIOS = {
    "normal_startup_and_prediction": r"""
await reply(last("/api/health"), {status: "ready"});
assert.equal(matching("/api/example").length, 1);
await reply(last("/api/example"), sample(0, "/video"));
assert.equal(fields.balls.value, "0");
assert.equal(el("video").hidden, false);
assert.equal(el("video-empty").hidden, true);
const active = predict();
assert.equal(JSON.parse(active.options.body).balls, 0);
assert.equal(el("predict").disabled, true);
await reply(active, output(17));
assert.equal(el("prediction").hidden, false);
assert.equal(el("predict").disabled, false);
assert.match(el("latency").textContent, /17 ms/);
assert.equal(el("hit").textContent, "20.00%");
""",
    "late_health_success_after_edit": r"""
edit(2);
const notice = el("notice").textContent;
await reply(last("/api/health"), {status: "ready"});
assert.equal(matching("/api/example").length, 0);
assert.equal(fields.balls.value, "2");
assert.equal(el("notice").textContent, notice);
assert.match(el("health").textContent, /준비 완료/);
""",
    "late_health_error_after_edit": r"""
edit(2);
const notice = el("notice").textContent;
await fail(last("/api/health"), "health unavailable");
assert.equal(el("notice").textContent, notice);
assert.equal(el("notice").classes.has("error"), false);
assert.equal(el("health").textContent, "연결 실패");
""",
    "late_health_does_not_dispatch_second_example": r"""
const active = example();
await reply(active, sample(2));
await reply(last("/api/health"), {status: "ready"});
assert.equal(matching("/api/example").length, 1);
assert.equal(fields.balls.value, "2");
""",
    "stale_example_success_after_edit": r"""
const old = example();
edit(2);
const notice = el("notice").textContent;
await reply(old, sample(0, "/old-video"));
assert.equal(fields.balls.value, "2");
assert.equal(el("notice").textContent, notice);
assert.equal(el("video").hidden, true);
""",
    "stale_example_error_after_edit": r"""
const old = example();
edit(2);
const notice = el("notice").textContent;
await fail(old);
assert.equal(el("notice").textContent, notice);
assert.equal(el("notice").classes.has("error"), false);
""",
    "reverse_examples_keep_latest_success_and_ignore_old_error": r"""
const oldest = example();
const middle = example();
const latest = example();
await reply(latest, sample(3, "/latest-video"));
const notice = el("notice").textContent;
await reply(middle, sample(1, "/middle-video"));
assert.equal(fields.balls.value, "3");
assert.equal(el("video").src, "/latest-video");
await fail(oldest);
assert.equal(el("notice").textContent, notice);
assert.equal(el("notice").classes.has("error"), false);
""",
    "stale_examples_cannot_replace_new_prediction": r"""
const oldest = example();
const old = example();
await reply(predict(), output(23));
const notice = el("notice").textContent;
await reply(old, sample(0));
assert.equal(el("prediction").hidden, false);
assert.equal(fields.balls.value, "1");
await fail(oldest);
assert.equal(el("notice").textContent, notice);
assert.match(el("latency").textContent, /23 ms/);
""",
    "example_dispatch_hides_old_visible_prediction": r"""
await reply(predict(), output());
assert.equal(el("prediction").hidden, false);
example();
assert.equal(el("prediction").hidden, true);
assert.equal(el("latency").textContent, "다시 계산 필요");
el("hit").textContent = "unchanged";
el("candidate").emit("change");
assert.equal(el("hit").textContent, "unchanged");
""",
    "example_dispatch_invalidates_pending_prediction": r"""
const old = predict();
example();
assert.equal(el("predict").disabled, false);
const notice = el("notice").textContent;
await reply(old, output());
assert.equal(el("prediction").hidden, true);
assert.equal(el("notice").textContent, notice);
""",
    "old_prediction_finally_cannot_unlock_new_prediction": r"""
const old = predict();
edit(2);
assert.equal(el("predict").disabled, false);
const active = predict();
const notice = el("notice").textContent;
await fail(old);
assert.equal(el("predict").disabled, true);
assert.equal(el("notice").textContent, notice);
assert.equal(el("prediction").hidden, true);
await reply(active, output(31));
assert.equal(el("predict").disabled, false);
assert.equal(el("prediction").hidden, false);
assert.match(el("latency").textContent, /31 ms/);
""",
    "latest_example_without_video_clears_old_video": r"""
await reply(example(), sample(1, "/previous-video"));
await reply(example(), sample(2));
assert.equal(el("video").src, "");
assert.equal(el("video").hidden, true);
assert.equal(el("video-empty").hidden, false);
assert.equal(el("video").loadCount, 1);
""",
    "current_example_error_does_not_mark_health_failed": r"""
await reply(last("/api/health"), {status: "ready"});
await fail(last("/api/example"), "example unavailable");
assert.equal(el("notice").textContent, "example unavailable");
assert.equal(el("notice").classes.has("error"), true);
assert.match(el("health").textContent, /준비 완료/);
""",
    "current_prediction_error_is_visible_and_unlocks_button": r"""
await fail(predict(), "prediction unavailable");
assert.equal(el("notice").textContent, "prediction unavailable");
assert.equal(el("notice").classes.has("error"), true);
assert.equal(el("prediction").hidden, true);
assert.equal(el("predict").disabled, false);
""",
}


@pytest.mark.skipif(NODE is None, reason="Node.js is required for browser behavior checks")
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_manual_ui_request_order(scenario):
    script = (
        HARNESS
        + "\n(async () => {\n"
        + SCENARIOS[scenario]
        + r"""
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    )
    completed = subprocess.run(
        [NODE, "-", str(APP)],
        input=script,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
