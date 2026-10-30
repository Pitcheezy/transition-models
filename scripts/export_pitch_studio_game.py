"""Export only curated display fields from the fixed, privately received 849843 pack.

This is an internal static replay format, not a change to Song's publication contract.
The original archive/report remain private and unchanged. No endpoint, model revision,
win expectancy or unprovided probability is invented.
"""

import argparse
import hashlib
import json
import math
import re
import zipfile
from pathlib import Path

ZIP_SHA256 = "51af1e8861ac5e7294b185acb3f525fa2b421765152ff2a65abdbb2f92317546"
REPORT_SHA256 = "154d9cd1cb166552db5975137e2ba431b9ab48f94fcfa6bdd05304f645427c80"
SOURCE_SHA256 = "df606a11c6db465c054252ef8d331aeb23aa21565b4960bd586f3dcf8f62f6b7"
SCHEMA = "pitcheezy-static-game-v1"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value, low=-20, high=20, nullable=False):
    _require(
        (nullable and value is None)
        or (type(value) in (int, float) and math.isfinite(value) and low <= value <= high),
        "invalid finite numeric field",
    )
    return value


def _int(value, low=0, high=100000):
    _require(type(value) is int and low <= value <= high, "invalid integer field")
    return value


def _text(value, nullable=False):
    _require(
        (nullable and value is None)
        or (
            isinstance(value, str) and 0 < len(value) <= 300 and not any(ord(c) < 32 for c in value)
        ),
        "invalid text field",
    )
    return value


def _person(value, hand_field):
    _require(value[hand_field] in (None, "L", "R", "S"), "invalid handedness")
    return {
        "id": _int(value["id"], 1, 999999999),
        "name": _text(value["name"]),
        "hand": value[hand_field],
    }


def project(report):
    """Whitelist projection with semantic checks; read_fixed_zip supplies byte provenance."""
    _require(
        report["schema"] == "pitcheezy-service-review-v1"
        and report["profile"] == "teammate_export_20261009_v1",
        "wrong input format",
    )
    source = report["source"]
    _require(
        source["input_kind"] == "provided_export"
        and source["sha256"] == SOURCE_SHA256
        and source["upstream_kind"] == "archive"
        and source["reported_revision"] is None,
        "unexpected archive source",
    )
    game = report["game"]
    _require(game["game_pk"] == 849843, "wrong game")
    rows = sorted(report["pitches"], key=lambda p: p["index"])
    _require(0 < len(rows) <= 2000, "empty or oversized game")
    ends = {r["at_bat_number"]: r["key"] for r in rows}
    keys, indexes, last = set(), set(), (0, 0)
    pitches = []
    policies = set()
    for row in rows:
        index = _int(row["index"])
        pa, number = _int(row["at_bat_number"], 1, 999), _int(row["pitch_number"], 1, 100)
        key = f"849843:{pa}:{number}"
        _require(row["key"] == key and row["pa_key"] == f"849843:{pa}", "pitch identity mismatch")
        _require(
            key not in keys and index not in indexes and (pa, number) > last,
            "duplicate or conflicting pitch order",
        )
        keys.add(key)
        indexes.add(index)
        last = (pa, number)
        pre = row["pre"]
        s = pre["situation"]
        situation = {
            k: _int(s[k], lo, hi)
            for k, lo, hi in (
                ("inning", 1, 99),
                ("outs", 0, 2),
                ("balls", 0, 3),
                ("strikes", 0, 2),
                ("bases", 0, 7),
                ("home_score", 0, 100),
                ("away_score", 0, 100),
            )
        }
        _require(s["half"] in ("Top", "Bot"), "invalid half")
        situation["half"] = s["half"]
        rec = pre["recommendation"]
        _require(
            rec["status"] in ("ready", "unsupported", "missing"), "invalid recommendation status"
        )
        _require(
            rec["provenance"] in ("asof_replay", "captured_live", "absent"), "invalid provenance"
        )
        _require(rec["event_probabilities"] is None, "unexpected event probabilities")
        _require(
            rec["location_basis"] == "historical_delivery_distribution_proxy_not_optimal_target",
            "unexpected location meaning",
        )
        policy = (
            None
            if rec["policy"] is None
            else {k: _text(rec["policy"][k], True) for k in ("name", "identity")}
        )
        if policy and policy["name"]:
            policies.add(policy["name"])
        candidates = []
        for c in rec["candidates"]:
            target = (
                None if c["target"] is None else {k: _number(c["target"][k]) for k in ("x", "z")}
            )
            candidates.append(
                {
                    "rank": _int(c["rank"], 1, 30),
                    "pitch_type": _text(c["pitch_type"]),
                    "pitch_label": _text(c["pitch_label"]),
                    "zone_id": _text(c["zone_id"], True),
                    "zone_label": _text(c["zone_label"], True),
                    "target": target,
                    "selection_probability": _number(c["selection_probability"], 0, 1, True),
                }
            )
        _require(
            len(candidates) <= 30 and bool(candidates) == (rec["status"] == "ready"),
            "status/candidates mismatch",
        )
        _require(
            all(len({c[k] for c in candidates}) == len(candidates) for k in ("rank", "pitch_type")),
            "duplicate recommendation",
        )
        _require(
            math.fsum(c["selection_probability"] or 0 for c in candidates) <= 1 + 1e-6,
            "selection shares exceed one",
        )
        actual, setup = None, None
        a = row["post"]["actual"]
        if a is not None:
            _require(
                not (a["event"] or a["event_label"]) or ends[pa] == key,
                "PA result occurs before terminal pitch",
            )
            actual = {
                k: _text(a[k], True)
                for k in (
                    "pitch_type",
                    "pitch_label",
                    "description",
                    "result_label",
                    "event",
                    "event_label",
                )
            }
            actual.update(
                {
                    "speed_mph": _number(a["speed_mph"], 0, 150, True),
                    "x": _number(a["x"], nullable=True),
                    "z": _number(a["z"], nullable=True),
                }
            )
            status, x = a["setup_status"], _number(a["setup_x_ft"], nullable=True)
            _require(status in (None, "estimated", "unavailable"), "invalid setup status")
            _require(status == "estimated" or x is None, "unavailable setup contains coordinates")
            if status is not None:
                setup = {"status": status, "x": x}
        pitches.append(
            {
                "index": index,
                "pitch_id": key,
                "at_bat_number": pa,
                "pitch_number": number,
                "situation": situation,
                "pitcher": _person(pre["pitcher"], "hand"),
                "batter": _person(pre["batter"], "side"),
                "pre": {
                    "status": rec["status"],
                    "provenance": rec["provenance"],
                    "recorded_at": _text(rec["recorded_at"], True),
                    "policy": policy,
                    "candidates": sorted(candidates, key=lambda c: c["rank"]),
                },
                "post": {"actual": actual, "setup": setup},
            }
        )
    _require(re.fullmatch(r"\d{4}-\d{2}-\d{2}", game["kst_date"]) is not None, "invalid date")
    return {
        "schema": SCHEMA,
        "source": {
            "kind": "provided_export",
            "sha256": SOURCE_SHA256,
            "report_sha256": REPORT_SHA256,
            "revision": None,
            "exported_at": None,
            "model_id": " / ".join(sorted(policies)) or "미제공",
            "upstream_kind": "archive",
        },
        "game": {
            "game_pk": 849843,
            "date": game["kst_date"],
            "away_team": _text(game["away_team"]),
            "home_team": _text(game["home_team"]),
        },
        "units": {
            "position": "feet",
            "speed": "mph",
            "probability": "pitch_type_selection_share",
            "setup": "feet_catcher_view_right_positive",
        },
        "claims": {
            "live_timing_verified": False,
            "complete_game_verified": False,
            "human_mitt_accuracy_measured": False,
        },
        "pitches": pitches,
    }


def read_fixed_zip(path):
    raw_zip = Path(path).read_bytes()
    _require(hashlib.sha256(raw_zip).hexdigest() == ZIP_SHA256, "received ZIP SHA mismatch")
    with zipfile.ZipFile(path) as archive:
        _require(archive.namelist().count("review-data.json") == 1, "ambiguous report member")
        raw = archive.read("review-data.json")
    _require(hashlib.sha256(raw).hexdigest() == REPORT_SHA256, "normalized report SHA mismatch")
    return json.loads(raw)


def serialize(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def summary(value):
    pitches = value["pitches"]
    return {
        "pitches": len(pitches),
        "plate_appearances": len({p["at_bat_number"] for p in pitches}),
        **{
            status: sum(p["pre"]["status"] == status for p in pitches)
            for status in ("ready", "unsupported", "missing")
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    value = project(read_fixed_zip(args.input_zip))
    counts = summary(value)
    _require(
        counts
        == {"pitches": 262, "plate_appearances": 71, "ready": 246, "unsupported": 16, "missing": 0},
        "fixed archive count mismatch",
    )
    data = serialize(value)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(json.dumps({**counts, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}))


if __name__ == "__main__":
    main()
