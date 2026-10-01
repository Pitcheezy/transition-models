"""M0: IntentEstimate v1 contract tests (three valid shapes, invalid inputs rejected) and hop 1 geometry."""

import json
from copy import deepcopy

import pytest

from intent.geometry import (
    homography_from_corners,
    inside_unit_square,
    project_point,
    reprojection_error_pixels,
)
from intent.run import build_records
from intent.schema import (
    IntentEstimateError,
    make_estimate,
    make_unavailable,
    validate_intent_estimate,
)

SHA = "a" * 64
METHOD = {"kind": "assistant_visual_estimate", "version": "v0"}
CORNERS = {
    "front_left": (600, 560),
    "front_right": (680, 560),
    "back_right": (676, 540),
    "back_left": (604, 540),
}
ZONE_STEP = {
    "source_frame": "image_pixels",
    "target_frame": "annotated_image_zone",
    "method": "plane_homography_plate_corners_to_unit_square",
    "version": "v0",
    "error": None,
    "error_units": "pixels",
    "error_status": "unmeasured",
    "evidence": {"plate_corners_image_pixels": {k: list(v) for k, v in CORNERS.items()}},
}


def normal():
    return make_estimate(
        "747139:6:2",
        "747139:decision_frame:525.50:evalset_525.50.jpg",
        SHA,
        METHOD,
        525.5,
        "assistant_visual_estimate",
        (640, 470),
        8,
        "2x crop with 20 px grid",
        annotated_zone=(0.5, -4.5, False),
        zone_transform=ZONE_STEP,
    )


def abstain():
    return make_unavailable(
        "747139:47:1",
        "747139:decision_frame:4610.25:evalset_4610.25.jpg",
        SHA,
        METHOD,
        4610.25,
        "assistant_visual_estimate",
        "catcher_hidden_by_umpire",
    )


def no_calibration():
    return make_estimate(
        "747139:76:1",
        "747139:decision_frame:7796.50:evalset_7796.50.jpg",
        SHA,
        METHOD,
        7796.5,
        "assistant_visual_estimate",
        (912, 804),
        25,
        "wide-angle frame, plate corners not resolvable",
    )


@pytest.mark.parametrize("factory", [normal, abstain, no_calibration])
def test_three_valid_shapes_pass_and_round_trip_json(factory):
    doc = factory()
    assert validate_intent_estimate(json.loads(json.dumps(doc))) == doc
    assert doc["is_intent_proxy"] is True and doc["claims"]["catcher_intent_verified"] is False
    assert (
        doc["claims"]["accuracy_estimate"] is None
        and doc["provenance"]["review_status"] == "unreviewed"
    )


def test_shapes_encode_how_far_the_chain_got():
    assert list(normal()["points"]) == ["image_pixels", "annotated_image_zone"]
    assert (
        normal()["deepest_frame"] == "annotated_image_zone"
        and normal()["blocked_by"] == "no_plate_plane_calibration"
    )
    assert (
        list(no_calibration()["points"]) == ["image_pixels"]
        and no_calibration()["transform_chain"] == []
    )
    assert (
        abstain()["points"] == {}
        and abstain()["deepest_frame"] is None
        and abstain()["blocked_by"] is None
    )


def _mutate(doc, path, value):
    doc = deepcopy(doc)
    node = doc
    for key in path[:-1]:
        node = node[key]
    if value == "__delete__":
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return doc


@pytest.mark.parametrize(
    "factory,path,value",
    [
        (normal, ("status",), "observed"),
        (normal, ("is_intent_proxy",), False),
        (normal, ("claims", "catcher_intent_verified"), True),
        (normal, ("claims", "independent_ground_truth"), True),
        (normal, ("claims", "accuracy_estimate"), 0.9),
        (normal, ("claims", "physical_plate_coordinates"), True),
        (normal, ("blocked_by",), None),
        (normal, ("blocked_by",), "something_else"),
        (normal, ("deepest_frame",), "plate_feet"),
        (normal, ("points", "annotated_image_zone"), "__delete__"),
        (normal, ("transform_chain",), []),
        (normal, ("transform_chain", 0, "error"), 3.0),
        (normal, ("transform_chain", 0, "error_status"), "measured"),
        (normal, ("transform_chain", 0, "target_frame"), "plate_feet"),
        (normal, ("pitch_id",), "747139-6-2"),
        (normal, ("clip_sha256",), "abc"),
        (normal, ("provenance", "label_source"), "guess"),
        (normal, ("provenance", "review_status"), "approved"),
        (normal, ("uncertainty", "value"), -1),
        (normal, ("evidence", "frame_time"), None),
        (normal, ("extra",), 1),
        (abstain, ("unavailable_reason",), None),
        (abstain, ("points",), {"image_pixels": {"x": 1, "y": 2}}),
        (abstain, ("deepest_frame",), "image_pixels"),
        (no_calibration, ("points", "image_pixels", "x"), float("nan")),
        (
            no_calibration,
            ("points", "plate_feet"),
            {"x": 0.1, "y": 2.0, "x_convention": "statcast_plate_x_catcher_view"},
        ),
    ],
)
def test_invalid_records_are_rejected(factory, path, value):
    with pytest.raises(IntentEstimateError):
        validate_intent_estimate(_mutate(factory(), path, value))


def test_make_estimate_refuses_a_zone_without_its_transform():
    with pytest.raises(IntentEstimateError):
        make_estimate(
            "1:1:1",
            "c",
            SHA,
            METHOD,
            1.0,
            "assistant_visual_estimate",
            (1, 1),
            1,
            "b",
            annotated_zone=(0, 0, True),
        )


def test_homography_sends_corners_to_the_unit_square_and_flags_outside_points():
    h = homography_from_corners(CORNERS)
    assert project_point(h, CORNERS["front_left"]) == pytest.approx((0, 0), abs=1e-9)
    assert project_point(h, CORNERS["back_right"]) == pytest.approx((1, 1), abs=1e-9)
    assert reprojection_error_pixels(h, CORNERS) < 1e-6
    inside = project_point(h, (640, 550))
    assert inside_unit_square(inside) and 0 < inside[0] < 1 and 0 < inside[1] < 1
    assert not inside_unit_square(project_point(h, (640, 470)))
    with pytest.raises(ValueError):
        homography_from_corners({**CORNERS, "back_right": CORNERS["back_left"]})


def test_build_records_emits_one_validated_line_per_annotated_pitch():
    timing = {
        "game_pk": 1,
        "annotations": [
            {
                "at_bat_number": 1,
                "pitch_number": 1,
                "status": "annotated",
                "decision_seconds": 10.25,
            },
            {
                "at_bat_number": 1,
                "pitch_number": 2,
                "status": "annotated",
                "decision_seconds": 20.5,
            },
            {
                "at_bat_number": 1,
                "pitch_number": 3,
                "status": "annotated",
                "decision_seconds": 30.0,
            },
            {
                "at_bat_number": 1,
                "pitch_number": 4,
                "status": "unavailable",
                "decision_seconds": None,
            },
        ],
    }
    points = {
        "schema": "intent_points_v0",
        "game_pk": 1,
        "method": METHOD,
        "label_source": "assistant_visual_estimate",
        "uncertainty_basis": "test",
        "frames": [
            {
                "at_bat_number": 1,
                "pitch_number": 1,
                "frame_seconds": 10.25,
                "image_sha256": SHA,
                "path": "outputs/frames/evalset_10.25.jpg",
                "status": "estimated",
                "mitt_center": [640, 470],
                "uncertainty_pixels": 8,
                "plate_corners": {k: list(v) for k, v in CORNERS.items()},
            },
            {
                "at_bat_number": 1,
                "pitch_number": 2,
                "frame_seconds": 20.5,
                "image_sha256": SHA,
                "path": "outputs/frames/evalset_20.50.jpg",
                "status": "unavailable",
                "unavailable_reason": "catcher_hidden",
                "mitt_center": None,
                "plate_corners": None,
            },
        ],
    }
    records, counters = build_records(1, timing, points)
    assert counters == {
        "lines": 3,
        "estimated": 1,
        "unavailable": 2,
        "zone": 1,
        "plate_feet": 1,
        "missing_annotation": 1,
    }
    assert [r["pitch_id"] for r in records] == ["1:1:1", "1:1:2", "1:1:3"]
    assert (
        records[0]["deepest_frame"] == "plate_feet"
        and records[2]["unavailable_reason"] == "no_point_annotation_for_pitch"
    )
    for r in records:
        validate_intent_estimate(r)
    bad = deepcopy(points)
    bad["frames"][0]["frame_seconds"] = 11.0
    with pytest.raises(ValueError):
        build_records(1, timing, bad)
