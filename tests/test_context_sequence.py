import copy
import importlib.util
import json
from html.parser import HTMLParser
from pathlib import Path

import pytest
from PIL import Image

SPEC = importlib.util.spec_from_file_location(
    "context_sequence", Path(__file__).resolve().parents[1] / "scripts/82_build_context_sequence.py"
)
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


@pytest.fixture
def bundle(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    manifest = {
        "schema": "cv49c_sequence_v1",
        "source_audit_sha256": "a" * 64,
        "source_context_sha256": "b" * 64,
        "selection_rule": "first_mid_representative_mid_last",
        "crop_xyxy": cli.CROP.copy(),
        "sequences": [],
    }
    for pitch in range(1, 4):
        seq = {
            "pitch_key": f"849843:1:{pitch}",
            "play_id": f"00000000-0000-0000-0000-00000000000{pitch}",
            "clip_sha256": str(pitch) * 64,
            "time_base": "1/90000",
            "first_pts": 100,
            "release_lower_pts": 1000,
            "representative_pts": 300,
            "frames": [],
        }
        for index in range(5):
            row = {"sample_index": index * 5, "frame_pts": (index + 1) * 100}
            for prefix, size in (("image", (1280, 720)), ("crop", (210, 230))):
                path = source / f"{pitch}_{index}_{prefix}.png"
                Image.new("RGB", size, (pitch * 30, index * 30, 20)).save(path)
                row[prefix + "_path"] = path.name
                row[prefix + "_sha256"] = cli.digest(path.read_bytes())
            seq["frames"].append(row)
        manifest["sequences"].append(seq)
    path = source / "manifest.json"
    save(path, manifest)
    readings = []
    for side in ("a", "b"):
        reading = {
            "schema": "cv49c_relations_v1",
            "manifest_sha256": cli.digest(path.read_bytes()),
            "reader": side,
            "model": f"model-{side}",
            "sequences": [],
        }
        for seq in manifest["sequences"]:
            reading["sequences"].append(
                {
                    "pitch_key": seq["pitch_key"],
                    "temporal_relation": "consistent_in_samples",
                    "sequence_note": "Synthetic evidence only.",
                    "frames": [
                        {
                            "frame_pts": frame["frame_pts"],
                            "image_sha256": frame["image_sha256"],
                            "owner": "catcher",
                            "arm_wrist_link": "visible",
                            "candidate_type": "mitt_like",
                            "attachment": "wrist",
                            "candidate_box": [500, 300, 540, 340],
                            "reason": '<script>malicious()</script> & "not markup"',
                        }
                        for frame in seq["frames"]
                    ],
                }
            )
        target = source / f"{side}.json"
        save(target, reading)
        readings.append(target)
    private = tmp_path / "outputs"
    private.mkdir()
    return path, *readings, private / "cv49c_test", private


def run(bundle):
    return cli.build_package(*bundle[:4], private_root=bundle[4])


def manifest(bundle):
    return json.loads(bundle[0].read_bytes())


def reading(bundle, side=1):
    return json.loads(bundle[side].read_bytes())


def test_export_binds_by_pitch_pts_and_never_promotes_agreement(bundle):
    before = {p: p.read_bytes() for p in bundle[0].parent.iterdir()}
    b = reading(bundle, 2)
    b["sequences"].reverse()
    for seq in b["sequences"]:
        seq["frames"].reverse()
    save(bundle[2], b)
    before[bundle[2]] = bundle[2].read_bytes()
    report = run(bundle)
    assert report["verified_mitt"] is False
    assert report["counts"]["readers"]["a"]["evidence_complete_frames"] == 15
    assert report["counts"]["readers"]["b"]["evidence_complete_frames"] == 15
    assert len(report["sequences"]) == 3
    for seq in report["sequences"]:
        assert seq["available_after_pts"] == 500
        for frame in seq["frames"]:
            assert frame["available_after_pts"] == 500
            assert frame["verified_mitt"] is False
            for row in frame["readings"].values():
                assert row["evidence_complete"] is True
                assert row["verified_mitt"] is False
    assert all(p.read_bytes() == raw for p, raw in before.items())
    assert sorted(p.name for p in bundle[3].iterdir()) == ["comparison.json", "index.html"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("frame_pts", True),
        ("frame_pts", 1000),
        ("frame_pts", 0),
        ("frame_pts", float("nan")),
        ("sample_index", True),
        ("sample_index", 4097),
        ("sample_index", 0),
        ("image_sha256", "x" * 64),
        ("image_path", "../elsewhere.png"),
        ("crop_path", "C:/elsewhere.png"),
        ("image_path", "sub\\file.png"),
    ],
)
def test_bad_frame_identity_or_cutoff_rejected(bundle, field, value):
    data = manifest(bundle)
    data["sequences"][0]["frames"][2][field] = value
    with pytest.raises(ValueError):
        cli.validate_manifest(data)


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_pitch",
        "duplicate_play",
        "locked_game",
        "unknown",
        "missing",
        "representative",
        "time_base",
        "unordered",
    ],
)
def test_manifest_scope_and_order_rejected(bundle, mutation):
    data = manifest(bundle)
    seq = data["sequences"][0]
    if mutation == "duplicate_pitch":
        data["sequences"][1]["pitch_key"] = seq["pitch_key"]
    elif mutation == "duplicate_play":
        data["sequences"][1]["play_id"] = seq["play_id"]
    elif mutation == "locked_game":
        seq["pitch_key"] = "849844:1:1"
    elif mutation == "unknown":
        seq["extra"] = "unexpected"
    elif mutation == "missing":
        seq["frames"].pop()
    elif mutation == "representative":
        seq["representative_pts"] = 400
    elif mutation == "time_base":
        seq["time_base"] = "1/30"
    else:
        seq["frames"][1]["frame_pts"] = 100
    with pytest.raises(ValueError):
        cli.validate_manifest(data)


@pytest.mark.parametrize(
    "mutation",
    [
        "manifest",
        "hash",
        "duplicate",
        "missing",
        "box_empty",
        "box_bool",
        "box_outside",
        "unclear_box",
        "unknown_relation",
        "extra",
    ],
)
def test_reading_binding_and_relations_are_strict(bundle, mutation):
    data = reading(bundle)
    seq, row = data["sequences"][0], data["sequences"][0]["frames"][0]
    if mutation == "manifest":
        data["manifest_sha256"] = "0" * 64
    elif mutation == "hash":
        row["image_sha256"] = "0" * 64
    elif mutation == "duplicate":
        seq["frames"][1] = copy.deepcopy(row)
    elif mutation == "missing":
        seq["frames"].pop()
    elif mutation.startswith("box_"):
        row["candidate_box"] = {
            "box_empty": [],
            "box_bool": [True, 2, 3, 4],
            "box_outside": [0, 0, 1300, 740],
        }[mutation]
    elif mutation == "unclear_box":
        row["candidate_type"] = "unclear"
    elif mutation == "unknown_relation":
        row["arm_wrist_link"] = "verified"
    else:
        row["identity_truth"] = True
    with pytest.raises(ValueError):
        cli.validate_reading(data, manifest(bundle), cli.digest(bundle[0].read_bytes()))


@pytest.mark.parametrize(
    "field,value",
    [
        ("owner", "unclear"),
        ("owner", "other"),
        ("arm_wrist_link", "occluded"),
        ("candidate_type", "bare_hand"),
        ("candidate_type", "gear"),
        ("attachment", "leg_or_torso"),
        ("candidate_box", None),
    ],
)
def test_insufficient_relations_never_complete(bundle, field, value):
    data = reading(bundle)
    row = data["sequences"][0]["frames"][0]
    row[field] = value
    cli.validate_reading(data, manifest(bundle), cli.digest(bundle[0].read_bytes()))
    assert cli.evidence_complete(row) is False


def test_last_raster_corruption_creates_no_output(bundle):
    frame = manifest(bundle)["sequences"][-1]["frames"][-1]
    path = bundle[0].parent / frame["crop_path"]
    path.write_bytes(path.read_bytes() + b"corrupted")
    with pytest.raises(ValueError, match="SHA-256"):
        run(bundle)
    assert not bundle[3].exists()


def test_symlink_is_rejected(bundle, monkeypatch):
    frame = manifest(bundle)["sequences"][0]["frames"][0]
    path = bundle[0].parent / frame["image_path"]
    monkeypatch.setattr(cli.overlay, "_is_link", lambda p: p == path)
    with pytest.raises(ValueError, match="symlink"):
        run(bundle)
    assert not bundle[3].exists()


def test_wrong_dimensions_with_matching_hash_rejected(bundle):
    data = manifest(bundle)
    frame = data["sequences"][0]["frames"][0]
    image = bundle[0].parent / frame["image_path"]
    Image.new("RGB", (100, 100)).save(image)
    frame["image_sha256"] = cli.digest(image.read_bytes())
    save(bundle[0], data)
    for side in (1, 2):
        value = reading(bundle, side)
        value["manifest_sha256"] = cli.digest(bundle[0].read_bytes())
        value["sequences"][0]["frames"][0]["image_sha256"] = frame["image_sha256"]
        save(bundle[side], value)
    with pytest.raises(ValueError, match="dimensions"):
        run(bundle)
    assert not bundle[3].exists()


def test_output_must_be_new_and_private(bundle):
    run(bundle)
    with pytest.raises(ValueError, match="new private"):
        run(bundle)
    with pytest.raises(ValueError, match="private outputs"):
        cli.build_package(*bundle[:3], bundle[4].parent / "public", private_root=bundle[4])


def test_frame_panels_keep_local_identity_and_escape_text(bundle):
    report = run(bundle)
    html = (bundle[3] / "index.html").read_text(encoding="utf-8")

    class Parser(HTMLParser):
        panels, images, boxes = [], [], []

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if tag == "section":
                self.panels.append(attributes)
            if tag == "image":
                self.images.append(attributes["href"])
            if tag == "rect":
                self.boxes.append(attributes["data-reader"])

    parser = Parser()
    parser.feed(html)
    assert len(parser.panels) == 15
    assert len({(p["data-sequence"], p["data-frame"]) for p in parser.panels}) == 15
    assert all("hidden" in p for p in parser.panels)
    assert len(parser.images) == 30
    assert all(src.startswith("data:image/png;base64,") for src in parser.images)
    assert set(parser.boxes) == {"a", "b"}
    assert "<script>malicious()" not in html
    assert "&lt;script&gt;malicious()&lt;/script&gt;" in html
    assert "frame = 0; render();" in html
    assert "panel.hidden = !(Number(panel.dataset.sequence)" in html
    assert html.count("<details><summary>판독 원문·모델 정보</summary>") == 30
    assert "전체 15장 · 검증된 미트 0장" in html
    assert "상자 좌표는 원본 1280×720의 정수 픽셀" in html
    assert report["artifacts"][0]["sha256"] == cli.digest((bundle[3] / "index.html").read_bytes())


def test_duplicate_json_keys_and_nan_rejected():
    for raw in (b'{"schema":1,"schema":2}', b'{"frame_pts":NaN}'):
        with pytest.raises(ValueError):
            cli.loads_json(raw)


@pytest.mark.parametrize("position,value", [(1, 4), (3, 16)])
def test_midpoint_selection_is_not_replaced_by_ascending_arbitrary_frames(bundle, position, value):
    data = manifest(bundle)
    data["sequences"][0]["frames"][position]["sample_index"] = value
    with pytest.raises(ValueError, match="midpoint"):
        cli.validate_manifest(data)


def update_image_binding(bundle, data):
    save(bundle[0], data)
    image_sha = data["sequences"][0]["frames"][0]["image_sha256"]
    for side in (1, 2):
        value = reading(bundle, side)
        value["manifest_sha256"] = cli.digest(bundle[0].read_bytes())
        value["sequences"][0]["frames"][0]["image_sha256"] = image_sha
        save(bundle[side], value)


@pytest.mark.parametrize("kind", ["wrong_source", "off_by_one"])
def test_matching_hash_cannot_hide_wrong_source_crop(bundle, kind):
    data = manifest(bundle)
    frame = data["sequences"][0]["frames"][0]
    full_path = bundle[0].parent / frame["image_path"]
    crop_path = bundle[0].parent / frame["crop_path"]
    if kind == "wrong_source":
        Image.new("RGB", (210, 230), (255, 5, 30)).save(crop_path)
    else:
        full = Image.new("RGB", (1280, 720), (0, 0, 0))
        full.putpixel((450, 240), (255, 0, 0))
        full.save(full_path)
        full.crop((451, 240, 661, 470)).save(crop_path)
    frame["image_sha256"] = cli.digest(full_path.read_bytes())
    frame["crop_sha256"] = cli.digest(crop_path.read_bytes())
    update_image_binding(bundle, data)
    with pytest.raises(ValueError, match="crop pixels"):
        run(bundle)
    assert not bundle[3].exists()


@pytest.mark.parametrize("mode", ["RGBA", "L"])
def test_crop_mode_policy_is_explicit(bundle, mode):
    data = manifest(bundle)
    frame = data["sequences"][0]["frames"][0]
    path = bundle[0].parent / frame["crop_path"]
    with Image.open(path) as image:
        converted = image.convert(mode)
    converted.save(path)
    frame["crop_sha256"] = cli.digest(path.read_bytes())
    update_image_binding(bundle, data)
    if mode == "RGBA":
        assert run(bundle)["verified_mitt"] is False
    else:
        with pytest.raises(ValueError, match="RGB or RGBA"):
            run(bundle)


def test_missing_private_root_is_not_created(bundle):
    missing = bundle[4] / "not_created"
    with pytest.raises(ValueError, match="already exist"):
        cli.build_package(*bundle[:3], missing / "cv49c_test", private_root=missing)
    assert not missing.exists()


def test_write_failure_preserves_partial_pack_without_index(bundle, monkeypatch):
    original_write = Path.write_bytes

    def fail_index(path, raw):
        if path == bundle[3] / "index.html":
            raise OSError("simulated storage failure")
        return original_write(path, raw)

    monkeypatch.setattr(Path, "write_bytes", fail_index)
    with pytest.raises(OSError, match="storage failure"):
        run(bundle)
    assert (bundle[3] / "comparison.json").is_file()
    assert not (bundle[3] / "index.html").exists()
    with pytest.raises(ValueError, match="new private"):
        run(bundle)
