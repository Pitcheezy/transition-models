"""Source identity and prefix-only exposure of a tiny local development fixture."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

from intent.replay import FRAME_KEYS, PrefixStream, prefix, prepare


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    windows = {
        "schema": "intent_broadcast_windows_v0",
        "game_pk": 123456,
        "media_url": "https://example.invalid/local-fixture.mp4",
        "fps": "30/1",
        "window": {"step_frames": 3},
        "windows": [],
    }
    timing = {
        "schema": "intent_broadcast_timing_v0",
        "game_pk": 123456,
        "source": {"media_url": windows["media_url"], "fps": "30/1"},
        "annotations": [],
    }
    for pitch, indices in ((3, [27, 30, 33]), (5, [57, 60, 63])):
        directory = f"frames/pa43_p{pitch}"
        frames = []
        for index in indices:
            path = root / directory / f"frame_{index:06d}.jpg"
            path.parent.mkdir(parents=True, exist_ok=True)
            # The feeder copies/hashes bytes only; no image decoder/CV is involved.
            data = f"fixture image bytes {index}".encode()
            path.write_bytes(data)
            frames.append(
                {
                    "frame_index": index,
                    "frame_time": index / 30,
                    "path": path.relative_to(root).as_posix(),
                    "image_sha256": hashlib.sha256(data).hexdigest(),
                }
            )
        windows["windows"].append({"pitch": f"43:{pitch}", "dir": directory, "frames": frames})
        timing["annotations"].append(
            {
                "game_pk": 123456,
                "at_bat_number": 43,
                "pitch_number": pitch,
                "status": "annotated",
                "decision_frame_index": indices[0],
                "decision_seconds": indices[0] / 30,
                "release_seconds": indices[1] / 30,
            }
        )
    write(root / "windows.json", windows)
    write(root / "timing.json", timing)
    return root, windows, timing


def build(source, name="run"):
    root, _, _ = source
    out = root / "outputs" / name
    result = prepare(root, 123456, 43, out, windows="windows.json", timing="timing.json")
    return out, result


def test_prepare_separates_evaluator_and_preserves_image_bytes(source):
    root, _, _ = source
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    package, result = build(source)
    assert result["frame_count"] == 6 and result["window_count"] == 2
    assert result["only_development"] and not result["cv_inference_performed"]
    processor = json.loads((package / "processor/manifest.json").read_text())
    evaluator = json.loads((package / "evaluator_manifest.json").read_text())
    assert all(set(f) == FRAME_KEYS for f in processor["frames"])
    assert "release_seconds" not in json.dumps(processor) and "pitch_id" not in json.dumps(
        processor
    )
    assert {f["pitch_id"] for f in evaluator["mapping"]} == {"123456:43:3", "123456:43:5"}
    for frame, record in zip(processor["frames"], evaluator["mapping"], strict=True):
        assert (package / "processor" / frame["path"]).read_bytes() == (
            root / record["source_path"]
        ).read_bytes()
    assert all(p.read_bytes() == data for p, data in before.items())
    with pytest.raises(ValueError, match="already exists"):
        build(source)
    with pytest.raises(ValueError, match="outputs"):
        prepare(root, 123456, 43, root / "docs/new", windows="windows.json", timing="timing.json")


def test_future_prefix_invariance_and_monotonic_api(source):
    root, windows, timing = source
    full, _ = build(source, "full")
    prefix_windows, prefix_timing = deepcopy(windows), deepcopy(timing)
    prefix_windows["windows"] = prefix_windows["windows"][:1]
    prefix_timing["annotations"] = prefix_timing["annotations"][:1]
    write(root / "windows.json", prefix_windows)
    write(root / "timing.json", prefix_timing)
    early, _ = build(source, "early")
    a, b = PrefixStream(full), PrefixStream(early)
    assert a.advance(0.95) == b.advance(0.95)
    assert len(a.advance(1.0)) == 2  # inclusive cutoff
    assert all(f["source_time_seconds"] <= 1 for f in a.advance(1.0))
    with pytest.raises(ValueError, match="cannot decrease"):
        a.advance(0.99)
    assert len(a.advance(2.1)) == 6


def test_prefix_rehashes_only_exposed_frames_and_binds_manifest(source):
    package, _ = build(source)
    stream = PrefixStream(package)
    future = package / "processor" / stream.frames[-1]["path"]
    future.write_bytes(b"corrupt future frame")
    assert len(stream.advance(1.1)) == 3
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        stream.advance(2.1)
    assert stream.last_cutoff == 1.1
    stream.manifest.write_text(stream.manifest.read_text() + " ")
    with pytest.raises(ValueError, match="manifest changed"):
        stream.advance(1.1)


def test_cli_prefix_state_rejects_backward_cutoff(source):
    package, _ = build(source)
    assert prefix(package, 1.0)["frame_count"] == 2
    with pytest.raises(ValueError, match="cannot decrease"):
        prefix(package, 0.9)
    assert prefix(package, 1.1)["frame_count"] == 3
    assert json.loads((package / "prefix_state.json").read_text())["last_cutoff"] == 1.1


def test_pre_first_prefix_timestamp_tamper_cannot_change_availability(source):
    package, _ = build(source)
    manifest_path = package / "processor/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["frames"][0]["source_time_seconds"] == 0.9
    manifest["frames"][0]["source_time_seconds"] = 0.4
    write(manifest_path, manifest)
    with pytest.raises(ValueError, match="prepared evaluator hash"):
        PrefixStream(package).advance(0.5)
    assert not (package / "prefix_state.json").exists()


def test_decision_frame_in_clock_range_but_missing_from_window_is_rejected(source):
    root, _, timing = source
    timing["annotations"][0]["decision_frame_index"] = 28
    timing["annotations"][0]["decision_seconds"] = 28 / 30
    write(root / "timing.json", timing)
    with pytest.raises(ValueError, match="decision frame index is absent"):
        build(source)
    assert not (root / "outputs/run").exists()


@pytest.mark.parametrize(
    "change",
    [
        "hash",
        "source",
        "fps",
        "clock",
        "duplicate_window",
        "duplicate_timing",
        "duplicate_frame",
        "unavailable",
        "missing_timing",
        "path_escape",
    ],
)
def test_invalid_sources_fail_before_creating_package(source, change):
    root, windows, timing = source
    frame = windows["windows"][0]["frames"][0]
    if change == "hash":
        frame["image_sha256"] = "0" * 64
    elif change == "source":
        timing["source"]["media_url"] += "wrong"
    elif change == "fps":
        timing["source"]["fps"] = "60/1"
    elif change == "clock":
        frame["frame_time"] += 1
    elif change == "duplicate_window":
        windows["windows"].append(deepcopy(windows["windows"][0]))
    elif change == "duplicate_timing":
        timing["annotations"].append(deepcopy(timing["annotations"][0]))
    elif change == "duplicate_frame":
        windows["windows"][0]["frames"].append(deepcopy(frame))
    elif change == "unavailable":
        timing["annotations"][0]["status"] = "unavailable"
    elif change == "missing_timing":
        timing["annotations"] = timing["annotations"][1:]
    else:
        frame["path"] = "../outside.jpg"
    write(root / "windows.json", windows)
    write(root / "timing.json", timing)
    with pytest.raises(ValueError):
        build(source)
    assert not (root / "outputs/run").exists()


def test_nonfinite_cutoff_rejected(source):
    package, _ = build(source)
    with pytest.raises(ValueError, match="finite"):
        PrefixStream(package).advance(float("nan"))


def test_symlink_source_rejected_when_host_allows_it(source, tmp_path):
    root, windows, _ = source
    path = root / windows["windows"][0]["frames"][0]["path"]
    other = tmp_path / "real.jpg"
    other.write_bytes(path.read_bytes())
    path.unlink()
    try:
        path.symlink_to(other)
    except OSError:
        pytest.skip("host does not permit creating test symlinks")
    with pytest.raises(ValueError, match="symlink"):
        build(source)
