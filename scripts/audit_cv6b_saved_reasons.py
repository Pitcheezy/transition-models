"""Audit the frozen CV6 26-case processing routes, without new visual judgments.

This deliberately audits one existing cohort and its first received human response.
Run with --repo-root <canonical repository> --out <new private outputs directory>.
Only public_summary.json is intended for a public results directory.
"""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

READER_SHA = {
    849845: "f42f838b5749264c04516c474f8d4118774213238b447a9b3e3b356d06f30dd5",
    823407: "009cdf6864a20ab37dc8f69e5d2df52f6e90868856054c227c73d9023083e75d",
}
RESPONSE_SHA = "d25fa9908aa90aacfcdab6e068543e62e8eca698bd7322e615c428fb6df5ffeb"
REPORTED_SETUP_REASONS = {
    "glove_not_presented: catcher drops glove to rest on the ground before release",
    "glove_not_presented_resting_on_ground",
    "glove_resting_on_dirt_not_presented",
    "glove_already_lowered_at_cut",
}
PREDICATES = {
    "reported_not_presented_or_lowered": (
        "Exactly one eligible candidate; the other has null setup_frame and mitt_center, "
        "and setup_reason exactly matches reported_not_presented_or_lowered_reason_values: "
        "stored claims of not presented, resting or lowered; no actual target absence inferred."
    ),
    "camera_rejection_one_candidate": (
        "Exactly one eligible candidate; the other has null setup_frame and mitt_center "
        "and setup_reason == not_centre_field."
    ),
    "replay_rejection_one_candidate": (
        "Exactly one eligible candidate; the other has null setup_frame and mitt_center "
        "and setup_reason == slow_motion_replay_not_live."
    ),
    "plate_missing_with_two_mitt_readings": (
        "Exactly one eligible candidate; both have non-null setup_frame and mitt_center, "
        "both setup_frame values are equal; the excluded reader has no setup_plate_front."
    ),
    "different_frame_mitt_disagreement": (
        "Two eligible candidates; decide_setup returns readers_disagree_on_mitt "
        "under the frozen >15px rule; setup_frame values differ."
    ),
    "same_frame_mitt_disagreement": (
        "Two eligible candidates; decide_setup returns readers_disagree_on_mitt "
        "under the frozen >15px rule; setup_frame values are equal."
    ),
    "camera_rejection_and_plate_missing": (
        "Zero eligible candidates; one has null setup_frame/mitt_center and reason "
        "not_centre_field; the other has non-null setup_frame/mitt_center but no plate."
    ),
}
SCOPE = {
    "description": "Saved processing-route audit of 26 disagreement-selected development frames.",
    "reader_evidence": "Saved AI claims, not verified visual facts or human judgments.",
    "candidate_definition": "bool(row and setup_frame is not None and mitt_center and "
    "setup_plate_front), exactly as frozen decide_setup.",
    "reported_not_presented_or_lowered_reason_values": sorted(REPORTED_SETUP_REASONS),
    "human_link": "Source ID/hash binding and submitted status/visibility only; no pose use.",
    "missing_reason_definition": "Null/blank setup_reason only among null setup_frame rows; "
    "a null reason on a supplied setup is not a missing abstention explanation.",
    "limits": [
        "No image viewing, new annotation, relabeling, model invocation or training.",
        "No AI error rate, human agreement, target/intent truth or unseen validation.",
        "No change to frozen M3 decisions, points, prompt or consensus rule.",
        "Successful exported reader rows do not authenticate complete attempt/error history.",
        "Final reason names combine mitt, frame eligibility and plate prerequisites.",
    ],
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def index_unique(rows, key, label):
    result = {row[key]: row for row in rows}
    require(len(result) == len(rows), f"duplicate {label}")
    return result


def candidate(row):
    return bool(
        row
        and row.get("setup_frame") is not None
        and row.get("mitt_center")
        and row.get("setup_plate_front")
    )


def has_mitt(row):
    return row.get("setup_frame") is not None and row.get("mitt_center") is not None


def no_setup(row):
    return row.get("setup_frame") is None and row.get("mitt_center") is None


def classify(a, b, decision):
    """Return an exclusive structural route; never classify from free-text notes."""
    eligible = [r for r in (a, b) if candidate(r)]
    if len(eligible) == 2 and decision["reason"] == "readers_disagree_on_mitt":
        prefix = "same" if a["setup_frame"] == b["setup_frame"] else "different"
        return f"{prefix}_frame_mitt_disagreement"
    if len(eligible) == 1:
        other = b if eligible[0] is a else a
        if (
            has_mitt(a)
            and has_mitt(b)
            and a["setup_frame"] == b["setup_frame"]
            and not other.get("setup_plate_front")
        ):
            return "plate_missing_with_two_mitt_readings"
        if no_setup(other):
            reason = other.get("setup_reason")
            if reason in REPORTED_SETUP_REASONS:
                return "reported_not_presented_or_lowered"
            if reason == "not_centre_field":
                return "camera_rejection_one_candidate"
            if reason == "slow_motion_replay_not_live":
                return "replay_rejection_one_candidate"
    if not eligible:
        for rejected, missing in ((a, b), (b, a)):
            if (
                no_setup(rejected)
                and rejected.get("setup_reason") == "not_centre_field"
                and has_mitt(missing)
                and not missing.get("setup_plate_front")
            ):
                return "camera_rejection_and_plate_missing"
    raise ValueError("unclassified saved route; do not infer a cause from notes")


def validate_raw(document, point_keys):
    require(document.get("schema") == "intent_condensed_read_reads_v0", "raw reader schema")
    for reader in ("A", "B"):
        rows = [r for block in document["reads"] for r in (block.get(reader) or [])]
        keys = [(r["at_bat_number"], r["pitch_number"]) for r in rows]
        require(len(set(keys)) == len(keys), f"duplicate raw {reader} key")
        require(set(keys) == point_keys, f"raw {reader} and frozen points keys differ")


def audit(root):
    # Import only after the explicitly selected canonical checkout is on sys.path.
    sys.path.insert(0, str(root))
    from intent import condensed, review_queue

    require(Path(condensed.__file__).resolve() == root / "intent/condensed.py", "wrong repo import")
    require(condensed.AGREE_PX == 15, "frozen consensus threshold changed")
    package = root / "outputs/cv_review_20261008_ko_v1"
    response_path = root / "outputs/cv_review_response_20261008_v1/human_review_response.json"
    report_path = root / "docs/results/cv_followup_20261005/quality_audit_v1.json"
    results = root / "docs/results/mlb_p0"
    sources = {}

    def bind(role, path, expected=None):
        digest = sha(path)
        require(expected is None or digest == expected, f"source SHA mismatch: {role}")
        sources[role] = {"path": str(path), "sha256": digest}
        return read(path) if path.suffix == ".json" else None

    private = bind("private_selection", package / "private_selection.json")
    manifest = bind(
        "reviewer_manifest", package / "reviewer/manifest.json", private["reviewer_manifest_sha256"]
    )
    bind("quality_audit", report_path, private["quality_report_sha256"])
    response = bind("first_human_response", response_path, RESPONSE_SHA)
    bind("audit_script", Path(__file__).resolve())
    for name in ("condensed.py", "quality_audit.py", "review_queue.py"):
        bind("code_" + name, root / "intent" / name)
    bind("frozen_reader_prompt", root / "intent/workflows/condensed_read.js")
    selected, _, report = review_queue._collect(root, report_path, results, 26)
    require(
        private["sources"]
        == [{"game_pk": g["game_pk"], "sources": g["sources"]} for g in report["games"]],
        "private source bindings differ",
    )
    checked = review_queue.check_response(package, response_path)
    require(checked == {"completed": 26, "unreviewed": 0, "unknown": 0}, "unexpected intake")
    original = index_unique(selected, "pitch_id", "frozen selection pitch")
    mapping = index_unique(private["mapping"], "pitch_id", "private pitch")
    observations = index_unique(private["mapping"], "observation_id", "private observation")
    frames = index_unique(manifest["frames"], "observation_id", "manifest observation")
    human = index_unique(response["rows"], "observation_id", "human observation")
    require(mapping.keys() == original.keys() and len(mapping) == 26, "selection key mismatch")
    require(observations.keys() == frames.keys() == human.keys(), "observation join mismatch")
    require(len({r["image_sha256"] for r in selected}) == 26, "duplicate selected image")
    reads, points = {}, {}
    for game in report["games"]:
        g = game["game_pk"]
        for role, source in game["sources"].items():
            bind(f"legacy_{g}_{role}", results / source["path"], source["sha256"])
        point_doc = read(results / game["sources"]["points"]["path"])
        points[g] = {(p["at_bat_number"], p["pitch_number"]): p for p in point_doc["frames"]}
        raw_path = results / f"game_{g}_condensed_reads_v0.json"
        raw = bind(f"raw_readers_{g}", raw_path, READER_SHA[g])
        validate_raw(raw, set(points[g]))
        reads[g] = condensed.collect_reads(condensed.load_reader_results(raw_path))
    rows = []
    for pid in sorted(mapping):
        m, source = mapping[pid], original[pid]
        obs = m["observation_id"]
        for key in ("source_path", "frame_seconds", "image_sha256", "selection_evidence"):
            require(m[key] == source[key], f"private selection source mismatch: {key}")
        frame, h = frames[obs], human[obs]
        require(
            frame["image_sha256"] == h["image_sha256"] == source["image_sha256"],
            "human/source image join mismatch",
        )
        require((frame["width"], frame["height"]) == source["dimensions"], "dimension mismatch")
        require(h["status"] == "marked" and h["visibility"] == "full", "unexpected human status")
        g, pa, pn = map(int, pid.split(":"))
        pair = reads[g][f"{pa}:{pn}"]
        a, b = pair["A"], pair["B"]
        point = points[g][pa, pn]
        decision = condensed.decide_setup(a, b)
        for actual, expected in (
            (decision["status"], point["status"]),
            (decision["reason"], point["unavailable_reason"]),
            (decision["frame_index"], point["frame_index"]),
            (decision["note"], point["note"]),
        ):
            require(actual == expected, "saved decision does not reproduce")
        route = classify(a, b, decision)
        rows.append(
            {
                "pitch_id": pid,
                "observation_id": obs,
                "image_sha256": source["image_sha256"],
                "route": route,
                "exact_predicate": PREDICATES[route],
                "raw_reader_rows": pair,
                "reader_evidence_status": "saved_AI_claim_not_verified_visual_truth",
                "replayed_decision": decision,
                "human_source_binding": {
                    "response_sha256": RESPONSE_SHA,
                    "status": h["status"],
                    "visibility": h["visibility"],
                },
            }
        )
    counts = Counter(r["route"] for r in rows)
    no_frame = [
        r for row in rows for r in row["raw_reader_rows"].values() if r["setup_frame"] is None
    ]
    summary = {
        "schema": "cv6b_saved_processing_routes_v1",
        "scope": SCOPE,
        "totals": {
            "selected_frames": 26,
            "raw_reader_rows": 52,
            "reproduced_decisions": len(rows),
            "human_source_bindings": len(rows),
            "human_submitted_marked_full": len(rows),
            "null_setup_frame_rows": len(no_frame),
            "null_setup_frame_rows_without_reason": sum(
                not (r.get("setup_reason") or "").strip() for r in no_frame
            ),
        },
        "routes": {
            name: {"count": counts[name], "exact_predicate": predicate}
            for name, predicate in PREDICATES.items()
        },
        "source_digests": {role: v["sha256"] for role, v in sorted(sources.items())},
    }
    # A second snapshot prevents exporting a report from changed inputs.
    require(
        all(sha(v["path"]) == v["sha256"] for v in sources.values()), "input changed during audit"
    )
    return {
        "schema": "cv6b_saved_processing_routes_private_v1",
        "scope": SCOPE,
        "sources": sources,
        "rows": rows,
    }, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root, out = args.repo_root.resolve(), args.out.resolve()
    allowed = [root / "outputs"]
    allowed.extend(p for p in Path(__file__).resolve().parents if p.name == "outputs")
    require(
        any(out != p and out.is_relative_to(p) for p in allowed), "private audit requires outputs"
    )
    require(not out.exists(), "output already exists; choose a new directory")
    private, public = audit(root)
    out.mkdir(parents=True, exist_ok=False)
    for name, document in (("private_row_audit.json", private), ("public_summary.json", public)):
        (out / name).write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(public["totals"]))


if __name__ == "__main__":
    main()
