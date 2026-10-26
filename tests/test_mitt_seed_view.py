"""The viewer joins full saved streams, including held pitches, without pixel inference."""

import copy
import hashlib
import json
from collections import Counter

import pytest
from PIL import Image

from intent import mitt_reacquire_pilot, mitt_seed_pilot
from intent import mitt_seed_view as view
from intent.mitt_reacquire import SegmentedStationarySelector
from intent.mitt_seed_gate import POLICY, POLICY_SHA256


def save(path, value):
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal_report(args):
    report = read(args["seed_report"])
    report["source_hashes"]["baseline"] = sha(args["baseline_records"])
    report["outputs"] = {
        "records_seed_gate.json": sha(args["seed_records"]),
        "gate_decisions.json": sha(args["gate_decisions"]),
    }
    save(args["seed_report"], report)
    args["seed_report_sha256"] = sha(args["seed_report"])


def seal_pack(args):
    pack = args["ocr_pack"]
    receipt = {
        "schema": "pitcheezy-ocr-frame-view-receipt-v1",
        "input_unchanged": True,
        "independent_decoded_pts_verified": False,
        "input_sha256": {"ocr_observations": sha(args["ocr_observations"])},
        "files": {
            p.relative_to(pack).as_posix(): {"sha256": sha(p), "bytes": p.stat().st_size}
            for p in pack.rglob("*")
            if p.is_file() and p.name != "receipt.json"
        },
    }
    save(pack / "receipt.json", receipt)
    args["ocr_pack_receipt_sha256"] = sha(pack / "receipt.json")


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    args = {
        k: tmp_path / k
        for k in (
            "bundle",
            "pilot",
            "seed_report",
            "seed_records",
            "gate_decisions",
            "baseline_records",
            "ocr_pack",
            "ocr_observations",
            "out",
        )
    }
    for name in ("bundle", "pilot", "ocr_pack"):
        args[name].mkdir()
    (args["pilot"] / "answers").mkdir()
    save(args["pilot"] / "pilot_private.json", {})
    save(args["pilot"] / "answers" / "b1.json", {})
    image_path = tmp_path / "source.jpg"
    Image.new("RGB", (1280, 720)).save(image_path)
    image = image_path.read_bytes()
    selected, observations, old_seeds, metadata = [], {}, {}, []
    for number in range(1, 4):
        pitch = f"747139:3:{number}"
        metadata.append({"pitch_id": pitch, "play_id": f"play-{number}"})
        old_seeds[pitch] = (0, [600, 300])
        for step in range(12):
            index = step * 6
            seconds = index * 1001 / 60000
            path = args["bundle"] / f"{number}-{index}.jpg"
            path.write_bytes(image)
            selected.append(
                (
                    pitch,
                    {
                        "index": index,
                        "pts_time": seconds,
                        "sha256": sha(path),
                        "bytes": len(image),
                        "path": path,
                    },
                )
            )
            if step % 2 == 0:
                observations[pitch, index] = {
                    "pitch_id": pitch,
                    "frame_index": index,
                    "frame_seconds": seconds,
                    "view": "live_centre_field",
                    "catcher": "set",
                    "mitt_visibility": "full",
                    "occluder": None,
                    "mitt_center_px": [600, 300],
                    "pitcher_phase": "before_delivery",
                    "uncertainty_px": 8 if number == 1 else 11,
                }
    save(args["bundle"] / "manifest.json", {"selection": metadata})
    preserved = {
        str(p): sha(p)
        for root in (args["bundle"], args["pilot"])
        for p in root.rglob("*")
        if p.is_file()
    }
    monkeypatch.setattr(
        view.inputs,
        "load_inputs",
        lambda *_: (
            copy.deepcopy(selected),
            copy.deepcopy(old_seeds),
            copy.deepcopy(observations),
            preserved.copy(),
            sha(args["bundle"] / "manifest.json"),
        ),
    )

    def forbidden(*_args, **_kwargs):
        pytest.fail("pixel tracker or model must not run")

    monkeypatch.setattr(mitt_reacquire_pilot, "replay_candidate", forbidden)
    monkeypatch.setattr(mitt_seed_pilot, "gated_replay", forbidden)
    monkeypatch.setattr(view.inputs, "replay", forbidden)
    seeds, decisions = view.choose(selected, observations)

    def rows(seed_map, gated):
        result, current = [], None
        for pitch, frame in selected:
            if current != pitch:
                current, selector, prior = pitch, SegmentedStationarySelector(), "unseeded"
            seed = seed_map[pitch]
            active = seed is not None and frame["index"] >= seed[0]
            first = active and frame["index"] == seed[0]
            row = {
                "pitch_id": pitch,
                "frame_index": frame["index"],
                "frame_seconds": frame["pts_time"],
                "source_pts_ticks": frame["index"] * 1001,
                "source_time_base": "1/60000",
                "source_sha256": frame["sha256"],
                "state": "tracking" if active else "unseeded",
                "reason": "external_seed" if first else "patch_continuity" if active else "no_seed",
                "point_px": [600, 300] if active else None,
                "reacquire_candidate_px": None,
                "segment_id": 1 if active else None,
                "segment_end_reason": None,
                "reacquisitions": 0,
                "prior_state": prior,
                "mitt_identity": "unverified",
                "seed_requested_px": [600, 300] if first else None,
                "seed_source": (
                    "saved_AI_seed_gate_dev_v1_current_observation"
                    if gated
                    else "saved_AI_first_usable_sequence_point"
                )
                if first
                else None,
                "raw_ai_point_px": [600, 300] if (pitch, frame["index"]) in observations else None,
            }
            if not first:
                del row["seed_requested_px"]
            row["stationary"] = selector.step(row)
            result.append(row)
            prior = row["state"]
        return result

    base, candidate = rows(old_seeds, False), rows(seeds, True)
    save(args["baseline_records"], base)
    save(args["seed_records"], candidate)
    save(args["gate_decisions"], decisions)
    provenance = view.inputs.saved_pilot_provenance(args["pilot"], preserved)
    save(
        args["seed_report"],
        {
            "schema": "pitcheezy-seed-gate-pilot-dev-v1",
            "policy": POLICY,
            "policy_sha256": POLICY_SHA256,
            "source_hashes": {
                "manifest": sha(args["bundle"] / "manifest.json"),
                "pilot": provenance["pilot_private_sha256"],
                "answers": provenance["answers_manifest_sha256"],
            },
            "saved_pilot_inputs": provenance,
            "baseline_every_field_reproduced": True,
            "all_input_bytes_unchanged": True,
            "independent_evaluation": False,
            "support_observations_are_not_truth": True,
            "mitt_identity": "unverified",
            "accuracy": "unmeasured",
            "baseline": view.summarize(base),
            "candidate": view.summarize(candidate),
            "baseline_rows": len(base),
            "saved_observation_keys_matched": len(observations),
            "seeded_pitches": 1,
            "decision_reasons": dict(Counter(d["reason"] for d in decisions)),
        },
    )
    seal_report(args)
    pitches = []
    for meta in metadata[:2]:
        frames = []
        for pitch, f in selected:
            if pitch != meta["pitch_id"]:
                continue
            relative = f"{pitch.replace(':', '_')}-{f['index']}.jpg"
            (args["ocr_pack"] / relative).write_bytes(image)
            frames.append(
                {
                    "frame_index": f["index"],
                    "frame_seconds": f["pts_time"],
                    "image": relative,
                    "sha256": f["sha256"],
                    "width": 1280,
                    "height": 720,
                }
            )
        pitches.append({**meta, "frames": frames})
    common = {"time_basis": "manifest_index_timebase", "independent_decoded_pts_verified": False}
    save(
        args["ocr_pack"] / "payload.json",
        {
            "schema": "pitcheezy-track-frame-view-dev-v1",
            **common,
            "pitches": pitches,
        },
    )
    role = {
        "raw_text": "",
        "name_text": None,
        "lineup_order": None,
        "status": "abstain",
        "reason": "no_panel",
        "temporal_relation": "not_compared",
        "compared_to_frame": None,
    }
    ocr_rows = [
        {
            "pitch_id": pitches[0]["pitch_id"],
            "frame_index": f["frame_index"],
            "frame_seconds": f["frame_seconds"],
            "image_sha256": f["sha256"],
            "roles": {"pitcher": copy.deepcopy(role), "batter": copy.deepcopy(role)},
        }
        for f in pitches[0]["frames"]
    ]
    save(
        args["ocr_observations"],
        {
            "schema": "pitcheezy-frame-name-observations-dev-v1",
            **common,
            "pitch_id": pitches[0]["pitch_id"],
            "rows": ocr_rows,
        },
    )
    save(
        args["ocr_pack"] / "ocr.json",
        {
            "schema": "pitcheezy-ocr-frame-view-dev-v1",
            **common,
            "pitches": [{"pitch_id": pitches[0]["pitch_id"], "rows": ocr_rows}],
            "pitches_without_observations": [pitches[1]["pitch_id"]],
        },
    )
    seal_pack(args)
    return args


def test_full_stream_preserves_rows_images_ocr_and_has_no_future_summary(fixture):
    source = {p: p.read_bytes() for p in fixture["bundle"].parent.rglob("*") if p.is_file()}
    result = view.build(**fixture)
    assert result["displayed_frames"] == 36 and result["displayed_pitches"] == 3
    assert result["seeded_pitches"] == 1 and result["pitches_without_seed"] == 2
    assert result["observation_rows_bound"] == 12 and result["frames_without_ocr"] == 24
    assert result["ocr_source_images_checked"] == 24
    payload = read(fixture["out"] / "payload.json")
    flat = [f for p in payload["pitches"] for f in p["frames"]]
    for frame, base, candidate, decision in zip(
        flat,
        read(fixture["baseline_records"]),
        read(fixture["seed_records"]),
        read(fixture["gate_decisions"]),
        strict=True,
    ):
        assert frame["tracking"] | {"stationary": frame["selection"]} == base
        assert (
            frame["seed_gate"]["tracking"] | {"stationary": frame["seed_gate"]["selection"]}
            == candidate
        )
        assert frame["seed_gate"]["decision"] == decision
        assert "reacquire" not in frame
    assert all(set(p) == {"pitch_id", "play_id", "frames"} for p in payload["pitches"])
    assert flat[1]["seed_gate"]["decision"]["seed"] is None
    assert flat[4]["seed_gate"]["decision"]["seed"] is not None
    assert all(f["seed_gate"]["tracking"]["point_px"] is None for f in flat[12:])
    ocr = read(fixture["out"] / "ocr.json")
    assert ocr["pitches"] == read(fixture["ocr_pack"] / "ocr.json")["pitches"]
    assert len(ocr["pitches_without_observations"]) == 2
    assert all(p.read_bytes() == raw for p, raw in source.items())
    assert all(
        sha(fixture["out"] / name) == info["sha256"] for name, info in result["files"].items()
    )


@pytest.mark.parametrize(
    "target",
    ["seed_report", "seed_records", "gate_decisions", "baseline_records", "ocr_observations"],
)
def test_pinned_input_change_rejected_before_output(fixture, target):
    fixture[target].write_bytes(fixture[target].read_bytes() + b" ")
    with pytest.raises(ValueError):
        view.build(**fixture)
    assert not fixture["out"].exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "bool_key",
        "huge_key",
        "nan",
        "sha",
        "duplicate",
        "reverse",
        "time",
        "selector",
        "future_history",
        "held_point",
        "early_seed",
        "seed_point",
        "wrong_initialized_point",
        "segment",
        "prior",
    ],
)
def test_resealed_candidate_semantic_corruption_rejected(fixture, mutation):
    rows = read(fixture["seed_records"])
    row = rows[4]
    if mutation == "bool_key":
        row["frame_index"] = True
    elif mutation == "huge_key":
        row["frame_index"] = 10**100
    elif mutation == "nan":
        row["frame_seconds"] = float("nan")
    elif mutation == "sha":
        row["source_sha256"] = "0" * 64
    elif mutation == "duplicate":
        rows[5] = copy.deepcopy(row)
    elif mutation == "reverse":
        rows.reverse()
    elif mutation == "time":
        row["frame_seconds"] += 0.1
    elif mutation == "selector":
        row["stationary"]["reason"] = "stationary"
    elif mutation == "future_history":
        rows[0]["stationary"]["last_historical_candidate"] = {"frame_index": 66}
    elif mutation == "held_point":
        rows[-1]["point_px"] = [600, 300]
    elif mutation == "early_seed":
        rows[0]["reason"] = "external_seed"
    elif mutation == "seed_point":
        row["seed_requested_px"] = [601, 300]
    elif mutation == "wrong_initialized_point":
        row["point_px"] = [601, 300]
    elif mutation == "segment":
        row["segment_id"] = True
    elif mutation == "prior":
        row["prior_state"] = "lost"
    save(fixture["seed_records"], rows)
    seal_report(fixture)
    with pytest.raises(ValueError):
        view.build(**fixture)
    assert not fixture["out"].exists()


@pytest.mark.parametrize(
    "mutation", ["future_support", "fake_missing_observation_seed", "identity", "policy"]
)
def test_resealed_gate_corruption_rejected(fixture, mutation):
    decisions = read(fixture["gate_decisions"])
    if mutation == "future_support":
        decisions[0]["support_keys"] = decisions[4]["support_keys"]
    elif mutation == "fake_missing_observation_seed":
        decisions[1]["seed"] = decisions[4]["seed"]
    elif mutation == "identity":
        decisions[4]["mitt_identity"] = "verified"
    elif mutation == "policy":
        decisions[4]["policy_sha256"] = "0" * 64
    save(fixture["gate_decisions"], decisions)
    seal_report(fixture)
    with pytest.raises(ValueError, match="gate decisions"):
        view.build(**fixture)
    assert not fixture["out"].exists()


@pytest.mark.parametrize(
    "source", [None, "manual_label", "saved_AI_seed_gate_dev_v1_current_observation"]
)
def test_resealed_baseline_seed_provenance_must_match_cv37b(fixture, source):
    rows = read(fixture["baseline_records"])
    assert rows[0]["reason"] == "external_seed"
    rows[0]["seed_source"] = source
    save(fixture["baseline_records"], rows)
    seal_report(fixture)
    with pytest.raises(ValueError, match="seed point or provenance"):
        view.build(**fixture)
    assert not fixture["out"].exists()


def test_raw_ocr_text_cannot_be_silently_replaced(fixture):
    ocr = read(fixture["ocr_pack"] / "ocr.json")
    ocr["pitches"][0]["rows"][0]["roles"]["batter"]["raw_text"] = "invented"
    save(fixture["ocr_pack"] / "ocr.json", ocr)
    seal_pack(fixture)
    with pytest.raises(ValueError, match="OCR source rows"):
        view.build(**fixture)


def test_nested_output_rejected_and_existing_output_not_overwritten(fixture):
    fixture["out"] = fixture["bundle"] / "new"
    with pytest.raises(ValueError, match="outside"):
        view.build(**fixture)
    fixture["out"] = fixture["bundle"].parent / "existing"
    fixture["out"].mkdir()
    with pytest.raises(FileExistsError):
        view.build(**fixture)
