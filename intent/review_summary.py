"""Describe supplied development reviews without adjudication or accuracy claims."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from itertools import combinations
from pathlib import Path
from statistics import median

from intent.replay import _load, _no_links, _sha, _write_new
from intent.review_queue import check_response

SCHEMA = "intent_review_summary_v1"
STATUSES = ("marked", "unavailable", "unknown", "unreviewed")
DECIDED = {"marked", "unavailable"}


def _digest(path):
    _no_links(path)
    return _sha(path.read_bytes())


def _pair(left, right, observation_ids):
    a, b = left["rows"], right["rows"]
    eligible, same, distances, conflicts = 0, 0, [], []
    unknown, unreviewed = 0, 0
    for obs in observation_ids:
        x, y = a[obs], b[obs]
        statuses = {x["status"], y["status"]}
        unknown += "unknown" in statuses
        unreviewed += "unreviewed" in statuses
        if not statuses <= DECIDED:
            continue
        eligible += 1
        same += x["status"] == y["status"]
        if x["status"] != y["status"]:
            conflicts.append(obs)
        elif x["status"] == "marked":
            distances.append(math.dist(x["mitt"], y["mitt"]))
    distances.sort()
    return {
        "reviewer_ids": [left["reviewer_id"], right["reviewer_id"]],
        "total_observations": len(observation_ids),
        "eligible_both_decided": eligible,
        "excluded_observations": len(observation_ids) - eligible,
        "excluded_with_unknown": unknown,
        "excluded_with_unreviewed": unreviewed,
        "exclusion_flags_may_overlap": True,
        "same_status": same,
        "different_status": eligible - same,
        "same_status_rate": same / eligible if eligible else None,
        "status_conflict_observation_ids": conflicts,
        "both_marked_pixel_distance": {
            "n": len(distances),
            "median": median(distances) if distances else None,
            "p90": distances[math.ceil(0.9 * len(distances)) - 1] if distances else None,
            "p90_method": "nearest_rank_ceiling_0.9_n",
            "meaning": "distance between supplied points; not physical or ground-truth error",
        },
    }


def summarize(package, response_paths=()):
    """Validate a package and explicit human response files; never write or infer labels."""
    package = Path(package).absolute()
    manifest_path = package / "reviewer/manifest.json"
    template_path = package / "reviewer/response_template.json"
    private_path = package / "private_selection.json"
    paths = [Path(path).absolute() for path in response_paths]
    tracked = [manifest_path, template_path, private_path, *paths]
    before = {path: _digest(path) for path in tracked}
    if len({path.resolve() for path in paths}) != len(paths):
        raise ValueError("duplicate response input path")
    if len({before[path] for path in paths}) != len(paths):
        raise ValueError("duplicate response SHA256")
    blank = check_response(package, template_path)
    template = _load(template_path)
    if blank["completed"] or blank["unknown"] or template["reviewer_id"].strip():
        raise ValueError("package template must remain blank")
    manifest = _load(manifest_path)
    observation_ids = [frame["observation_id"] for frame in manifest["frames"]]
    if not observation_ids:
        raise ValueError("empty review package")
    reviewers, normalized_ids = [], set()
    for path in paths:
        if _digest(path) != before[path]:
            raise ValueError("response changed before validation")
        counts = check_response(package, path)
        response = _load(path)
        if _digest(path) != before[path]:
            raise ValueError("response changed during validation")
        reviewer_id = response["reviewer_id"].strip()
        identity = reviewer_id.casefold()
        if not identity or counts["completed"] + counts["unknown"] == 0:
            raise ValueError("supplied response requires reviewer_id and at least one reviewed row")
        if identity in normalized_ids:
            raise ValueError("duplicate normalized reviewer_id")
        normalized_ids.add(identity)
        rows = {row["observation_id"]: row for row in response["rows"]}
        status_counts = Counter(row["status"] for row in rows.values())
        reviewed = [row for row in rows.values() if row["status"] != "unreviewed"]
        reviewers.append(
            {
                "reviewer_id": reviewer_id,
                "response_sha256": before[path],
                "counts": {status: status_counts[status] for status in STATUSES},
                "visibility_among_reviewed": dict(Counter(row["visibility"] for row in reviewed)),
                "pose_among_reviewed": dict(Counter(row["pose"] for row in reviewed)),
                "rows": rows,
            }
        )
    reviewed_union, decided_union = set(), set()
    for reviewer in reviewers:
        for obs, row in reviewer["rows"].items():
            if row["status"] != "unreviewed":
                reviewed_union.add(obs)
            if row["status"] in DECIDED:
                decided_union.add(obs)
    pairs = [_pair(a, b, observation_ids) for a, b in combinations(reviewers, 2)]
    # Revalidate all images and document bindings after aggregation, including the zero-input case.
    check_response(package, template_path)
    if any(_digest(path) != digest for path, digest in before.items()):
        raise ValueError("input or package changed during summary")
    return {
        "schema": SCHEMA,
        "status": "responses_described" if reviewers else "awaiting_human_responses",
        "scope": "descriptive supplied development responses; no automatic adjudication",
        "independent_validation": False,
        "human_identity_not_authenticated": True,
        "accuracy_measured": False,
        "manifest_sha256": before[manifest_path],
        "template_sha256": before[template_path],
        "reviewer_count": len(reviewers),
        "coverage": {
            "denominator_observations": len(observation_ids),
            "reviewed_union": len(reviewed_union),
            "unreviewed_by_all": len(observation_ids) - len(reviewed_union),
            "decided_union": len(decided_union),
            "only_unknown_union": len(reviewed_union - decided_union),
            "reviewed_definition": "at least one marked, unavailable or unknown response",
            "decided_definition": "at least one marked or unavailable response",
        },
        "reviewers": [{k: v for k, v in reviewer.items() if k != "rows"} for reviewer in reviewers],
        "pairwise": pairs,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--response", type=Path, action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = summarize(args.package, args.response)
    _write_new(args.out, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
