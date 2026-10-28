import hashlib
import json
from copy import deepcopy

import pytest

from scripts.prepare_replay_evidence import prepare, sha


@pytest.fixture
def fixture(tmp_path):
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    image = audit_dir / "frame.png"
    image.write_bytes(b"synthetic image bytes")
    frame = {
        "image": "frame.png",
        "image_sha256": sha(image),
        "pts": 10,
        "clip_seconds": 10 / 90000,
    }
    row = {
        "pitch_key": "849843:1:1",
        "play_id": "synthetic-play",
        "clip_sha256": "a" * 64,
        "first_pts": 0,
        "time_base": "1/90000",
        "sampled_frames": [frame, dict(frame, image="other.png", pts=20)],
    }
    audit = audit_dir / "audit.json"
    audit.write_text(json.dumps({"records": [row]}))
    entry = {
        "image": "evidence/frame.png",
        "image_sha256": sha(image),
        "pitch_key": row["pitch_key"],
        "play_id": row["play_id"],
        "clip_sha256": row["clip_sha256"],
        "clip_first_pts": 0,
        "time_base": "1/90000",
        "frame_pts": 10,
        "clip_seconds": 10 / 90000,
        "release_lower_bound_pts": 20,
    }
    review = {
        "game_pk": 849843,
        "audit_sha256": sha(audit),
        "package_sidecar": {"entries": [entry]},
        "image_bindings": [
            {"image": entry["image"], "source_image": "frame.png", "sha256": sha(image)}
        ],
    }
    decisions = tmp_path / "decisions.json"
    decisions.write_text(json.dumps(review))
    return audit_dir, decisions, tmp_path / "out"


def test_prepare_preserves_source_and_reproduces_bytes(fixture):
    audit, decisions, out = fixture
    before = sha(audit / "audit.json")
    assert prepare(*fixture) == 1
    assert (out / "evidence/frame.png").read_bytes() == (audit / "frame.png").read_bytes()
    assert sha(audit / "audit.json") == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("pitch_key", "849843:2:1"),
        ("frame_pts", 11),
        ("release_lower_bound_pts", 99),
        ("image_sha256", "b" * 64),
    ],
)
def test_changed_frame_binding_rejected_before_output(fixture, field, value):
    _, path, out = fixture
    review = json.loads(path.read_text())
    review["package_sidecar"]["entries"][0][field] = value
    path.write_text(json.dumps(review))
    with pytest.raises(ValueError):
        prepare(*fixture)
    assert not out.exists()


def test_changed_audit_rejected(fixture):
    audit, _, out = fixture
    (audit / "audit.json").write_text("{}")
    with pytest.raises(ValueError):
        prepare(*fixture)
    assert not out.exists()


@pytest.fixture
def interval_fixture(fixture, tmp_path):
    audit_dir, decisions, out = fixture
    base = json.loads(decisions.read_text())
    sidecar = base["package_sidecar"]
    sidecar.update(schema="pitcheezy-service-review-evidence-v2", game_pk=849843)
    entry = sidecar["entries"][0]
    entry.update(
        status="candidate",
        reason="old point",
        point={"x": 5, "y": 5},
        image_width=10,
        image_height=10,
        context_crop=[0, 0, 10, 10],
    )
    decisions.write_text(json.dumps(base))
    interval_dir = tmp_path / "interval"
    interval_dir.mkdir()
    frames = []
    for index, pts in enumerate((8, 10, 12)):
        image = interval_dir / f"frame_{index}.png"
        image.write_bytes((audit_dir / "frame.png").read_bytes())
        frames.append(
            {
                "ordinal": index,
                "pts": pts,
                "clip_seconds": pts / 90000,
                "image": image.name,
                "image_sha256": sha(image),
            }
        )
    interval = {
        "lower_pts_inclusive": 8,
        "upper_pts_inclusive": 12,
        "expected_decoded_frames": 3,
        "representative_pts": 10,
    }
    actual = {
        "pitch_key": entry["pitch_key"],
        "play_id": entry["play_id"],
        "clip_sha256": entry["clip_sha256"],
        "first_pts": 0,
        "time_base": "1/90000",
        "interval": interval,
        "sampled_frames": frames,
    }
    audit_path = interval_dir / "audit.json"
    audit_path.write_text(
        json.dumps({"game_pk": 849843, "source_registry_sha256": "c" * 64, "records": [actual]})
    )
    reviewed = deepcopy(actual)
    reviewed["frames"] = reviewed.pop("sampled_frames")
    for frame in reviewed["frames"]:
        frame.update(review_decision="identity_unresolved", published_new_point_xy=None)
    reviewed.update(decoded_frames_in_interval=3, counts={"identity_unresolved": 3})
    review = {
        "schema": "pitcheezy-exhibition-interval-review-v1",
        "audit_sha256": sha(audit_path),
        "source_registry_sha256": "c" * 64,
        "records": [reviewed],
        "counts": {
            "pitches": 1,
            "frames": 3,
            "supported_development_candidate": 0,
            "identity_unresolved": 3,
            "posture_unresolved": 0,
            "new_point_outputs": 0,
            "independent_human_reviews": 0,
            "validated_targets": 0,
        },
    }
    review_path = tmp_path / "interval-review.json"
    review_path.write_text(json.dumps(review, indent=2))
    return fixture, {"interval_review": review_path, "interval_audit_dir": interval_dir}


def test_interval_summary_suppresses_unresolved_point_without_changing_original(interval_fixture):
    args, kwargs = interval_fixture
    before = args[1].read_bytes()
    assert prepare(*args, **kwargs) == 1
    result = json.loads((args[2] / "review-evidence.json").read_bytes())
    assert result["schema"] == "pitcheezy-service-review-evidence-v3"
    row = result["entries"][0]
    assert row["point"] is None and row["status"] == "abstained"
    assert row["interval_review"]["decoded_frames"] == 3
    assert row["interval_review"]["identity_unresolved"] == 3
    assert row["interval_review"]["representative_decision"] == "identity_unresolved"
    assert (
        row["interval_review"]["source_sha256_lf"]
        == hashlib.sha256(
            kwargs["interval_review"].read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest()
    )
    assert args[1].read_bytes() == before


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r["records"][0].update(pitch_key="849843:1:2"),
        lambda r: r["records"].append(deepcopy(r["records"][0])),
        lambda r: r["records"][0].update(play_id="wrong"),
        lambda r: r["records"][0].update(clip_sha256="f" * 64),
        lambda r: r["records"][0].update(time_base="1/60"),
        lambda r: r["records"][0]["interval"].update(upper_pts_inclusive=20),
        lambda r: r["records"][0]["frames"].pop(),
        lambda r: r["records"][0]["frames"][1].update(pts=8),
        lambda r: r["records"][0]["frames"].reverse(),
        lambda r: r["records"][0]["frames"][1].update(ordinal=99),
        lambda r: r["records"][0]["frames"][1].update(image_sha256="f" * 64),
        lambda r: r["records"][0]["frames"][1].update(clip_seconds=float("nan")),
        lambda r: r["records"][0]["frames"][1].update(published_new_point_xy=[2, 3]),
        lambda r: r["records"][0]["frames"][1].update(review_decision="verified"),
        lambda r: r["records"][0].update(counts={"identity_unresolved": 2}),
        lambda r: r["counts"].update(frames=2),
        lambda r: r["counts"].update(independent_human_reviews=1),
        lambda r: r.update(source_registry_sha256="d" * 64),
    ],
)
def test_interval_malformed_source_rejected_before_output(interval_fixture, mutation):
    args, kwargs = interval_fixture
    path = kwargs["interval_review"]
    review = json.loads(path.read_bytes())
    mutation(review)
    path.write_text(json.dumps(review))
    with pytest.raises(ValueError):
        prepare(*args, **kwargs)
    assert not args[2].exists()


def test_interval_actual_image_tamper_is_rejected(interval_fixture):
    args, kwargs = interval_fixture
    (kwargs["interval_audit_dir"] / "frame_0.png").write_bytes(b"replaced")
    with pytest.raises(ValueError, match="image bytes"):
        prepare(*args, **kwargs)
    assert not args[2].exists()


def test_interval_requires_both_inputs(fixture, tmp_path):
    with pytest.raises(ValueError, match="together"):
        prepare(*fixture, interval_review=tmp_path / "unused")
    assert not fixture[2].exists()


def test_interval_canonical_lf_sha_independent_of_checkout_newlines(interval_fixture):
    args, kwargs = interval_fixture
    path = kwargs["interval_review"]
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    expected = hashlib.sha256(raw).hexdigest()
    path.write_bytes(raw.replace(b"\n", b"\r\n"))
    prepare(*args, **kwargs)
    row = json.loads((args[2] / "review-evidence.json").read_bytes())["entries"][0]
    assert row["interval_review"]["source_sha256_lf"] == expected
