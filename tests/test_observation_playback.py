"""Synthetic playback packaging boundaries; no real video, model, network or labels."""

import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest

from intent import clip_frames
from intent import observation_playback as playback


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value) + "\n").encode()
    path.write_bytes(raw)
    return digest(raw)


def read(path):
    return json.loads(path.read_bytes())


def table(start, *, missing=None, first_shift=0, last_shift=0):
    header = (
        "#format: frame checksums\n#version: 2\n#hash: MD5\n#tb 0: 1/1\n"
        "#media_type 0: video\n#codec_id 0: rawvideo\n#dimensions 0: 2x2\n"
        "#sar 0: 1/1\n#stream#, dts, pts, duration, size, hash\n"
    )
    rows = []
    for index in range(30):
        if index == missing:
            continue
        timestamp = start + index
        timestamp += first_shift if index == 0 else last_shift if index == 29 else 0
        rows.append(f"0,{timestamp},{timestamp},1,12,{index + 1:032x}\n")
    return (header + "".join(rows)).encode()


@pytest.fixture
def package(tmp_path, monkeypatch):
    capture, run = tmp_path / "capture", tmp_path / "run"
    capture.mkdir()
    run.mkdir()
    clip = tmp_path / "video/clip.mp4"
    clip.parent.mkdir()
    clip.write_bytes(b"synthetic checksum-bound media, not decoded")
    source = {"kind": "url", "value": "https://private.invalid/secret-video"}
    artifacts = {}
    for name, raw in (("source.framemd5", table(10)), ("clip.framemd5", table(0))):
        (capture / name).write_bytes(raw)
        artifacts[name] = {"sha256": digest(raw), "bytes": len(raw)}
    receipt = {
        "schema": "intent_clip_capture_v1",
        "status": "captured",
        "errors": [],
        "source": source,
        "clip": {
            "path": str(clip),
            "sha256_before": digest(clip.read_bytes()),
            "sha256_after": digest(clip.read_bytes()),
            "unchanged": True,
        },
        "artifacts": artifacts,
    }
    capture_hash = write(capture / "receipt.json", receipt)
    captured, _, bindings, mapping = clip_frames._capture_inputs(capture)
    input_hashes = clip_frames._input_hashes(captured, bindings, mapping)
    cutoffs = ["12", "16", "22", "26"]
    write(
        run / "run_manifest.json",
        {
            "plan": {"cutoffs": cutoffs, "capture_dir": str(capture)},
            "started_monotonic_ns": 100_000_000_000,
            "input_code_bindings": [
                {"path": str(capture / "receipt.json"), "sha256": capture_hash}
            ],
        },
    )
    saved_rows = []
    for index, state in enumerate(("candidate", "no_candidate", "error", "not_attempted")):
        saved_rows.append(
            {
                "index": index,
                "status": state,
                "cutoff_seconds_exact": cutoffs[index],
                "observation_status": "unknown"
                if index == 0
                else "unavailable"
                if index == 1
                else None,
            }
        )
        if state == "not_attempted":
            continue
        accepted = index < 2
        publication = 15 if index == 0 else 17
        write(
            run / "attempts" / f"{index:03d}.json",
            {
                "status": "accepted" if accepted else "error",
                "actual_source_seconds_exact": cutoffs[index],
                "cutoff_seconds_exact": cutoffs[index],
                "response_accepted": {"monotonic_ns": 100_000_000_000 + (publication - 12) * 10**9}
                if accepted
                else None,
            },
        )
        if not accepted:
            continue
        image = run / "outputs" / f"cv_observation_{index:03d}" / "request/image.jpg"
        image.parent.mkdir(parents=True)
        image.write_bytes(f"saved JPEG bytes {index}".encode())
        frame_hash = write(
            run / "frames" / f"frame_{index:03d}" / "receipt.json",
            {
                "status": "extracted",
                "input_hashes": input_hashes,
                "source": source,
                "actual_source_seconds_exact": cutoffs[index],
                "requested_source_seconds_exact": cutoffs[index],
                "extraction_verified": True,
                "bindings_verified": True,
                "mapping": mapping["rows"][int(cutoffs[index]) - 10],
                "artifacts": {"image.jpg": {"sha256": digest(image.read_bytes())}},
            },
        )
        write(
            image.parent.parent / "session.json",
            {
                "source_receipt_sha256": frame_hash,
                "image_sha256": digest(image.read_bytes()),
            },
        )
    refs = tmp_path / "references"
    timing, manifest, sources = (
        refs / name for name in ("timing.json", "manifest.json", "sources.json")
    )
    write(
        timing,
        {
            "source": {"media_url": source["value"]},
            "annotator": "private name",
            "manifest_sha256": "a" * 64,
            "annotations": [
                {
                    "game_pk": 747139,
                    "at_bat_number": 2,
                    "pitch_number": index + 1,
                    "decision_seconds": decision,
                    "release_seconds": release,
                    "uncertainty_seconds": 0.25,
                }
                for index, (decision, release) in enumerate(((15, 18), (24, 28)))
            ],
        },
    )
    write(
        manifest,
        {
            "pitches": [
                {"game_pk": 747139, "at_bat_number": 2, "pitch_number": number} for number in (1, 2)
            ]
        },
    )
    write(sources, {"private": "not exported"})
    assets = tmp_path / "assets"
    assets.mkdir()
    for name in ("index.html", "playback.js", "style.css"):
        (assets / name).write_text(f"synthetic {name}", encoding="utf-8")
    # These two independent, extensively tested validators have their own fixtures.
    # Keep real deadline calculation, frame binding, capture mapping and file checks.
    monkeypatch.setattr(
        playback.saved,
        "build_report",
        lambda run: {
            "observations": saved_rows,
            "evidence_sha256": {},
        },
    )
    monkeypatch.setattr(playback.replay_pitch_deadlines, "validate_annotations", lambda *args: None)
    args = dict(
        run=run,
        capture_dir=capture,
        timing=timing,
        manifest=manifest,
        sources=sources,
        pa=2,
        start="14",
        end="32",
        out_dir=tmp_path / "result",
        asset_dir=assets,
    )
    return args, saved_rows


def build(package, **changes):
    return playback.build_package(**(package[0] | changes))


def edit_frame(package, index, **changes):
    run = package[0]["run"]
    path = run / "frames" / f"frame_{index:03d}" / "receipt.json"
    data = read(path)
    data.update(changes)
    hashed = write(path, data)
    session_path = run / "outputs" / f"cv_observation_{index:03d}" / "session.json"
    session = read(session_path)
    session["source_receipt_sha256"] = hashed
    write(session_path, session)


def replace_clip_table(package, **changes):
    capture = package[0]["capture_dir"]
    path = capture / "clip.framemd5"
    raw = table(0, **changes)
    path.write_bytes(raw)
    receipt = read(capture / "receipt.json")
    receipt["artifacts"]["clip.framemd5"] = {"sha256": digest(raw), "bytes": len(raw)}
    write(capture / "receipt.json", receipt)


def test_saved_publication_projection_preserves_all_rows_and_private_boundary(package):
    args = package[0]
    before = playback.saved._inventory(args["run"])
    result = build(package)
    assert result["schema"] == "intent_observation_playback_v1"
    assert result["media"]["source_offset_seconds_exact"] == "10"
    assert result["media"]["clip_end_seconds_exact"] == "30"
    assert result["scope"]["game_pk"] == 747139
    assert result["summary"] == {
        "planned_observations": 4,
        "interval_observations": 3,
        "outside_interval_observations": 1,
        "accepted": 2,
        "errors": 1,
        "not_attempted": 1,
        "verified_mitt": 0,
        "conservative_ready_pitches": 1,
    }
    first, second, failed, absent = result["observations"]
    assert (
        first["publication_seconds_exact"] == "15"
    )  # Source origin + run elapsed, not current clock.
    assert first["reference_pitch_id"] is None  # Never assign the last/nearest pitch.
    assert second["publication_seconds_exact"] == "17"
    assert second["reference_pitch_id"] == "747139:2:1"
    assert failed["image_path"] is None and absent["image_path"] is None
    assert all(not row["usable_mitt"] for row in result["references"])
    assert playback.saved._inventory(args["run"]) == before
    output = args["out_dir"]
    assert read(output / "replay-data.json") == result
    package_manifest = read(output / "manifest.json")
    expected_files = {
        "PRIVATE.txt",
        "index.html",
        "playback.js",
        "style.css",
        "media/clip.mp4",
        "frames/000.jpg",
        "frames/001.jpg",
        "replay-data.json",
    }
    assert set(package_manifest["artifacts"]) == expected_files
    for path, record in package_manifest["artifacts"].items():
        raw = (output / path).read_bytes()
        assert record == {"sha256": digest(raw), "bytes": len(raw)}
    text = (output / "replay-data.json").read_text() + (output / "manifest.json").read_text()
    for secret in (str(args["run"]), "private.invalid", "private name", "not exported"):
        assert secret not in text


@pytest.mark.parametrize("start,end", [(14.0, "32"), (True, "32"), ("14", "14"), ("14", "nan")])
def test_exact_interval_required(package, start, end):
    with pytest.raises(ValueError):
        build(package, start=start, end=end)
    assert not package[0]["out_dir"].exists()


@pytest.mark.parametrize(
    "change,match",
    [
        ({"missing": 7}, "fully covered"),
        ({"last_shift": 1}, "constant"),
        ({"first_shift": -1}, "constant"),
    ],
)
def test_mapping_gaps_or_varying_offset_rejected_before_output(package, change, match):
    replace_clip_table(package, **change)
    with pytest.raises(ValueError, match=match):
        build(package)
    assert not package[0]["out_dir"].exists()


def test_interval_before_first_source_frame_rejected(package):
    with pytest.raises(ValueError, match="fully covered"):
        build(package, start="9")


def test_nonzero_first_pts_rejected(package, monkeypatch):
    original = clip_frames._capture_inputs

    def shifted(directory):
        captured, clip, bindings, mapping = original(directory)
        mapping["clip"]["first_pts"] = 1
        mapping["clip"]["first_seconds_exact"] = "1"
        return captured, clip, bindings, mapping

    monkeypatch.setattr(clip_frames, "_capture_inputs", shifted)
    with pytest.raises(ValueError, match="first PTS"):
        build(package)


def test_frame_after_cutoff_rejected(package):
    path = package[0]["run"] / "attempts/001.json"
    attempt = read(path)
    attempt["actual_source_seconds_exact"] = "17"
    write(path, attempt)
    edit_frame(package, 1, actual_source_seconds_exact="17")
    with pytest.raises(ValueError, match="later than its cutoff"):
        build(package)


def test_saved_frame_mapping_cannot_be_replaced(package):
    edit_frame(package, 1, mapping={"source_seconds_exact": "16"})
    with pytest.raises(ValueError, match="causal mapping"):
        build(package)


def test_unknown_cannot_be_promoted_to_marked(package):
    package[1][0]["observation_status"] = "marked"
    with pytest.raises(ValueError, match="unverified"):
        build(package)


def test_capture_receipt_must_belong_to_frozen_run(package):
    path = package[0]["run"] / "run_manifest.json"
    value = read(path)
    value["input_code_bindings"][0]["sha256"] = "f" * 64
    write(path, value)
    with pytest.raises(ValueError, match="bound to the saved run"):
        build(package)


def test_source_clock_identity_cannot_change(package):
    path = package[0]["timing"]
    value = read(path)
    value["source"]["media_url"] = "https://other.invalid/video"
    write(path, value)
    with pytest.raises(ValueError, match="same unchanged media source"):
        build(package)


def test_missing_reference_or_saved_index_not_silently_omitted(package):
    package[1].pop()
    # Denominator follows the saved validator report. Reject an index hole explicitly.
    package[1][1]["index"] = 8
    with pytest.raises((ValueError, FileNotFoundError)):
        build(package)


def test_original_media_changes_rejected(package):
    clip = Path(read(package[0]["capture_dir"] / "receipt.json")["clip"]["path"])
    clip.write_bytes(b"changed media")
    with pytest.raises(ValueError, match="SHA256"):
        build(package)


def test_mid_copy_input_mutation_detected_and_inputs_not_overwritten(package, monkeypatch):
    original = playback._copy
    changed = package[0]["run"] / "attempts/000.json"

    def mutate(source, destination, expected_hash):
        original(source, destination, expected_hash)
        if destination.name == "clip.mp4":
            changed.write_bytes(changed.read_bytes() + b" ")

    monkeypatch.setattr(playback, "_copy", mutate)
    with pytest.raises(ValueError, match="Saved run changed"):
        build(package)
    assert not (package[0]["out_dir"] / "replay-data.json").exists()
    assert not (package[0]["out_dir"] / "manifest.json").exists()


def test_existing_output_is_never_overwritten(package):
    output = package[0]["out_dir"]
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("keep")
    with pytest.raises(FileExistsError):
        build(package)
    assert sentinel.read_text() == "keep"


@pytest.mark.parametrize("target", ["run", "capture_dir", "asset_dir"])
def test_new_output_inside_inputs_rejected(package, target):
    with pytest.raises(ValueError, match="overlap"):
        build(package, out_dir=package[0][target] / "new-child")


def test_symlink_source_rejected(package):
    args = package[0]
    original = args["asset_dir"] / "playback.js"
    alias = args["asset_dir"] / "linked.js"
    try:
        alias.symlink_to(original)
    except OSError as exc:
        pytest.skip(f"OS cannot create test symlink: {exc}")
    original.unlink()
    alias.rename(original)
    with pytest.raises(ValueError, match="Symlinks"):
        build(package)


def test_exact_start_and_end_use_frame_then_cutoff(package):
    result = build(package, start="16", end="26")
    assert (
        result["summary"]["interval_observations"] == 2
    )  # frame16 + error frame22; excludes cutoff26.
    assert Fraction(result["scope"]["start_source_seconds_exact"]) == 16


def test_unmeasured_reference_is_rejected_without_making_a_label(package):
    path = package[0]["timing"]
    value = read(path)
    value["annotations"][0]["decision_seconds"] = None
    write(path, value)
    with pytest.raises(ValueError, match="measured reference"):
        build(package)
    assert not package[0]["out_dir"].exists()


def test_late_output_keeps_its_own_pitch_and_is_not_reused(package):
    path = package[0]["run"] / "attempts/001.json"
    value = read(path)
    value["response_accepted"]["monotonic_ns"] = 116_000_000_000  # source 28
    write(path, value)
    result = build(package)
    row = result["observations"][1]
    assert row["publication_seconds_exact"] == "28"
    assert row["reference_pitch_id"] == "747139:2:1"
    assert not result["references"][0]["conservative_temporal_ready"]
    assert not result["references"][1]["conservative_temporal_ready"]


def test_source_table_hash_change_is_not_accepted_as_a_mapping(package):
    path = package[0]["capture_dir"] / "source.framemd5"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="byte size changed"):
        build(package)


def test_image_receipt_hash_must_match_copied_image(package):
    path = package[0]["run"] / "outputs/cv_observation_001/request/image.jpg"
    path.write_bytes(b"different saved image")
    with pytest.raises(ValueError, match="input image differs"):
        build(package)
