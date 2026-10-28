import sqlite3

import pytest

from src.data import replay_feasibility as f


def probe(pts):
    return {"streams": [{"time_base": "1/90000"}], "frames": [{"pts": x} for x in pts]}


def test_decoded_pts_not_nominal_fps():
    tb, rows = f.decode_index(probe([3000, 4502, 7505]))
    assert tb == "1/90000"
    assert rows[2]["clip_seconds"] == pytest.approx(4505 / 90000)
    assert rows[2]["seconds"] == pytest.approx(7505 / 90000)
    assert rows[2]["ordinal"] == 2


@pytest.mark.parametrize("pts", [[], [1, 1], [2, 1], [None], ["100"], [True]])
def test_invalid_pts_fail_closed(pts):
    with pytest.raises(ValueError):
        f.decode_index(probe(pts))


def test_sample_includes_last_and_uses_pts():
    _, rows = f.decode_index(probe([0, 1500, 45000, 46000, 90000, 91000]))
    assert [r["ordinal"] for r in f.sample_frames(rows)] == [0, 2, 4, 5]


@pytest.mark.parametrize("n", [0, 6, True])
def test_investigation_bound_precedes_database_open(n):
    with pytest.raises(ValueError, match="limited"):
        f.read_candidates("does-not-exist", n)


def test_eval_locked_game_rejected_before_pitch_query(tmp_path):
    with sqlite3.connect(tmp_path / "registry.sqlite") as conn:
        conn.execute("create table games(game_pk integer, split text)")
        conn.execute("insert into games values(849843,'eval_locked')")
    before = (tmp_path / "registry.sqlite").read_bytes()
    with pytest.raises(ValueError, match="development"):
        f.read_candidates(tmp_path)
    assert (tmp_path / "registry.sqlite").read_bytes() == before


def test_clip_escape_and_wrong_bytes_refused(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"clip")
    row = {
        "status": "downloaded",
        "file_path": str(clip),
        "bytes": 4,
        "file_sha256": f.digest(clip),
    }
    with pytest.raises(ValueError, match="outside"):
        f.clip_file(tmp_path, row)
    row.update(file_path="clip.mp4", file_sha256="0" * 64)
    with pytest.raises(ValueError, match="mismatch"):
        f.clip_file(tmp_path, row)


def test_failed_pitch_stays_in_denominator(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    (root / "registry.sqlite").write_bytes(b"test")
    row = {"pitch_key": "849843:1:1", "play_id": "a", "file_sha256": "a" * 64}
    monkeypatch.setattr(f, "read_candidates", lambda *_: [row])

    def reject(*_):
        raise ValueError("not decoded")

    monkeypatch.setattr(f, "inspect_clip", reject)
    report = f.build_audit(root, tmp_path / "out", "unused", "unused")
    assert report["examined"] == 1 and report["decoded"] == 0
    assert report["records"][0]["decode_status"] == "failed"
