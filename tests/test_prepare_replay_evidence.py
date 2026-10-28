import json

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
