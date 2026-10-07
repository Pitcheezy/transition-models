"""Project a supplied S snapshot without claiming live timing or model equivalence.

This provisional profile comes from the teammate's 2026-10-07 STATUS, not from
an independently verified backend response. It is a local review format, not a
receiver-v1 packet or a prediction request. Unknown upstream fields are omitted.
"""

import copy
import math
import re
from datetime import datetime

INPUT_SCHEMA = "pitcheezy-service-game-v2"
OUTPUT_SCHEMA = "pitcheezy-service-review-v1"
PROFILE = "teammate_status_20261007_provisional_v1"
POST_FIELDS = {"actual", "we", "post", "result", "catcher_setup"}
ZONES = {
    f"{height}_{side}"
    for height in ("low", "middle", "high")
    for side in ("left", "middle", "right")
}


class ServiceGameError(ValueError):
    """Reject an inconsistent or unsupported service snapshot."""


def _fail(path, message):
    raise ServiceGameError(f"{path}: {message}")


def _object(value, path):
    if type(value) is not dict:
        _fail(path, "expected an object")
    return value


def _integer(value, path, low=0, high=2**31 - 1):
    if type(value) is not int or not low <= value <= high:
        _fail(path, f"expected an integer in [{low}, {high}]")
    return value


def _number(value, path, low=-20, high=20, *, nullable=False):
    if nullable and value is None:
        return None
    if type(value) not in (int, float) or not low <= value <= high or not math.isfinite(value):
        _fail(path, "expected a finite number in the supported range")
    return value


def _text(value, path, *, nullable=False, limit=1000):
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        _fail(path, "expected nonempty bounded text")
    return value


def _choice(value, choices, path):
    if not isinstance(value, str) or value not in choices:
        _fail(path, "unsupported value")
    return value


def _time(value, path):
    if value is None:
        return None
    _text(value, path, limit=80)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _fail(path, "expected an ISO timestamp with timezone")
    if "T" not in value or parsed.utcoffset() is None:
        _fail(path, "timestamp must include a time and timezone")
    return value


def _no_post_fields(value, path, depth=0):
    """Do not accept an explicitly post-pitch field inside pre-pitch containers."""
    if depth > 24:
        _fail(path, "nested input is too deep")
    if isinstance(value, dict):
        if POST_FIELDS.intersection(value):
            _fail(path, "post-pitch fields are forbidden in pre-pitch data")
        for item in value.values():
            _no_post_fields(item, path, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _no_post_fields(item, path, depth + 1)


def _person(value, path, hand_key):
    value = _object(value, path)
    _no_post_fields(value, path)
    hand = value.get(hand_key)
    if hand is not None:
        _choice(hand, {"L", "R", "S"} if hand_key == "side" else {"L", "R"}, path)
    return {
        "id": _integer(value.get("id"), path + ".id", 1),
        "name": _text(value.get("name"), path + ".name", limit=200),
        hand_key: hand,
    }


def _situation(value, row, path):
    value = _object(value, path)
    _no_post_fields(value, path)
    result = {
        key: _integer(value.get(key), path + "." + key, low, high)
        for key, low, high in (
            ("inning", 1, 99),
            ("outs", 0, 2),
            ("balls", 0, 3),
            ("strikes", 0, 2),
            ("bases", 0, 7),
            ("home_score", 0, 1000),
            ("away_score", 0, 1000),
        )
    }
    result["half"] = _choice(value.get("half"), {"Top", "Bot"}, path + ".half")
    if "inning" in row:
        _integer(row["inning"], path + ".row_inning", 1, 99)
    for key in ("inning", "half"):
        if key in row and row[key] != result[key]:
            _fail(path, "row and situation inning/half disagree")
    if "runners" in value:
        runners = _object(value["runners"], path + ".runners")
        bits = 0
        for key, bit in (("first", 1), ("second", 2), ("third", 4)):
            if type(runners.get(key)) is not bool:
                _fail(path + ".runners", "runner occupancy must be boolean")
            if runners[key]:
                bits += bit
        if bits != result["bases"]:
            _fail(path, "runners and bases bitmask disagree")
    return result


def _candidate(value, path):
    value = _object(value, path)
    detail = _object(value.get("detail"), path + ".detail")
    if "probability" not in detail:
        _fail(path + ".detail", "probability must be explicit, including null")
    probability = _number(detail["probability"], path + ".probability", 0, 1, nullable=True)
    zone = value.get("zone_id")
    if zone is not None:
        _choice(zone, ZONES, path + ".zone_id")
    if "target" not in value:
        _fail(path, "target must be explicit, including null")
    target = value["target"]
    if target is not None:
        target = _object(target, path + ".target")
        if zone is None:
            _fail(path, "target coordinates require a zone identifier")
        target = {k: _number(target.get(k), path + ".target." + k) for k in ("x", "z")}
    return {
        "rank": _integer(value.get("rank"), path + ".rank", 1, 30),
        "pitch_type": _text(value.get("pitch_type"), path + ".pitch_type", limit=20),
        "pitch_label": _text(value.get("pitch_label"), path + ".pitch_label", limit=100),
        "zone_id": zone,
        "zone_label": _text(value.get("zone_label"), path + ".zone_label", nullable=True),
        "target": target,
        "selection_probability": probability,
    }


def _recommendation(value, path):
    value = _object(value, path)
    _no_post_fields(value, path)
    status = _choice(value.get("status"), {"ready", "unsupported", "missing"}, path + ".status")
    raw = value.get("candidates")
    if not isinstance(raw, list) or len(raw) > 30:
        _fail(path, "expected at most 30 candidates")
    if (status == "ready") != bool(raw):
        _fail(path, "ready requires candidates; unsupported/missing require none")
    candidates = [_candidate(c, path + ".candidates") for c in raw]
    for key in ("rank", "pitch_type"):
        if len({c[key] for c in candidates}) != len(candidates):
            _fail(path, "duplicate candidate rank or pitch type")
    candidates.sort(key=lambda c: c["rank"])
    mass = math.fsum(
        c["selection_probability"] for c in candidates if c["selection_probability"] is not None
    )
    if mass > 1 + 1e-6:
        _fail(path, "candidate selection probabilities sum above one")
    policy = value.get("policy")
    if policy is not None:
        policy = _object(policy, path + ".policy")
        policy = {
            key: _text(policy.get(key), path + ".policy." + key, nullable=True)
            for key in ("name", "identity")
        }
    return {
        "status": status,
        "reason": _text(value.get("reason"), path + ".reason", nullable=True),
        "provenance": _choice(
            value.get("provenance", "absent"),
            {"captured_live", "asof_replay", "absent"},
            path + ".provenance",
        ),
        "recorded_at": _time(value.get("recorded_at"), path + ".recorded_at"),
        "policy": policy,
        "candidates": candidates,
        "known_selection_mass": mass,
        "distribution_complete": None,
        "event_probabilities": None,
        "location_basis": "historical_delivery_distribution_proxy_not_optimal_target",
    }


def _actual(value, path):
    if value is None:
        return None
    value = _object(value, path)
    result = {
        key: _text(value.get(key), path + "." + key, nullable=True)
        for key in (
            "pitch_type",
            "pitch_label",
            "description",
            "result_label",
            "event",
            "event_label",
            "play_text",
            "zone_label",
        )
    }
    result.update(
        {
            key: _number(value.get(key), path + "." + key, low, high, nullable=True)
            for key, low, high in (("speed_mph", 0, 150), ("x", -20, 20), ("z", -20, 20))
        }
    )
    # The STATUS does not establish the backend catcher's setup object shape.
    # True means a non-null raw value exists; even {} is not a verified estimate.
    result["has_setup_estimate"] = value.get("catcher_setup") is not None
    result["setup_x_ft"] = None
    result["setup_interpretation"] = "unverified_upstream_shape"
    return result


def normalize_service_game(payload, *, input_kind, source_sha256, reported_revision=None):
    """Validate and project a snapshot; preserve IDs and do not infer missing evidence."""
    _choice(input_kind, {"synthetic", "provided_export"}, "input_kind")
    if not isinstance(source_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", source_sha256):
        _fail("source_sha256", "expected the original bytes' lowercase SHA256")
    if reported_revision is not None and (
        not isinstance(reported_revision, str)
        or not re.fullmatch(r"[a-f0-9]{7,40}", reported_revision)
    ):
        _fail("reported_revision", "expected a reported 7-40 character hexadecimal revision")
    payload = _object(payload, "snapshot")
    if payload.get("schema") != INPUT_SCHEMA:
        _fail("schema", "expected pitcheezy-service-game-v2; receiver-v1 is a different contract")
    source = _object(payload.get("source"), "source")
    source_kind = _choice(source.get("kind"), {"archive", "live", "demo"}, "source.kind")
    game = _object(payload.get("game"), "game")
    game_pk = _integer(game.get("game_pk"), "game.game_pk", 1)
    feed = _object(payload.get("feed"), "feed")
    if type(feed.get("ok")) is not bool:
        _fail("feed.ok", "expected a boolean")
    feed = {
        "as_of": _time(feed.get("as_of"), "feed.as_of"),
        "ok": feed["ok"],
        "stale_s": _number(feed.get("stale_s"), "feed.stale_s", 0, 1e9, nullable=True),
    }
    if "cutoff" not in payload:
        _fail("cutoff", "must be explicit, including null; its time meaning is unverified")
    cutoff = payload["cutoff"]
    if cutoff is not None:
        _integer(cutoff, "cutoff", -(2**31), 2**31 - 1)
    bounds = _object(payload.get("zone_bounds"), "zone_bounds")
    bounds = {key: _number(bounds.get(key), "zone_bounds." + key) for key in ("bottom", "top")}
    if bounds["bottom"] >= bounds["top"]:
        _fail("zone_bounds", "bottom must be below top")
    raw_pitches = payload.get("pitches")
    if not isinstance(raw_pitches, list) or len(raw_pitches) > 2000:
        _fail("pitches", "expected at most 2000 pitches")
    pitches, keys, indexes = [], set(), set()
    for raw in raw_pitches:
        row = _object(raw, "pitch")
        index = _integer(row.get("index"), "pitch.index", 0, 100000)
        pa = _integer(row.get("at_bat_number"), "pitch.at_bat_number", 1, 999)
        number = _integer(row.get("pitch_number"), "pitch.pitch_number", 1, 100)
        pa_key, key = f"{game_pk}:{pa}", f"{game_pk}:{pa}:{number}"
        if row.get("key") != key or row.get("pa_key") != pa_key:
            _fail("pitch", "key/pa_key disagree with game, plate appearance or pitch number")
        if key in keys or index in indexes:
            _fail("pitch", "duplicate pitch key or original index")
        keys.add(key)
        indexes.add(index)
        pitches.append(
            {
                "index": index,
                "key": key,
                "pa_key": pa_key,
                "at_bat_number": pa,
                "pitch_number": number,
                "pre": {
                    "situation": _situation(row.get("situation_before"), row, "situation_before"),
                    "pitcher": _person(row.get("pitcher"), "pitcher", "hand"),
                    "batter": _person(row.get("batter"), "batter", "side"),
                    "recommendation": _recommendation(row.get("rec"), "rec"),
                },
                "post": {"actual": _actual(row.get("actual"), "actual")},
            }
        )
    pitches.sort(key=lambda p: p["index"])
    ordering = [(p["at_bat_number"], p["pitch_number"]) for p in pitches]
    if ordering != sorted(ordering):
        _fail("pitches", "original index conflicts with plate appearance/pitch order")
    summary = {
        "pitches": len(pitches),
        "ready": 0,
        "unsupported": 0,
        "missing": 0,
        "actual_available": 0,
        "uninterpreted_setup": 0,
    }
    for pitch in pitches:
        summary[pitch["pre"]["recommendation"]["status"]] += 1
        actual = pitch["post"]["actual"]
        summary["actual_available"] += actual is not None
        summary["uninterpreted_setup"] += bool(actual and actual["has_setup_estimate"])
    return {
        "schema": OUTPUT_SCHEMA,
        "profile": PROFILE,
        "source": {
            "input_kind": input_kind,
            "sha256": source_sha256,
            "reported_revision": reported_revision,
            "upstream_kind": source_kind,
        },
        "claims": {
            "verified_against_real_s_response": False,
            "live_timing_verified": False,
            "policy_evaluation_identity_verified": False,
            "complete_game_verified": False,
        },
        "units": {
            "target_x_z": "feet",
            "actual_x_z": "feet",
            "speed": "mph",
            "candidate_probability": "pitch_type_selection_share",
        },
        "game": {
            "game_pk": game_pk,
            "start": _time(game.get("start"), "game.start"),
            **{
                key: _text(game.get(key), "game." + key, nullable=True)
                for key in ("kst_date", "away_team", "home_team")
            },
        },
        "feed": feed,
        "cutoff": cutoff,
        "zone_bounds": bounds,
        "pitches": pitches,
        "summary": summary,
        "uninterpreted_sections": [
            key for key in ("current", "next", "pas", "linescore", "pregame") if key in payload
        ],
        "warnings": [
            "Provisional projection based on STATUS, not an independently verified S API contract.",
            "input_kind and revision are supplier declarations, not authenticated provenance.",
            "Candidate probabilities are selection shares; kept without top-k renormalization.",
            "Targets are historical delivery proxies, not validated optimal locations.",
            "Feed time, cutoff and captured_live do not prove pre-pitch availability.",
            "Catcher setup shape is unverified: raw setup values are not interpreted or copied.",
            "Only projected pitch fields are retained; current/next/PA and other metadata are not consumed.",
            "This local review contains post-pitch data; display hiding is not access control.",
        ],
    }


def build_pitch_view(report, pitch_key, *, revealed=False):
    """Return a display projection that keeps actual/setup hidden until explicit reveal.

    The complete report already holds post-pitch data. This controls presentation,
    not secrecy, live timing, an authentication boundary, or pre-pitch inference.
    """
    if type(revealed) is not bool:
        _fail("revealed", "expected an explicit boolean")
    if report.get("schema") != OUTPUT_SCHEMA or report.get("profile") != PROFILE:
        _fail("report", "expected the normalized provisional review report")
    matches = [pitch for pitch in report["pitches"] if pitch["key"] == pitch_key]
    if len(matches) != 1:
        _fail("pitch_key", "expected one exact pitch key")
    pitch = matches[0]
    return copy.deepcopy(
        {
            "schema": "pitcheezy-service-pitch-view-v1",
            "game_pk": report["game"]["game_pk"],
            "key": pitch["key"],
            "index": pitch["index"],
            "input_kind": report["source"]["input_kind"],
            "pre": pitch["pre"],
            "actual": pitch["post"]["actual"] if revealed else None,
            "revealed": revealed,
            "live_timing_verified": False,
        }
    )
