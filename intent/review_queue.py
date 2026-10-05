"""Prepare source-only development rechecks; wait for real human responses.

Copies original images unchanged. Selection is the frozen quality report's human-only
availability disagreements, not new ground truth or an independent validation sample.
"""

from __future__ import annotations

import argparse
import json
from fractions import Fraction
from pathlib import Path

from PIL import Image

from intent.quality_audit import SCHEMA as AUDIT_SCHEMA
from intent.quality_audit import availability, validate_inputs
from intent.replay import _inside, _load, _no_links, _number, _sha, _write_new
from intent.reviewer_ui import render_review_page

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "cv_observation_v1"
MANIFEST_SCHEMA = "intent_source_review_pack_v1"
RESPONSE_SCHEMA = "intent_source_review_response_v1"
INSTRUCTIONS = (
    "보이는 포수 미트 몸체의 중심을 원본 전체 프레임 픽셀 좌표로 표시합니다. "
    "땅에 내려놓은 resting 미트도 보이면 표시합니다. 손목끈·팔·공의 중심을 대신 찍지 않습니다. "
    "좌표와 pose를 따로 판단합니다. 투수 의도나 목표 위치를 추측하지 않습니다. "
    "중심을 판단할 수 없으면 unavailable, 판정 자체가 불확실하면 unknown으로 두고 "
    "mitt는 null, reason은 이유로 작성합니다. marked에는 유한한 [x,y]를 기록합니다. "
    "이전 AI/사람 결과를 보지 말고 읽으세요. 점수판 등 원본 영상 정보는 그대로여서 "
    "영상 자체가 익명화된 것은 아닙니다. 이 팩은 기존 자료의 개발 재검토이며 "
    "독립 평가가 아닙니다. response_template.json을 별도 이름으로 저장해 실제 사람이 "
    "reviewer_id와 각 행을 작성합니다. 표시된 이미지는 원본 사본이며 화면에서는 축소될 수 있습니다."
    " visibility는 full/partial/hidden/unknown, pose는 presented_target/resting/moving/unknown "
    "중 하나입니다. 아직 보지 않은 행은 unreviewed로 그대로 둡니다."
)


def _dimensions(path):
    with Image.open(path) as image:
        width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError("invalid image dimensions")
    return width, height


def _collect(root, report_path, results, expected_count):
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    if report.get("schema") != AUDIT_SCHEMA:
        raise ValueError("unexpected quality report schema")
    games, selected = set(), []
    for game in report["games"]:
        g = game["game_pk"]
        if type(g) is not int or g in games:
            raise ValueError("duplicate/invalid report game")
        games.add(g)
        paths = {}
        for key, source in game["sources"].items():
            path = _inside(results, source["path"])
            if _sha(path.read_bytes()) != source["sha256"]:
                raise ValueError(f"report source SHA256 mismatch: {key}")
            paths[key] = path
        if not {"points", "labels", "manifest", "jsonl"} <= paths.keys():
            raise ValueError("report lacks required source bindings")
        docs = {key: _load(paths[key]) for key in ("points", "labels", "manifest")}
        records = [
            json.loads(line)
            for line in paths["jsonl"].read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
        points, labels, _ = validate_inputs(
            g,
            **docs,
            records=records,
            calibration=_load(paths["calibration"]) if "calibration" in paths else None,
        )
        measured = availability(points, labels)
        if measured != game["availability"]:
            raise ValueError("report availability differs from its bound source data")
        manifest = {row["pitch_id"]: row for row in docs["manifest"]["frames"]}
        video = docs["points"]["video"]
        num, den = video["fps_num"], video["fps_den"]
        if type(num) is not int or type(den) is not int or num <= 0 or den <= 0:
            raise ValueError("invalid source video fps")
        fps = Fraction(num, den)
        for disagreement in measured["disagreements"]:
            if (
                disagreement["ai_status"] != "unavailable"
                or disagreement["human_status"] != "marked"
            ):
                continue
            pid = disagreement["pitch_id"]
            point, reference = points[pid], manifest[pid]
            path = _inside(root, point["path"])
            if path != _inside(root, reference["path"]):
                raise ValueError("points/label manifest source path mismatch")
            index = point.get("frame_index")
            if (
                type(index) is not int
                or index < 0
                or abs(index / fps - point["frame_seconds"]) > 1e-6
            ):
                raise ValueError("point frame_index/source clock mismatch")
            data = path.read_bytes()
            if _sha(data) != point["image_sha256"]:
                raise ValueError("source image SHA256 mismatch")
            selected.append(
                {
                    "pitch_id": pid,
                    "source_path": point["path"],
                    "frame_seconds": point["frame_seconds"],
                    "image_sha256": _sha(data),
                    "dimensions": _dimensions(path),
                    "data": data,
                    "selection_evidence": disagreement,
                }
            )
    if games != {849845, 823407} or len(selected) != expected_count:
        raise ValueError("this queue requires the two frozen games and expected human-only count")
    if len({row["pitch_id"] for row in selected}) != len(selected):
        raise ValueError("duplicate selected pitch")
    return selected, _sha(report_bytes), report


def prepare(root, report_path, out, *, results="docs/results/mlb_p0", expected_count=26):
    """Create a new private pack; never change source reports, images or human labels."""
    root, out, report_path = (
        Path(root).absolute(),
        Path(out).absolute(),
        Path(report_path).absolute(),
    )
    for path in (root, out, report_path):
        _no_links(path)
    root, out = root.resolve(), out.resolve()
    relative = out.relative_to(root) if out.is_relative_to(root) else None
    if (
        relative is None
        or len(relative.parts) != 2
        or relative.parts[0] != "outputs"
        or not relative.parts[1].startswith("cv_review_")
    ):
        raise ValueError("output must be a new repo outputs/cv_review_* directory")
    if out.exists():
        raise ValueError("output already exists; choose a new directory")
    selected, report_hash, report = _collect(
        root, report_path, _inside(root, results), expected_count
    )
    selected.sort(key=lambda row: _sha(row["pitch_id"].encode()))
    out.mkdir(parents=True, exist_ok=False)
    reviewer = out / "reviewer"
    (reviewer / "images").mkdir(parents=True)
    frames, private = [], []
    for row in selected:
        obs = "review_" + _sha((row["pitch_id"] + row["image_sha256"]).encode())[:24]
        image_path = f"images/{obs}.jpg"
        with (reviewer / image_path).open("xb") as stream:
            stream.write(row["data"])
        frames.append(
            {
                "observation_id": obs,
                "image_sha256": row["image_sha256"],
                "path": image_path,
                "width": row["dimensions"][0],
                "height": row["dimensions"][1],
            }
        )
        private.append(
            {
                key: value
                for key, value in dict(row, observation_id=obs).items()
                if key not in {"data", "dimensions"}
            }
        )
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "protocol_version": PROTOCOL,
        "scope": "development_source_only_recheck",
        "frames": frames,
    }
    _write_new(reviewer / "manifest.json", manifest)
    manifest_hash = _sha((reviewer / "manifest.json").read_bytes())
    _write_new(
        reviewer / "response_template.json",
        {
            "schema": RESPONSE_SCHEMA,
            "protocol_version": PROTOCOL,
            "manifest_sha256": manifest_hash,
            "reviewer_id": "",
            "rows": [
                {
                    "observation_id": f["observation_id"],
                    "image_sha256": f["image_sha256"],
                    "status": "unreviewed",
                    "mitt": None,
                    "visibility": "unknown",
                    "pose": "unknown",
                    "reason": "",
                }
                for f in frames
            ],
        },
    )
    _write_new(
        out / "private_selection.json",
        {
            "schema": "intent_review_selection_v1",
            "reviewer_manifest_sha256": manifest_hash,
            "quality_report_sha256": report_hash,
            "sources": [
                {"game_pk": g["game_pk"], "sources": g["sources"]} for g in report["games"]
            ],
            "selection": "exact frozen human_only disagreements; no correctness adjudication",
            "scope": "development preparation; real human responses still required",
            "mapping": private,
        },
    )
    page = render_review_page(manifest, _load(reviewer / "response_template.json"), INSTRUCTIONS)
    (reviewer / "index.html").write_text(page, encoding="utf-8")
    (reviewer / "review_ui.js").write_bytes(Path(__file__).with_name("review_ui.js").read_bytes())
    return {
        "prepared": len(frames),
        "completed_reviews": 0,
        "unreviewed": len(frames),
        "cv_inference_performed": False,
        "independent_validation": False,
        "reviewer_manifest_sha256": manifest_hash,
    }


def check_response(package, response_path):
    """Validate actual external responses without altering any response or status."""
    package, response_path = Path(package).absolute(), Path(response_path).absolute()
    _no_links(package)
    _no_links(response_path)
    reviewer = package / "reviewer"
    _no_links(reviewer / "manifest.json")
    raw_manifest = (reviewer / "manifest.json").read_bytes()
    manifest = _load(reviewer / "manifest.json")
    private = _load(package / "private_selection.json")
    digest = _sha(raw_manifest)
    response = _load(response_path)
    if set(response) != {"schema", "protocol_version", "manifest_sha256", "reviewer_id", "rows"}:
        raise ValueError("unexpected response document fields")
    if not isinstance(response.get("reviewer_id"), str):
        raise ValueError("reviewer_id must be a string")
    if (
        manifest.get("schema") != MANIFEST_SCHEMA
        or manifest.get("protocol_version") != PROTOCOL
        or private.get("reviewer_manifest_sha256") != digest
        or response.get("schema") != RESPONSE_SCHEMA
        or response.get("protocol_version") != PROTOCOL
        or response.get("manifest_sha256") != digest
    ):
        raise ValueError("response version/manifest SHA256 mismatch")
    expected = {frame["observation_id"]: frame for frame in manifest["frames"]}
    if len(expected) != len(manifest["frames"]):
        raise ValueError("duplicate manifest observation ID")
    seen, counts = set(), {"completed": 0, "unreviewed": 0, "unknown": 0}
    for row in response["rows"]:
        if set(row) != {
            "observation_id",
            "image_sha256",
            "status",
            "mitt",
            "visibility",
            "pose",
            "reason",
        }:
            raise ValueError("unexpected response fields (use opaque IDs, not pitch IDs)")
        obs = row["observation_id"]
        if obs not in expected or obs in seen:
            raise ValueError("unknown/duplicate response observation ID")
        seen.add(obs)
        frame = expected[obs]
        path = _inside(reviewer.resolve(), frame["path"])
        if (
            row["image_sha256"] != frame["image_sha256"]
            or _sha(path.read_bytes()) != frame["image_sha256"]
        ):
            raise ValueError("response/image SHA256 mismatch")
        if _dimensions(path) != (frame["width"], frame["height"]):
            raise ValueError("manifest/image bounds mismatch")
        status = row["status"]
        if status not in {"unreviewed", "marked", "unavailable", "unknown"}:
            raise ValueError("unknown review status")
        if (
            row["visibility"] not in {"full", "partial", "hidden", "unknown"}
            or row["pose"] not in {"presented_target", "resting", "moving", "unknown"}
            or not isinstance(row["reason"], str)
        ):
            raise ValueError("invalid visibility/pose/reason")
        if status == "marked":
            mitt = row["mitt"]
            if (
                not isinstance(mitt, list)
                or len(mitt) != 2
                or row["visibility"] not in {"full", "partial"}
            ):
                raise ValueError("marked requires a visible finite mitt point")
            x, y = (_number(v, "mitt") for v in mitt)
            if not 0 <= x < frame["width"] or not 0 <= y < frame["height"]:
                raise ValueError("mitt outside image bounds")
        elif row["mitt"] is not None:
            raise ValueError("unreviewed/unavailable/unknown must have null mitt")
        if status in {"unavailable", "unknown"} and not row["reason"].strip():
            raise ValueError("unavailable/unknown requires an explicit reason")
        counts["completed" if status in {"marked", "unavailable"} else status] += 1
    if seen != expected.keys():
        raise ValueError("response lacks manifest rows")
    if counts["completed"] + counts["unknown"] and not (response.get("reviewer_id") or "").strip():
        raise ValueError("actual reviewed responses require reviewer_id")
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    make = subs.add_parser("prepare")
    make.add_argument("--repo-root", type=Path, default=ROOT)
    make.add_argument("--report", type=Path, required=True)
    make.add_argument("--out", type=Path, required=True)
    check = subs.add_parser("check-response")
    check.add_argument("--package", type=Path, required=True)
    check.add_argument("--response", type=Path, required=True)
    args = parser.parse_args(argv)
    result = (
        prepare(args.repo_root, args.report, args.out)
        if args.command == "prepare"
        else check_response(args.package, args.response)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
