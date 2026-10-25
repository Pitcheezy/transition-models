"""CV-32: what mitt material exists on this machine, and why the existing readers abstained.

Two read-only reports, both rebuilt from saved files (no new visual judgment, no model call):

* ``inventory``: per development game, the broadcast and video form, pitch keys, the local frame
  windows (file counts, source-index continuity, content digest), how much live centre-field view
  precedes release in each window, and where the 26 re-reviewed frames sit inside those windows.
* ``bottleneck``: every saved ``unavailable`` row of the frozen readers, split into six cause
  categories by exact structural rules or exact reason strings. Free-text notes are never parsed.
  A route that no rule covers stays ``unclassified`` and is counted, never guessed.

The categories describe the *saved processing route*. They are not verified visual facts: a
reader's claim that a glove was "not presented" is recorded as that claim, not as a resting
catcher. Human marks are joined only to show whether a person could place the mitt on the same
frame; they do not turn an abstention into an AI error.

    python -m intent.mitt_inventory --out-private outputs/cv_mitt_inventory_NEW \
        --out-public docs/results/cv_mitt_20261025/inventory_v1.json
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/results/mlb_p0"
FPS = Fraction(60000, 1001)

# Static facts recorded in the M3 plan and source records; the code checks the files exist.
GAMES = {
    747139: {"broadcast": "SNY", "form": "full_game_remote_mp4", "m3_role": "development"},
    849843: {"broadcast": "NBC", "form": "condensed_game_windows", "m3_role": "development"},
    849845: {
        "broadcast": "NBC/Peacock",
        "form": "condensed_game_windows",
        "m3_role": "evaluation E1",
    },
    823407: {"broadcast": "FOX", "form": "condensed_game_windows", "m3_role": "evaluation E2"},
    849849: {
        "broadcast": "NBC",
        "form": "condensed_game_windows",
        "m3_role": "prepared fallback, unused",
    },
}

CATEGORIES = {
    "C1_mitt_not_visible": "미트 자체가 안 보임(저장된 판독 주장)",
    "C2_visible_target_undeterminable": "미트는 보이나 목표 제시 여부 판단 불가 또는 미제시 주장",
    "C3_reader_disagreement": "판독자 간 불일치",
    "C4_no_transform_reference": "좌표 변환에 필요한 기준점 없음",
    "C5_no_pitch_link_or_time_evidence": "투구 연결·관측 장면·시각 근거 없음(중앙 카메라 아님·리플레이·컷 포함)",
    "C6_execution_or_format_error": "실행·형식 오류",
}

# Exact saved reason strings -> category. Anything else is unclassified.
REASON_TABLE = {
    "glove_hidden_by_umpire": "C1_mitt_not_visible",
    "glove_not_visible": "C1_mitt_not_visible",
    "glove_hidden_by_catcher_body": "C1_mitt_not_visible",
    "glove_not_distinguishable": "C1_mitt_not_visible",
    "glove_hidden_by_batter": "C1_mitt_not_visible",
    "glove_not_identifiable_blur_and_batter_leg_overlap": "C1_mitt_not_visible",
    "glove_not_identifiable_held_low_behind_leg": "C1_mitt_not_visible",
    "catcher_not_in_setup": "C2_visible_target_undeterminable",
    "glove_not_presented: catcher drops glove to rest on the ground before release": "C2_visible_target_undeterminable",
    "glove_not_presented_resting_on_ground": "C2_visible_target_undeterminable",
    "glove_resting_on_dirt_not_presented": "C2_visible_target_undeterminable",
    "glove_already_lowered_at_cut": "C2_visible_target_undeterminable",
    "readers_disagree_on_mitt": "C3_reader_disagreement",
    "camera_not_centre_field": "C5_no_pitch_link_or_time_evidence",
    "not_centre_field": "C5_no_pitch_link_or_time_evidence",
    "slow_motion_replay_not_live": "C5_no_pitch_link_or_time_evidence",
    "cut_after_release": "C5_no_pitch_link_or_time_evidence",
}

# Structural routes of the CV6b audit (reused as is) and the extensions added here.
ROUTE_CATEGORIES = {
    "reported_not_presented_or_lowered": ["C2_visible_target_undeterminable"],
    "camera_rejection_one_candidate": ["C5_no_pitch_link_or_time_evidence"],
    "replay_rejection_one_candidate": ["C5_no_pitch_link_or_time_evidence"],
    "plate_missing_with_two_mitt_readings": ["C4_no_transform_reference"],
    "different_frame_mitt_disagreement": ["C3_reader_disagreement"],
    "same_frame_mitt_disagreement": ["C3_reader_disagreement"],
    "camera_rejection_and_plate_missing": [
        "C5_no_pitch_link_or_time_evidence",
        "C4_no_transform_reference",
    ],
}

SCOPE = {
    "evidence": "saved reader outputs and saved human marks; no image viewing or model call in this report",
    "not_claims": [
        "categories describe saved processing routes, not verified visual causes",
        "a human mark on the same frame does not make an AI abstention an error",
        "AI-reader timing annotations of 747139 are not independent human ground truth",
        "no accuracy, agreement or real-time claim",
    ],
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def pitch_key(game: int, ab: int, pn: int) -> str:
    return f"{game}:{ab}:{pn}"


def digest_lines(records) -> str:
    """Order-independent content digest: sha256 over sorted 'name<TAB>size<TAB>sha256' lines."""
    lines = sorted(f"{name}\t{size}\t{sha}" for name, size, sha in records)
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def frame_index(name: str) -> int | None:
    if name.startswith("frame_") and name.endswith(".jpg") and name[6:-4].isdigit():
        return int(name[6:-4])
    return None


def window_inventory(windows_dir: Path, release_by_key: dict, game: int, hash_frames: bool = True):
    """Per window: frame files, source-index steps, span around release, digest of frame files."""
    rows, digest_records = [], []
    if not windows_dir.is_dir():
        return {"present": False, "windows": []}
    for target in sorted(p for p in windows_dir.iterdir() if p.is_dir()):
        frames = sorted(
            (frame_index(p.name), p) for p in target.iterdir() if frame_index(p.name) is not None
        )
        indices = [i for i, _ in frames]
        steps = Counter(b - a for a, b in zip(indices, indices[1:], strict=False))
        name = target.name
        try:
            ab, pn = (int(v) for v in name.removeprefix("pa").split("_p"))
        except ValueError:
            rows.append({"window": name, "error": "unexpected_window_name"})
            continue
        key = pitch_key(game, ab, pn)
        release = release_by_key.get(key)
        first_t = float(Fraction(indices[0]) / FPS) if indices else None
        last_t = float(Fraction(indices[-1]) / FPS) if indices else None
        if hash_frames:
            for _, path in frames:
                digest_records.append(
                    (f"{name}/{path.name}", path.stat().st_size, sha256_file(path))
                )
        rows.append(
            {
                "pitch": key,
                "frames": len(indices),
                "first_index": indices[0] if indices else None,
                "step_counts": dict(sorted(steps.items())),
                "seconds_before_release": None
                if release is None or first_t is None
                else round(release - first_t, 3),
                "seconds_after_release": None
                if release is None or last_t is None
                else round(last_t - release, 3),
                "has_crops": any(p.name.startswith("crop_") for p in target.iterdir()),
                "has_strip": (target / "strip.jpg").is_file(),
            }
        )
    return {
        "present": True,
        "windows": rows,
        "frame_digest": digest_lines(digest_records) if hash_frames else None,
        "frames_total": sum(r.get("frames", 0) for r in rows),
    }


def reader_pairs(game: int):
    """Saved two-reader rows keyed by 'ab:pn', via the frozen loader; None when not saved."""
    path = RESULTS / f"game_{game}_condensed_reads_v0.json"
    if not path.is_file():
        return None, None
    sys.path.insert(0, str(ROOT))
    from intent import condensed

    return condensed.collect_reads(condensed.load_reader_results(path)), sha256_file(path)


def live_view_lead(pairs) -> dict:
    """Seconds of live centre-field view before release, and how early the chosen setup frame is.

    A reader row whose live-view start or setup frame lies after its own release frame is not
    summarised; it is counted as an inconsistent saved row (format/consistency, category C6 kind).
    """
    live, setup_lead, inconsistent = [], [], []
    for key, pair in sorted((pairs or {}).items()):
        for reader, row in sorted(pair.items()):
            rel, cf, st = (
                row.get("release_frame"),
                row.get("live_cf_first_frame"),
                row.get("setup_frame"),
            )
            if rel is not None and ((cf is not None and cf > rel) or (st is not None and st > rel)):
                inconsistent.append(f"{key}:{reader}")
                continue
            if rel is not None and cf is not None:
                live.append(float(Fraction(rel - cf) / FPS))
            if rel is not None and st is not None:
                setup_lead.append(float(Fraction(rel - st) / FPS))

    def summary(values):
        if not values:
            return {"n": 0}
        ordered = sorted(values)
        return {
            "n": len(values),
            "median": round(statistics.median(ordered), 3),
            "p10": round(ordered[int(0.1 * (len(ordered) - 1))], 3),
            "p90": round(ordered[int(0.9 * (len(ordered) - 1))], 3),
            "min": round(ordered[0], 3),
            "max": round(ordered[-1], 3),
        }

    return {
        "live_centre_view_before_release_seconds": summary(live),
        "chosen_setup_frame_before_release_seconds": summary(setup_lead),
        "unit": "reader rows (A and B counted separately)",
        "inconsistent_rows_excluded": inconsistent,
    }


def classify_pair(a, b, decision, cv6b_classify):
    """Structural route of one unavailable two-reader decision. Returns (route, categories)."""
    try:
        route = cv6b_classify(a, b, decision)
        return route, ROUTE_CATEGORIES[route]
    except ValueError:
        pass

    def candidate(row):
        return bool(
            row
            and row.get("setup_frame") is not None
            and row.get("mitt_center")
            and row.get("setup_plate_front")
        )

    def no_setup(row):
        return row is not None and row.get("setup_frame") is None and row.get("mitt_center") is None

    eligible = [r for r in (a, b) if candidate(r)]
    if len(eligible) == 1:
        other = b if eligible[0] is a else a
        if no_setup(other):
            category = REASON_TABLE.get(other.get("setup_reason"))
            if category:
                return f"one_candidate_other_reason:{other.get('setup_reason')}", [category]
        if other and other.get("mitt_center") is not None and not other.get("setup_plate_front"):
            return "plate_missing_on_other_reader_different_frame", [
                "C4_no_transform_reference",
                "C3_reader_disagreement",
            ]
    if not eligible and no_setup(a) and no_setup(b):
        cats = sorted({REASON_TABLE.get(r.get("setup_reason")) for r in (a, b)} - {None})
        if cats and all(REASON_TABLE.get(r.get("setup_reason")) for r in (a, b)):
            return "both_no_setup:" + "|".join(
                sorted({a.get("setup_reason"), b.get("setup_reason")})
            ), cats
    return "unclassified", []


def bottleneck(games=(849845, 823407, 849849, 849843, 747139)):
    sys.path.insert(0, str(ROOT))
    from intent import condensed

    spec = importlib.util.spec_from_file_location(
        "audit_cv6b", ROOT / "scripts/audit_cv6b_saved_reasons.py"
    )
    cv6b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cv6b)
    cv6b_classify = cv6b.classify

    if condensed.AGREE_PX != 15:
        raise ValueError("frozen consensus threshold changed")
    report, private_rows, sources = {}, [], {}
    for game in games:
        jsonl_path = RESULTS / f"game_{game}_intent_v0.jsonl"
        rows = read_jsonl(jsonl_path)
        sources[f"{game}_jsonl"] = sha256_file(jsonl_path)
        pairs, reads_sha = reader_pairs(game)
        if reads_sha:
            sources[f"{game}_reads"] = reads_sha
        humans = {}
        human_path = RESULTS / f"game_{game}_intent_human_labels_v0.json"
        if human_path.is_file():
            sources[f"{game}_human_labels"] = sha256_file(human_path)
            humans = {r["pitch_id"]: r.get("mitt_status") for r in read_json(human_path)["frames"]}
        categories, routes, human_marked, conversion = Counter(), Counter(), Counter(), Counter()
        unclassified = []
        for row in rows:
            if row["status"] == "estimated":
                conversion[f"{row.get('deepest_frame')}|{row.get('blocked_by')}"] += 1
                continue
            _, ab, pn = row["pitch_id"].split(":")
            pair = (pairs or {}).get(f"{ab}:{pn}")
            if pair is not None:
                a, b = pair.get("A"), pair.get("B")
                decision = condensed.decide_setup(a, b)
                if (
                    decision["status"] != "unavailable"
                    or decision["reason"] != row["unavailable_reason"]
                ):
                    raise ValueError(f"saved decision does not reproduce for {row['pitch_id']}")
                route, cats = classify_pair(a, b, decision, cv6b_classify)
            else:
                reason = row.get("unavailable_reason")
                category = REASON_TABLE.get(reason)
                route, cats = (
                    (f"reason:{reason}", [category])
                    if category
                    else (f"reason_without_reader_rows:{reason}", [])
                )
            routes[route] += 1
            if not cats:
                unclassified.append(row["pitch_id"])
            for c in cats:
                categories[c] += 1
            primary = cats[0] if cats else "unclassified"
            hm = humans.get(row["pitch_id"])
            if hm is not None:
                human_marked[f"{primary}|human_{hm}"] += 1
            private_rows.append(
                {
                    "pitch_id": row["pitch_id"],
                    "route": route,
                    "categories": cats,
                    "human_mitt_status": hm,
                }
            )
        unavailable = sum(1 for r in rows if r["status"] != "estimated")
        report[str(game)] = {
            "rows": len(rows),
            "estimated": len(rows) - unavailable,
            "unavailable": unavailable,
            "category_counts": {c: categories.get(c, 0) for c in CATEGORIES},
            "multi_category_rows": sum(
                1
                for r in private_rows
                if r["pitch_id"].startswith(f"{game}:") and len(r["categories"]) > 1
            ),
            "unclassified": len(unclassified),
            "unclassified_reasons": sorted(
                Counter(
                    r for r in routes if r.startswith(("unclassified", "reason_without"))
                ).elements()
            ),
            "routes": dict(sorted(routes.items())),
            "human_join": dict(sorted(human_marked.items())) or None,
            "estimated_conversion_stage": dict(sorted(conversion.items())),
            "reader_rows_saved": pairs is not None,
        }
    return {
        "games": report,
        "category_labels": CATEGORIES,
        "reason_table": REASON_TABLE,
        "route_categories": ROUTE_CATEGORIES,
        "sources_sha256": sources,
    }, private_rows


def rereview_links(selection_path: Path):
    """Where the 26 re-reviewed frames sit in their saved windows (frames before/after, seconds)."""
    if not selection_path.is_file():
        return {"present": False}, []
    selection = read_json(selection_path)
    rows, private, readers = [], [], {}
    for item in selection["mapping"]:
        game = int(item["pitch_id"].split(":")[0])
        if game not in readers:
            readers[game] = reader_pairs(game)[0] or {}
        path = ROOT / item["source_path"]
        record = {"pitch_id": item["pitch_id"], "exists": path.is_file()}
        if path.is_file():
            record["sha_matches"] = sha256_file(path) == item["image_sha256"]
            indices = sorted(
                i for i in (frame_index(p.name) for p in path.parent.iterdir()) if i is not None
            )
            me = frame_index(path.name)
            record["window_frames_before"] = sum(1 for i in indices if i < me)
            record["window_frames_after"] = sum(1 for i in indices if i > me)
            record["window_seconds_before"] = round(float(Fraction(me - indices[0]) / FPS), 3)
            pair = readers[game].get(item["pitch_id"].split(":", 1)[1], {})
            releases = sorted(
                r["release_frame"] for r in pair.values() if r.get("release_frame") is not None
            )
            if releases:
                lead = Fraction(releases[len(releases) // 2] - me) / FPS
                record["seconds_before_reader_release"] = round(float(lead), 3)
        private.append(
            {**record, "observation_id": item["observation_id"], "source_path": item["source_path"]}
        )
        rows.append(record)
    exists = [r for r in rows if r["exists"]]
    return {
        "present": True,
        "frames": len(rows),
        "files_present": len(exists),
        "sha_matches": sum(1 for r in exists if r.get("sha_matches")),
        "games": dict(Counter(r["pitch_id"].split(":")[0] for r in rows)),
        "frames_before_in_window": sorted(r["window_frames_before"] for r in exists),
        "frames_after_in_window": sorted(r["window_frames_after"] for r in exists),
        "seconds_before_reader_release": sorted(
            r["seconds_before_reader_release"]
            for r in exists
            if r.get("seconds_before_reader_release") is not None
        ),
        "note": "each reviewed frame is one frame of a saved ~3 s window (about 20 fps); the window gives the short continuous context",
    }, private


def inventory(hash_frames: bool = True):
    games = {}
    sources = {}
    timing = read_json(RESULTS / "game_747139_timing.json")
    sources["747139_timing"] = sha256_file(RESULTS / "game_747139_timing.json")
    src = read_json(RESULTS / "game_747139_sources.json")["sources"]["full_game"]
    statuses = Counter(r["status"] for r in timing["annotations"])
    games["747139"] = {
        **GAMES[747139],
        "pitch_keys": len(timing["annotations"]),
        "timing_status": dict(statuses),
        "remote_source": {
            "page_url": src["page_url"],
            "media_url_recorded": timing["source"]["media_url"],
            "duration_seconds": timing["source"]["duration_seconds"],
            "full_video_downloaded": src["inspection"].get("full_video_downloaded"),
        },
        "local_continuous_clips": [],
        "timing_annotator": "AI visual annotation (Codex/Claude agents); not independent human ground truth",
    }
    for rel in ("outputs/cv_local_pa_interval_v1/broadcast_context.mp4",):
        path = ROOT / rel
        if path.is_file():
            games["747139"]["local_continuous_clips"].append(
                {
                    "path": rel,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                    "covers": "PA2 broadcast interval only (CV23)",
                }
            )
    for game in (849843, 849845, 823407, 849849):
        jsonl = read_jsonl(RESULTS / f"game_{game}_intent_v0.jsonl")
        pitches_path = ROOT / f"outputs/frames/{game}_pitches.json"
        release = {}
        if pitches_path.is_file():
            release = {
                pitch_key(game, p["at_bat_number"], p["pitch_number"]): p["release_t"]
                for p in read_json(pitches_path)
            }
        win = window_inventory(ROOT / f"outputs/frames/{game}_windows", release, game, hash_frames)
        pairs, _ = reader_pairs(game)
        reader_lead = []
        for w in win.get("windows", []):
            rows = (pairs or {}).get(w["pitch"].split(":", 1)[1], {})
            releases = sorted(
                r["release_frame"] for r in rows.values() if r.get("release_frame") is not None
            )
            if releases and w.get("first_index") is not None:
                lead = Fraction(releases[len(releases) // 2] - w["first_index"]) / FPS
                reader_lead.append(float(lead))
        pack = ROOT / f"outputs/intent_label/game_{game}_pack.html"
        games[str(game)] = {
            **GAMES[game],
            "pitch_keys_in_output": len(jsonl),
            "windows": {k: v for k, v in win.items() if k != "windows"},
            "window_count": len(win.get("windows", [])),
            "release_time_source": pitches_path.name if pitches_path.is_file() else None,
            "windows_with_release_time": sum(
                1 for w in win.get("windows", []) if w.get("seconds_before_release") is not None
            ),
            "seconds_after_release": _summary(
                [
                    w["seconds_after_release"]
                    for w in win.get("windows", [])
                    if w.get("seconds_after_release") is not None
                ]
            ),
            "seconds_before_release": _summary(
                [
                    w["seconds_before_release"]
                    for w in win.get("windows", [])
                    if w.get("seconds_before_release") is not None
                ]
            ),
            "window_start_before_reader_release_seconds": _summary(reader_lead),
            "release_time_note": "seconds_before/after_release use the scan release_t (0.25 s grid) "
            "that centred the window; the reader release frame can differ (up to about 0.6 s here)",
            "step_counts": dict(
                sum((Counter(w.get("step_counts", {})) for w in win.get("windows", [])), Counter())
            ),
            "live_view": live_view_lead(pairs) if pairs else None,
            "label_pack_page_local": pack.is_file(),
        }
    return {"games": games, "sources_sha256": sources}


def _summary(values):
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "median": round(statistics.median(ordered), 3),
        "min": round(ordered[0], 3),
        "max": round(ordered[-1], 3),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-private", type=Path, required=True)
    parser.add_argument("--out-public", type=Path, required=True)
    parser.add_argument("--skip-frame-hash", action="store_true")
    args = parser.parse_args(argv)
    if "outputs" not in args.out_private.resolve().parts:
        parser.error("private rows go under outputs/ (git-ignored)")
    if args.out_private.exists() or args.out_public.exists():
        parser.error("outputs must be new paths")
    args.out_private.mkdir(parents=True)
    inv = inventory(hash_frames=not args.skip_frame_hash)
    bott, private_rows = bottleneck()
    links, private_links = rereview_links(
        ROOT / "outputs/cv_review_20261008_ko_v1/private_selection.json"
    )
    cv24 = read_json(ROOT / "docs/results/cv_independent_20261008/cv24_pitch_deadlines_v1.json")[
        "counts"
    ]
    public = {
        "schema": "pitcheezy-mitt-inventory-v1",
        "scope": SCOPE,
        "inventory": inv,
        "rereview_26": links,
        "bottleneck": bott,
        "local_loop_cv24": {
            "counts": cv24,
            "interpretation": "the local loop used an unadopted generic detector whose responses never confirm a mitt; "
            "0 usable mitts is a design limit, not a finding that mitts were absent",
        },
    }
    (args.out_private / "bottleneck_rows.json").write_text(
        json.dumps(private_rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (args.out_private / "rereview_links.json").write_text(
        json.dumps(private_links, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    args.out_public.parent.mkdir(parents=True, exist_ok=True)
    args.out_public.write_text(
        json.dumps(public, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                g: {
                    k: v
                    for k, v in r.items()
                    if k in ("unavailable", "unclassified", "category_counts")
                }
                for g, r in bott["games"].items()
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
