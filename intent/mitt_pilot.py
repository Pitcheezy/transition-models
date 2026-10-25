"""CV-33 pilot: stateless per-frame AI reading of the development bundle, then the causal rule.

Pre-registered rule (CV-33 acceptance criteria, fixed before any pilot frame was read): the first
10 extracted pitches of ``bundle_v1`` in pitch order; every second grid frame (about 5 fps) from
the window start up to the release-nearest index (grid frames at or before it, so the last read
frame can be up to about 0.2 s earlier); plus, for the same pitches, the image the
frozen v0 reader actually read (``v0_read_frames``) for a same-frame re-read.

Stateless reading: a batch never holds two frames of the same pitch, files carry opaque ids, and
the reader is told the images are unrelated. So reading frame t cannot use a later frame of the
same pitch. The reader prompt asks for layer-A fields only (no target / resting judgment).

    python -m intent.mitt_pilot prepare --bundle outputs/cv_mitt_dev_20261025/bundle_v1 \
        --out outputs/cv_mitt_dev_20261025/pilot_v1
    (each batch is read by one agent, which writes answers/<batch>.json)
    python -m intent.mitt_pilot evaluate --pilot outputs/cv_mitt_dev_20261025/pilot_v1 \
        --out docs/results/cv_mitt_20261025/pilot_v1.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from fractions import Fraction
from pathlib import Path

from intent import mitt_temporal as mt
from intent.mitt_dev_bundle import FPS, MAIN_BOX, RESULTS, read_json, sha256_file

SCHEMA = "pitcheezy-mitt-pilot-dev-v1"
RULE = {
    "pitches": "first 10 extracted pitches of bundle_v1 in pitch order",
    "frames": "every 2nd grid frame (step 12 source frames, about 5 fps) from window start "
    "through the release-nearest frame",
    "same_frame_reread": "the image the frozen v0 reader actually read, one per pitch",
    "batching": "at most one frame per pitch per batch; opaque ids; batch order by id",
    "reader": "Claude Code agent, model Fable 5.1 (the v0 747139 reader model), same 2x crop",
    "fixed_before_reading": True,
}
READER_FIELDS = (
    "view",
    "catcher",
    "mitt_visibility",
    "occluder",
    "mitt_center_px",
    "uncertainty_px",
    "plate_front",
    "pitcher_phase",
)

PROMPT = """You read single broadcast baseball frames for a computer-vision development test.

Each image in the list below is a 2x enlarged crop of a 1280x720 broadcast frame covering
ORIGINAL x 440-840 and y 120-400. Yellow grid lines every 100 original px carry their original
coordinate labels; grey lines every 20 original px. The images come from DIFFERENT pitches and
are in no meaningful order. Read each image on its own. Do not compare images or reuse what you
saw in another image.

Open every image with the Read tool. For each image report exactly these fields:
- view: "live_centre_field" (the standard live camera from behind the pitcher showing catcher,
  umpire, batter and home plate), "other_view", "replay", "graphic_or_transition" or "unknown"
- catcher: "set" (crouched behind the plate), "not_set" (standing, walking, not yet crouched),
  "not_visible" or "unknown"
- mitt_visibility: "full", "partial", "hidden", "out_of_view" or "unknown" (the catcher's glove)
- occluder: null, "batter", "umpire", "catcher_body", "pitcher", "motion_blur", "graphic" or "other"
- mitt_center_px: [x, y] centre of the catcher's glove in ORIGINAL frame pixels read from the grid
  labels, only when mitt_visibility is "full" or "partial"; otherwise null
- uncertainty_px: your honest +/- in original pixels for that centre (null when no centre)
- plate_front: {{"left_end": [x, y], "right_end": [x, y]}} the front straight edge of home plate
  (the lowest straight edge of the white pentagon, facing the pitcher) in original pixels when
  clearly visible, otherwise null
- pitcher_phase: "before_delivery", "delivery", "after_release", "not_visible" or "unknown",
  only from what this crop shows
- note: at most 15 words

Report only what is visible and where it is. Do NOT say whether the glove is a target, presented,
set up, resting, relaxed or lowered on purpose, and do not guess the pitch outcome.

Images (id: path):
{images}

Write a JSON file to {answer_path} with the Write tool, shaped exactly as
{{"batch": "{batch}", "frames": [{{"id": "<id>", "view": ..., ..., "note": "..."}}]}}
with one entry per image id above. Then reply with only the word done."""


def opaque(pitch_id: str, index: int, salt: str) -> str:
    return hashlib.sha256(f"{salt}|{pitch_id}|{index}".encode()).hexdigest()[:12]


def plan(manifest, count=10, every=2):
    """Pitch keys and frame indices of the pilot, from the fixed rule."""
    pitches = [p for p in manifest["pitches"] if p["status"] == "extracted"][:count]
    out = []
    for p in pitches:
        release = p["window"]["release_index"]
        grid = [f for f in p["frames"] if "grid" in f["roles"] and f["index"] <= release]
        out.append({"pitch_id": p["pitch_id"], "window": p["window"], "frames": grid[::every]})
    return out


def batches_for(items, salt):
    """Round-robin by relative position: batch k holds the k-th frame of every pitch."""
    depth = max(len(p["frames"]) for p in items)
    batches = []
    for k in range(depth):
        rows = [
            {"pitch_id": p["pitch_id"], "index": p["frames"][k]["index"], "kind": "sequence"}
            for p in items
            if k < len(p["frames"])
        ]
        for r in rows:
            r["id"] = opaque(r["pitch_id"], r["index"], salt)
        batches.append(sorted(rows, key=lambda r: r["id"]))
    return batches


def prepare(bundle: Path, out: Path, salt: str = "cv33-pilot-v1"):
    from PIL import Image

    from intent.broadcast_windows import _grid

    if out.exists():
        raise SystemExit("pilot directory must be new")
    manifest = read_json(bundle / "manifest.json")
    items = plan(manifest)
    batches = batches_for(items, salt)
    reread = []
    for p in items:
        found = sorted(
            (bundle / "v0_read_frames").glob(f"{p['pitch_id'].replace(':', '_')}_frame_*.jpg")
        )
        if len(found) != 1:
            raise SystemExit(f"v0 read image missing for {p['pitch_id']}")
        index = int(found[0].stem.rsplit("_", 1)[1])
        reread.append(
            {"pitch_id": p["pitch_id"], "index": index, "kind": "v0_reread", "source": found[0]}
        )
    for r in reread:
        r["id"] = opaque(r["pitch_id"], r["index"], salt + "-reread")
    batches.append(sorted(reread, key=lambda r: r["id"]))
    (out / "answers").mkdir(parents=True)
    private = []
    for number, rows in enumerate(batches, start=1):
        name = f"b{number:02d}"
        folder = out / "batches" / name
        folder.mkdir(parents=True)
        lines = []
        for r in rows:
            _, ab, pn = r["pitch_id"].split(":")
            if r["kind"] == "sequence":
                src = bundle / f"pa{ab}_p{pn}" / f"crop_{r['index']:06d}.jpg"
                (folder / f"{r['id']}.jpg").write_bytes(src.read_bytes())
            else:
                with Image.open(r["source"]) as image:
                    _grid(image.convert("RGB"), MAIN_BOX, 2).save(
                        folder / f"{r['id']}.jpg", quality=92
                    )
            path = (folder / f"{r['id']}.jpg").resolve()
            lines.append(f"- {r['id']}: {path}")
            private.append(
                {
                    "batch": name,
                    "id": r["id"],
                    "pitch_id": r["pitch_id"],
                    "index": r["index"],
                    "kind": r["kind"],
                    "image_sha256": sha256_file(folder / f"{r['id']}.jpg"),
                }
            )
        answer = (out / "answers" / f"{name}.json").resolve()
        prompt = PROMPT.format(images="\n".join(lines), answer_path=answer, batch=name)
        (folder / "prompt.txt").write_text(prompt, encoding="utf-8")
    meta = {
        "schema": SCHEMA,
        "rule": RULE,
        "salt": salt,
        "bundle_manifest_sha256": sha256_file(bundle / "manifest.json"),
        "pitches": [p["pitch_id"] for p in items],
        "batches": len(batches),
        "frames": len(private),
        "mapping": private,
    }
    (out / "pilot_private.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    return meta


def load_answers(pilot: Path):
    meta = read_json(pilot / "pilot_private.json")
    by_id = {m["id"]: m for m in meta["mapping"]}
    answers, problems = {}, Counter()
    for path in sorted((pilot / "answers").glob("b*.json")):
        try:
            doc = read_json(path)
        except (json.JSONDecodeError, UnicodeDecodeError):
            problems["unreadable_answer_file"] += 1
            continue
        for row in doc.get("frames", []):
            if row.get("id") not in by_id:
                problems["unknown_id"] += 1
                continue
            if row["id"] in answers:
                problems["duplicate_id"] += 1
                continue
            answers[row["id"]] = row
    missing = [m["id"] for m in meta["mapping"] if m["id"] not in answers]
    return meta, answers, problems, missing


def _reader_point(value, field):
    """Reject malformed coordinates instead of coercing reader mistakes into pixels."""
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
            for v in value
        )
    ):
        raise ValueError(f"{field} must be two finite numbers")
    return [float(v) for v in value]


def to_observation(mapping, answer):
    """Reader answer -> layer-A record, or (None, reason) when a field is outside the schema."""
    try:
        if not isinstance(answer, dict):
            raise ValueError("reader answer must be an object")
        centre = answer.get("mitt_center_px")
        plate = answer.get("plate_front")
        obs = {
            "pitch_id": mapping["pitch_id"],
            "frame_index": mapping["index"],
            "frame_seconds": float(Fraction(mapping["index"]) / FPS),
            "view": answer.get("view"),
            "catcher": answer.get("catcher"),
            "mitt_visibility": answer.get("mitt_visibility"),
            "occluder": answer.get("occluder"),
            "mitt_center_px": _reader_point(centre, "mitt_center_px")
            if centre is not None
            else None,
            "pitcher_phase": answer.get("pitcher_phase"),
            "uncertainty_px": answer.get("uncertainty_px"),
        }
        if plate is not None:
            if not isinstance(plate, dict):
                raise ValueError("plate_front must be an object or null")
            left = _reader_point(plate.get("left_end"), "plate_front.left_end")
            right = _reader_point(plate.get("right_end"), "plate_front.right_end")
            if left == right:
                raise ValueError("plate_front endpoints must differ")
            obs["plate_front"] = {"left_end": left, "right_end": right}
        mt.validate_observation(obs)
    except (ValueError, TypeError, OverflowError) as error:
        return None, f"schema:{error}"
    return obs, None


def _px_summary(values):
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    p90 = ordered[min(len(ordered) - 1, math.ceil(0.9 * len(ordered)) - 1)]
    return {
        "n": len(ordered),
        "median": round(statistics.median(ordered), 2),
        "p90": round(p90, 2),
        "max": round(ordered[-1], 2),
    }


def evaluate(pilot: Path, out: Path, delivery_path: Path | None = None, params=mt.PARAMS_DEV_V1):
    meta, answers, problems, missing = load_answers(pilot)
    timing = {
        f"747139:{a['at_bat_number']}:{a['pitch_number']}": a
        for a in read_json(RESULTS / "game_747139_timing.json")["annotations"]
    }
    v0 = {
        f"747139:{f['at_bat_number']}:{f['pitch_number']}": f
        for f in read_json(RESULTS / "game_747139_intent_points_v0.json")["frames"]
    }
    delivery_doc = read_json(delivery_path) if delivery_path and delivery_path.is_file() else None
    delivery = delivery_doc["pitches"] if delivery_doc else {}
    delivery_meta = (
        {k: delivery_doc[k] for k in ("definition", "uncertainty_seconds", "annotator")}
        if delivery_doc
        else {"status": "none; layer-A pitcher phase used if present"}
    )
    sequences, schema_errors = {}, Counter()
    reread = {}
    for m in meta["mapping"]:
        answer = answers.get(m["id"])
        if answer is None:
            continue
        obs, error = to_observation(m, answer)
        if error:
            schema_errors[error.split(":", 2)[0] + ":" + error.split(":", 2)[1][:40]] += 1
            continue
        if m["kind"] == "v0_reread":
            reread[m["pitch_id"]] = obs
        else:
            sequences.setdefault(m["pitch_id"], []).append(obs)
    rows, comparisons = [], []
    for pid in meta["pitches"]:
        seq = sorted(sequences.get(pid, []), key=lambda o: o["frame_seconds"])
        planned = sorted(
            float(Fraction(m["index"]) / FPS)
            for m in meta["mapping"]
            if m["pitch_id"] == pid and m["kind"] == "sequence"
        )
        first_seen = planned[0] if planned else None  # planned window start, not first answer
        floor = next(
            (x for x in planned[1:] if x - planned[0] + 1e-9 >= params["min_hold_seconds"]), None
        )
        t = timing[pid]
        v0_row = v0.get(pid, {})
        d_info = delivery.get(pid) or {}
        summary = mt.summarize_pitch(
            seq,
            release_seconds=t["release_seconds"],
            delivery_start_seconds=d_info.get("delivery_start_seconds"),
            params=params,
        )
        cand_d = summary["candidate_before_delivery_start"]
        cand_r = summary["candidate_before_release"]
        v0_point = v0_row.get("mitt_center") if v0_row.get("status") == "estimated" else None
        row = {
            "pitch_id": pid,
            "frames_planned": sum(
                1 for m in meta["mapping"] if m["pitch_id"] == pid and m["kind"] == "sequence"
            ),
            "frames_observed": len(seq),
            "usable_frames": sum(1 for o in seq if mt.unusable_reason(o) is None),
            "state_counts": summary["state_counts"],
            "unclear_reasons": summary["unclear_reasons"],
            "candidates": summary["candidates"],
            "decision_seconds": t["decision_seconds"],
            "earliest_possible_emission_after_decision_s": round(floor - t["decision_seconds"], 3)
            if floor is not None
            else None,
            "delivery_start_seconds": summary["delivery_start_seconds"],
            "delivery_start_source": summary["delivery_start_source"],
            "release_seconds": t["release_seconds"],
            "candidate_before_delivery_start": _brief(cand_d, t, first_seen),
            "candidate_before_release": _brief(cand_r, t, first_seen),
            "conversion_before_delivery_start": summary["conversion_before_delivery_start"][
                "status"
            ],
            "undeterminable_before_delivery_start": summary["undeterminable_before_delivery_start"],
            "undeterminable_before_release": summary["undeterminable_before_release"],
            "v0": {
                "status": v0_row.get("status"),
                "point_px": v0_point,
                "frame_seconds": t["decision_seconds"],
            },
        }
        if v0_point and cand_d:
            row["candidate_vs_v0_px"] = round(math.dist(v0_point, cand_d["point_px"]), 2)
        rr = reread.get(pid)
        if rr is not None and v0_point and rr["mitt_center_px"]:
            comparisons.append(math.dist(v0_point, rr["mitt_center_px"]))
            row["same_frame_reread_px"] = round(comparisons[-1], 2)
        row["same_frame_reread_status"] = (
            "no_reread_answer"
            if rr is None
            else "no_centre_in_reread"
            if not rr["mitt_center_px"]
            else "no_v0_point"
            if not v0_point
            else "compared"
        )
        row["reader_jumps"] = reader_jumps(seq)
        rows.append(row)
    n = len(rows)
    summary = {
        "schema": SCHEMA + "-public-summary",
        "scope": "development pilot on 747139 (development data); AI reader outputs, not human ground truth; "
        "local offline replay, not a live test",
        "rule": RULE,
        "frames_note": "frames read are grid frames with index at or before the release-nearest index "
        "(every 2nd); the release-nearest frame itself is read only when it lies on that grid; the delivery "
        "sheets use every grid frame at or before the same index",
        "window_note": "frames start at decision - 1.0 s; the earliest possible emission per pitch is the "
        "first planned frame reached min_hold_seconds after the first planned frame "
        "(earliest_possible_emission_after_decision_s, from params); segment_start_after_window_start_s is "
        "measured from the first planned frame",
        "params": params,
        "params_sha256": mt.params_sha256(params),
        "delivery_start_annotation": delivery_meta,
        "release_basis": "AI visual annotation in game_747139_timing.json (evaluation cut-off only)",
        "candidate_at_cutoff": "the most recent candidate emitted strictly before the cut-off",
        "reader_answers": {
            "frames_planned": len(meta["mapping"]),
            "answered": len(answers),
            "missing": len(missing),
            "answer_file_problems": dict(problems),
            "schema_rejected": dict(schema_errors),
        },
        "denominator_pitches": n,
        "old_vs_new_common_task": {
            "task": "one mitt pixel point per pitch, available before delivery start, from frames up to that time",
            "v0_decision_frame": {
                "pixel_output": sum(1 for r in rows if r["v0"]["point_px"]),
                "output_time": "decision frame (start of the set window)",
                "temporal_evidence": "none (one frame)",
            },
            "temporal_rule": {
                "candidate_before_delivery_start": sum(
                    1 for r in rows if r["candidate_before_delivery_start"]
                ),
                "candidate_before_release": sum(1 for r in rows if r["candidate_before_release"]),
                "delivery_start_unknown": sum(
                    1 for r in rows if r["delivery_start_seconds"] is None
                ),
                "undeterminable_before_delivery_start": dict(
                    Counter(
                        r["undeterminable_before_delivery_start"]
                        for r in rows
                        if r["undeterminable_before_delivery_start"]
                    )
                ),
                "undeterminable_before_release": dict(
                    Counter(
                        r["undeterminable_before_release"]
                        for r in rows
                        if r["undeterminable_before_release"]
                    )
                ),
                "left_censored_candidates_before_delivery": sum(
                    1
                    for r in rows
                    if r["candidate_before_delivery_start"]
                    and r["candidate_before_delivery_start"]["left_censored"]
                ),
                "front_edge_units_before_delivery": sum(
                    1 for r in rows if r["conversion_before_delivery_start"] == "front_edge_units"
                ),
            },
            "candidate_vs_v0_point_px": _px_summary(
                [r["candidate_vs_v0_px"] for r in rows if "candidate_vs_v0_px" in r]
            ),
            "candidate_vs_v0_note": "distance between two AI readings at different moments; not an error",
        },
        "same_frame_reread_vs_v0_px": {
            **_px_summary(comparisons),
            "statuses": dict(Counter(r["same_frame_reread_status"] for r in rows)),
            "note": "same image, v0 reader vs pilot reader (same model family); repeatability, not accuracy",
        },
        "reader_instability": {
            "consecutive_usable_pairs": sum(r["reader_jumps"]["pairs"] for r in rows),
            "pairs_over_30px": sum(r["reader_jumps"]["over_30px"] for r in rows),
            "pairs_over_50px": sum(r["reader_jumps"]["over_50px"] for r in rows),
            "note": "jumps between consecutive usable frames 0.2 s apart; real motion and reader "
            "identity switches are not separable without human review",
        },
        "sensitivity": sensitivity(sequences, meta["pitches"], timing, delivery),
        "reader_calls": usage_summary(pilot / "agent_usage.json"),
        "pitches": rows,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


SENSITIVITY_GRID = [
    {"hold_radius_px": r, "min_hold_seconds": h} for r in (8.0, 12.0, 16.0) for h in (0.3, 0.5)
]


def reader_jumps(seq):
    usable = [o for o in seq if mt.unusable_reason(o) is None]
    pairs = [
        math.dist(a["mitt_center_px"], b["mitt_center_px"])
        for a, b in zip(usable, usable[1:], strict=False)
        if b["frame_seconds"] - a["frame_seconds"] <= 0.25
    ]
    return {
        "pairs": len(pairs),
        "over_30px": sum(1 for d in pairs if d > 30),
        "over_50px": sum(1 for d in pairs if d > 50),
        "median_px": round(statistics.median(pairs), 2) if pairs else None,
    }


PITCHER_BOX = (470, 250, 720, 590)  # 747139 centre-field view: the pitcher on the mound
DELIVERY_DEFINITION = (
    "first 10 fps grid frame (window start through release-nearest) in which the pitcher's lead leg "
    "visibly starts to lift for the delivery"
)


def _sheet_frames(manifest, pitch_id):
    p = next(x for x in manifest["pitches"] if x["pitch_id"] == pitch_id)
    release = p["window"]["release_index"]
    return [f for f in p["frames"] if "grid" in f["roles"] and f["index"] <= release]


def delivery_sheets(bundle: Path, pilot: Path, cols=12, scale=0.5):
    """Pitcher-region contact sheets (10 fps, labelled by position and seconds from decision)."""
    from PIL import Image, ImageDraw

    manifest = read_json(bundle / "manifest.json")
    out = pilot / "delivery_sheets"
    out.mkdir(exist_ok=True)
    tw = int((PITCHER_BOX[2] - PITCHER_BOX[0]) * scale)
    th = int((PITCHER_BOX[3] - PITCHER_BOX[1]) * scale) + 12
    made = {}
    for pid in read_json(pilot / "pilot_private.json")["pitches"]:
        frames = _sheet_frames(manifest, pid)
        _, ab, pn = pid.split(":")
        rows = (len(frames) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * tw, rows * th))
        draw = ImageDraw.Draw(sheet)
        for k, f in enumerate(frames):
            with Image.open(bundle / f"pa{ab}_p{pn}" / f"frame_{f['index']:06d}.jpg") as image:
                tile = image.crop(PITCHER_BOX).resize((tw, th - 12))
            x, y = (k % cols) * tw, (k // cols) * th
            sheet.paste(tile, (x, y + 12))
            draw.text((x + 2, y), f"{k:02d} {f['seconds_from_decision']:+.2f}", fill=(255, 255, 0))
        sheet.save(out / f"pa{ab}_p{pn}.jpg", quality=85)
        made[pid] = len(frames)
    return made


def delivery_annotation(bundle: Path, pilot: Path, marks, annotator):
    """Turn sheet positions read by an annotator into the delivery-start cut-off file."""
    manifest = read_json(bundle / "manifest.json")
    timing = {
        f"747139:{a['at_bat_number']}:{a['pitch_number']}": a
        for a in read_json(RESULTS / "game_747139_timing.json")["annotations"]
    }
    doc = {
        "schema": "pitcheezy-mitt-delivery-start-dev-v1",
        "definition": DELIVERY_DEFINITION,
        "uncertainty_seconds": 0.1,
        "annotator": annotator,
        "pitches": {},
    }
    for pid, position in sorted(marks.items()):
        f = _sheet_frames(manifest, pid)[position]
        seconds = float(Fraction(f["index"]) / FPS)
        doc["pitches"][pid] = {
            "sheet_position": position,
            "frame_index": f["index"],
            "delivery_start_seconds": seconds,
            "after_decision_s": round(seconds - timing[pid]["decision_seconds"], 3),
            "before_release_s": round(timing[pid]["release_seconds"] - seconds, 3),
        }
    (pilot / "delivery_start_v1.json").write_text(
        json.dumps(doc, indent=1) + "\n", encoding="utf-8"
    )
    return doc


def usage_summary(path: Path):
    """Per-call usage as the agent runner reported it (tokens, tool uses, wall time)."""
    if not path.is_file():
        return {"status": "unmeasured"}
    doc = read_json(path)
    calls = doc["calls"]
    tokens = sorted(v[0] for v in calls.values())
    seconds = sorted(v[2] / 1000 for v in calls.values())
    return {
        "basis": doc["basis"],
        "calls": len(calls),
        "tokens_total": sum(tokens),
        "tokens_per_call_median": statistics.median(tokens),
        "tokens_per_call_range": [tokens[0], tokens[-1]],
        "seconds_per_call_median": round(statistics.median(seconds), 1),
        "seconds_per_call_range": [round(seconds[0], 1), round(seconds[-1], 1)],
        "money": "not measured",
    }


def sensitivity(sequences, pitches, timing, delivery):
    """Pre-declared grid around dev-v1; reported to show fragility, not used to pick a winner."""
    out = []
    for cell in SENSITIVITY_GRID:
        params = {**mt.PARAMS_DEV_V1, **cell, "version": "sensitivity"}
        before, emitted = 0, []
        for pid in pitches:
            seq = sorted(sequences.get(pid, []), key=lambda o: o["frame_seconds"])
            summary = mt.summarize_pitch(
                seq,
                release_seconds=timing[pid]["release_seconds"],
                delivery_start_seconds=(delivery.get(pid) or {}).get("delivery_start_seconds"),
                params=params,
            )
            cand = summary["candidate_before_delivery_start"]
            if cand:
                before += 1
                emitted.append(cand["emitted_seconds"] - timing[pid]["decision_seconds"])
        out.append(
            {
                **cell,
                "candidate_before_delivery_start": before,
                "emitted_after_decision_s_median": round(statistics.median(emitted), 3)
                if emitted
                else None,
            }
        )
    return out


def _brief(candidate, timing, window_start=None):
    if not candidate:
        return None
    return {
        "segment_start_seconds": round(candidate["segment_start_seconds"], 3),
        "emitted_seconds": round(candidate["emitted_seconds"], 3),
        "emitted_after_decision_s": round(
            candidate["emitted_seconds"] - timing["decision_seconds"], 3
        ),
        "emitted_before_release_s": round(
            timing["release_seconds"] - candidate["emitted_seconds"], 3
        ),
        "point_px": candidate["point_px"],
        "frames_in_segment": candidate["frames_in_segment"],
        "spread_px": candidate["spread_px"],
        "left_censored": candidate.get("left_censored"),
        "segment_start_after_window_start_s": round(
            candidate["segment_start_seconds"] - window_start, 3
        )
        if window_start is not None
        else None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--bundle", type=Path, required=True)
    prep.add_argument("--out", type=Path, required=True)
    ev = sub.add_parser("evaluate")
    ev.add_argument("--pilot", type=Path, required=True)
    ev.add_argument("--out", type=Path, required=True)
    ev.add_argument("--delivery", type=Path)
    sh = sub.add_parser("delivery-sheets")
    sh.add_argument("--bundle", type=Path, required=True)
    sh.add_argument("--pilot", type=Path, required=True)
    an = sub.add_parser("delivery-annotation")
    an.add_argument("--bundle", type=Path, required=True)
    an.add_argument("--pilot", type=Path, required=True)
    an.add_argument(
        "--marks", required=True, help="pitch_id=sheet_position,... read off the sheets"
    )
    an.add_argument("--annotator", required=True)
    args = parser.parse_args(argv)
    if args.cmd == "delivery-sheets":
        print(json.dumps(delivery_sheets(args.bundle, args.pilot)))
        return
    if args.cmd == "delivery-annotation":
        marks = dict(item.split("=") for item in args.marks.split(","))
        doc = delivery_annotation(
            args.bundle, args.pilot, {k: int(v) for k, v in marks.items()}, args.annotator
        )
        print(json.dumps({k: v["delivery_start_seconds"] for k, v in doc["pitches"].items()}))
        return
    if args.cmd == "prepare":
        meta = prepare(args.bundle, args.out)
        print(
            json.dumps(
                {"batches": meta["batches"], "frames": meta["frames"], "pitches": meta["pitches"]}
            )
        )
    else:
        s = evaluate(args.pilot, args.out, args.delivery)
        print(json.dumps(s["old_vs_new_common_task"], ensure_ascii=False))


if __name__ == "__main__":
    main()
