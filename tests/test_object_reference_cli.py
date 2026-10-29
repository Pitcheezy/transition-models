import base64
import importlib.util
import json
from pathlib import Path
from xml.etree import ElementTree

import pytest
from PIL import Image

from src.data.object_reference import (
    COORDINATE_SYSTEM,
    IDENTITY_FIELDS,
    INPUT_SCHEMA,
    KINDS,
    READING_SCHEMA,
)

SPEC = importlib.util.spec_from_file_location(
    "object_reference_cli",
    Path(__file__).resolve().parents[1] / "scripts/79_compare_object_references.py",
)
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


def save(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


@pytest.fixture
def bundle(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    manifest = {
        "schema": INPUT_SCHEMA,
        "source_commit": "a" * 40,
        "source_review_sha256_lf": "b" * 64,
        "game_pk": 849843,
        "frames": [],
    }
    for index in range(1, 4):
        path = source / f"frame{index}.png"
        Image.new("RGB", (64, 48), (index * 30, 10, 20)).save(path)
        manifest["frames"].append(
            {
                "pitch_key": f"849843:1:{index}",
                "play_id": f"00000000-0000-0000-0000-00000000000{index}",
                "clip_sha256": str(index) * 64,
                "frame_pts": index * 1000,
                "time_base": "1/90000",
                "image": path.name,
                "image_sha256": cli.digest(path.read_bytes()),
                "width": 64,
                "height": 48,
                "context_crop": [4, 5, 40, 45],
            }
        )
    input_path = source / "input.json"
    save(input_path, manifest)
    readings = []
    for side in ("a", "b"):
        reading = {
            "schema": READING_SCHEMA,
            "input_sha256": cli.digest(input_path.read_bytes()),
            "reviewer_id": side,
            "model": "model-" + side,
            "prior_exposure": "synthetic test",
            "coordinate_system": COORDINATE_SYSTEM,
            "frames": [],
        }
        for frame in manifest["frames"]:
            row = {key: frame[key] for key in IDENTITY_FIELDS}
            row["objects"] = [
                {
                    "kind": kind,
                    "status": "located" if kind == "mitt" else "unclear",
                    "boxes": [[10, 10, 22, 24]] if kind == "mitt" else [],
                    "reason": '<script>alert("x")</script> & body cue',
                }
                for kind in KINDS
            ]
            reading["frames"].append(row)
        path = source / (side + ".json")
        save(path, reading)
        readings.append(path)
    private = tmp_path / "outputs"
    return input_path, *readings, private / "comparison", private


def run(bundle):
    return cli.export_comparison(*bundle[:4], private_root=bundle[4])


def rebind(bundle, manifest):
    save(bundle[0], manifest)
    sha = cli.digest(bundle[0].read_bytes())
    for path in bundle[1:3]:
        reading = json.loads(path.read_bytes())
        reading["input_sha256"] = sha
        save(path, reading)


def test_export_joins_by_id_preserves_sources_and_embeds_only_exact_png(bundle):
    b = json.loads(bundle[2].read_bytes())
    b["frames"].reverse()
    for row in b["frames"]:
        row["objects"].reverse()
    save(bundle[2], b)
    originals = {path: path.read_bytes() for path in bundle[0].parent.iterdir()}
    report = run(bundle)
    assert report["counts"]["frames"] == 3
    assert report["counts"]["object_comparisons"] == 9
    assert report["provenance"]["reading_b_sha256"] == cli.digest(originals[bundle[2]])
    assert len(list(bundle[3].iterdir())) == 4
    namespace = {"s": "http://www.w3.org/2000/svg"}
    for frame in json.loads(bundle[0].read_bytes())["frames"]:
        path = bundle[3] / (frame["pitch_key"].replace(":", "_") + ".svg")
        raw = path.read_bytes()
        svg = ElementTree.fromstring(raw)
        image = svg.find(".//s:image", namespace)
        assert (
            base64.b64decode(image.attrib["href"].split(",", 1)[1])
            == originals[bundle[0].parent / frame["image"]]
        )
        assert svg.find(".//s:script", namespace) is None
        assert b"&lt;script&gt;" in raw
        assert all(
            node.attrib["href"].startswith(("#", "data:image/png;base64,"))
            for node in svg.iter()
            if "href" in node.attrib
        )
        boxes = [node for node in svg.findall(".//s:rect", namespace) if node.attrib.get("stroke")]
        assert [
            (box.attrib["x"], box.attrib["y"], box.attrib["width"], box.attrib["height"])
            for box in boxes
        ] == [("10", "10", "12", "14")] * 2
    assert all(path.read_bytes() == raw for path, raw in originals.items())


def test_last_image_hash_failure_creates_no_partial_output(bundle):
    image = bundle[0].parent / "frame3.png"
    image.write_bytes(image.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="SHA-256"):
        run(bundle)
    assert not bundle[3].exists()


def test_actual_dimensions_must_match_manifest(bundle):
    manifest = json.loads(bundle[0].read_bytes())
    manifest["frames"][2]["width"] = 65
    rebind(bundle, manifest)
    with pytest.raises(ValueError, match="dimensions"):
        run(bundle)
    assert not bundle[3].exists()


@pytest.mark.parametrize(
    "bad_path", ["../frame1.png", "C:/private.png", "x/../../frame1.png", "x\\frame1.png"]
)
def test_image_traversal_rejected_without_output(bundle, bad_path):
    manifest = json.loads(bundle[0].read_bytes())
    manifest["frames"][0]["image"] = bad_path
    rebind(bundle, manifest)
    with pytest.raises(ValueError, match="image"):
        run(bundle)
    assert not bundle[3].exists()


@pytest.mark.parametrize("mutation", ["schema", "pts", "bounds", "input_digest"])
def test_invalid_reading_rejected_before_output(bundle, mutation):
    reading = json.loads(bundle[2].read_bytes())
    if mutation == "schema":
        reading["schema"] = "wrong"
    elif mutation == "pts":
        reading["frames"][1]["frame_pts"] += 1
    elif mutation == "bounds":
        reading["frames"][1]["objects"][0]["boxes"] = [[10, 10, 65, 20]]
    else:
        reading["input_sha256"] = "f" * 64
    save(bundle[2], reading)
    with pytest.raises(ValueError):
        run(bundle)
    assert not bundle[3].exists()


def test_duplicate_json_key_rejected_before_output(bundle):
    raw = bundle[2].read_bytes()
    bundle[2].write_bytes(
        raw.replace(b'"reviewer_id": "b",', b'"reviewer_id": "b", "reviewer_id": "other",')
    )
    with pytest.raises(ValueError, match="duplicate JSON key"):
        run(bundle)
    assert not bundle[3].exists()


def test_existing_pack_never_overwritten(bundle):
    run(bundle)
    before = {path: path.read_bytes() for path in bundle[3].iterdir()}
    with pytest.raises(ValueError, match="new private subdirectory"):
        run(bundle)
    assert all(path.read_bytes() == raw for path, raw in before.items())


def test_output_cannot_escape_private_root(bundle):
    changed = (*bundle[:3], bundle[4].parent / "public", bundle[4])
    with pytest.raises(ValueError, match="private outputs"):
        run(changed)
    assert not changed[3].exists()


def test_symlink_image_rejected_even_if_bytes_match(bundle):
    image = bundle[0].parent / "frame1.png"
    target = bundle[0].parent / "actual.png"
    target.write_bytes(image.read_bytes())
    image.unlink()
    try:
        image.symlink_to(target)
    except OSError:
        pytest.skip("platform cannot create symlinks without privilege")
    with pytest.raises(ValueError, match="symlink"):
        run(bundle)
    assert not bundle[3].exists()


def test_cli_validation_error_has_bounded_message_and_no_output(bundle, capsys, monkeypatch):
    monkeypatch.setattr(cli, "ROOT", bundle[4].parent)
    reading = json.loads(bundle[2].read_bytes())
    reading["frames"] = []
    save(bundle[2], reading)
    with pytest.raises(SystemExit) as result:
        cli.main(
            [
                "--input",
                str(bundle[0]),
                "--reading-a",
                str(bundle[1]),
                "--reading-b",
                str(bundle[2]),
                "--out",
                str(bundle[3]),
            ]
        )
    assert result.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("comparison rejected:")
    assert len(captured.err) < 550
    assert not bundle[3].exists()


def test_no_point_is_invented_for_unresolved_object(bundle):
    report = run(bundle)
    row = report["frames"][0]
    unresolved = [obj for obj in row["objects"] if obj["kind"] != "mitt"]
    assert all(
        obj["boxes_a"] == obj["boxes_b"] == [] and obj["max_iou"] is None for obj in unresolved
    )
    assert all("point" not in obj for obj in row["objects"])


def test_overlay_uses_short_color_coded_labels_and_explicit_legend(bundle):
    reading = json.loads(bundle[1].read_bytes())
    objects = reading["frames"][0]["objects"]
    objects[1].update(status="located", boxes=[[25, 10, 30, 20]])
    objects[2].update(status="located", boxes=[[10, 25, 20, 35], [25, 25, 35, 40]])
    save(bundle[1], reading)
    run(bundle)
    svg = ElementTree.fromstring((bundle[3] / "849843_1_1.svg").read_bytes())
    texts = svg.findall(".//{http://www.w3.org/2000/svg}text")
    labels = [node for node in texts if node.attrib.get("class") == "boxlabel"]
    assert [node.text for node in labels] == ["A M", "A H", "A G1", "A G2", "B M"]
    assert [node.attrib["style"] for node in labels] == ["fill:#00e5ff"] * 4 + ["fill:#ff5de4"]
    assert any("M=mitt, H=bare hand, G=protective gear" in (node.text or "") for node in texts)
    assert not any(
        "protective_gear" in (node.text or "") or "bare_hand" in (node.text or "")
        for node in labels
    )


def test_invalid_png_rejected_even_with_updated_hash(bundle):
    manifest = json.loads(bundle[0].read_bytes())
    path = bundle[0].parent / "frame3.png"
    path.write_bytes(b"not a PNG")
    manifest["frames"][2]["image_sha256"] = cli.digest(path.read_bytes())
    rebind(bundle, manifest)
    for reading_path in bundle[1:3]:
        reading = json.loads(reading_path.read_bytes())
        reading["frames"][2]["image_sha256"] = manifest["frames"][2]["image_sha256"]
        save(reading_path, reading)
    with pytest.raises(ValueError, match="invalid PNG"):
        run(bundle)
    assert not bundle[3].exists()
