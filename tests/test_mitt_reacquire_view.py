"""A comparison page must preserve the baseline and bind every saved candidate row."""

import copy
import hashlib
import json
from collections import Counter
from dataclasses import asdict

import pytest
from PIL import Image

from intent import mitt_reacquire_view as view
from intent.mitt_reacquire import ReacquireParams, SegmentedStationarySelector
from intent.mitt_stationary import StationaryParams, StationarySelector
from intent.mitt_tracking import TrackParams


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal_pack(args):
    pack = args["pack"]
    receipt = {
        "schema": "pitcheezy-ocr-frame-view-receipt-v1",
        "independent_decoded_pts_verified": False,
        "input_unchanged": True,
        "input_sha256": {"ocr_observations": sha(args["ocr_observations"])},
        "files": {
            p.relative_to(pack).as_posix(): {"sha256": sha(p), "bytes": p.stat().st_size}
            for p in pack.rglob("*")
            if p.is_file() and p.name != "receipt.json"
        },
    }
    save(pack / "receipt.json", receipt)
    args["pack_receipt_sha256"] = sha(pack / "receipt.json")


def seal_report(args):
    base, candidate = read(args["baseline_records"]), read(args["candidate_records"])
    report = {
        "schema": "pitcheezy-mitt-reacquire-pilot-dev-v1",
        "device": "cpu",
        "candidate_records_sha256": sha(args["candidate_records"]),
        "saved_tracking_records_sha256": sha(args["baseline_records"]),
        "base_regression": {"equal_to_saved_records": True, "rows": len(base)},
        "metrics": {
            "totals": {
                "frames": len(base),
                "pitches": len({r["pitch_id"] for r in base}),
                "base_states": dict(Counter(r["state"] for r in base)),
                "candidate_states": dict(Counter(r["state"] for r in candidate)),
            }
        },
    }
    for name, params in (
        ("track", TrackParams()),
        ("reacquire", ReacquireParams()),
        ("stationary", StationaryParams()),
    ):
        report[name + "_params"] = asdict(params)
        report[name + "_params_sha256"] = params.digest()
    save(args["candidate_report"], report)
    args["candidate_report_sha256"] = sha(args["candidate_report"])


@pytest.fixture
def inputs(tmp_path):
    pack = tmp_path / "pack"
    pack.mkdir()
    args = {
        "pack": pack,
        "out": tmp_path / "comparison",
        **{
            key: tmp_path / (key + ".json")
            for key in (
                "candidate_report",
                "candidate_records",
                "baseline_records",
                "ocr_observations",
            )
        },
    }
    base, candidate, pitches = [], [], []
    for p in range(1, 5):
        pitch = f"747139:3:{p}"
        frames = []
        selector, segmented = StationarySelector(), SegmentedStationarySelector()
        prior = "unseeded"
        for i in range(12):
            index = 600 + p * 120 + i * 6
            image = tmp_path / "source.jpg"
            Image.new("RGB", (1280, 720), (p * 40, i * 15, 50)).save(image)
            raw = image.read_bytes()
            digest = sha(image)
            row = {
                "pitch_id": pitch,
                "frame_index": index,
                "frame_seconds": index * 1001 / 60000,
                "source_sha256": digest,
                "source_pts_ticks": index * 1001,
                "source_time_base": "1/60000",
                "mitt_identity": "unverified",
                "state": "unseeded" if i == 0 else "tracking" if i < 5 else "lost",
                "reason": "no_seed"
                if i == 0
                else "external_seed"
                if i == 1
                else "patch_continuity"
                if i < 5
                else "low_similarity",
                "point_px": [600, 300] if 1 <= i < 5 else None,
            }
            base.append(row)
            selection = selector.step(row)
            changed = copy.deepcopy(row)
            state = (
                "unseeded"
                if i == 0
                else "reacquire_search"
                if i == 5
                else ("reacquire_candidate" if i == 6 else "lost" if i == 11 else "tracking")
            )
            reason = {
                0: "no_seed",
                1: "external_seed",
                5: "reacquire_low_similarity",
                6: "reacquire_candidate",
                7: "reacquired_continuity",
                11: "time_gap",
            }.get(i, "patch_continuity")
            changed.update(
                state=state,
                reason=reason,
                point_px=[600, 300] if state == "tracking" else None,
                reacquire_candidate_px=[600, 300] if i == 6 else None,
                segment_id=(1 if i < 5 else 2) if state == "tracking" else None,
                segment_end_reason="low_similarity" if i == 5 else "time_gap" if i == 11 else None,
                reacquisitions=int(i >= 7),
                prior_state=prior,
                quality={},
            )
            changed["stationary"] = segmented.step(changed)
            candidate.append(changed)
            prior = state
            if p < 4:
                relative = f"frames/{pitch.replace(':', '_')}/{index}.jpg"
                dest = pack / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(raw)
                frames.append(
                    {
                        "frame_index": index,
                        "frame_seconds": row["frame_seconds"],
                        "image": relative,
                        "sha256": digest,
                        "width": 1280,
                        "height": 720,
                        "selection": selection,
                    }
                )
        if p < 4:
            pitches.append({"pitch_id": pitch, "play_id": f"play-{p}", "frames": frames})
    payload = {
        "schema": "pitcheezy-track-frame-view-dev-v1",
        "time_basis": "manifest_index_timebase",
        "independent_decoded_pts_verified": False,
        "pitches": pitches,
    }
    observation_rows = []
    for frame in pitches[0]["frames"]:
        role = {
            "raw_text": "",
            "name_text": None,
            "lineup_order": None,
            "status": "abstain",
            "reason": "name_panel_absent",
            "temporal_relation": "not_compared",
            "compared_to_frame": None,
        }
        observation_rows.append(
            {
                "pitch_id": pitches[0]["pitch_id"],
                "frame_index": frame["frame_index"],
                "frame_seconds": frame["frame_seconds"],
                "image_sha256": frame["sha256"],
                "roles": {"pitcher": copy.deepcopy(role), "batter": copy.deepcopy(role)},
            }
        )
    time_basis = {
        "time_basis": "manifest_index_timebase",
        "independent_decoded_pts_verified": False,
    }
    save(
        args["ocr_observations"],
        {
            "schema": "pitcheezy-frame-name-observations-dev-v1",
            **time_basis,
            "pitch_id": pitches[0]["pitch_id"],
            "rows": observation_rows,
        },
    )
    save(
        pack / "ocr.json",
        {
            "schema": "pitcheezy-ocr-frame-view-dev-v1",
            **time_basis,
            "pitches": [{"pitch_id": pitches[0]["pitch_id"], "rows": observation_rows}],
            "pitches_without_observations": [p["pitch_id"] for p in pitches[1:]],
        },
    )
    save(pack / "payload.json", payload)
    save(args["baseline_records"], base)
    save(args["candidate_records"], candidate)
    seal_report(args)
    seal_pack(args)
    return args


def test_join_checks_offscreen_rows_and_preserves_existing_display_and_ocr(inputs):
    sources = {p: p.read_bytes() for p in inputs["pack"].rglob("*") if p.is_file()}
    payload_before = read(inputs["pack"] / "payload.json")
    result = view.build(**inputs)
    assert result["all_record_keys_checked"] == 48
    assert result["displayed_frames"] == 36
    assert result["observation_rows_bound"] == 12
    after = read(inputs["out"] / "payload.json")
    assert after.pop("comparison_schema") == view.COMPARISON_SCHEMA
    expected = {(r["pitch_id"], r["frame_index"]): r for r in read(inputs["candidate_records"])}
    for pitch in after["pitches"]:
        for frame in pitch["frames"]:
            joined = frame.pop("reacquire")
            row = expected[(pitch["pitch_id"], frame["frame_index"])]
            assert joined["selection"] == row["stationary"]
            assert joined["tracking"] == {k: v for k, v in row.items() if k != "stationary"}
    assert after == payload_before
    assert (inputs["out"] / "ocr.json").read_bytes() == sources[inputs["pack"] / "ocr.json"]
    assert all(p.read_bytes() == value for p, value in sources.items())
    assert all(
        sha(inputs["out"] / name) == info["sha256"] for name, info in result["files"].items()
    )


@pytest.mark.parametrize(
    "target", ["candidate_report", "candidate_records", "baseline_records", "ocr_observations"]
)
def test_changed_pinned_input_is_rejected_without_output(inputs, target):
    inputs[target].write_bytes(inputs[target].read_bytes() + b" ")
    with pytest.raises(ValueError, match="SHA|pinned"):
        view.build(**inputs)
    assert not inputs["out"].exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "boolean_index",
        "huge_time",
        "nan_time",
        "source_hash",
        "source_ticks",
        "duplicate",
        "reverse",
        "offscreen_key",
        "point_on_lost",
        "point_outside_image",
        "candidate_as_current",
        "invalid_segment",
        "boolean_segment",
        "wrong_count",
        "wrong_prior",
        "future_history",
        "wrong_stationary",
        "resurrect_after_lost",
    ],
)
def test_invalid_candidate_evidence_cannot_reach_the_view(inputs, mutation):
    rows = read(inputs["candidate_records"])
    if mutation == "boolean_index":
        rows[0]["frame_index"] = False
    elif mutation == "huge_time":
        rows[0]["frame_seconds"] = 10**400
    elif mutation == "nan_time":
        rows[0]["frame_seconds"] = float("nan")
    elif mutation == "source_hash":
        rows[0]["source_sha256"] = "0" * 64
    elif mutation == "source_ticks":
        rows[0]["source_pts_ticks"] = True
    elif mutation == "duplicate":
        rows[1] = copy.deepcopy(rows[0])
    elif mutation == "reverse":
        rows.reverse()
    elif mutation == "offscreen_key":
        rows[-1]["pitch_id"] = "747139:4:1"
    elif mutation == "point_on_lost":
        rows[11]["point_px"] = [600, 300]
    elif mutation == "point_outside_image":
        rows[7]["point_px"] = [1280, 300]
    elif mutation == "candidate_as_current":
        rows[6]["point_px"] = [600, 300]
    elif mutation == "invalid_segment":
        rows[7]["segment_id"] = 1
    elif mutation == "boolean_segment":
        rows[1]["segment_id"] = True
    elif mutation == "wrong_count":
        rows[7]["reacquisitions"] = 0
    elif mutation == "wrong_prior":
        rows[7]["prior_state"] = "tracking"
    elif mutation == "future_history":
        rows[0]["stationary"]["last_historical_candidate"] = rows[10]["stationary"]["event"]
    elif mutation == "wrong_stationary":
        rows[4]["stationary"]["current_candidate"] = None
    elif mutation == "resurrect_after_lost":
        rows[8]["state"], rows[8]["reason"], rows[8]["point_px"] = "lost", "time_gap", None
        rows[8]["segment_id"] = None
        rows[9]["prior_state"] = "lost"
    save(inputs["candidate_records"], rows)
    seal_report(inputs)
    with pytest.raises(ValueError):
        view.build(**inputs)
    assert not inputs["out"].exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "image_bytes",
        "image_key",
        "image_size",
        "selection",
        "missing_frame",
        "ocr_rows",
        "unsafe_path",
    ],
)
def test_pack_cannot_change_data_even_after_its_receipt_is_resealed(inputs, mutation):
    pack = inputs["pack"]
    payload = read(pack / "payload.json")
    frame = payload["pitches"][0]["frames"][0]
    if mutation == "image_bytes":
        (pack / frame["image"]).write_bytes(b"not a jpeg")
    elif mutation == "image_key":
        frame["sha256"] = "0" * 64
    elif mutation == "image_size":
        frame["width"] = True
    elif mutation == "selection":
        frame["selection"]["current_track_point_px"] = [600, 300]
    elif mutation == "missing_frame":
        payload["pitches"][0]["frames"].pop()
    elif mutation == "ocr_rows":
        ocr = read(pack / "ocr.json")
        ocr["pitches"][0]["rows"][0]["frame_seconds"] += 0.1
        save(pack / "ocr.json", ocr)
    save(pack / "payload.json", payload)
    seal_pack(inputs)
    if mutation == "unsafe_path":
        receipt = read(pack / "receipt.json")
        receipt["files"]["../escape"] = {"bytes": 0, "sha256": "0" * 64}
        save(pack / "receipt.json", receipt)
        inputs["pack_receipt_sha256"] = sha(pack / "receipt.json")
    with pytest.raises(ValueError):
        view.build(**inputs)
    assert not inputs["out"].exists()


def test_original_ocr_key_types_are_checked_even_when_all_hashes_agree(inputs):
    observations = read(inputs["ocr_observations"])
    observations["rows"][0]["frame_index"] = True
    save(inputs["ocr_observations"], observations)
    ocr = read(inputs["pack"] / "ocr.json")
    ocr["pitches"][0]["rows"] = observations["rows"]
    save(inputs["pack"] / "ocr.json", ocr)
    seal_pack(inputs)
    with pytest.raises(ValueError):
        view.build(**inputs)
    assert not inputs["out"].exists()


def test_no_overwrite_or_output_inside_source_pack(inputs):
    with pytest.raises(ValueError):
        view.build(**{**inputs, "out": inputs["pack"] / "child"})
    inputs["out"].mkdir()
    marker = inputs["out"] / "keep"
    marker.write_text("untouched")
    with pytest.raises(FileExistsError):
        view.build(**inputs)
    assert marker.read_text() == "untouched"


def test_strict_json_rejects_duplicate_keys_and_nonfinite_values():
    for raw in (b'{"key":1,"key":2}', b'{"key":Infinity}', b'{"key":1e999}'):
        with pytest.raises(ValueError):
            view._json(raw)


@pytest.mark.parametrize("encoding", ["utf-16", "utf-32"])
def test_json_rejects_non_utf8_before_template_embedding(encoding):
    with pytest.raises(ValueError, match="invalid JSON"):
        view._json('{"valid":true}'.encode(encoding))


@pytest.mark.parametrize("error", [OSError, Image.DecompressionBombError])
def test_decoder_failure_is_reported_without_partial_output(inputs, monkeypatch, error):
    def fail_decode(*_args, **_kwargs):
        raise error("invalid image")

    monkeypatch.setattr(view.Image, "open", fail_decode)
    with pytest.raises(ValueError, match="safely decoded"):
        view.build(**inputs)
    assert not inputs["out"].exists()
