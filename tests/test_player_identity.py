"""Synthetic identity contracts; manual evidence is never generated from feed player IDs."""

import json
import subprocess
import sys
from copy import deepcopy

import pytest
from PIL import Image

from src.data.blind_review import canonical_hash, read_json
from src.data.player_identity import (
    REVIEW_SCHEMA,
    ROOT,
    build_name_roster,
    build_player_identity_evalset,
    bytes_hash,
    check_player_identity_evalset,
    resolve_name,
)
from src.vision.frames import frame_path

URL = "https://example.invalid/synthetic.mp4"


@pytest.fixture
def inputs():
    people = {
        10: ("Tylor Megill", "Megill", "away"),
        20: ("Marcell Ozuna", "Ozuna", "home"),
        30: ("Jose Iglesias", "Iglesias", "away"),
        40: ("Raisel Iglesias", "Iglesias", "home"),
    }
    teams = {"away": {"id": 1, "abbreviation": "NYM"}, "home": {"id": 2, "abbreviation": "ATL"}}
    feed = {
        "gamePk": 7,
        "gameData": {
            "status": {"abstractGameState": "Final"},
            "teams": teams,
            "players": {
                f"ID{i}": {"id": i, "fullName": name, "lastName": last}
                for i, (name, last, _) in people.items()
            },
        },
        "liveData": {
            "boxscore": {
                "teams": {
                    side: {
                        "team": teams[side],
                        "players": {
                            f"ID{i}": {"person": {"id": i, "fullName": name}}
                            for i, (name, _, own) in people.items()
                            if own == side
                        },
                    }
                    for side in teams
                }
            },
            "plays": {"allPlays": []},
        },
    }
    manifest = {"schema": "mlb_video_manifest_v1", "game_pk": 7, "pitches": []}
    timing = {
        "schema": "mlb_broadcast_timing_v1",
        "game_pk": 7,
        "source": {
            "page_url": "https://example.invalid/video",
            "media_url": URL,
            "duration_seconds": 100,
        },
        "annotations": [],
    }
    review = {
        "schema": REVIEW_SCHEMA,
        "game_pk": 7,
        "source": {"media_url": URL},
        "reviewed_by": "Synthetic fixture",
        "reviewer_kind": "ai_assisted",
        "reviewed_on": "2026-09-27",
        "rows": [],
        "context_observations": [],
    }
    for pa, seconds in ((1, (10, 20, 50)), (2, (60,))):
        play = {
            "about": {"atBatIndex": pa - 1},
            "matchup": {"pitcher": {"id": 10}, "batter": {"id": 20}},
            "playEvents": [],
        }
        feed["liveData"]["plays"]["allPlays"].append(play)
        for pitch, t in enumerate(seconds, 1):
            keys = {"game_pk": 7, "at_bat_number": pa, "pitch_number": pitch}
            play_id = f"play-{pa}-{pitch}"
            manifest["pitches"].append(
                {
                    **keys,
                    "identity_status": "verified",
                    "video": {"play_id": play_id},
                    "pre_state": {"pitcher": 10, "batter": 20},
                }
            )
            timing["annotations"].append(
                {**keys, "play_id": play_id, "status": "annotated", "decision_seconds": t}
            )
            play["playEvents"].append({"isPitch": True, "pitchNumber": pitch, "playId": play_id})
            for role, name in (("pitcher", "MEGILL"), ("batter", "OZUNA")):
                review["rows"].append(
                    {
                        **keys,
                        "play_id": play_id,
                        "role": role,
                        "name_text": name,
                        "readability": "readable",
                        "team": None,
                        "lineup_order": None,
                        "continuity": "unknown",
                        "evidence": {
                            "media_url": URL,
                            "frame_seconds": t,
                            "image_sha256": "a" * 64,
                            "path": f"frames/{t}.jpg",
                        },
                        "note": "Synthetic direct observation, not a real video reading.",
                    }
                )
    return manifest, timing, feed, review


def build(inputs):
    manifest, timing, feed, review = deepcopy(inputs)
    feed_hash = bytes_hash(json.dumps(feed, ensure_ascii=False).encode())
    manifest["feed_sha256"] = feed_hash
    timing["manifest_sha256"] = canonical_hash(manifest)
    review.update(
        manifest_sha256=canonical_hash(manifest),
        timing_sha256=canonical_hash(timing),
        feed_sha256=feed_hash,
    )
    return build_player_identity_evalset(manifest, timing, feed, review, feed_sha256=feed_hash)


def row(inputs, pa, pitch, role="batter"):
    return next(
        r
        for r in inputs[3]["rows"]
        if (r["at_bat_number"], r["pitch_number"], r["role"]) == (pa, pitch, role)
    )


def derived(document, pa, pitch, role="batter"):
    return next(
        r
        for r in document["rows"]
        if (r["at_bat_number"], r["pitch_number"], r["role"]) == (pa, pitch, role)
    )


def unreadable(item, continuity="confirmed"):
    item.update(name_text=None, readability="unreadable", continuity=continuity)


def test_whole_roster_exact_names_do_not_use_expected_role_or_player(inputs):
    roster = build_name_roster(inputs[2])
    assert resolve_name(" MEGILL ", "readable", None, roster) == [10]
    assert resolve_name("IGLESIAS", "readable", None, roster) == [30, 40]
    assert resolve_name("José Iglesias", "readable", None, roster) == [30]
    assert resolve_name("IGLESIAS", "readable", "ATL", roster) == [40]
    assert resolve_name("OZUN…", "partial", None, roster) == []
    assert resolve_name("OZUN", "readable", None, roster) == []
    row(inputs, 1, 1, "pitcher")["name_text"] = "IGLESIAS"
    result = derived(build(inputs), 1, 1, "pitcher")
    assert result["candidate_ids"] == [30, 40] and result["status"] == "abstain"
    row(inputs, 1, 1, "pitcher")["team"] = "NYM"
    result = derived(build(inputs), 1, 1, "pitcher")
    assert result["resolved_player_id"] == 30 and result["reference_player_id"] == 10
    assert result["matches_hindsight_reference"] is False  # wrong relative to feed is preserved


def test_hold_is_same_pa_confirmed_and_ages_from_original_observation(inputs):
    unreadable(row(inputs, 1, 2))
    unreadable(row(inputs, 1, 3))
    unreadable(row(inputs, 2, 1))
    document = build(inputs)
    second, third, next_pa = (
        derived(document, pa, pitch) for pa, pitch in ((1, 2), (1, 3), (2, 1))
    )
    assert (second["status"], second["age_seconds"], second["stale"]) == ("held", 10, False)
    assert second["identity_evidence"]["frame_seconds"] == 10
    assert (third["status"], third["age_seconds"], third["stale"]) == ("abstain", 40, True)
    assert next_pa["status"] == "abstain" and next_pa["resolved_player_id"] is None


@pytest.mark.parametrize("continuity", ["unknown", "changed"])
def test_unknown_continuity_or_role_change_clears_hold(inputs, continuity):
    unreadable(row(inputs, 1, 2), continuity)
    unreadable(row(inputs, 1, 3))
    document = build(inputs)
    assert derived(document, 1, 2)["status"] == "abstain"
    assert derived(document, 1, 3)["identity_evidence"] is None


def test_partial_or_ambiguous_new_name_cannot_hold_previous_identity(inputs):
    row(inputs, 1, 2).update(name_text="OZUN…", readability="partial", continuity="confirmed")
    unreadable(row(inputs, 1, 3))
    document = build(inputs)
    assert derived(document, 1, 2)["status"] == "abstain"
    assert derived(document, 1, 3)["resolved_player_id"] is None


@pytest.mark.parametrize("seconds", [9, 10.5, 20])
def test_nondecision_evidence_is_not_backfilled_or_looked_ahead(inputs, seconds):
    row(inputs, 1, 1)["evidence"]["frame_seconds"] = seconds
    row(inputs, 1, 1)["continuity"] = "confirmed"
    with pytest.raises(ValueError, match="decision frame|Future evidence"):
        build(inputs)


def test_context_is_audit_only_even_when_name_is_fully_readable(inputs):
    source = row(inputs, 1, 1)
    context = {
        k: deepcopy(source[k])
        for k in ("role", "name_text", "readability", "team", "lineup_order", "evidence", "note")
    }
    context["scope_at_bat_number"] = 1
    context["evidence"]["frame_seconds"] = 5
    inputs[3]["context_observations"].append(context)
    unreadable(source, "confirmed")
    document = build(inputs)
    assert derived(document, 1, 1)["status"] == "abstain"
    assert document["summary"]["context_only"] == 1


@pytest.mark.parametrize(
    "event",
    [
        {"isSubstitution": True},
        {"details": {"eventType": "offensive_substitution"}},
        {"details": {"eventType": "pitching_substitution"}},
        {"details": {"eventType": "defensive_switch"}},
    ],
)
def test_scoped_player_changes_are_unsupported_instead_of_trusting_pa_matchup(inputs, event):
    inputs[2]["liveData"]["plays"]["allPlays"][0]["playEvents"].append(event)
    with pytest.raises(ValueError, match="substitution/switch"):
        build(inputs)


@pytest.mark.parametrize(
    "event",
    [
        {"isSubstitution": True},
        {"details": {"eventType": "pitching_substitution"}},
        {"details": {"eventType": "defensive_switch"}},
    ],
)
def test_player_changes_recorded_before_the_first_pitch_keep_the_pa_matchup(inputs, event):
    # F-4h: a substitution/switch that precedes every pitch of the PA only says who starts it.
    inputs[2]["liveData"]["plays"]["allPlays"][0]["playEvents"].insert(0, event)
    document = build(inputs)
    assert document["summary"]["role_opportunities"] > 0


@pytest.mark.parametrize(
    "change", ["missing", "duplicate", "play_id", "feed_id", "future_source", "boolean_slot"]
)
def test_review_contract_rejects_invalid_or_incomplete_observed_rows(inputs, change):
    rows = inputs[3]["rows"]
    if change == "missing":
        rows.pop()
    elif change == "duplicate":
        rows.append(deepcopy(rows[0]))
    elif change == "play_id":
        rows[0]["play_id"] = "wrong"
    elif change == "feed_id":
        rows[0]["player_id"] = 10
    elif change == "future_source":
        rows[0]["evidence"]["media_url"] = URL + "?other"
    else:
        rows[1]["lineup_order"] = True
    with pytest.raises(ValueError):
        build(inputs)


def test_keyed_observations_ignore_list_order_and_snapshot_check_detects_changes(inputs):
    expected = build(inputs)
    inputs[3]["rows"].reverse()
    actual = build(inputs)
    assert actual["rows"] == expected["rows"]
    result = check_player_identity_evalset(actual)
    assert result["feed_bytes_reverified"] is False and result["observed"] == 8
    for key in ("rows", "roster", "review"):
        bad = deepcopy(actual)
        if key == "rows":
            bad[key][0]["resolved_player_id"] = 999
        elif key == "roster":
            bad[key][0]["full_name"] = "changed"
        else:
            bad[key]["rows"][0]["name_text"] = "changed"
        with pytest.raises(ValueError, match="changed|do not match"):
            check_player_identity_evalset(bad)


def test_exact_image_proof_checks_alternative_captures_and_hash_changes(inputs, tmp_path):
    document = build(inputs)
    for t in (10, 20, 50, 60):
        for label, shade in (("aaa", 20), ("zzz", 80)):
            path = frame_path(tmp_path / "frames", label, t, URL)
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (16, 16), (shade, shade, shade)).save(path)
            path.with_suffix(".jpg.json").write_text(
                json.dumps(
                    {
                        "schema": "broadcast_frame_cache_v1",
                        "media_url": URL,
                        "frame_seconds": t,
                        "sha256": bytes_hash(path.read_bytes()),
                    }
                )
            )
        for observation in document["review"]["rows"]:
            if observation["evidence"]["frame_seconds"] == t:
                observation["evidence"].update(
                    path=path.relative_to(tmp_path).as_posix(),
                    image_sha256=bytes_hash(path.read_bytes()),
                )
    # Rebuild from the amended synthetic review, rather than hand-editing derived outputs.
    document = build((*inputs[:3], document["review"]))
    assert check_player_identity_evalset(document, verify_frames=True, root=tmp_path)[
        "frame_bytes_reverified"
    ]
    path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="image hash changed"):
        check_player_identity_evalset(document, verify_frames=True, root=tmp_path)


def test_real_pa6_contract_when_ignored_feed_is_present():
    feed_path = ROOT / "data/raw/mlb_video/747139/feed.json"
    if not feed_path.is_file():
        pytest.skip("Optional frozen raw feed is not included in Git")
    results = ROOT / "docs/results/mlb_p0"
    document = build_player_identity_evalset(
        read_json(results / "game_747139_manifest.json"),
        read_json(results / "game_747139_timing.json"),
        read_json(feed_path),
        read_json(results / "game_747139_player_identity_review_pa6.json"),
        feed_sha256=bytes_hash(feed_path.read_bytes()),
    )
    assert document["summary"]["role_opportunities"] == 12
    assert (
        document["summary"]["observed"] == document["summary"]["matches_hindsight_reference"] == 11
    )
    assert document["summary"]["abstain"] == 1 and document["summary"]["held"] == 0
    assert resolve_name("IGLESIAS", "readable", None, document["roster"]) == [578428, 628452]


def test_cli_help_is_available_without_feed():
    run = subprocess.run(
        [sys.executable, str(ROOT / "scripts/73_build_player_identity_evalset.py"), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    assert run.returncode == 0 and "--verify-frames" in run.stdout


def test_held_identity_cannot_override_current_observed_team(inputs):
    unreadable(row(inputs, 1, 2))
    row(inputs, 1, 2)["team"] = "NYM"  # prior readable OZUNA is an ATL player
    result = derived(build(inputs), 1, 2)
    assert result["status"] == "abstain" and result["reason"] == "held_team_contradiction"
    assert result["resolved_player_id"] is None


@pytest.mark.parametrize("name", ["manifest", "timing", "feed", "review"])
def test_cli_refuses_output_alias_before_reading_or_overwriting_input(tmp_path, name):
    source = tmp_path / "source.json"
    source.write_text('{"sentinel":"preserve"}')
    run = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/73_build_player_identity_evalset.py"),
            "build",
            f"--{name}",
            str(source),
            "--output",
            str(source),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    assert run.returncode == 2 and "must not alias" in run.stderr
    assert source.read_text() == '{"sentinel":"preserve"}'


def test_cli_custom_input_requires_explicit_output(tmp_path):
    run = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/73_build_player_identity_evalset.py"),
            "build",
            "--review",
            str(tmp_path / "custom.json"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    assert run.returncode == 2 and "custom inputs requires an explicit --output" in run.stderr


@pytest.mark.parametrize(
    "canonical", ["game_747139_player_identity_evalset_pa6.json", "game_747139_timing.json"]
)
def test_cli_custom_build_cannot_overwrite_canonical_artifacts(tmp_path, canonical):
    run = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/73_build_player_identity_evalset.py"),
            "build",
            "--review",
            str(tmp_path / "custom.json"),
            "--output",
            str(ROOT / "docs/results/mlb_p0" / canonical),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    assert run.returncode == 2
    assert "canonical PA6 evalset" in run.stderr or "must not alias" in run.stderr


def test_cli_distinguishes_frozen_snapshot_check_from_full_feed_rebuild(inputs, tmp_path):
    document = build(inputs)
    manifest, timing, feed, _ = deepcopy(inputs)
    manifest["feed_sha256"] = document["input_hashes"]["feed_sha256"]
    timing["manifest_sha256"] = canonical_hash(manifest)
    command = [sys.executable, str(ROOT / "scripts/73_build_player_identity_evalset.py"), "check"]
    for name, value in (
        ("manifest", manifest),
        ("timing", timing),
        ("review", document["review"]),
        ("output", document),
    ):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        command.extend((f"--{name}", str(path)))
    feed_path = tmp_path / "feed.json"
    command.extend(("--feed", str(feed_path)))
    offline = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    assert offline.returncode == 0, offline.stderr
    assert json.loads(offline.stdout)["validation_level"] == "frozen_snapshot_recomputed"
    assert json.loads(offline.stdout)["feed_bytes_reverified"] is False
    feed_path.write_text(json.dumps(feed, ensure_ascii=False), encoding="utf-8")
    full = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    assert full.returncode == 0, full.stderr
    assert json.loads(full.stdout)["validation_level"] == "full_input_rebuild"
    assert json.loads(full.stdout)["feed_bytes_reverified"] is True
