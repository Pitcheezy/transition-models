"""Source integrity and separation of processor inputs from legacy references."""

import hashlib
import json
from copy import deepcopy

import pytest
from PIL import Image

from intent import local_detector_data as data


def write(path, document):
    path.write_text(json.dumps(document), encoding="utf-8")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "EXPECTED_COUNTS", {823407: 2, 849845: 1})
    results = tmp_path / "results"
    results.mkdir()
    for game, count in data.EXPECTED_COUNTS.items():
        images = tmp_path / "outputs" / "frames" / str(game)
        images.mkdir(parents=True)
        frames, labels, points = [], [], []
        for pitch in range(1, count + 1):
            image = images / f"frame_{pitch:06}.jpg"
            Image.new("RGB", (16, 12), (game % 255, pitch * 60, 1)).save(image)
            frame = {
                "pitch_id": f"{game}:1:{pitch}",
                "frame_seconds": float(pitch),
                "path": image.relative_to(tmp_path).as_posix(),
                "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            }
            frames.append(frame)
            labels.append(
                dict(
                    frame,
                    mitt_status="marked",
                    mitt=[5.5, 6.0],
                    plate_status="hidden",
                    plate_front=None,
                )
            )
            points.append(dict(frame, at_bat_number=1, pitch_number=pitch))
        pack_id = hashlib.sha256(
            json.dumps([[f["pitch_id"], f["image_sha256"]] for f in frames]).encode()
        ).hexdigest()[:16]
        manifest = {
            "schema": "intent_label_pack_v0",
            "game_pk": game,
            "pack_id": pack_id,
            "selection": {"all_frames": True},
            "crops": {"main": {"box": [2, 2, 14, 10]}, "plate": {"box": [1, 7, 15, 12]}},
            "frames": frames,
        }
        raw = {
            "schema": "intent_human_labels_v0",
            "game_pk": game,
            "pack_id": pack_id,
            "frames": labels,
        }
        raw_path = results / f"game_{game}_intent_human_labels_raw_v0.json"
        write(raw_path, raw)
        clean = dict(raw, raw_sha256=hashlib.sha256(raw_path.read_bytes()).hexdigest())
        write(results / f"game_{game}_intent_label_pack_v0.json", manifest)
        write(results / f"game_{game}_intent_human_labels_v0.json", clean)
        write(
            results / f"game_{game}_intent_points_v0.json",
            {"schema": "intent_points_v0", "game_pk": game, "frames": points},
        )
        write(
            results / f"game_{game}_condensed_source_v0.json",
            {
                "schema": "intent_condensed_source_v0",
                "game_pk": game,
                "condensed_game": {"probe": {"width": 16, "height": 12}},
            },
        )
    return results, tmp_path, tmp_path / "outputs" / "new_package"


def change(sample, suffix, mutate, game=823407):
    path = sample[0] / f"game_{game}_{suffix}.json"
    document = load(path)
    mutate(document)
    write(path, document)


def change_reference(sample, value):
    for suffix in ("intent_human_labels_raw_v0", "intent_human_labels_v0"):
        change(sample, suffix, lambda d: d["frames"][0].update(mitt=value))
    raw = sample[0] / "game_823407_intent_human_labels_raw_v0.json"
    change(
        sample,
        "intent_human_labels_v0",
        lambda d: d.update(raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest()),
    )


def test_separate_inputs_references_and_public_audit(sample):
    audit = data.prepare(*sample)
    manifest = load(sample[2] / "manifest.json")
    references = load(sample[2] / "references.json")
    assert len(manifest["frames"]) == 3
    assert manifest["schema"] == "local_glove_frames_v1"
    assert references["schema"] == "local_glove_references_v1"
    assert (
        references["manifest_sha256"]
        == hashlib.sha256((sample[2] / "manifest.json").read_bytes()).hexdigest()
    )
    assert set(manifest["frames"][0]) == {
        "observation_id",
        "game_pk",
        "image_path",
        "image_sha256",
        "width",
        "height",
        "legacy_main_crop",
    }
    assert references["references"][0]["mitt"] == [5.5, 6.0]
    assert str(sample[1]) not in json.dumps(audit)
    assert audit["source_image_bytes_verified"] == 3
    with pytest.raises(ValueError, match="already exists"):
        data.prepare(*sample)


def test_pitch_key_mismatch_aborts_before_any_output(sample):
    change(
        sample, "intent_points_v0", lambda d: d["frames"][0].update(pitch_number=99), game=849845
    )
    with pytest.raises(ValueError, match="pitch_id"):
        data.prepare(*sample)
    assert not sample[2].exists()


def test_image_tampering_aborts_before_output(sample):
    path = sample[1] / "outputs/frames/823407/frame_000001.jpg"
    path.write_bytes(path.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="image SHA256"):
        data.prepare(*sample)
    assert not sample[2].exists()


@pytest.mark.parametrize("point", [[16, 0], [-1, 3], [2, 12], [float("nan"), 4], [True, 2]])
def test_reference_requires_finite_in_bounds_coordinates(sample, point):
    change_reference(sample, point)
    with pytest.raises(ValueError):
        data.prepare(*sample)
    assert not sample[2].exists()


@pytest.mark.parametrize("box", [[0, 0, 17, 12], [0, -1, 16, 12], [3, 2, 3, 10], [0, 0, 1.5, 3]])
def test_crop_bounds(sample, box):
    change(sample, "intent_label_pack_v0", lambda d: d["crops"]["main"].update(box=box))
    with pytest.raises(ValueError, match="crop"):
        data.prepare(*sample)


@pytest.mark.parametrize(
    "suffix", ["intent_label_pack_v0", "intent_human_labels_v0", "intent_points_v0"]
)
def test_duplicate_keys(sample, suffix):
    change(sample, suffix, lambda d: d["frames"].append(deepcopy(d["frames"][0])))
    with pytest.raises(ValueError, match="duplicate"):
        data.prepare(*sample)


@pytest.mark.parametrize(
    "path",
    [
        "../outside.jpg",
        "/outside.jpg",
        "C:/outside.jpg",
        "outputs/../outside.jpg",
        "outputs\\frame.jpg",
    ],
)
def test_image_path_cannot_escape_root(sample, path):
    for suffix in ("intent_label_pack_v0", "intent_points_v0"):
        change(sample, suffix, lambda d: d["frames"][0].update(path=path))
    with pytest.raises(ValueError, match="path"):
        data.prepare(*sample)


def test_declared_dimensions_must_match_decoded_full_frame(sample):
    change(sample, "condensed_source_v0", lambda d: d["condensed_game"]["probe"].update(width=17))
    with pytest.raises(ValueError, match="dimensions"):
        data.prepare(*sample)


def test_raw_human_label_bytes_bound_to_imported_file(sample):
    change(sample, "intent_human_labels_raw_v0", lambda d: d.update(extra="change"))
    with pytest.raises(ValueError, match="raw label SHA256"):
        data.prepare(*sample)


def test_output_outside_private_root_rejected(sample):
    with pytest.raises(ValueError, match="private package"):
        data.prepare(sample[0], sample[1], sample[1] / "public")


def test_results_directory_outside_root_rejected(sample):
    with pytest.raises(ValueError, match="results directory"):
        data.prepare(sample[1].parent, sample[1], sample[2])


def test_symlink_image_rejected(sample):
    alias = sample[1] / "outputs/alias.jpg"
    try:
        alias.symlink_to(sample[1] / "outputs/frames/823407/frame_000001.jpg")
    except OSError:
        pytest.skip("host does not grant symlink creation")
    for suffix in ("intent_label_pack_v0", "intent_points_v0"):
        change(sample, suffix, lambda d: d["frames"][0].update(path="outputs/alias.jpg"))
    with pytest.raises(ValueError, match="symlink"):
        data.prepare(*sample)
    assert not sample[2].exists()
