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
    assert "default-src 'none'" in page and '<script src="sequence_review.js?v=dev" defer>' in page
    embedded = json.loads(page.split('id="review-data">')[1].split("</script>")[0])
    assert embedded["response"] == response
    lowered = page.lower()
    for leaked in ("pitch_id", "release", "747139", "mitt_center_px", "candidate"):
        assert leaked not in lowered


def _fake_bundle(root, pitch_ids, frames=25):
    from PIL import Image

    pitches = []
    for pid in pitch_ids:
        _, ab, pn = pid.split(":")
        folder = root / f"pa{ab}_p{pn}"
        folder.mkdir(parents=True)
        rows = []
        for k in range(frames):
            index = 1000 + 6 * k
            Image.new("RGB", (64, 48), (k * 9 % 255, 40, 90)).save(
                folder / f"frame_{index:06d}.jpg"
            )
            rows.append({"index": index, "roles": ["grid"]})
        pitches.append(
            {
                "pitch_id": pid,
                "status": "extracted",
                "window": {"release_index": 1000 + 6 * (frames - 1)},
                "frames": rows,
            }
        )
    (root / "manifest.json").write_text(json.dumps({"pitches": pitches}), encoding="utf-8")


def test_build_preserves_the_full_window_and_keeps_order_times_and_map_private(tmp_path):
    ids = ["747139:3:1", "747139:3:2", "747139:3:3", "747139:4:1"]
    _fake_bundle(tmp_path / "bundle", ids)
    pack, private = tmp_path / "out" / "pack", tmp_path / "out" / "private"
    manifest, digest, double = sr.build(tmp_path / "bundle", pack, private, crop_box=[8, 4, 40, 28])
    text = (pack / "manifest.json").read_text(encoding="utf-8") + (pack / "index.html").read_text(
        encoding="utf-8"
    )
    for leaked in ("747139", "pitch_id", "release", "at_bat"):
        assert leaked not in text
    secret = json.loads((private / "private_map.json").read_text(encoding="utf-8"))
    assert {m["pitch_id"] for m in secret["mapping"]} == set(ids)
    assert not any(p.name == "private_map.json" for p in pack.rglob("*"))
    for m in secret["mapping"]:
        seq = next(s for s in manifest["sequences"] if s["sequence_id"] == m["sequence_id"])
        assert len(seq["frames"]) == 25
        assert (m["dropped_leading_grid_frames"], m["dropped_trailing_grid_frames"]) == (0, 0)
        assert m["frame_indices"] == [1000 + 6 * k for k in range(25)]
        assert seq["frames"][0]["width"] == 32 and seq["frames"][0]["height"] == 24
    frame_files = list((pack / "frames").rglob("*"))
    assert {int(p.stat().st_mtime) for p in frame_files} == {sr.FIXED_MTIME}
    assert int((pack / "index.html").stat().st_mtime) != sr.FIXED_MTIME
    for seq in manifest["sequences"]:
        for frame in seq["frames"]:
            assert frame["path"].endswith(f"_{frame['sha256'][:8]}.jpg")
            assert sr.sha256_file(pack / frame["path"]) == frame["sha256"]
    assert [m["sequence_id"] for m in secret["mapping"]] == sorted(
        m["sequence_id"] for m in secret["mapping"]
    )
    assert manifest["source_crop_box"] == [8, 4, 40, 28]
    assert sr.to_source_pixels([10, 5], [8, 4, 40, 28]) == [18, 9]
    assert len(double) == 1


def test_build_keeps_the_pitch_map_outside_the_reviewer_pack(tmp_path):
    with pytest.raises(SystemExit):
        sr.build(tmp_path / "bundle", tmp_path / "pack", tmp_path / "pack" / "private")


@pytest.mark.parametrize("seed", ["cv34-double-v1", "another-review-seed"])
def test_early_hold_and_last_pre_release_frame_survive_blinding(tmp_path, seed):
    bundle = tmp_path / "bundle"
    _fake_bundle(bundle, ["747139:4:1"])
    source = json.loads((bundle / "manifest.json").read_text())
    source["pitches"][0]["window"]["release_index"] = 1121  # exclude grid frames 1126..1144
    (bundle / "manifest.json").write_text(json.dumps(source))
    pack, private = tmp_path / "pack", tmp_path / "private"
    m, digest, _ = sr.build(bundle, pack, private, seed=seed)
    indices = json.loads((private / "private_map.json").read_text())["mapping"][0]["frame_indices"]
    assert indices == list(range(1000, 1122, 6))
    # An early held interval and its emission stay reviewable regardless of the sampling seed.
    assert 1006 in indices and 1030 in indices and indices[-1] == 1120
    assert len(m["sequences"][0]["frames"]) == 21
    old = copy.deepcopy(m)
    old["sequences"][0]["frames"] = old["sequences"][0]["frames"][8:]
    old_digest = sr.hashlib.sha256(json.dumps(old).encode()).hexdigest()
    with pytest.raises(ValueError):
        sr.validate_response(m, digest, sr.blank_response(old, old_digest))


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
    bads = []
    for change in ({"point_n": 12}, {"mitt": [True, 5]}):
        bad = copy.deepcopy(good)
        bad["rows"][0].update(change)
        bads.append(bad)
    for reviewer in (None, 3):
        for base in (good, sr.blank_response(m, HASH)):
            bad = copy.deepcopy(base)
            bad["reviewer_id"] = reviewer
            bads.append(bad)
    checks = "".join(
        f"assert.throws(() => ui.validate(manifest, hash, {json.dumps(b)}));\n" for b in bads
    )
    _node(f"ui.validate(manifest, hash, {json.dumps(good)});\n" + checks)
    sr.validate_response(m, HASH, good)
    for bad in bads:
        with pytest.raises(ValueError):
            sr.validate_response(m, HASH, bad)


def test_a_hold_bound_on_the_wrong_side_clears_the_other_bound():
    _node("""
let row = ui.markHold(copy(response.rows[0]), "end", 5);
row = ui.markHold(row, "start", 9);
assert.equal(row.hold_start_n, 9); assert.equal(row.hold_end_n, null);
row = ui.markHold(row, "end", 12);
row = ui.markHold(row, "end", 4);
assert.equal(row.hold_start_n, null); assert.equal(row.hold_end_n, 4);
""")
