"""Materialize private evidence images from a fixed, explicitly reviewed decision file.

This copies verified bytes only. It neither creates visual judgments nor calls a model.
"""

import argparse
import hashlib
import json
import math
import shutil
from collections import Counter
from copy import deepcopy
from pathlib import Path


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


DECISIONS = ("supported_development_candidate", "identity_unresolved", "posture_unresolved")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def finite(value):
        if isinstance(value, float):
            _require(math.isfinite(value), "nonfinite JSON number")
        elif isinstance(value, dict):
            for item in value.values():
                finite(item)
        elif isinstance(value, list):
            for item in value:
                finite(item)

    result = json.loads(raw, object_pairs_hook=pairs)
    finite(result)
    return result


def _keyed(rows, field):
    _require(isinstance(rows, list), "records must be a list")
    result = {}
    for row in rows:
        _require(isinstance(row, dict), "record must be an object")
        key = row.get(field)
        _require(isinstance(key, str) and key not in result, "duplicate or invalid record key")
        result[key] = row
    return result


def _integer(value):
    return type(value) is int and 0 <= value <= 2**53 - 1


def _interval_sidecar(sidecar, interval_review, interval_audit_dir):
    """Bind the saved qualitative decisions to exact decoded frames before copying anything."""
    raw = Path(interval_review).read_bytes()
    review = _json(raw.decode("utf-8"))
    audit_dir = Path(interval_audit_dir).resolve()
    audit_path = audit_dir / "audit.json"
    _require(
        review.get("schema") == "pitcheezy-exhibition-interval-review-v1"
        and sha(audit_path) == review.get("audit_sha256"),
        "interval review does not match its extraction audit",
    )
    audit = _json(audit_path.read_text(encoding="utf-8"))
    _require(
        sidecar.get("schema") == "pitcheezy-service-review-evidence-v2"
        and audit.get("game_pk") == sidecar.get("game_pk") == 849843
        and audit.get("source_registry_sha256") == review.get("source_registry_sha256"),
        "interval game, registry or base evidence version mismatch",
    )
    records = _keyed(review.get("records"), "pitch_key")
    decoded = _keyed(audit.get("records"), "pitch_key")
    entries = _keyed(sidecar.get("entries"), "pitch_key")
    _require(set(records) == set(decoded) == set(entries), "interval pitch sets differ")
    source_sha = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    overall = Counter()
    for key, entry in entries.items():
        record, actual = records[key], decoded[key]
        _require(
            all(
                record.get(k) == actual.get(k) == entry.get(k)
                for k in ("play_id", "clip_sha256", "time_base")
            )
            and record.get("first_pts") == actual.get("first_pts") == entry.get("clip_first_pts"),
            "interval clip identity differs from representative evidence",
        )
        interval = record.get("interval")
        _require(
            isinstance(interval, dict)
            and set(interval)
            == {
                "lower_pts_inclusive",
                "upper_pts_inclusive",
                "expected_decoded_frames",
                "representative_pts",
            }
            and interval == actual.get("interval")
            and all(_integer(value) for value in interval.values()),
            "interval bounds differ from decoded audit",
        )
        lower, upper, count, representative = (
            interval[name]
            for name in (
                "lower_pts_inclusive",
                "upper_pts_inclusive",
                "expected_decoded_frames",
                "representative_pts",
            )
        )
        _require(
            entry["clip_first_pts"]
            <= lower
            <= representative
            == entry["frame_pts"]
            <= upper
            < entry["release_lower_bound_pts"]
            and 1 <= count <= upper - lower + 1
            and type(record.get("decoded_frames_in_interval")) is int
            and record["decoded_frames_in_interval"] == count,
            "interval range, representative or count is invalid",
        )
        frames, actual_frames = record.get("frames"), actual.get("sampled_frames")
        _require(
            isinstance(frames, list)
            and isinstance(actual_frames, list)
            and len(frames) == len(actual_frames) == count,
            "interval frame count mismatch",
        )
        actual_by_pts, previous_pts, previous_ordinal = {}, -1, -1
        for frame in actual_frames:
            pts, ordinal = frame.get("pts"), frame.get("ordinal")
            _require(
                _integer(pts)
                and _integer(ordinal)
                and lower <= pts <= upper
                and pts > previous_pts
                and ordinal > previous_ordinal,
                "decoded interval has duplicate or unordered frame identity",
            )
            actual_by_pts[pts] = frame
            previous_pts, previous_ordinal = pts, ordinal
        _require(
            next(iter(actual_by_pts)) == lower and previous_pts == upper,
            "interval endpoints are not decoded frames",
        )
        decisions, representative_decision, seen, previous = Counter(), None, set(), -1
        for frame in frames:
            pts = frame.get("pts")
            _require(
                _integer(pts) and pts in actual_by_pts and pts not in seen and pts > previous,
                "review frame identity mismatch",
            )
            expected = actual_by_pts[pts]
            _require(
                all(
                    frame.get(field) == expected.get(field)
                    for field in ("ordinal", "image", "image_sha256", "clip_seconds")
                )
                and type(frame.get("ordinal")) is int
                and type(frame.get("clip_seconds")) in (int, float)
                and abs(frame["clip_seconds"] - (pts - entry["clip_first_pts"]) / 90000) <= 1e-6
                and frame.get("published_new_point_xy", "missing") is None,
                "review frame metadata differs from decode evidence or contains a new point",
            )
            image = (audit_dir / frame["image"]).resolve()
            _require(
                image.is_relative_to(audit_dir) and sha(image) == frame["image_sha256"],
                "interval image bytes mismatch",
            )
            decision = frame.get("review_decision")
            _require(
                isinstance(decision, str) and decision in DECISIONS, "unknown interval decision"
            )
            decisions[decision] += 1
            seen.add(pts)
            previous = pts
            if pts == representative:
                _require(
                    frame["image_sha256"] == entry["image_sha256"],
                    "representative image SHA mismatch",
                )
                representative_decision = decision
        counts = record.get("counts")
        _require(
            isinstance(counts, dict)
            and set(counts) <= set(DECISIONS)
            and all(_integer(value) for value in counts.values())
            and all(counts.get(name, 0) == decisions[name] for name in DECISIONS)
            and representative_decision is not None,
            "interval summary differs from its frame decisions",
        )
        overall.update(decisions)
        entry["interval_review"] = {
            "source_sha256_lf": source_sha,
            "lower_pts_inclusive": lower,
            "upper_pts_inclusive": upper,
            "decoded_frames": count,
            **{name: decisions[name] for name in DECISIONS},
            "representative_decision": representative_decision,
        }
        if representative_decision != "supported_development_candidate":
            entry["point"], entry["status"] = None, "abstained"
            entry["reason"] = (
                "구간 교차판독에서 미트와 다른 물체의 식별이 해결되지 않아 기존 대표점을 숨깁니다."
                if representative_decision == "identity_unresolved"
                else "대표 프레임의 자세 판단이 해결되지 않아 기존 대표점을 숨깁니다."
            ) + " 근거 이미지만 보존하며 검증된 목표나 추적점으로 쓰지 않습니다."
    totals = review.get("counts")
    expected_totals = {
        "pitches": len(entries),
        "frames": sum(overall.values()),
        **{name: overall[name] for name in DECISIONS},
        "new_point_outputs": 0,
        "independent_human_reviews": 0,
        "validated_targets": 0,
    }
    _require(
        isinstance(totals, dict)
        and totals == expected_totals
        and all(_integer(value) for value in totals.values()),
        "interval overall totals or evidence kind mismatch",
    )
    sidecar["schema"] = "pitcheezy-service-review-evidence-v3"


def prepare(audit_dir, decisions, out_dir, *, interval_review=None, interval_audit_dir=None):
    audit_dir, decisions, out_dir = map(Path, (audit_dir, decisions, out_dir))
    repo = Path(__file__).resolve().parents[1]
    if out_dir.exists() or any(out_dir.resolve().is_relative_to(repo / x) for x in ("docs", "web")):
        raise ValueError("use a new private output directory")
    _require(
        (interval_review is None) == (interval_audit_dir is None),
        "interval review and audit must be supplied together",
    )
    review = _json(decisions.read_text(encoding="utf-8"))
    if review["game_pk"] != 849843 or sha(audit_dir / "audit.json") != review["audit_sha256"]:
        raise ValueError("decisions do not match this development audit")
    audit = _json((audit_dir / "audit.json").read_text(encoding="utf-8"))
    frames = {f["image"]: (r, f) for r in audit["records"] for f in r.get("sampled_frames", [])}
    if len(frames) != sum(len(r.get("sampled_frames", [])) for r in audit["records"]):
        raise ValueError("duplicate decoded image identities")
    sidecar = deepcopy(review["package_sidecar"])
    entries = {e["image"]: e for e in sidecar["entries"]}
    bindings = review["image_bindings"]
    if len(entries) != len(sidecar["entries"]) or len(bindings) != len(entries):
        raise ValueError("evidence image bindings must be one to one")
    seen, copies = set(), []
    for binding in bindings:
        name, source_name = binding["image"], binding["source_image"]
        if name in seen:
            raise ValueError("duplicate evidence image")
        seen.add(name)
        source, target = (audit_dir / source_name).resolve(), (out_dir / name).resolve()
        if not source.is_relative_to(audit_dir.resolve()) or not target.is_relative_to(
            out_dir.resolve()
        ):
            raise ValueError("evidence path leaves its directory")
        row, frame = frames[source_name]
        entry = entries[name]
        if not (
            row["pitch_key"] == entry["pitch_key"]
            and row["play_id"] == entry["play_id"]
            and row["clip_sha256"] == entry["clip_sha256"]
            and row["first_pts"] == entry["clip_first_pts"]
            and row["time_base"] == entry["time_base"]
            and frame["pts"] == entry["frame_pts"]
            and frame["clip_seconds"] == entry["clip_seconds"]
            and entry["release_lower_bound_pts"] in {f["pts"] for f in row["sampled_frames"]}
            and sha(source) == frame["image_sha256"] == binding["sha256"] == entry["image_sha256"]
        ):
            raise ValueError("evidence frame identity or bytes mismatch")
        copies.append((source, target))
    if interval_review is not None:
        _interval_sidecar(sidecar, interval_review, interval_audit_dir)
    out_dir.mkdir(parents=True)
    for source, target in copies:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (out_dir / "review-evidence.json").write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return len(copies)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--interval-review", type=Path)
    parser.add_argument("--interval-audit-dir", type=Path)
    args = parser.parse_args()
    print(
        f"Prepared {prepare(args.audit_dir, args.decisions, args.out_dir, interval_review=args.interval_review, interval_audit_dir=args.interval_audit_dir)} existing evidence images"
    )


if __name__ == "__main__":
    main()
