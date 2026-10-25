"""CV-33 pilot harness: stateless batching, opaque ids and strict layer-A intake."""

import json

from intent import mitt_pilot as pilot


def items():
    return [
        {"pitch_id": "747139:3:1", "frames": [{"index": i} for i in (10, 22, 34)]},
        {"pitch_id": "747139:3:2", "frames": [{"index": i} for i in (50, 62)]},
        {"pitch_id": "747139:3:3", "frames": [{"index": i} for i in (90,)]},
    ]


def test_a_batch_never_holds_two_frames_of_one_pitch_and_every_frame_is_placed_once():
    batches = pilot.batches_for(items(), "salt")
    assert [len(b) for b in batches] == [3, 2, 1]
    for batch in batches:
        pitches = [r["pitch_id"] for r in batch]
        assert len(pitches) == len(set(pitches))
        assert [r["id"] for r in batch] == sorted(r["id"] for r in batch)
    placed = sorted((r["pitch_id"], r["index"]) for b in batches for r in b)
    assert placed == sorted((p["pitch_id"], f["index"]) for p in items() for f in p["frames"])


def test_ids_are_opaque_and_salted():
    a = pilot.opaque("747139:3:1", 10, "s1")
    assert len(a) == 12 and "747139" not in a and "10" != a
    assert a != pilot.opaque("747139:3:1", 10, "s2")
    assert a != pilot.opaque("747139:3:1", 16, "s1")


def test_plan_takes_every_second_grid_frame_up_to_release_from_the_first_ten():
    frames = [{"index": i, "roles": ["grid"]} for i in range(100, 160, 6)]
    frames.insert(3, {"index": 117, "roles": ["decision"]})
    manifest = {
        "pitches": [{"pitch_id": "x:0:0", "status": "excluded"}]
        + [
            {
                "pitch_id": f"x:{k}:1",
                "status": "extracted",
                "window": {"release_index": 136},
                "frames": frames,
            }
            for k in range(12)
        ]
    }
    chosen = pilot.plan(manifest)
    assert len(chosen) == 10 and chosen[0]["pitch_id"] == "x:0:1"
    assert [f["index"] for f in chosen[0]["frames"]] == [100, 112, 124, 136]


def test_reader_answers_outside_layer_a_are_rejected_not_repaired():
    mapping = {"pitch_id": "747139:3:1", "index": 14970}
    good = {
        "view": "live_centre_field",
        "catcher": "set",
        "mitt_visibility": "partial",
        "occluder": None,
        "mitt_center_px": [610, 250],
        "uncertainty_px": 6,
        "plate_front": {"left_end": [600, 320], "right_end": [660, 320]},
        "pitcher_phase": "before_delivery",
    }
    obs, error = pilot.to_observation(mapping, good)
    assert error is None and obs["frame_seconds"] == 14970 * 1001 / 60000
    assert obs["plate_front"]["left_end"] == [600, 320]
    for bad in (
        {**good, "view": "centre"},
        {**good, "mitt_visibility": "hidden"},
        {**good, "pitcher_phase": "windup"},
        *[
            {**good, "mitt_center_px": value}
            for value in (
                [None, 250],
                ["610", 250],
                [True, 250],
                [float("inf"), 250],
                [float("nan"), 250],
                [610],
                [],
                610,
                "610,250",
                {},
            )
        ],
        *[
            {**good, "plate_front": value}
            for value in (
                [],
                {},
                {"left_end": [None, 320], "right_end": [660, 320]},
                {"left_end": [600, 320], "right_end": [600, 320]},
            )
        ],
        [],
    ):
        obs, error = pilot.to_observation(mapping, bad)
        assert obs is None and error.startswith("schema:")


def test_reader_jumps_count_only_adjacent_usable_frames():
    def o(i, x, view="live_centre_field"):
        return {
            "frame_seconds": 10 + 0.2 * i,
            "view": view,
            "catcher": "set",
            "mitt_visibility": "full",
            "mitt_center_px": [x, 200.0],
        }

    seq = [o(0, 600), o(1, 640), o(2, 641), o(3, 700, view="other_view"), o(4, 760), o(6, 700)]
    jumps = pilot.reader_jumps(seq)
    # 600->640 (40) and 640->641 (1); the cut frame is unusable; 760->700 is 0.4 s apart
    assert jumps == {"pairs": 2, "over_30px": 1, "over_50px": 0, "median_px": 20.5}


def test_sensitivity_grid_is_fixed_and_centred_on_dev_v1():
    cells = {(c["hold_radius_px"], c["min_hold_seconds"]) for c in pilot.SENSITIVITY_GRID}
    from intent import mitt_temporal as mt

    assert (mt.PARAMS_DEV_V1["hold_radius_px"], mt.PARAMS_DEV_V1["min_hold_seconds"]) in cells
    assert len(cells) == 6


def test_evaluate_end_to_end_on_a_tiny_pilot(tmp_path):
    pid, first = "747139:3:1", 14910  # real key: timing and v0 points come from the saved files
    mapping, frames = [], []
    for k in range(8):
        mapping.append(
            {
                "batch": "b01",
                "id": f"s{k}",
                "pitch_id": pid,
                "index": first + 12 * k,
                "kind": "sequence",
                "image_sha256": "0" * 64,
            }
        )
        centre = [640.0, 240.0] if k >= 2 else None
        frames.append(
            {
                "id": f"s{k}",
                "view": "live_centre_field" if k >= 2 else "other_view",
                "catcher": "set" if k >= 2 else "not_visible",
                "mitt_visibility": "full" if k >= 2 else "out_of_view",
                "occluder": None,
                "mitt_center_px": centre,
                "uncertainty_px": 8 if centre else None,
                "plate_front": {"left_end": [610, 320], "right_end": [690, 320]}
                if k == 3
                else None,
                "pitcher_phase": "before_delivery",
                "note": "",
            }
        )
    mapping.append(
        {
            "batch": "b02",
            "id": "r0",
            "pitch_id": pid,
            "index": 14970,
            "kind": "v0_reread",
            "image_sha256": "0" * 64,
        }
    )
    frames2 = [
        {
            "id": "r0",
            "view": "live_centre_field",
            "catcher": "set",
            "mitt_visibility": "full",
            "occluder": None,
            "mitt_center_px": [646.0, 241.0],
            "uncertainty_px": 6,
            "plate_front": None,
            "pitcher_phase": "before_delivery",
            "note": "",
        }
    ]
    (tmp_path / "answers").mkdir()
    (tmp_path / "pilot_private.json").write_text(json.dumps({"pitches": [pid], "mapping": mapping}))
    (tmp_path / "answers" / "b01.json").write_text(json.dumps({"batch": "b01", "frames": frames}))
    (tmp_path / "answers" / "b02.json").write_text(
        json.dumps({"batch": "b02", "frames": frames2 + [{"id": "zz"}]})
    )
    delivery = tmp_path / "delivery.json"
    delivery.write_text(
        json.dumps(
            {
                "definition": "d",
                "uncertainty_seconds": 0.1,
                "annotator": "test",
                "pitches": {pid: {"delivery_start_seconds": 250.0}},
            }
        )
    )
    out = pilot.evaluate(tmp_path, tmp_path / "out.json", delivery)
    assert out["reader_answers"]["answered"] == 9 and out["reader_answers"][
        "answer_file_problems"
    ] == {"unknown_id": 1}
    row = out["pitches"][0]
    assert row["frames_observed"] == 8 and row["usable_frames"] == 6
    cand = row["candidate_before_delivery_start"]
    assert cand is not None and cand["left_censored"] is True  # hold starts right after the cut
    assert cand["segment_start_after_window_start_s"] == 0.4  # third planned frame
    assert row["earliest_possible_emission_after_decision_s"] == -0.601  # 2 steps of 0.2 s >= 0.3 s
    assert row["conversion_before_delivery_start"] == "front_edge_units"
    assert row["same_frame_reread_status"] == "compared"
    assert out["delivery_start_annotation"]["annotator"] == "test"
    assert out["reader_calls"] == {"status": "unmeasured"}
    early = json.loads(delivery.read_text())
    early["pitches"][pid]["delivery_start_seconds"] = 248.9
    delivery.write_text(json.dumps(early))
    out = pilot.evaluate(tmp_path, tmp_path / "out.json", delivery)
    assert (
        out["pitches"][0]["undeterminable_before_delivery_start"]
        == "no_usable_frame:view_not_live_centre_field"
    )
    # A malformed answer is counted and skipped, not allowed to abort the entire pilot.
    frames[-1]["mitt_center_px"] = [None, 240]
    (tmp_path / "answers" / "b01.json").write_text(json.dumps({"batch": "b01", "frames": frames}))
    out = pilot.evaluate(tmp_path, tmp_path / "rejected.json", delivery)
    assert sum(out["reader_answers"]["schema_rejected"].values()) == 1
    assert out["pitches"][0]["frames_observed"] == 7
    assert out["pitches"][0]["usable_frames"] == 5
    assert out["pitches"][0]["same_frame_reread_status"] == "compared"
