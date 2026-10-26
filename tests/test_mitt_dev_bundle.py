"""CV-32 development bundle: fixed selection rule and presentation-time frame verification."""

import json
import subprocess
from pathlib import Path

import pytest

from intent import mitt_dev_bundle as bundle


def annotation(ab, pn, status="annotated", decision=10.0, release=13.0):
    return {
        "game_pk": 747139,
        "at_bat_number": ab,
        "pitch_number": pn,
        "play_id": f"p{ab}-{pn}",
        "status": status,
        "decision_seconds": decision if status == "annotated" else None,
        "release_seconds": release if status == "annotated" else None,
        "uncertainty_seconds": 0.2,
    }


def test_selection_is_ordered_from_the_first_key_and_keeps_exclusions_in_the_denominator():
    rows = [
        annotation(4, 1),
        annotation(2, 3),
        annotation(3, 2, status="unavailable"),
        annotation(3, 1),
        annotation(3, 3, decision=5.0, release=5.0),
        annotation(5, 1),
    ]
    rule = {**bundle.RULE, "count": 4}
    chosen = bundle.select_pitches(rows, rule)
    assert [c["pitch_id"] for c in chosen] == [
        "747139:3:1",
        "747139:3:2",
        "747139:3:3",
        "747139:4:1",
    ]
    assert [c["exclusion_reason"] for c in chosen] == [
        None,
        "timing_unavailable_in_annotations",
        "release_not_after_decision",
        None,
    ]
    with pytest.raises(ValueError):
        bundle.select_pitches(rows, {**bundle.RULE, "count": 6})
    with pytest.raises(ValueError):
        bundle.select_pitches(rows + [annotation(3, 1)], rule)


def test_window_keeps_the_grid_plus_the_decision_and_release_frames():
    item = {"decision_seconds": 249.75, "release_seconds": 255.9}
    win = bundle.window(item)
    assert win["decision_index"] == 14970  # the index v0 recorded; v0 read D+1 for this pitch
    assert win["first_index"] == bundle.frame_at(248.75)
    assert win["last_index"] == bundle.frame_at(256.4)
    grid = [i for i, r in win["roles"].items() if "grid" in r]
    assert grid == list(range(win["first_index"], win["last_index"] + 1, 6))
    assert "decision" in win["roles"][win["decision_index"]]
    assert "release_nearest" in win["roles"][win["release_index"]]
    assert list(win["roles"]) == sorted(win["roles"])


def test_showinfo_parsing_maps_presentation_time_to_whole_source_frames():
    log = "\n".join(
        [
            "[showinfo@all @ 000001926f014f00] n:   0 pts:14976962 pts_time:249.616033 duration:1001",
            "[showinfo@all @ 000001926f014f00]   side data - SMPTE 12-1 timecode: 00:04:09:37",
            "[showinfo@kept @ 000001926f015340] n:   0 pts:14976962 pts_time:249.616033",
            "[showinfo@all @ 000001926f014f00] n:   1 pts:14977963 pts_time:249.632717",
        ]
    )
    assert bundle.parse_showinfo(log) == {"all": [14962, 14963], "kept": [14962]}
    with pytest.raises(ValueError):
        bundle.parse_showinfo("[showinfo@all @ 0x1] n:   0 pts:14976963 pts_time:249.6")


def test_decode_check_rejects_gaps_partial_coverage_and_unexpected_kept_frames():
    win = {
        "first_index": 10,
        "last_index": 16,
        "roles": {10: ["grid"], 13: ["decision"], 16: ["grid"]},
    }
    good = {"all": list(range(5, 20)), "kept": [10, 13, 16]}
    assert bundle.verify_decode(good, win) == {
        "decoded_first": 5,
        "decoded_last": 19,
        "window_covered": True,
        "index_gaps_in_window": 0,
        "kept_equals_expected": True,
    }
    gap = {"all": [9, 10, 11, 13, 14, 15, 16, 17], "kept": [10, 13, 16]}
    assert bundle.verify_decode(gap, win)["index_gaps_in_window"] == 1
    short = {"all": list(range(11, 20)), "kept": [13, 16]}
    check = bundle.verify_decode(short, win)
    assert not check["window_covered"] and not check["kept_equals_expected"]


def test_selector_expression_escapes_filtergraph_commas():
    win = {"first_index": 10, "last_index": 16, "decision_index": 13, "release_index": 15}
    expression = bundle.select_expression(win, 6)
    assert "," not in expression.replace("\\,", "")
    command = bundle.ffmpeg_command(
        "ffmpeg", "https://example.invalid/v.mp4", win, 6, "out_%05d.jpg"
    )
    assert command[command.index("-ss") + 1] == f"{float(bundle.Fraction(0) / bundle.FPS):.6f}"
    assert "-copyts" in command and command[command.index("-fps_mode") + 1] == "passthrough"


def test_rule_on_the_saved_747139_timing_gives_forty_keys_with_one_exclusion():
    timing = bundle.read_json(bundle.RESULTS / "game_747139_timing.json")
    chosen = bundle.select_pitches(timing["annotations"])
    assert len(chosen) == 40
    assert (chosen[0]["pitch_id"], chosen[-1]["pitch_id"]) == ("747139:3:1", "747139:12:2")
    assert [c["pitch_id"] for c in chosen if not c["included"]] == ["747139:5:5"]
    old = bundle.existing_method(chosen)
    assert old["status_counts"] == {"estimated": 38, "unavailable": 1, "no_output_row": 1}
    assert (
        sum(1 for r in old["rows"] if r.get("v0_recorded_index_equals_bundle_decision_index")) == 39
    )


@pytest.fixture
def decoding(tmp_path, monkeypatch):
    win = {
        "first_index": 10,
        "last_index": 16,
        "decision_index": 13,
        "release_index": 16,
        "roles": {10: ["grid"], 13: ["decision"], 16: ["release_nearest"]},
    }
    item = {"pitch_id": "747139:3:1", "decision_seconds": 1.0, "release_seconds": 1.1}
    lines = [
        f"[showinfo@{name} @ 0x1] config in time_base: 1/60000, frame_rate: 60000/1001"
        for name in ("all", "kept")
    ]
    for name, indices in (("all", range(10, 17)), ("kept", [10, 13, 16])):
        lines.extend(
            f"[showinfo@{name} @ 0x1] n: {n} pts: {index * 1001} pts_time:{index * 1001 / 60000:.6f}"
            for n, index in enumerate(indices)
        )
    state = {"log": "\n".join(lines), "steps": ["success"], "outputs": 3, "calls": 0}
    monkeypatch.setattr(bundle, "window", lambda *_: win)
    monkeypatch.setattr(bundle.time, "sleep", lambda *_: None)
    monkeypatch.setattr(bundle.time, "monotonic", lambda: 10.0)

    def run(command, **_kwargs):
        state["calls"] += 1
        if "-version" in command:
            return subprocess.CompletedProcess(command, 0, "ffmpeg version 8.0 Copyright", "")
        step = state["steps"].pop(0)
        log = state["log"] + "\nInput from https://secret.invalid/token\nC:/private/secret.mp4"
        if step == "timeout":
            raise subprocess.TimeoutExpired(command, 600, stderr=log.encode())
        for n in range(1, state["outputs"] + 1):
            Path(command[-1].replace("%05d", f"{n:05d}")).write_bytes(f"jpeg {n}".encode())
        return subprocess.CompletedProcess(command, 1 if step == "failed" else 0, "", log)

    monkeypatch.setattr(bundle.subprocess, "run", run)
    args = {
        "item": item,
        "out_dir": tmp_path,
        "ffmpeg": "C:/private/ffmpeg.exe",
        "url": "https://secret.invalid/token",
        "crop": False,
        "retries": 1,
        "save_decode_evidence": True,
        "ffmpeg_version": "ffmpeg version 8.0 Copyright",
    }
    return args, state


def test_optional_evidence_binds_actual_pts_jpegs_and_redacts_commands(decoding):
    args, state = decoding
    result = bundle.extract_one(**args)
    assert result["status"] == "extracted" and state["calls"] == 1
    binding = result["attempts"][0]["decode_evidence"]
    path = args["out_dir"] / binding["relative_path"]
    assert bundle.sha256_file(path) == binding["sha256"]
    evidence = json.loads(path.read_bytes())
    assert evidence["status"] == "saved_decode_evidence"
    assert evidence["input_time_base_config"] == {"all": ["1/60000"], "kept": ["1/60000"]}
    assert evidence["decoded"]["kept"][0]["pts"] == 10010
    assert evidence["decoded"]["kept"][0]["pts_time_rational"] == "1001/6000"
    assert evidence["ffmpeg_version"] == "8.0"
    assert evidence["independent_decoded_pts_verified"] is False
    assert evidence["jpeg_binding_stage"] == "decoded_staging_before_publish"
    assert evidence["relative_path_role"].startswith("intended_output")
    for image in evidence["kept_jpegs"]:
        jpeg = args["out_dir"] / image["relative_path"]
        assert bundle.sha256_file(jpeg) == image["sha256"] and jpeg.stat().st_size == image["bytes"]
    serialized = json.dumps([result, evidence])
    assert "secret.invalid" not in serialized and "C:/private" not in serialized
    assert str(args["out_dir"]) not in serialized


def test_timeout_and_failed_retries_retain_each_attempt_outside_staging(decoding):
    args, state = decoding
    args["retries"] = 3
    state["steps"] = ["timeout", "failed", "success"]
    result = bundle.extract_one(**args)
    assert result["status"] == "extracted"
    saved = [
        json.loads((args["out_dir"] / a["decode_evidence"]["relative_path"]).read_bytes())
        for a in result["attempts"]
    ]
    assert [a["status"] for a in saved] == ["timeout", "ffmpeg_failed", "saved_decode_evidence"]
    assert saved[0]["decoded"]["all"] and not saved[0]["kept_jpegs"]
    assert saved[0]["diagnostic_hints"] == ["timeout"]
    assert not (args["out_dir"] / ".staging_pa3_p1").exists()


def test_failure_hints_keep_allowlisted_categories_without_raw_private_text(decoding):
    args, state = decoding
    state["steps"] = ["failed"]
    state["log"] += "\nHTTP error 403 from https://secret.invalid/token C:/private/data"
    result = bundle.extract_one(**args)
    evidence = json.loads(
        (args["out_dir"] / result["attempts"][0]["decode_evidence"]["relative_path"]).read_bytes()
    )
    assert evidence["diagnostic_hints"] == ["http_403"]
    assert evidence["non_showinfo_line_count"] == 3
    assert "secret.invalid" not in json.dumps(evidence) and "C:/private" not in json.dumps(evidence)


@pytest.mark.parametrize("bad", ["config", "missing", "nonfinite", "order", "count", "ticks"])
def test_evidence_failures_are_explicit_and_never_claim_independent_verification(decoding, bad):
    args, state = decoding
    if bad == "config":
        state["log"] = state["log"].replace("time_base: 1/60000", "time_base: 1/1000")
    elif bad == "missing":
        state["log"] = "\n".join(line for line in state["log"].splitlines() if "config" not in line)
    elif bad == "nonfinite":
        state["log"] = state["log"].replace("pts_time:0.166833", "pts_time:nan")
    elif bad == "order":
        state["log"] = state["log"].replace("n: 1 pts: 11011", "n: 2 pts: 11011")
    elif bad == "count":
        state["outputs"] = 2
    else:
        state["log"] = state["log"].replace("pts: 10010", "pts: 10011")
    result = bundle.extract_one(**args)
    assert result["status"] == "extraction_failed"
    evidence = json.loads(
        (args["out_dir"] / result["attempts"][0]["decode_evidence"]["relative_path"]).read_bytes()
    )
    assert evidence["status"] == "validation_failed" and evidence["validation_errors"]
    assert evidence["independent_decoded_pts_verified"] is False and not evidence["kept_jpegs"]
    assert not (args["out_dir"] / "pa3_p1").exists()


def test_default_extraction_has_no_new_fields_version_query_or_evidence_files(decoding):
    args, state = decoding
    args["save_decode_evidence"] = False
    result = bundle.extract_one(**args)
    assert result["status"] == "extracted" and state["calls"] == 1
    assert set(result) == {
        "pitch_id",
        "window",
        "attempts",
        "command",
        "status",
        "frames",
        "crop_box",
    }
    assert "decode_evidence" not in result["attempts"][0]
    assert not (args["out_dir"] / "decode_evidence").exists()


def test_default_timeout_still_propagates(decoding):
    args, state = decoding
    args["save_decode_evidence"] = False
    state["steps"] = ["timeout"]
    with pytest.raises(subprocess.TimeoutExpired):
        bundle.extract_one(**args)
    assert not (args["out_dir"] / "decode_evidence").exists()
