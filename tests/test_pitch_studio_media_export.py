"""Official-video joins use fixed IDs and verified local bytes, not row order."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "media_export", ROOT / "scripts/export_pitch_studio_media.py"
)
EXPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORT)


@pytest.fixture
def source(tmp_path):
    game = json.loads((ROOT / "web/pitch-studio/game-849843.json").read_bytes())
    game["pitches"] = game["pitches"][:2]
    rows = []
    for i, pitch in enumerate(game["pitches"], 1):
        play = f"00000000-0000-0000-0000-{i:012d}"
        video = f"https://sporty-clips.mlb.com/observed_{i}==.mp4"
        data = f"synthetic clip bytes {i}".encode()
        page = (
            f'<link rel="canonical" href="https://baseballsavant.mlb.com/sporty-videos?playId&#x3D;{play}">'
            f'<video src="{video}"></video>'
        ).encode()
        (tmp_path / f"{i}.mp4").write_bytes(data)
        (tmp_path / f"{i}.html").write_bytes(page)
        rows.append(
            {
                "game_pk": 849843,
                "at_bat_number": pitch["at_bat_number"],
                "pitch_number": pitch["pitch_number"],
                "play_id": play,
                "pitcher_id": pitch["pitcher"]["id"],
                "batter_id": pitch["batter"]["id"],
                "inning": pitch["situation"]["inning"],
                "inning_topbot": pitch["situation"]["half"],
                "pitch_type": pitch["post"]["actual"]["pitch_type"],
                "status": "downloaded",
                "media_url": video,
                "media_candidates": json.dumps([video]),
                "page_path": f"{i}.html",
                "page_sha256": hashlib.sha256(page).hexdigest(),
                "file_path": f"{i}.mp4",
                "file_sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "duration_s": 7.01,
                "private_path": "DO_NOT_PUBLISH",
                "internal_credentials": "DO_NOT_PUBLISH",
            }
        )
    return rows, game, tmp_path


def run(source):
    rows, game, root = source
    return EXPORT.project(rows, game, root, "a" * 64, "b" * 64)


def test_id_join_is_order_independent_and_allowlisted(source):
    baseline = copy.deepcopy(source[:2])
    result = run(source)
    source[0].reverse()
    assert run(source) == result
    assert source[1] == baseline[1]
    assert result["source_pitch_count"] == 2 and len(result["records"]) == 2
    assert result["excluded"] == []
    assert "DO_NOT_PUBLISH" not in EXPORT.serialize(result).decode()
    assert result["records"][0]["page_url"].endswith(source[0][1]["play_id"])
    assert result["records"][0]["video"].endswith("observed_1==.mp4")


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("pitcher_id", 17, "pitcher_id_mismatch"),
        ("batter_id", 17, "batter_id_mismatch"),
        ("inning", 7, "inning_mismatch"),
        ("inning_topbot", "Bot", "inning_half_mismatch"),
        ("status", "pending", "clip_not_downloaded"),
        ("file_sha256", "0" * 64, "local_file_sha_mismatch"),
        ("bytes", 123, "local_file_size_mismatch"),
        ("page_sha256", "0" * 64, "local_file_sha_mismatch"),
        ("duration_s", float("nan"), "invalid_clip_duration"),
        ("duration_s", -1, "invalid_clip_duration"),
        ("duration_s", True, "invalid_clip_duration"),
        ("file_path", "../1.mp4", "unsafe_local_path"),
        ("file_path", "C:/private/file.mp4", "unsafe_local_path"),
        ("pitch_type", "private credential", "invalid_pitch_type"),
    ],
)
def test_bad_rows_are_explicitly_excluded_without_changing_other_pitches(
    source, field, value, reason
):
    source[0][0][field] = value
    result = run(source)
    assert [x["pitch_id"] for x in result["records"]] == ["849843:1:2"]
    assert result["excluded"] == [{"pitch_id": "849843:1:1", "reason": reason}]
    assert result["source_pitch_count"] == 2


def test_pitch_type_disagreement_preserves_both_sources_as_exclusion(source):
    source[0][0]["pitch_type"] = "FC"
    actual = source[1]["pitches"][0]["post"]["actual"]["pitch_type"]
    result = run(source)
    assert result["excluded"] == [
        {
            "pitch_id": "849843:1:1",
            "reason": "pitch_type_mismatch",
            "registry_pitch_type": "FC",
            "received_pitch_type": actual,
        }
    ]
    assert source[1]["pitches"][0]["post"]["actual"]["pitch_type"] == actual


@pytest.mark.parametrize(
    "url",
    [
        "http://sporty-clips.mlb.com/a.mp4",
        "https://evil.test/a.mp4",
        "https://sporty-clips.mlb.com.evil.test/a.mp4",
        "https://user:secret@sporty-clips.mlb.com/a.mp4",
        "https://sporty-clips.mlb.com/a.mp4?token=secret",
        "https://sporty-clips.mlb.com/a.mp4#secret",
        "https://sporty-clips.mlb.com:443/a.mp4",
        "https://sporty-clips.mlb.com/%2e%2e/a.mp4",
        "https://sporty-clips.mlb.com/a.mp4\n",
    ],
)
def test_nonpublic_or_unexpected_urls_never_reach_output(source, url):
    source[0][0]["media_url"] = url
    result = run(source)
    assert len(result["records"]) == 1
    assert result["excluded"][0]["reason"] in ("unsafe_media_url", "invalid_media_url")
    assert "secret" not in EXPORT.serialize(result).decode()


def test_observed_single_candidate_and_page_bytes_are_both_required(source):
    source[0][0]["media_candidates"] = json.dumps(
        [source[0][0]["media_url"], "https://sporty-clips.mlb.com/b.mp4"]
    )
    assert run(source)["excluded"][0]["reason"] == "ambiguous_media_candidates"
    source[0][0]["media_candidates"] = json.dumps([source[0][0]["media_url"]])
    page = (
        f'<link rel="canonical" href="https://baseballsavant.mlb.com/sporty-videos?playId={source[0][0]["play_id"]}">'
        '<video src="https://sporty-clips.mlb.com/changed.mp4"></video>'
    ).encode()
    (source[2] / "1.html").write_bytes(page)
    source[0][0]["page_sha256"] = hashlib.sha256(page).hexdigest()
    assert run(source)["excluded"][0]["reason"] == "page_media_mismatch"


def test_matching_media_url_cannot_be_taken_from_a_different_pitch_page(source):
    path = source[2] / "1.html"
    page = path.read_bytes().replace(
        source[0][0]["play_id"].encode(), source[0][1]["play_id"].encode()
    )
    path.write_bytes(page)
    source[0][0]["page_sha256"] = hashlib.sha256(page).hexdigest()
    assert run(source)["excluded"][0]["reason"] == "page_play_id_mismatch"


def test_duplicate_registry_key_or_play_id_is_rejected(source):
    source[0].append(copy.deepcopy(source[0][0]))
    with pytest.raises(ValueError, match="duplicate_registry_identity"):
        run(source)
    source[0].pop()
    source[0][1]["play_id"] = source[0][0]["play_id"]
    with pytest.raises(ValueError, match="duplicate_registry_identity"):
        run(source)


def test_game_key_integrity_and_locked_game_are_rejected(source):
    source[1]["pitches"][0]["pitch_id"] = "849843:1:2"
    with pytest.raises(ValueError, match="duplicate_or_wrong_game_pitch_id"):
        run(source)
    source[1]["game"]["game_pk"] = 849844
    with pytest.raises(ValueError, match="wrong_game"):
        run(source)


def test_missing_registry_row_remains_in_denominator(source):
    source[0].pop()
    result = run(source)
    assert result["source_pitch_count"] == 2
    assert result["excluded"] == [{"pitch_id": "849843:1:2", "reason": "registry_pitch_missing"}]


def test_unexpected_registry_row_is_not_silently_ignored(source):
    source[0][0]["pitch_number"] = 30
    with pytest.raises(ValueError, match="unexpected_registry_pitch"):
        run(source)


def test_missing_file_reason_does_not_publish_local_path(source):
    (source[2] / "1.mp4").unlink()
    result = run(source)
    assert result["excluded"] == [{"pitch_id": "849843:1:1", "reason": "local_file_unreadable"}]
    assert str(source[2]) not in EXPORT.serialize(result).decode()


def test_source_game_byte_pin_is_required_before_registry_access(tmp_path):
    fake = tmp_path / "game.json"
    fake.write_text("{}")
    with pytest.raises(ValueError, match="game_asset_changed"):
        EXPORT.export_game(tmp_path / "nonexistent", fake)


def test_committed_manifest_matches_game_identity_and_explicit_conflict():
    media_path = ROOT / "web/pitch-studio/game-849843-media.json"
    if not media_path.exists():
        pytest.skip("real export is generated after synthetic validation")
    game_path = ROOT / "web/pitch-studio/game-849843.json"
    game = json.loads(game_path.read_bytes())
    media = json.loads(media_path.read_bytes())
    assert media["game_sha256"] == hashlib.sha256(game_path.read_bytes()).hexdigest()
    assert media["source_pitch_count"] == 262
    by_id = {p["pitch_id"]: p for p in game["pitches"]}
    assert len(media["records"]) == 261
    assert media["excluded"] == [
        {
            "pitch_id": "849843:69:2",
            "reason": "pitch_type_mismatch",
            "registry_pitch_type": "SL",
            "received_pitch_type": "FC",
        }
    ]
    for row in media["records"]:
        pitch = by_id[row["pitch_id"]]
        assert row["pitcher_id"] == pitch["pitcher"]["id"]
        assert row["batter_id"] == pitch["batter"]["id"]
        assert row["pitch_type"] == pitch["post"]["actual"]["pitch_type"]
