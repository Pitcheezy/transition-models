"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs");
const site = fs.existsSync(path.join(__dirname, "../dist"))
  ? path.join(__dirname, "../dist")
  : path.join(__dirname, "../pitch-studio");
const { assemble, createSession } = require(
  path.join(site, "receiver-contract.js"),
);
const fixture = require(path.join(site, "receiver-sample.js"));
const raw = () => {
  const packet = structuredClone(fixture);
  return {
    timeline: packet.timeline,
    at_bat_number: packet.at_bat_number,
    source: packet.source,
    reveals: packet.reveals.map(({ source_endpoint, response }) => ({
      source_endpoint,
      response,
    })),
  };
};
test("raw files use original index and request path, regardless of ordering", () => {
  const input = raw();
  input.timeline.decisions.reverse();
  input.reveals.reverse();
  input.reveals[0].source_endpoint =
    "https://example.org" + input.reveals[0].source_endpoint;
  const packet = assemble(input),
    session = createSession(packet);
  assert.deepEqual(
    packet.reveals.map((r) => r.pitch_id),
    ["900001:5:3", "900001:5:2", "900001:5:1"],
  );
  assert.equal(
    packet.reveals[0].source_endpoint,
    "/api/watch/900001/reveal/16",
  );
  assert.equal(session.view().pitch_id, "900001:5:1");
  assert.equal(session.view().post, null);
  session.reveal(true);
  session.next();
  session.reveal(true);
  assert.equal(session.view().post.actual.x, null);
  assert.equal(session.view().pre.status, "unsupported");
});
for (const [name, mutate] of [
  [
    "other game's original URL",
    (x) => {
      x.reveals[0].source_endpoint = "/api/watch/849843/reveal/14";
    },
  ],
  [
    "wrong original index",
    (x) => {
      x.reveals[0].source_endpoint = "/api/watch/900001/reveal/16";
    },
  ],
  [
    "missing original URL",
    (x) => {
      delete x.reveals[0].source_endpoint;
    },
  ],
  [
    "URL with credentials",
    (x) => {
      x.reveals[0].source_endpoint =
        "https://secret@example.org/api/watch/900001/reveal/14";
    },
  ],
  [
    "URL query",
    (x) => {
      x.reveals[0].source_endpoint += "?token=secret";
    },
  ],
  [
    "URL fragment",
    (x) => {
      x.reveals[0].source_endpoint += "#result";
    },
  ],
  [
    "non-HTTP URL",
    (x) => {
      x.reveals[0].source_endpoint = "file:///api/watch/900001/reveal/14";
    },
  ],
  [
    "unmatched response index",
    (x) => {
      x.reveals[0].response.index = 99;
    },
  ],
  [
    "other PA",
    (x) => {
      x.at_bat_number = 6;
    },
  ],
  [
    "duplicate reveal",
    (x) => {
      x.reveals[1] = x.reveals[0];
    },
  ],
  [
    "missing reveal",
    (x) => {
      x.reveals.pop();
    },
  ],
  [
    "empty reveals",
    (x) => {
      x.reveals = [];
    },
  ],
  [
    "internal final score",
    (x) => {
      x.timeline.game.final = { home: 4 };
    },
  ],
  [
    "internal post value",
    (x) => {
      x.timeline.decisions[0].actual = { x: 1 };
    },
  ],
  [
    "missing model",
    (x) => {
      delete x.source.model_id;
    },
  ],
  [
    "missing revision",
    (x) => {
      delete x.source.revision;
    },
  ],
  [
    "missing generation timestamp",
    (x) => {
      delete x.source.exported_at;
    },
  ],
  [
    "non-object timeline row",
    (x) => {
      x.timeline.decisions.unshift(null);
    },
  ],
])
  test(`raw assembly rejects ${name}`, () => {
    const input = raw();
    mutate(input);
    assert.throws(() => assemble(input));
  });
test("assembly retains null WE and does not manufacture new probabilities", () => {
  const input = raw();
  for (const key of Object.keys(input.reveals[0].response.we))
    input.reveals[0].response.we[key] = null;
  const session = createSession(assemble(input));
  assert.equal(session.view().pre.candidates[0].selection_probability, 0.48);
  session.reveal(true);
  assert.equal(session.view().post.we.home_delta, null);
  assert.equal("outcome_probabilities" in session.view().pre, false);
});
