import copy
import json

import pytest

from src.data import object_reference as o


def manifest():
    return {
        "schema": o.INPUT_SCHEMA,
        "source_commit": "a" * 40,
        "source_review_sha256_lf": "b" * 64,
        "game_pk": 849843,
        "frames": [
            {
                "pitch_key": f"849843:1:{n}",
                "play_id": f"00000000-0000-4000-8000-{n:012d}",
                "clip_sha256": str(n) * 64,
                "frame_pts": n * 100,
                "time_base": "1/90000",
                "image": f"frames/p{n}.png",
                "image_sha256": str(n + 3) * 64,
                "width": 1280,
                "height": 720,
                "context_crop": [450, 240, 660, 470],
            }
            for n in (1, 2, 3)
        ],
    }


def reading(source, reviewer="a"):
    return {
        "schema": o.READING_SCHEMA,
        "input_sha256": "c" * 64,
        "reviewer_id": reviewer,
        "model": "test-model",
        "prior_exposure": "synthetic_test",
        "coordinate_system": o.COORDINATE_SYSTEM,
        "frames": [
            {
                **{name: frame[name] for name in o.IDENTITY_FIELDS},
                "objects": [
                    {"kind": kind, "status": "unclear", "boxes": [], "reason": "synthetic"}
                    for kind in o.KINDS
                ],
            }
            for frame in source["frames"]
        ],
    }


def locate(obj, *boxes):
    obj.update(status="located", boxes=list(boxes))


@pytest.mark.parametrize(
    "raw",
    [
        '{"a":1,"a":2}',
        '{"nested":{"a":1,"a":2}}',
        '{"x":NaN}',
        '{"x":Infinity}',
        '{"x":-Infinity}',
        '{"x":1e999}',
        "[]",
        "null",
        b"\xff",
        b"\xef\xbb\xbf{}",
    ],
)
def test_strict_json_rejects_lossy_or_nonfinite_inputs(raw):
    with pytest.raises(ValueError):
        o.loads_json(raw)


def test_utf8_json_file_snapshot(tmp_path):
    path = tmp_path / "data.json"
    path.write_bytes('{"reason":"미트"}'.encode())
    assert o.load_json(path) == {"reason": "미트"}


def test_validated_objects_and_comparison_do_not_mutate_inputs():
    source = manifest()
    a, b = reading(source), reading(source, "b")
    before = copy.deepcopy((source, a, b))
    assert o.validate_input(source) == source
    assert o.validate_reading(a, source, "c" * 64) == a
    result = o.compare_readings(source, "c" * 64, a, b)
    assert (source, a, b) == before
    assert result["counts"] == {
        "frames": 3,
        "object_comparisons": 9,
        "classifications": {
            "located_pair_disjoint": 0,
            "located_pair_with_overlap": 0,
            "both_not_visible": 0,
            "one_or_both_unresolved": 9,
        },
    }
    assert result["frames"][0]["objects"][0]["max_iou"] is None
    assert "accuracy" not in json.dumps(result)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "wrong"),
        ("source_commit", "a" * 39),
        ("source_review_sha256_lf", "B" * 64),
        ("game_pk", True),
        ("game_pk", 849844),
        ("frames", []),
        ("frames", {}),
    ],
)
def test_input_metadata_is_strict(field, value):
    source = manifest()
    source[field] = value
    with pytest.raises(ValueError):
        o.validate_input(source)


@pytest.mark.parametrize(
    "field,value",
    [
        ("pitch_key", "849845:1:1"),
        ("pitch_key", "0849843:1:1"),
        ("pitch_key", "849843:0:1"),
        ("play_id", "00000000000040008000000000000001"),
        ("play_id", None),
        ("clip_sha256", "g" * 64),
        ("image_sha256", 123),
        ("frame_pts", True),
        ("frame_pts", -1),
        ("frame_pts", 1.0),
        ("time_base", "0/90000"),
        ("time_base", "1/0"),
        ("time_base", "0.1"),
        ("time_base", "1/090000"),
        ("width", 0),
        ("height", True),
        ("context_crop", [450, 240, 1281, 470]),
        ("context_crop", [450, 240, 450, 470]),
        ("context_crop", [450.0, 240, 660, 470]),
        ("context_crop", None),
    ],
)
def test_input_frame_identity_geometry_and_types(field, value):
    source = manifest()
    source["frames"][0][field] = value
    with pytest.raises(ValueError):
        o.validate_input(source)


@pytest.mark.parametrize(
    "path",
    [
        "../image.png",
        "/image.png",
        "C:/image.png",
        "frames\\image.png",
        "./image.png",
        "frames//image.png",
        "frames/../image.png",
        "frames/NUL.png",
        "frames/COM1.png",
        "frames./image.png",
        "https://x/image.png",
        "image.png:stream",
    ],
)
def test_input_path_is_portably_relative(path):
    source = manifest()
    source["frames"][0]["image"] = path
    with pytest.raises(ValueError, match="path"):
        o.validate_input(source)


@pytest.mark.parametrize("field", ["pitch_key", "play_id", "image"])
def test_input_duplicates_rejected(field):
    source = manifest()
    source["frames"][1][field] = source["frames"][0][field]
    with pytest.raises(ValueError, match="duplicate"):
        o.validate_input(source)


def test_image_paths_are_duplicate_on_case_insensitive_hosts():
    source = manifest()
    source["frames"][1]["image"] = source["frames"][0]["image"].upper()
    with pytest.raises(ValueError, match="duplicate"):
        o.validate_input(source)


@pytest.mark.parametrize("target", ["input", "input frame", "reading", "reading frame", "object"])
@pytest.mark.parametrize("operation", ["missing", "extra"])
def test_all_contract_objects_require_exact_fields(target, operation):
    source = manifest()
    a = reading(source)
    value = {
        "input": source,
        "input frame": source["frames"][0],
        "reading": a,
        "reading frame": a["frames"][0],
        "object": a["frames"][0]["objects"][0],
    }[target]
    if operation == "extra":
        value["unexpected"] = None
    else:
        del value[next(iter(value))]
    with pytest.raises(ValueError, match="fields"):
        o.validate_reading(a, source, "c" * 64)


@pytest.mark.parametrize("field", o.IDENTITY_FIELDS)
def test_reading_identity_mismatch_is_rejected(field):
    source = manifest()
    a = reading(source)
    a["frames"][0][field] = source["frames"][1][field]
    if field == "time_base":
        a["frames"][0][field] = "1/45000"
    with pytest.raises(ValueError):
        o.validate_reading(a, source, "c" * 64)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "wrong"),
        ("input_sha256", "d" * 64),
        ("coordinate_system", "crop_xyxy"),
        ("reviewer_id", ""),
        ("model", None),
        ("prior_exposure", "x" * 201),
        ("frames", None),
        ("frames", []),
    ],
)
def test_reading_metadata_validation(field, value):
    source = manifest()
    a = reading(source)
    a[field] = value
    with pytest.raises(ValueError):
        o.validate_reading(a, source, "c" * 64)


def test_reading_duplicate_and_extra_frames_cannot_replace_a_missing_frame():
    source = manifest()
    a = reading(source)
    a["frames"][1] = copy.deepcopy(a["frames"][0])
    with pytest.raises(ValueError, match="duplicate"):
        o.validate_reading(a, source, "c" * 64)
    a = reading(source)
    a["frames"].append(copy.deepcopy(a["frames"][0]))
    with pytest.raises(ValueError, match="extra"):
        o.validate_reading(a, source, "c" * 64)


@pytest.mark.parametrize(
    "box",
    [
        [0, 0, 0, 1],
        [0, 0, 1, 0],
        [-1, 0, 1, 1],
        [0, 0, 1281, 1],
        [0, 0, 1, 721],
        [0.0, 0, 1, 1],
        [False, 0, 1, 1],
        [0, 0, 1],
        [0, 0, float("nan"), 1],
        [0, 0, float("inf"), 1],
        {},
        None,
    ],
)
def test_invalid_located_box_rejected(box):
    source = manifest()
    a = reading(source)
    locate(a["frames"][0]["objects"][0], box)
    with pytest.raises(ValueError, match="box|coordinates"):
        o.validate_reading(a, source, "c" * 64)


@pytest.mark.parametrize(
    "field,value",
    [
        ("kind", "mask"),
        ("kind", []),
        ("status", "verified"),
        ("status", {}),
        ("reason", "  "),
        ("reason", "x" * 2001),
        ("reason", "a\x00b"),
        ("reason", "\ud800"),
        ("boxes", {}),
        ("boxes", [[1, 1, 2, 2]]),
    ],
)
def test_object_semantics_rejected(field, value):
    source = manifest()
    a = reading(source)
    a["frames"][0]["objects"][0][field] = value
    with pytest.raises(ValueError):
        o.validate_reading(a, source, "c" * 64)


@pytest.mark.parametrize("count", [0, 5])
def test_located_box_count_is_bounded(count):
    source = manifest()
    a = reading(source)
    locate(a["frames"][0]["objects"][0], *[[n, n, n + 1, n + 1] for n in range(count)])
    with pytest.raises(ValueError, match="1..4"):
        o.validate_reading(a, source, "c" * 64)


def test_duplicate_objects_and_boxes_rejected():
    source = manifest()
    a = reading(source)
    a["frames"][0]["objects"][1]["kind"] = "mitt"
    with pytest.raises(ValueError, match="duplicate kind"):
        o.validate_reading(a, source, "c" * 64)
    a = reading(source)
    locate(a["frames"][0]["objects"][0], [0, 0, 1, 1], [0, 0, 1, 1])
    with pytest.raises(ValueError, match="duplicate box"):
        o.validate_reading(a, source, "c" * 64)


def test_common_coordinates_distinguish_same_label_different_object_and_known_iou():
    source = manifest()
    a, b = reading(source), reading(source, "b")
    locate(a["frames"][0]["objects"][0], [0, 0, 10, 10])
    locate(b["frames"][0]["objects"][0], [10, 0, 20, 10])
    locate(a["frames"][1]["objects"][0], [0, 0, 10, 10], [30, 30, 40, 40])
    locate(b["frames"][1]["objects"][0], [5, 0, 15, 10])
    a["frames"][2]["objects"][0]["status"] = "not_visible"
    b["frames"][2]["objects"][0]["status"] = "not_visible"
    result = o.compare_readings(source, "c" * 64, a, b)
    first = result["frames"][0]["objects"][0]
    assert first["classification"] == "located_pair_disjoint"
    assert first["pairwise_ious"] == [[0.0]]
    second = result["frames"][1]["objects"][0]
    assert second["classification"] == "located_pair_with_overlap"
    assert second["pairwise_ious"] == [[pytest.approx(1 / 3)], [0.0]]
    assert second["max_iou"] == pytest.approx(1 / 3)
    assert result["frames"][2]["objects"][0]["classification"] == "both_not_visible"
    assert result["counts"]["classifications"] == {
        "located_pair_disjoint": 1,
        "located_pair_with_overlap": 1,
        "both_not_visible": 1,
        "one_or_both_unresolved": 6,
    }
    # A result consumer cannot alter the original stored response via shared box lists.
    first["boxes_a"][0][0] = 999
    assert a["frames"][0]["objects"][0]["boxes"][0][0] == 0


def test_identity_join_is_independent_of_both_frame_and_object_order():
    source = manifest()
    a, b = reading(source), reading(source, "b")
    locate(a["frames"][0]["objects"][0], [1, 1, 2, 2])
    locate(b["frames"][0]["objects"][0], [1, 1, 2, 2])
    before = o.compare_readings(source, "c" * 64, a, b)
    for response in (a, b):
        response["frames"].reverse()
        for frame in response["frames"]:
            frame["objects"].reverse()
    assert o.compare_readings(source, "c" * 64, a, b) == before


@pytest.mark.parametrize("statuses", [("not_visible", "located"), ("unclear", "not_visible")])
def test_missing_location_does_not_generate_an_overlap(statuses):
    source = manifest()
    a, b = reading(source), reading(source, "b")
    for response, status in zip((a, b), statuses, strict=True):
        obj = response["frames"][0]["objects"][0]
        obj["status"] = status
        if status == "located":
            obj["boxes"] = [[1, 1, 2, 2]]
    obj = o.compare_readings(source, "c" * 64, a, b)["frames"][0]["objects"][0]
    assert obj["classification"] == "one_or_both_unresolved"
    assert obj["max_iou"] is None and obj["pairwise_ious"] == []


def test_identical_reviewer_id_is_not_two_readers():
    source = manifest()
    with pytest.raises(ValueError, match="distinct reviewer"):
        o.compare_readings(source, "c" * 64, reading(source), reading(source))
