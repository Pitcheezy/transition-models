"""Saved OCR rows may reach the frame page only through an exact, hash-bound join."""

import copy
import hashlib
import json
import re

import pytest
from PIL import Image

from intent.mitt_ocr_view import build

PITCHES = ("747139:3:1", "747139:3:2", "747139:3:3")
FRAMES_PER_PITCH = 4


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def seal_pack(pack):
    files = {
        p.relative_to(pack).as_posix(): {"sha256": sha(p), "bytes": p.stat().st_size}
        for p in pack.rglob("*")
        if p.is_file() and p.name != "receipt.json"
    }
    save(
        pack / "receipt.json",
        {
            "schema": "pitcheezy-track-frame-view-receipt-v1",
            "independent_decoded_pts_verified": False,
            "files": files,
        },
    )
    return sha(pack / "receipt.json")


def make_pack(root, *, color_seed=0, base=600):
    pack = root / "frame-view"
    pitches = []
    for p, pitch_id in enumerate(PITCHES):
        folder = pack / "frames" / pitch_id.replace(":", "_")
        folder.mkdir(parents=True)
        frames = []
        for i in range(FRAMES_PER_PITCH):
            index = base + 120 * p + 6 * i
            path = folder / f"{index}.jpg"
            Image.new("RGB", (1280, 720), (color_seed + p * 40, i * 30, 60)).save(path)
            seconds = index * 1001 / 60000
            frames.append(
                {
                    "frame_index": index,
                    "frame_seconds": seconds,
                    "image": path.relative_to(pack).as_posix(),
                    "sha256": sha(path),
                    "width": 1280,
                    "height": 720,
                    "selection": {
                        "pitch_id": pitch_id,
                        "frame_index": index,
                        "frame_seconds": seconds,
                        "tracker_state": "unseeded",
                        "selection_state": "unavailable",
                        "reason": "no_seed",
                        "current_track_point_px": None,
                        "current_candidate": None,
                        "event": None,
                        "last_historical_candidate": None,
                    },
                }
            )
        pitches.append({"pitch_id": pitch_id, "play_id": f"play-{p}", "frames": frames})
    save(
        pack / "payload.json",
        {
            "schema": "pitcheezy-track-frame-view-dev-v1",
            "time_basis": "manifest_index_timebase",
            "independent_decoded_pts_verified": False,
            "pitches": pitches,
        },
    )
    return pack, seal_pack(pack)


def role(name=None, *, status=None, reason=None, relation="not_compared", compared=None):
    status = status or ("read" if name else "abstain")
    return {
        "raw_text": f"3.{name}" if name else "",
        "name_text": name if status == "read" else None,
        "lineup_order": None,
        "status": status,
        "reason": reason or ("literal_name" if status == "read" else "name_panel_absent"),
        "temporal_relation": relation,
        "compared_to_frame": compared,
    }


def make_ocr(root, pack, pack_receipt_sha, *, batter_names=("VLTNLUS", "VIENTOS", None, "VIENTOS")):
    """Rows for the first pitch only, following the saved adjacent-read comparison rule."""
    ocr = root / "ocr"
    ocr.mkdir()
    frames = read(pack / "payload.json")["pitches"][0]["frames"]
    rows, prior = [], None
    for frame, name in zip(frames, batter_names, strict=True):
        relation, compared = "not_compared", None
        if name is not None and prior is not None and frame["frame_seconds"] - prior[1] <= 0.25:
            relation = "literal_same" if name == prior[0] else "literal_changed"
            compared = prior[2]
        prior = (name, frame["frame_seconds"], frame["frame_index"]) if name else None
        rows.append(
            {
                "pitch_id": PITCHES[0],
                "frame_index": frame["frame_index"],
                "frame_seconds": frame["frame_seconds"],
                "image_sha256": frame["sha256"],
                "roles": {
                    "pitcher": role(None, reason="possible_truncated_name"),
                    "batter": role(name, relation=relation, compared=compared),
                },
            }
        )
    observations = {
        "schema": "pitcheezy-frame-name-observations-dev-v1",
        "time_basis": "manifest_index_timebase",
        "independent_decoded_pts_verified": False,
        "pitch_id": PITCHES[0],
        "rows": rows,
    }
    save(ocr / "observations.json", observations)
    return ocr, write_report(ocr, pack, pack_receipt_sha, rows)


def write_report(ocr, pack, pack_receipt_sha, rows):
    counts = {"pitcher": {}, "batter": {}}
    for row in rows:
        for name, value in row["roles"].items():
            for key in (value["status"], value["temporal_relation"]):
                counts[name][key] = counts[name].get(key, 0) + 1
    save(
        ocr / "report.json",
        {
            "schema": "pitcheezy-frame-name-ocr-report-dev-v1",
            "evidence_kind": "injected reader test",
            "pitch_id": PITCHES[0],
            "frames": len(rows),
            "execution_status": "completed",
            "roles": counts,
            "receipt_sha256": pack_receipt_sha,
            "payload_sha256": sha(pack / "payload.json"),
            "reader_metadata": {
                "engine": {"engine": "synthetic", "language": "en-US", "path": "C:\\private\\x"},
                "config": {},
            },
            "observations_sha256": sha(ocr / "observations.json"),
            "input_unchanged": True,
            "independent_decoded_pts_verified": False,
        },
    )
    return sha(ocr / "report.json")


@pytest.fixture
def inputs(tmp_path):
    pack, receipt_sha = make_pack(tmp_path)
    ocr, report_sha = make_ocr(tmp_path, pack, receipt_sha)
    return {
        "pack": pack,
        "pack_receipt_sha256": receipt_sha,
        "ocr_dir": ocr,
        "ocr_report_sha256": report_sha,
        "out": tmp_path / "new-ocr-view",
    }


def reseal_ocr(args):
    """Re-pin a deliberately altered observation file so only the join logic can reject it."""
    rows = read(args["ocr_dir"] / "observations.json")["rows"]
    args["ocr_report_sha256"] = write_report(
        args["ocr_dir"], args["pack"], args["pack_receipt_sha256"], rows
    )


def assert_rejected(args, match=None):
    with pytest.raises((ValueError, FileNotFoundError), match=match):
        build(**args)
    assert not args["out"].exists()


def embedded(page, element_id):
    found = re.search(rf'<script[^>]*id="{element_id}"[^>]*>(.*?)</script>', page, re.S)
    assert found is not None
    return found.group(1)


def test_exact_join_builds_a_new_pack_and_marks_pitches_without_observations(inputs):
    before = {p: p.read_bytes() for p in inputs["pack"].parent.rglob("*") if p.is_file()}
    receipt = build(**inputs)
    assert receipt["observation_rows_bound"] == FRAMES_PER_PITCH
    assert receipt["displayed_frames"] == FRAMES_PER_PITCH * len(PITCHES)
    assert receipt["pitches_with_observations"] == [PITCHES[0]]
    assert receipt["pitches_without_observations"] == list(PITCHES[1:])
    assert receipt["no_new_ocr_calls"] is True
    assert receipt["input_unchanged"] is True
    assert receipt["independent_decoded_pts_verified"] is False
    assert receipt["ocr_source_binding"]["same_receipt"] is True
    assert receipt["ocr_source_binding"]["source_receipt_checked"] is False
    assert read(inputs["out"] / "receipt.json") == receipt
    assert all(path.read_bytes() == raw for path, raw in before.items())
    # payload bytes are the frame-view payload, unchanged
    assert sha(inputs["out"] / "payload.json") == sha(inputs["pack"] / "payload.json")
    page = (inputs["out"] / "index.html").read_text(encoding="utf-8")
    assert "__TRACK_VIEW_DATA__" not in page and "__OCR_VIEW_DATA__" not in page
    ocr = json.loads(embedded(page, "ocr-data"))
    assert ocr == read(inputs["out"] / "ocr.json")
    assert ocr["schema"] == "pitcheezy-ocr-frame-view-dev-v1"
    assert [p["pitch_id"] for p in ocr["pitches"]] == [PITCHES[0]]
    rows = ocr["pitches"][0]["rows"]
    assert rows == read(inputs["ocr_dir"] / "observations.json")["rows"]
    assert [r["roles"]["batter"]["name_text"] for r in rows] == [
        "VLTNLUS",
        "VIENTOS",
        None,
        "VIENTOS",
    ]
    assert [r["roles"]["batter"]["temporal_relation"] for r in rows] == [
        "not_compared",
        "literal_changed",
        "not_compared",
        "not_compared",
    ]
    assert ocr["display_rule"]["no_fill_forward"] is True
    assert "C:\\" not in page and "private" not in page
    for name, record in receipt["files"].items():
        path = inputs["out"] / name
        assert path.is_relative_to(inputs["out"])
        assert sha(path) == record["sha256"] and path.stat().st_size == record["bytes"]


def test_source_receipt_of_the_ocr_run_may_differ_only_in_page_files(inputs, tmp_path):
    # the pack the OCR ran on (v2) has other page bytes but identical payload and frames
    source = tmp_path / "source-receipt.json"
    receipt = read(inputs["pack"] / "receipt.json")
    receipt["files"]["review.js"] = {"sha256": "1" * 64, "bytes": 1}
    save(source, receipt)
    rows = read(inputs["ocr_dir"] / "observations.json")["rows"]
    report = read(inputs["ocr_dir"] / "report.json")
    report["receipt_sha256"] = sha(source)
    save(inputs["ocr_dir"] / "report.json", report)
    inputs["ocr_report_sha256"] = sha(inputs["ocr_dir"] / "report.json")
    built = build(**inputs, ocr_source_receipt=source)
    binding = built["ocr_source_binding"]
    assert binding["same_receipt"] is False and binding["source_receipt_checked"] is True
    assert binding["data_files_compared"] == 1 + FRAMES_PER_PITCH * len(PITCHES)
    assert len(rows) == FRAMES_PER_PITCH
    # a source receipt that disagrees on one frame is rejected
    receipt["files"]["frames/747139_3_2/726.jpg"]["sha256"] = "2" * 64
    save(source, receipt)
    report["receipt_sha256"] = sha(source)
    save(inputs["ocr_dir"] / "report.json", report)
    inputs["ocr_report_sha256"] = sha(inputs["ocr_dir"] / "report.json")
    inputs["out"] = tmp_path / "second-out"
    assert_rejected({**inputs, "ocr_source_receipt": source}, match="differ on data files")
    # and a source receipt whose bytes do not match the report pin is rejected
    save(source, {**receipt, "extra": 1})
    inputs["out"] = tmp_path / "third-out"
    assert_rejected({**inputs, "ocr_source_receipt": source}, match="source receipt SHA")


@pytest.mark.parametrize(
    "change",
    [
        "report_pin",
        "report_bytes",
        "observations_bytes",
        "payload_bytes",
        "pack_receipt_pin",
        "frame_bytes",
    ],
)
def test_broken_hash_chain_is_rejected(inputs, change):
    if change == "report_pin":
        inputs["ocr_report_sha256"] = "0" * 64
    elif change == "report_bytes":
        path = inputs["ocr_dir"] / "report.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif change == "observations_bytes":
        path = inputs["ocr_dir"] / "observations.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif change == "payload_bytes":
        path = inputs["pack"] / "payload.json"
        path.write_bytes(path.read_bytes() + b" ")
        inputs["pack_receipt_sha256"] = seal_pack(inputs["pack"])
    elif change == "pack_receipt_pin":
        inputs["pack_receipt_sha256"] = "0" * 64
    else:
        path = next((inputs["pack"] / "frames" / "747139_3_3").glob("*.jpg"))
        path.write_bytes(path.read_bytes() + b"x")
    assert_rejected(inputs)


@pytest.mark.parametrize(
    "change",
    [
        "other_pitch",
        "missing_row",
        "duplicate_row",
        "reordered",
        "wrong_seconds",
        "wrong_sha",
        "wrong_index",
        "extra_row",
        "unknown_status",
        "name_on_abstain",
        "no_name_on_read",
        "same_but_different_names",
        "compared_to_wrong_frame",
        "comparison_after_gap",
        "bad_lineup",
        "extra_field",
        "report_count",
        "report_frames",
    ],
)
def test_misaligned_or_inconsistent_observations_are_rejected_even_when_resealed(inputs, change):
    path = inputs["ocr_dir"] / "observations.json"
    observations = read(path)
    rows = observations["rows"]
    if change == "other_pitch":
        observations["pitch_id"] = PITCHES[1]
        for row in rows:
            row["pitch_id"] = PITCHES[1]
    elif change == "missing_row":
        del rows[1]
    elif change == "duplicate_row":
        rows.insert(1, copy.deepcopy(rows[0]))
    elif change == "reordered":
        rows[1], rows[2] = rows[2], rows[1]
    elif change == "wrong_seconds":
        rows[1]["frame_seconds"] += 1e-6
    elif change == "wrong_sha":
        rows[1]["image_sha256"] = "f" * 64
    elif change == "wrong_index":
        rows[1]["frame_index"] += 1
    elif change == "extra_row":
        rows.append({**copy.deepcopy(rows[-1]), "frame_index": rows[-1]["frame_index"] + 6})
    elif change == "unknown_status":
        rows[0]["roles"]["pitcher"]["status"] = "guessed"
    elif change == "name_on_abstain":
        rows[0]["roles"]["pitcher"]["name_text"] = "MEGILL"
    elif change == "no_name_on_read":
        rows[1]["roles"]["batter"]["name_text"] = ""
    elif change == "same_but_different_names":
        rows[1]["roles"]["batter"]["temporal_relation"] = "literal_same"
    elif change == "compared_to_wrong_frame":
        rows[1]["roles"]["batter"]["compared_to_frame"] = rows[1]["frame_index"]
    elif change == "comparison_after_gap":
        rows[3]["roles"]["batter"].update(
            temporal_relation="literal_same", compared_to_frame=rows[1]["frame_index"]
        )
    elif change == "bad_lineup":
        rows[0]["roles"]["pitcher"]["lineup_order"] = 3
    elif change == "extra_field":
        rows[0]["roles"]["batter"]["player_id"] = 123
    save(path, observations)
    reseal_ocr(inputs)
    if change == "report_count":
        report = read(inputs["ocr_dir"] / "report.json")
        report["roles"]["batter"]["read"] += 1
        save(inputs["ocr_dir"] / "report.json", report)
        inputs["ocr_report_sha256"] = sha(inputs["ocr_dir"] / "report.json")
    elif change == "report_frames":
        report = read(inputs["ocr_dir"] / "report.json")
        report["frames"] += 1
        save(inputs["ocr_dir"] / "report.json", report)
        inputs["ocr_report_sha256"] = sha(inputs["ocr_dir"] / "report.json")
    assert_rejected(inputs)


def test_comparison_summary_when_present_must_match_the_rows(inputs):
    report = read(inputs["ocr_dir"] / "report.json")
    report["comparison_summary"] = {
        "pitcher": {
            "read": {"not_compared": 0, "literal_same": 0, "literal_changed": 0},
            "non_read_count": 4,
        },
        "batter": {
            "read": {"not_compared": 2, "literal_same": 0, "literal_changed": 1},
            "non_read_count": 1,
        },
    }
    save(inputs["ocr_dir"] / "report.json", report)
    inputs["ocr_report_sha256"] = sha(inputs["ocr_dir"] / "report.json")
    receipt = build(**inputs)
    assert receipt["comparison_summary_recount"] == report["comparison_summary"]
    report["comparison_summary"]["batter"]["read"]["literal_same"] = 1
    save(inputs["ocr_dir"] / "report.json", report)
    inputs["ocr_report_sha256"] = sha(inputs["ocr_dir"] / "report.json")
    inputs["out"] = inputs["out"].parent / "another-out"
    assert_rejected(inputs, match="comparison summary")


def test_ocr_for_a_pitch_outside_the_pack_or_for_a_different_payload_is_rejected(inputs, tmp_path):
    other_pack, other_receipt = make_pack(tmp_path / "other", color_seed=90)
    payload = read(other_pack / "payload.json")
    payload["pitches"] = payload["pitches"][1:]
    save(other_pack / "payload.json", payload)
    other_receipt = seal_pack(other_pack)
    assert_rejected(
        {**inputs, "pack": other_pack, "pack_receipt_sha256": other_receipt},
        match="different payload",
    )


def test_hostile_strings_are_kept_as_text_and_never_break_the_page(inputs):
    path = inputs["ocr_dir"] / "observations.json"
    observations = read(path)
    hostile = "</script><img src=x onerror=alert(1)>\u2028<b>VIENTOS</b>"
    observations["rows"][1]["roles"]["batter"].update(raw_text=hostile, name_text=hostile)
    observations["rows"][1]["roles"]["batter"]["temporal_relation"] = "literal_changed"
    save(path, observations)
    reseal_ocr(inputs)
    build(**inputs)
    page = (inputs["out"] / "index.html").read_text(encoding="utf-8")
    block = embedded(page, "ocr-data")
    assert "</script>" not in block and "<img" not in block and "<b>" not in block
    assert json.loads(block)["pitches"][0]["rows"][1]["roles"]["batter"]["raw_text"] == hostile
    assert "\\u003c/script>" in block
    assert (
        read(inputs["out"] / "ocr.json")["pitches"][0]["rows"][1]["roles"]["batter"]["name_text"]
        == hostile
    )


def test_output_location_rules(inputs):
    inputs["out"].mkdir()
    keep = inputs["out"] / "keep.txt"
    keep.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        build(**inputs)
    assert keep.read_text(encoding="utf-8") == "keep"
    for inside in (inputs["pack"] / "nested", inputs["ocr_dir"] / "nested"):
        with pytest.raises(ValueError, match="outside the inputs"):
            build(**{**inputs, "out": inside})
        assert not inside.exists()


def test_report_without_input_unchanged_or_wrong_schema_is_rejected(inputs):
    report = read(inputs["ocr_dir"] / "report.json")
    for change in ({"input_unchanged": False}, {"schema": "other"}, {"pitch_id": PITCHES[1]}):
        altered = {**report, **change}
        save(inputs["ocr_dir"] / "report.json", altered)
        inputs["ocr_report_sha256"] = sha(inputs["ocr_dir"] / "report.json")
        assert_rejected(inputs)


@pytest.mark.parametrize(
    "change", ["index_false", "seconds_false", "seconds_text", "index_float", "seconds_huge_int"]
)
def test_boolean_or_non_numeric_keys_never_equal_frame_zero(tmp_path, change):
    # Codex review finding: False == 0 in Python, so a frame at index/time zero must not join.
    pack, receipt_sha = make_pack(tmp_path, base=0)
    ocr, report_sha = make_ocr(tmp_path, pack, receipt_sha)
    args = {
        "pack": pack,
        "pack_receipt_sha256": receipt_sha,
        "ocr_dir": ocr,
        "ocr_report_sha256": report_sha,
        "out": tmp_path / "new-ocr-view",
    }
    observations = read(ocr / "observations.json")
    first = observations["rows"][0]
    assert first["frame_index"] == 0 and first["frame_seconds"] == 0
    if change == "index_false":
        first["frame_index"] = False
    elif change == "seconds_false":
        first["frame_seconds"] = False
    elif change == "seconds_text":
        first["frame_seconds"] = "0"
    elif change == "seconds_huge_int":
        first["frame_seconds"] = 10**400  # Codex re-check: must be a ValueError, not OverflowError
    else:
        first["frame_index"] = 0.0
    save(ocr / "observations.json", observations)
    reseal_ocr(args)
    assert_rejected(args, match="key")


def test_placeholder_tokens_inside_data_are_not_substituted_again(inputs):
    # Codex review finding: sequential replace() could re-scan inserted JSON for placeholders.
    path = inputs["ocr_dir"] / "observations.json"
    observations = read(path)
    token = "__TRACK_VIEW_DATA__ and __OCR_VIEW_DATA__"
    observations["rows"][0]["roles"]["batter"]["raw_text"] = token
    save(path, observations)
    reseal_ocr(inputs)
    build(**inputs)
    page = (inputs["out"] / "index.html").read_text(encoding="utf-8")
    track = json.loads(embedded(page, "track-data"))
    ocr = json.loads(embedded(page, "ocr-data"))
    assert track == read(inputs["out"] / "payload.json")
    assert ocr == read(inputs["out"] / "ocr.json")
    assert ocr["pitches"][0]["rows"][0]["roles"]["batter"]["raw_text"] == token
