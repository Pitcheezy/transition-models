"""Prepare current-protocol human point annotations without training or adjudication.

Inputs are trusted local CV6/CV12 artifacts, not authenticated human identities.
No image is transformed and no legacy point, model observation, box, presence
negative, consensus, training split or independent-validation claim is produced.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from intent import local_detector_data, review_summary
from intent.replay import _inside, _load, _no_links, _sha, _write_new
from intent.review_queue import PROTOCOL

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "intent_review_point_data_v1"
SOURCE_SUFFIXES = {
    "manifest": "intent_label_pack_v0.json",
    "labels": "intent_human_labels_v0.json",
    "raw_labels": "intent_human_labels_raw_v0.json",
    "points": "intent_points_v0.json",
    "source": "condensed_source_v0.json",
}
LIMITATIONS = [
    "Previously reviewed, disagreement-selected development frames; not unseen validation.",
    "Current labels remain separate from legacy points and AI observations.",
    "Reviewer annotations remain separate; no consensus or training cohort is selected.",
    "Unavailable means the center could not be read, not that a glove is absent.",
    "Point labels provide no boxes, masks, physical targets or pre-pitch availability.",
    "Human identity and independent labeling are not authenticated by this tool.",
]


def _snapshot(path, bindings, expected=None):
    path = Path(path).absolute()
    _no_links(path)
    digest = _sha(path.read_bytes())
    if expected is not None and digest != expected:
        raise ValueError("input SHA256 mismatch")
    if path in bindings and bindings[path] != digest:
        raise ValueError("input changed during preparation")
    bindings[path] = digest
    return digest


def _read(path, bindings):
    _snapshot(path, bindings)
    result = _load(path)
    _snapshot(path, bindings)
    return result


def _index(rows, key, name):
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"invalid {name} rows")
    result = {}
    for row in rows:
        identity = row.get(key)
        if not isinstance(identity, str) or not identity or identity in result:
            raise ValueError(f"duplicate or invalid {name} {key}")
        result[identity] = row
    return result


def _source_frames(root, manifest_path, audit_path, bindings):
    """Reconstruct the frozen CV12 sources with the existing full source validator."""
    manifest = _read(manifest_path, bindings)
    audit = _read(audit_path, bindings)
    if (
        audit.get("schema") != "local_glove_data_audit_v1"
        or audit.get("scope") != local_detector_data.SCOPE
        or manifest.get("schema") != "local_glove_frames_v1"
        or manifest.get("scope") != local_detector_data.SCOPE
        or audit.get("manifest_sha256") != bindings[manifest_path]
    ):
        raise ValueError("CV12 source schema/manifest SHA256 mismatch")
    frames, games, source_frames = [], [], {}
    results = root / "docs/results/mlb_p0"
    for game, count in local_detector_data.EXPECTED_COUNTS.items():
        collected, _, game_audit = local_detector_data._collect_game(results, root, game, count)
        for name, suffix in SOURCE_SUFFIXES.items():
            path = results / f"game_{game}_{suffix}"
            _snapshot(path, bindings, game_audit["source_sha256"][name])
        original = _read(results / f"game_{game}_{SOURCE_SUFFIXES['manifest']}", bindings)
        source_frames.update(_index(original["frames"], "pitch_id", "original source"))
        frames.extend(collected)
        games.append(game_audit)
    if (
        manifest.get("frames") != frames
        or audit.get("games") != games
        or audit.get("frames") != len(frames)
        or audit.get("source_image_bytes_verified") != len(frames)
    ):
        raise ValueError("CV12 manifest/audit differs from verified original sources")
    indexed = _index(frames, "observation_id", "CV12 source")
    _index(frames, "image_sha256", "CV12 source")
    for frame in frames:
        _snapshot(frame["image_path"], bindings, frame["image_sha256"])
    return indexed, source_frames, games


def _joined_frames(root, package, manifest, private, sources, original, games, bindings):
    if private.get("schema") != "intent_review_selection_v1":
        raise ValueError("unexpected private selection schema")
    private_sources = private.get("sources")
    if not isinstance(private_sources, list) or len(private_sources) != len(games):
        raise ValueError("private source games differ")
    by_game = {row.get("game_pk"): row for row in private_sources}
    if len(by_game) != len(games) or set(by_game) != {game["game_pk"] for game in games}:
        raise ValueError("duplicate or different private source games")
    for game in games:
        declared = by_game[game["game_pk"]]["sources"]
        for name in ("manifest", "points", "labels"):
            expected = game["source_sha256"][name]
            path = root / "docs/results/mlb_p0" / f"game_{game['game_pk']}_{SOURCE_SUFFIXES[name]}"
            if (
                declared[name]["sha256"] != expected
                or _inside(root / "docs/results/mlb_p0", declared[name]["path"]) != path
            ):
                raise ValueError("private source binding differs from verified CV12 source")
    mapping = _index(private.get("mapping"), "observation_id", "private mapping")
    _index(private["mapping"], "pitch_id", "private mapping")
    _index(private["mapping"], "image_sha256", "private mapping")
    frames = _index(manifest.get("frames"), "observation_id", "review manifest")
    _index(manifest["frames"], "image_sha256", "review manifest")
    if mapping.keys() != frames.keys():
        raise ValueError("private mapping/review observation sets differ")
    joined = []
    for observation, frame in frames.items():
        row = mapping[observation]
        source = sources.get(row["pitch_id"])
        if source is None:
            raise ValueError("private mapping pitch is absent from verified sources")
        raw = original[row["pitch_id"]]
        if (
            row["image_sha256"] != frame["image_sha256"]
            or row["image_sha256"] != source["image_sha256"]
            or (frame["width"], frame["height"]) != (source["width"], source["height"])
            or _inside(root, row["source_path"]) != Path(source["image_path"])
            or row.get("frame_seconds") != raw["frame_seconds"]
        ):
            raise ValueError("private mapping image/path/time differs from verified source")
        _snapshot(_inside(package / "reviewer", frame["path"]), bindings, frame["image_sha256"])
        joined.append(
            {
                "observation_id": observation,
                "pitch_id": row["pitch_id"],
                "game_pk": source["game_pk"],
                "group_key": f"game:{source['game_pk']}",
                "image_sha256": source["image_sha256"],
                "image_path": source["image_path"],
                "width": source["width"],
                "height": source["height"],
                "frame_seconds": raw["frame_seconds"],
                "data_role": "development",
                "annotations": [],
            }
        )
    return joined


def public_summary(document):
    """Return aggregate preparation counts without paths, private IDs or coordinates."""
    frames = document["frames"]
    annotations = [row for frame in frames for row in frame["annotations"]]
    marked = [row for row in annotations if row["status"] == "marked"]
    counts = Counter(row["status"] for row in annotations)
    return {
        "schema": "intent_review_point_data_summary_v1",
        "status": document["status"],
        "protocol_version": PROTOCOL,
        "source_frames": len(frames),
        "reviewer_count": document["reviewer_count"],
        "annotation_rows": len(annotations),
        "annotation_status_counts": {key: counts[key] for key in review_summary.STATUSES},
        "point_annotations": len(marked),
        "unique_frames_with_points": sum(
            any(row["status"] == "marked" for row in frame["annotations"]) for frame in frames
        ),
        "unreviewed_by_all": document["unreviewed_by_all"],
        "marked_visibility_counts": dict(Counter(row["visibility"] for row in marked)),
        "marked_pose_counts": dict(Counter(row["pose"] for row in marked)),
        "ready_for_training": False,
        "training_examples_selected": 0,
        "training_performed": False,
        "independent_validation": False,
        "limitations": list(LIMITATIONS),
    }


def prepare(root, package, dataset_manifest, dataset_audit, out, *, responses=()):
    """Write a fresh private annotation manifest and a separate shareable count summary."""
    root, package, dataset_manifest, dataset_audit, out = (
        Path(path).absolute() for path in (root, package, dataset_manifest, dataset_audit, out)
    )
    for path in (root, package, dataset_manifest, dataset_audit, out):
        _no_links(path)
    root, package, dataset_manifest, dataset_audit, out = (
        path.resolve() for path in (root, package, dataset_manifest, dataset_audit, out)
    )
    if out.exists():
        raise ValueError("output already exists; choose a new directory")
    if out == root / "outputs" or not out.is_relative_to(root / "outputs"):
        raise ValueError("output must be a new private directory inside repo outputs")
    bindings = {}
    sources, original, games = _source_frames(root, dataset_manifest, dataset_audit, bindings)
    manifest = _read(package / "reviewer/manifest.json", bindings)
    private = _read(package / "private_selection.json", bindings)
    _read(package / "reviewer/response_template.json", bindings)
    response_paths = [Path(path).absolute() for path in responses]
    supplied = [_read(path, bindings) for path in response_paths]
    described = review_summary.summarize(package, response_paths)
    frames = _joined_frames(root, package, manifest, private, sources, original, games, bindings)
    by_observation = {frame["observation_id"]: frame for frame in frames}
    for response, path in zip(supplied, response_paths, strict=True):
        for row in response["rows"]:
            by_observation[row["observation_id"]]["annotations"].append(
                {
                    "reviewer_id": response["reviewer_id"].strip(),
                    "response_sha256": bindings[path],
                    "label_source": "supplied_human_response_identity_not_authenticated",
                    **{key: row[key] for key in ("status", "mitt", "visibility", "pose", "reason")},
                    "candidate_point_mask": row["status"] == "marked",
                    "glove_presence_target": None,
                }
            )
    document = {
        "schema": SCHEMA,
        "protocol_version": PROTOCOL,
        "status": "annotations_prepared" if supplied else "awaiting_human_responses",
        "coordinate_system": "original full-frame pixels; x right, y down",
        "scope": "development annotation preparation; no training cohort selected",
        "reviewer_count": described["reviewer_count"],
        "unreviewed_by_all": described["coverage"]["unreviewed_by_all"],
        "ready_for_training": False,
        "independent_validation": False,
        "limitations": list(LIMITATIONS),
        "frames": frames,
        "inputs": [{"path": str(path), "sha256": digest} for path, digest in bindings.items()],
    }
    summary = public_summary(document)
    # Recheck every consumed document and image after joins, before the first output write.
    for path, digest in list(bindings.items()):
        _snapshot(path, bindings, digest)
    out.mkdir(parents=True, exist_ok=False)
    _write_new(out / "manifest.json", document)
    _write_new(out / "summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--dataset-audit", type=Path, required=True)
    parser.add_argument("--response", type=Path, action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            prepare(
                args.repo_root,
                args.package,
                args.dataset_manifest,
                args.dataset_audit,
                args.out,
                responses=args.response,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
