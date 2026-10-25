"""CV-34 sequence review: separate interval/centre fields, blind pack, seeded double sample."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from intent import sequence_review as sr

HASH = "b" * 64
SCRIPT = Path(__file__).resolve().parents[1] / "intent/sequence_review.js"


def manifest():
    return {
        "schema": sr.PACK_SCHEMA,
        "sequences": [
            {
                "sequence_id": sid,
                "fps_nominal": 10,
                "frames": [
                    {
                        "n": n,
                        "path": f"frames/{sid}/{n:03d}.jpg",
                        "sha256": "c" * 64,
                        "width": 1280,
                        "height": 720,
                        "seconds_from_start": round(0.1 * (n - 1), 3),
                    }
                    for n in range(1, 21)
                ],
            }
            for sid in ("seq_a", "seq_b")
        ],
    }


def held(response):
    row = response["rows"][0]
    row.update(
        presentation="held_seen",
        hold_start_n=5,
        hold_end_n=9,
        point_n=7,
        mitt=[612.5, 233.0],
        visibility="full",
        delivery_start_n=14,
    )
    response["reviewer_id"] = "r1"
    return response


def test_blank_response_is_a_valid_draft_and_a_reviewed_row_needs_every_part():
    m = manifest()
    blank = sr.blank_response(m, HASH)
    sr.validate_response(m, HASH, blank)
    good = held(copy.deepcopy(blank))
    sr.validate_response(m, HASH, good)
    bad_cases = [
        {"point_n": 10},  # centre frame outside the held interval
        {"hold_start_n": 9, "hold_end_n": 5},
        {"visibility": "hidden"},
        {"mitt": [1300, 10]},
        {"delivery_start_n": None},  # needs a frame or a note
        {"hold_end_n": 21},
    ]
    for change in bad_cases:
        case = copy.deepcopy(good)
        case["rows"][0].update(change)
        with pytest.raises(ValueError):
            sr.validate_response(m, HASH, case)
    noted = copy.deepcopy(good)
    noted["rows"][0].update(delivery_start_n=None, delivery_note="pitcher out of frame")
    sr.validate_response(m, HASH, noted)


def test_only_held_seen_carries_interval_and_point_and_others_need_a_reason():
    m = manifest()
    response = sr.blank_response(m, HASH)
    response["reviewer_id"] = "r1"
    row = response["rows"][1]
    row.update(presentation="no_clear_hold", delivery_start_n=12)
    with pytest.raises(ValueError):
        sr.validate_response(m, HASH, response)
    row["reason"] = "mitt keeps moving"
    sr.validate_response(m, HASH, response)
    row["hold_start_n"] = 3
    with pytest.raises(ValueError):
        sr.validate_response(m, HASH, response)


def test_reviewer_id_schema_and_hash_are_enforced():
    m = manifest()
    good = held(sr.blank_response(m, HASH))
    for mutate in (
        lambda r: r.update(reviewer_id=" "),
        lambda r: r.update(manifest_sha256="d" * 64),
        lambda r: r.update(schema="other"),
        lambda r: r["rows"].pop(),
        lambda r: r["rows"][0].update(extra=1),
    ):
        case = copy.deepcopy(good)
        mutate(case)
        with pytest.raises(ValueError):
            sr.validate_response(m, HASH, case)


def test_double_review_sample_is_seeded_fixed_size_and_order_free():
    ids = [f"seq_{i:02d}" for i in range(39)]
    first = sr.double_assignment(ids, "seed-1")
    assert len(first) == round(0.25 * 39) == 10
    assert first == sr.double_assignment(list(reversed(ids)), "seed-1")
    assert first != sr.double_assignment(ids, "seed-2")
    with pytest.raises(ValueError):
        sr.double_assignment(ids, "seed-1", fraction=1.0)


def test_page_embeds_inert_data_and_no_ai_fields():
    m = manifest()
    response = sr.blank_response(m, HASH)
    response["reviewer_id"] = "</script><script src=x.js>"
    page = sr.render_page(m, response)
    assert "<script src=x.js>" not in page and "\\u003c/script>" in page
    assert "default-src 'none'" in page and '<script src="sequence_review.js" defer>' in page
    embedded = json.loads(page.split('id="review-data">')[1].split("</script>")[0])
    assert embedded["response"] == response
    lowered = page.lower()
    for leaked in ("pitch_id", "release", "747139", "mitt_center_px", "candidate"):
        assert leaked not in lowered


def test_built_manifest_names_no_game_pitch_or_timing(tmp_path):
    import inspect

    source = inspect.getsource(sr.build)
    scope = source.split('"scope": ')[1].split(",")[0]
    assert not any(token in scope for token in ("747139", "pitch_id", "release", "at_bat"))


def test_build_keeps_the_pitch_map_outside_the_reviewer_pack(tmp_path):
    with pytest.raises(SystemExit):
        sr.build(tmp_path / "bundle", tmp_path / "pack", tmp_path / "pack" / "private")


def _node(source):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-independent JavaScript checks")
    m = manifest()
    script = (
        "const assert = require('node:assert/strict');\n"
        f"const ui = require({json.dumps(str(SCRIPT))});\n"
        f"const manifest = {json.dumps(m)};\n"
        f"const response = {json.dumps(sr.blank_response(m, HASH))};\n"
        f"const hash = {json.dumps(HASH)};\n"
        "const copy = x => JSON.parse(JSON.stringify(x));\n" + source
    )
    result = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, encoding="utf-8", timeout=20
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_page_logic_marks_interval_and_point_and_round_trips_a_draft():
    _node("""
let row = copy(response.rows[0]);
row = ui.markHold(row, "start", 5);
row = ui.markHold(row, "end", 9);
row = ui.markPoint(row, 7, [600, 240]);
assert.equal(row.presentation, "held_seen");
// moving the interval end before the centre frame clears the centre
const moved = ui.markHold(row, "end", 6);
assert.equal(moved.point_n, null); assert.equal(moved.mitt, null);
row.visibility = "full"; row.delivery_start_n = 14;
const state = copy(response); state.rows[0] = row; state.reviewer_id = "r1";
const text = ui.exportResponse(state, manifest, hash);
assert.deepEqual(ui.parseImport(text, manifest, hash).current, null);
const draft = ui.exportDraft(copy(response), manifest, hash, {sequence_id: "seq_b", n: 3});
assert.deepEqual(ui.parseImport(draft, manifest, hash).current, {sequence_id: "seq_b", n: 3});
assert.throws(() => ui.exportResponse({...state, reviewer_id: ""}, manifest, hash));
const cleared = ui.setPresentation(row, "not_determinable");
assert.equal(cleared.hold_start_n, null); assert.equal(cleared.mitt, null);
assert.throws(() => ui.imagePoint(10, 10, {left: 20, top: 20, width: 640, height: 360}, {width: 1280, height: 720}));
assert.deepEqual(ui.imagePoint(340, 200, {left: 20, top: 20, width: 640, height: 360}, {width: 1280, height: 720}), [640, 360]);
""")


def test_page_and_python_validators_agree_on_the_same_cases():
    m = manifest()
    good = held(sr.blank_response(m, HASH))
    bad = copy.deepcopy(good)
    bad["rows"][0]["point_n"] = 12
    _node(f"""
ui.validate(manifest, hash, {json.dumps(good)});
assert.throws(() => ui.validate(manifest, hash, {json.dumps(bad)}));
""")
    sr.validate_response(m, HASH, good)
    with pytest.raises(ValueError):
        sr.validate_response(m, HASH, bad)
