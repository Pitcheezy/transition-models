"""CV-33 pilot harness: stateless batching, opaque ids and strict layer-A intake."""

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
