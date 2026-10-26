"""A private frame consumer must bind exact records and pictures before displaying them."""

import copy
import hashlib
import json
import re

import pytest
from PIL import Image

from intent.mitt_stationary import StationaryParams
from intent.mitt_stationary_pilot import replay
from intent.mitt_track_view import build


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def reseal(args, *, regenerate_selection=True):
    """Create a new trusted pin for semantic corruption tests, not an old-byte-hash failure."""
    manifest_path = args["bundle"] / "manifest.json"
    manifest = read(manifest_path)
    manifest["source"]["timing_file_sha256"] = digest(args["timing"])
    save(manifest_path, manifest)
    tracking = read(args["tracking_records"])
    pitch_count = len({row["pitch_id"] for row in tracking})
    if regenerate_selection:
        selections, _ = replay(tracking)
        save(args["selection_records"], selections)
    save(
        args["tracking_report"],
        {
            "schema": "pitcheezy-mitt-tracking-pilot-dev-v2",
            "frames": len(tracking),
            "pitches": pitch_count,
            "source_manifest_sha256": digest(manifest_path),
            "devices": {"cpu": {"records_sha256": digest(args["tracking_records"])}},
        },
    )
    save(
        args["selection_report"],
        {
            "schema": "pitcheezy-stationary-pilot-dev-v1",
            "params_sha256": StationaryParams().digest(),
            "input_sha256": {
                "tracking_report": digest(args["tracking_report"]),
                "cpu": digest(args["tracking_records"]),
            },
            "devices": {
                "cpu": {
                    "output_sha256": digest(args["selection_records"]),
                    "frames": len(tracking),
                    "pitches": pitch_count,
                }
            },
        },
    )
    args["report_sha256"] = digest(args["selection_report"])


@pytest.fixture
def pack_inputs(tmp_path):
    bundle = tmp_path / "private-source"
    bundle.mkdir()
    args = {
        "bundle": bundle,
        **{
            name: tmp_path / f"{name}.json"
            for name in (
                "timing",
                "tracking_report",
                "tracking_records",
                "selection_report",
                "selection_records",
            )
        },
        "out": tmp_path / "new-view",
    }
    selection, pitches, annotations, tracking = [], [], [], []
    for pitch_number in range(1, 4):
        pitch_id = f"747139:3:{pitch_number}"
        start = 600 + 60 * (pitch_number - 1)
        decision = start * 1001 / 60000 + 0.02
        release = (start + 24) * 1001 / 60000
        play_id = f"00000000-0000-0000-0000-{pitch_number:012d}"
        annotations.append(
            {
                "game_pk": 747139,
                "at_bat_number": 3,
                "pitch_number": pitch_number,
                "play_id": play_id,
                "status": "annotated",
                "decision_seconds": decision,
                "release_seconds": release,
                "uncertainty_seconds": 0.01,
            }
        )
        selection.append(
            {
                "pitch_id": pitch_id,
                "play_id": play_id,
                "timing_status": "annotated",
                "decision_seconds": decision,
                "release_seconds": release,
                "uncertainty_seconds": 0.01,
                "included": True,
            }
        )
        folder = bundle / f"pa3_p{pitch_number}"
        folder.mkdir()
        frames = []
        for i in range(5):
            index = start + i * 6
            image = folder / f"frame_{index:06d}.jpg"
            Image.new("RGB", (1280, 720), (pitch_number * 40, i * 25, 40)).save(image)
            frame = {
                "index": index,
                "pts_time": index * 1001 / 60000,
                "roles": ["grid"],
                "bytes": image.stat().st_size,
                "sha256": digest(image),
            }
            frames.append(frame)
            tracking.append(
                {
                    "pitch_id": pitch_id,
                    "frame_index": index,
                    "frame_seconds": frame["pts_time"],
                    "state": "tracking" if i < 4 else "lost",
                    "reason": "external_seed"
                    if i == 0
                    else "patch_continuity"
                    if i < 4
                    else "low_similarity",
                    "point_px": [600, 300] if i < 4 else None,
                    "mitt_identity": "unverified",
                    "source_sha256": frame["sha256"],
                    "source_pts_ticks": index * 1001,
                    "source_time_base": "1/60000",
                }
            )
        pitches.append(
            {
                "pitch_id": pitch_id,
                "status": "extracted",
                "window": {"release_index": start + 24},
                "frames": frames,
            }
        )
    save(args["timing"], {"schema": "mlb_broadcast_timing_v1", "annotations": annotations})
    save(
        bundle / "manifest.json",
        {
            "schema": "pitcheezy-mitt-dev-bundle-v1",
            "source": {
                "time_base": "1/60000",
                "ticks_per_frame": 1001,
                "timing_file_sha256": digest(args["timing"]),
                "media_url": "https://do-not-publish.example.invalid/private.mp4",
            },
            "selection": selection,
            "pitches": pitches,
        },
    )
    save(args["tracking_records"], tracking)
    reseal(args)
    return args


def assert_rejected(args):
    with pytest.raises((ValueError, FileNotFoundError)):
        build(**args)
    assert not args["out"].exists()


def test_new_private_pack_contains_bound_frames_without_source_url_and_preserves_inputs(
    pack_inputs,
):
    args = pack_inputs
    before = {
        path: path.read_bytes() for path in args["bundle"].parent.rglob("*") if path.is_file()
    }
    receipt = build(**args)
    assert receipt["validated_frames"] == receipt["displayed_frames"] == 15
    assert receipt["validated_pitches"] == receipt["displayed_pitches"] == 3
    assert receipt["input_unchanged"] is True
    assert receipt["independent_decoded_pts_verified"] is False
    assert read(args["out"] / "receipt.json") == receipt
    page = (args["out"] / "index.html").read_text(encoding="utf-8")
    assert "__TRACK_VIEW_DATA__" not in page
    match = re.search(r'<script[^>]*id="track-data"[^>]*>(.*?)</script>', page, re.S)
    assert match is not None
    payload = json.loads(match.group(1))
    assert payload["schema"] == "pitcheezy-track-frame-view-dev-v1"
    assert payload["time_basis"] == "manifest_index_timebase"
    assert payload["independent_decoded_pts_verified"] is False
    assert [pitch["pitch_id"] for pitch in payload["pitches"]] == [
        f"747139:3:{n}" for n in range(1, 4)
    ]
    assert sum(len(pitch["frames"]) for pitch in payload["pitches"]) == 15
    for pitch in payload["pitches"]:
        for frame in pitch["frames"]:
            path = args["out"] / frame["image"]
            assert path.is_relative_to(args["out"])
            assert digest(path) == frame["sha256"]
            assert (frame["width"], frame["height"]) == (1280, 720)
    for path in args["out"].rglob("*"):
        if path.suffix in {".html", ".json", ".js", ".txt"}:
            text = path.read_text(encoding="utf-8")
            assert "do-not-publish.example.invalid" not in text
            assert str(args["bundle"]) not in text
    assert all(path.read_bytes() == raw for path, raw in before.items())


@pytest.mark.parametrize("corrupt", [False, True])
def test_even_non_displayed_pa_images_are_validated_before_filtering(pack_inputs, corrupt):
    args = pack_inputs
    manifest_path = args["bundle"] / "manifest.json"
    manifest = read(manifest_path)
    pitch = copy.deepcopy(manifest["pitches"][-1])
    pitch["pitch_id"] = "747139:4:1"
    pitch["window"]["release_index"] += 60
    folder = args["bundle"] / "pa4_p1"
    folder.mkdir()
    for frame in pitch["frames"]:
        original = args["bundle"] / "pa3_p3" / f"frame_{frame['index']:06d}.jpg"
        frame["index"] += 60
        frame["pts_time"] = frame["index"] * 1001 / 60000
        (folder / f"frame_{frame['index']:06d}.jpg").write_bytes(original.read_bytes())
    manifest["pitches"].append(pitch)
    selected = {**manifest["selection"][-1], "pitch_id": pitch["pitch_id"], "play_id": "fourth-pa"}
    selected["decision_seconds"] += 1001 / 1000
    selected["release_seconds"] += 1001 / 1000
    manifest["selection"].append(selected)
    save(manifest_path, manifest)
    timing = read(args["timing"])
    timing["annotations"].append(
        {
            **timing["annotations"][-1],
            "at_bat_number": 4,
            "pitch_number": 1,
            "play_id": "fourth-pa",
            "decision_seconds": selected["decision_seconds"],
            "release_seconds": selected["release_seconds"],
        }
    )
    save(args["timing"], timing)
    tracking = read(args["tracking_records"])
    added = copy.deepcopy(tracking[-5:])
    for row in added:
        row["pitch_id"] = pitch["pitch_id"]
        row["frame_index"] += 60
        row["source_pts_ticks"] = row["frame_index"] * 1001
        row["frame_seconds"] = row["source_pts_ticks"] / 60000
    save(args["tracking_records"], tracking + added)
    reseal(args)
    if corrupt:
        image = next(folder.glob("*.jpg"))
        image.write_bytes(image.read_bytes() + b"changed")
        assert_rejected(args)
    else:
        receipt = build(**args)
        assert receipt["validated_frames"] == 20
        assert receipt["displayed_frames"] == 15
        assert receipt["validated_pitches"] == 4
        assert receipt["displayed_pitches"] == 3


def test_existing_output_is_never_overwritten(pack_inputs):
    args = pack_inputs
    args["out"].mkdir()
    sentinel = args["out"] / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises((ValueError, FileExistsError)):
        build(**args)
    assert sentinel.read_text() == "keep"
    assert list(args["out"].iterdir()) == [sentinel]


@pytest.mark.parametrize(
    "name",
    [
        "timing",
        "tracking_report",
        "tracking_records",
        "selection_report",
        "selection_records",
        "manifest",
    ],
)
def test_changed_bytes_break_the_pinned_chain(pack_inputs, name):
    args = pack_inputs
    path = args["bundle"] / "manifest.json" if name == "manifest" else args[name]
    path.write_bytes(path.read_bytes() + b" ")
    assert_rejected(args)


@pytest.mark.parametrize("change", ["missing", "duplicate", "reordered", "wrong_pitch"])
def test_incomplete_or_misaligned_corpus_is_rejected_even_with_new_hashes(pack_inputs, change):
    args = pack_inputs
    rows = read(args["tracking_records"])
    if change == "missing":
        del rows[1]
    elif change == "duplicate":
        rows.insert(1, rows[0])
    elif change == "reordered":
        rows[1], rows[2] = rows[2], rows[1]
    else:
        rows[1]["pitch_id"] = "747139:3:2"
    save(args["tracking_records"], rows)
    reseal(args, regenerate_selection=False)
    assert_rejected(args)


def test_wrong_play_id_cannot_be_joined_by_pitch_number_alone(pack_inputs):
    args = pack_inputs
    timing = read(args["timing"])
    timing["annotations"][0]["play_id"] = "different-play"
    save(args["timing"], timing)
    reseal(args)
    assert_rejected(args)


def test_incomplete_pa_is_not_presented_as_a_whole_pa(pack_inputs):
    args = pack_inputs
    timing = read(args["timing"])
    timing["annotations"].append(
        {**timing["annotations"][-1], "pitch_number": 4, "play_id": "another-play"}
    )
    save(args["timing"], timing)
    reseal(args)
    assert_rejected(args)


@pytest.mark.parametrize(
    "where", ["manifest_time", "record_time", "record_subnanosecond", "ticks", "time_base"]
)
def test_declared_time_mismatch_is_rejected_without_claiming_decoded_pts(pack_inputs, where):
    args = pack_inputs
    if where == "manifest_time":
        manifest = read(args["bundle"] / "manifest.json")
        manifest["pitches"][0]["frames"][1]["pts_time"] += 0.001
        save(args["bundle"] / "manifest.json", manifest)
    else:
        rows = read(args["tracking_records"])
        if where == "record_time":
            rows[1]["frame_seconds"] += 0.001
        elif where == "record_subnanosecond":
            rows[3]["frame_seconds"] += 1e-10
        elif where == "ticks":
            rows[1]["source_pts_ticks"] += 1
        else:
            rows[1]["source_time_base"] = "1/30000"
        save(args["tracking_records"], rows)
    reseal(args)
    assert_rejected(args)


def test_changed_jpeg_bytes_are_rejected(pack_inputs):
    args = pack_inputs
    image = next(args["bundle"].glob("pa3_p1/frame_*.jpg"))
    image.write_bytes(image.read_bytes() + b"changed")
    assert_rejected(args)


def test_persisting_current_candidate_matches_exact_display_frame_and_keeps_first_event(
    pack_inputs,
):
    args = pack_inputs
    rows = read(args["tracking_records"])
    rows[4].update(state="tracking", reason="patch_continuity", point_px=[600, 300])
    save(args["tracking_records"], rows)
    reseal(args)
    build(**args)
    frames = read(args["out"] / "payload.json")["pitches"][0]["frames"]
    assert frames[3]["selection"]["current_candidate"] is not None
    assert frames[4]["selection"]["current_candidate"] is not None
    for frame in frames[3:5]:
        selection = frame["selection"]
        current = selection["current_candidate"]
        assert selection["selection_state"] == "stationary"
        assert current["pitch_id"] == selection["pitch_id"] == "747139:3:1"
        assert current["frame_index"] == frame["frame_index"]
        assert current["frame_seconds"] == frame["frame_seconds"]
    assert frames[3]["selection"]["event"] == frames[4]["selection"]["last_historical_candidate"]
    assert frames[4]["selection"]["event"] is None


def test_rebound_wrong_resolution_is_still_rejected(pack_inputs):
    args = pack_inputs
    manifest = read(args["bundle"] / "manifest.json")
    frame = manifest["pitches"][0]["frames"][0]
    image = args["bundle"] / "pa3_p1" / f"frame_{frame['index']:06d}.jpg"
    Image.new("RGB", (640, 360)).save(image)
    frame["sha256"], frame["bytes"] = digest(image), image.stat().st_size
    save(args["bundle"] / "manifest.json", manifest)
    rows = read(args["tracking_records"])
    rows[0]["source_sha256"] = digest(image)
    save(args["tracking_records"], rows)
    reseal(args)
    assert_rejected(args)


def test_tracking_point_outside_source_image_is_not_clamped_for_display(pack_inputs):
    args = pack_inputs
    rows = read(args["tracking_records"])
    rows[0]["point_px"] = [1280, 300]
    save(args["tracking_records"], rows)
    reseal(args)
    assert_rejected(args)


@pytest.mark.parametrize("change", ["future_history", "current_on_lost", "wrong_candidate_point"])
def test_modified_selection_must_match_replay_not_only_its_resealed_hash(pack_inputs, change):
    args = pack_inputs
    rows = read(args["selection_records"])
    assert rows[3]["current_candidate"] is not None
    if change == "future_history":
        rows[4]["last_historical_candidate"]["available_frame"] = 99999
    elif change == "current_on_lost":
        rows[4]["current_candidate"] = rows[3]["current_candidate"]
    else:
        rows[3]["current_candidate"]["point_px"] = [610, 300]
    save(args["selection_records"], rows)
    reseal(args, regenerate_selection=False)
    assert_rejected(args)


def test_placeholder_token_inside_play_id_is_embedded_verbatim(pack_inputs):
    # Codex review finding: the OCR slot must not be re-filled inside already inserted data.
    args = pack_inputs
    timing = read(args["timing"])
    timing["annotations"][0]["play_id"] = "__OCR_VIEW_DATA__"
    save(args["timing"], timing)
    manifest = read(args["bundle"] / "manifest.json")
    manifest["selection"][0]["play_id"] = "__OCR_VIEW_DATA__"
    save(args["bundle"] / "manifest.json", manifest)
    reseal(args)
    build(**args)
    page = (args["out"] / "index.html").read_text(encoding="utf-8")
    track = re.search(r'<script[^>]*id="track-data"[^>]*>(.*?)</script>', page, re.S).group(1)
    ocr = re.search(r'<script[^>]*id="ocr-data"[^>]*>(.*?)</script>', page, re.S).group(1)
    assert json.loads(track)["pitches"][0]["play_id"] == "__OCR_VIEW_DATA__"
    assert json.loads(ocr) is None
