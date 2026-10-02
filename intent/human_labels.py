"""Import a person's hand labels from the labeling pack and compare them with the assistant points.

    python -m intent.human_labels --game 747139 --labels <downloaded labels json>

Writes ``docs/results/mlb_p0/game_<game>_intent_human_labels_v0.json`` (the person's
coordinates, checked against the committed pack manifest) and
``game_<game>_intent_setup_check_v0.json`` (assistant vs person on the same decision frames):

- availability agreement: both marked, both abstained, only one marked;
- mitt pixel difference (assistant minus person) where both marked;
- the same difference in feet with both mitts mapped through the PERSON's plate front edge
  and the calibrated hop-2 matrix, which isolates the mitt reading;
- full-chain difference: assistant mitt through the assistant's own plate edge versus the
  person's mitt through the person's plate edge;
- output difference: the assistant's published ``plate_feet`` (the JSONL line) versus the
  person's mitt through the person's plate edge;
- plate front-edge end differences in pixels.

The game's role (development or evaluation) comes from
``docs/results/mlb_p0/intent_eval_plan_v0.json``. On a development game (747139, 849843) this
measures how well the assistant reads the setup mitt on frames the pipeline was built on, not a
held-out accuracy.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intent.geometry import front_edge_similarity, project_point  # noqa: E402
from intent.plate_feet import hop2_parameters, load_calibration, zone_to_plate_feet  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/results/mlb_p0"
LABELS_SCHEMA = "intent_human_labels_v0"
MITT_STATUSES = ("marked", "hidden", "not_in_setup", "not_centre_field")
PLATE_STATUSES = ("marked", "hidden")


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _mean(values):
    values = [float(v) for v in values]
    return sum(values) / len(values) if values else None


def _sd(values):
    values = [float(v) for v in values]
    if len(values) < 2:
        return None
    m = _mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))


def _rms(values):
    values = [float(v) for v in values]
    return math.sqrt(sum(v * v for v in values) / len(values)) if values else None


def _percentile(values, q):
    values = sorted(float(v) for v in values)
    if not values:
        return None
    index = min(len(values) - 1, max(0, math.ceil(q * len(values)) - 1))
    return values[index]


def _axis(values):
    n = len(values)
    sd = _sd(values)
    return {
        "n": n,
        "mean": _mean(values),
        "se_of_mean": sd / math.sqrt(n) if sd is not None else None,
        "sd": sd,
        "rms": _rms(values),
    }


def validate_labels(labels, manifest):
    """Check the downloaded labels against the committed pack manifest; return them cleaned."""
    if labels.get("schema") != LABELS_SCHEMA:
        raise ValueError("labels file schema is not intent_human_labels_v0")
    if labels.get("game_pk") != manifest["game_pk"] or labels.get("pack_id") != manifest["pack_id"]:
        raise ValueError("labels belong to another game or labeling pack")
    expected = {f["pitch_id"]: f for f in manifest["frames"]}
    rows = {}
    for row in labels.get("frames", []):
        pid = row.get("pitch_id")
        if pid not in expected:
            raise ValueError(f"labels contain a frame outside the pack: {pid}")
        if pid in rows:
            raise ValueError(f"duplicate label for {pid}")
        if row.get("image_sha256") != expected[pid]["image_sha256"]:
            raise ValueError(f"frame hash differs from the pack for {pid}")
        mitt_status, plate_status = row.get("mitt_status"), row.get("plate_status")
        if mitt_status is not None and mitt_status not in MITT_STATUSES:
            raise ValueError(f"unknown mitt_status for {pid}: {mitt_status}")
        if plate_status is not None and plate_status not in PLATE_STATUSES:
            raise ValueError(f"unknown plate_status for {pid}: {plate_status}")
        if (mitt_status == "marked") != (row.get("mitt") is not None):
            raise ValueError(f"mitt point and status disagree for {pid}")
        front = row.get("plate_front")
        if (plate_status == "marked") != bool(
            front and front.get("left_end") and front.get("right_end")
        ):
            raise ValueError(f"plate front edge and status disagree for {pid}")
        rows[pid] = {
            "pitch_id": pid,
            "frame_seconds": row.get("frame_seconds"),
            "image_sha256": row["image_sha256"],
            "mitt_status": mitt_status,
            "mitt": [float(v) for v in row["mitt"]] if row.get("mitt") else None,
            "plate_status": plate_status,
            "plate_front": {
                "left_end": [float(v) for v in front["left_end"]],
                "right_end": [float(v) for v in front["right_end"]],
            }
            if plate_status == "marked"
            else None,
        }
    return [rows[f["pitch_id"]] for f in manifest["frames"] if f["pitch_id"] in rows]


def _display_path(path):
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def game_role(game_pk, plan_path=None):
    """'development', 'evaluation' or 'unplanned' from the committed evaluation plan."""
    path = Path(plan_path) if plan_path else RESULTS / "intent_eval_plan_v0.json"
    if not path.is_file():
        return "unplanned"
    plan = _load(path)
    if any(g["game_pk"] == game_pk for g in plan["development_games"]):
        return "development"
    if any(g["game_pk"] == game_pk for g in plan["evaluation_games"]["games"]):
        return "evaluation"
    return "unplanned"


def _feet(plate_front, mitt, matrix):
    h, _ = front_edge_similarity(
        {"front_left": plate_front["left_end"], "front_right": plate_front["right_end"]}
    )
    return zone_to_plate_feet(project_point(h, mitt), matrix)


def compare(human_rows, points, calibration, records=None):
    """Assistant vs person on the labeled frames; ``records`` = JSONL lines by pitch_id."""
    records = records or {}
    matrix = hop2_parameters(calibration)["matrix"]
    by_id = {
        f"{points['game_pk']}:{f['at_bat_number']}:{f['pitch_number']}": f for f in points["frames"]
    }
    per_frame, availability = (
        [],
        {
            "both_marked": 0,
            "both_abstained": 0,
            "assistant_only": 0,
            "person_only": 0,
            "person_undecided": 0,
        },
    )
    px_dx, px_dy, px_d, ft_dx, ft_dz, chain_dx, chain_dz, plate_d = [], [], [], [], [], [], [], []
    out_dx, out_dz, out_d = [], [], []
    for row in human_rows:
        a = by_id[row["pitch_id"]]
        a_marked = a["status"] == "estimated" and a.get("mitt_center") is not None
        h_marked = row["mitt_status"] == "marked"
        entry = {
            "pitch_id": row["pitch_id"],
            "assistant_status": a["status"],
            "assistant_reason": a.get("unavailable_reason"),
            "person_status": row["mitt_status"],
        }
        if row["mitt_status"] is None:
            availability["person_undecided"] += 1
        elif a_marked and h_marked:
            availability["both_marked"] += 1
        elif not a_marked and not h_marked:
            availability["both_abstained"] += 1
        elif a_marked:
            availability["assistant_only"] += 1
        else:
            availability["person_only"] += 1
        if a_marked and h_marked:
            dx = a["mitt_center"][0] - row["mitt"][0]
            dy = a["mitt_center"][1] - row["mitt"][1]
            px_dx.append(dx)
            px_dy.append(dy)
            px_d.append(math.hypot(dx, dy))
            entry["mitt_px_diff"] = [round(dx, 2), round(dy, 2)]
            if row["plate_status"] == "marked":
                ax, az = _feet(row["plate_front"], a["mitt_center"], matrix)
                hx, hz = _feet(row["plate_front"], row["mitt"], matrix)
                ft_dx.append(ax - hx)
                ft_dz.append(az - hz)
                entry["mitt_feet_diff_same_plate"] = [round(ax - hx, 4), round(az - hz, 4)]
                corners = a.get("plate_corners") or {}
                if corners.get("front_left") and corners.get("front_right"):
                    own = {"left_end": corners["front_left"], "right_end": corners["front_right"]}
                    cx, cz = _feet(own, a["mitt_center"], matrix)
                    chain_dx.append(cx - hx)
                    chain_dz.append(cz - hz)
                    entry["full_chain_feet_diff"] = [round(cx - hx, 4), round(cz - hz, 4)]
                published = ((records.get(row["pitch_id"]) or {}).get("points") or {}).get(
                    "plate_feet"
                )
                if published:
                    ox, oz = published["x"] - hx, published["z"] - hz
                    out_dx.append(ox)
                    out_dz.append(oz)
                    out_d.append(math.hypot(ox, oz))
                    entry["output_feet_diff"] = [round(ox, 4), round(oz, 4)]
        corners = a.get("plate_corners") or {}
        if row["plate_status"] == "marked" and corners.get("front_left"):
            dl = math.dist(corners["front_left"], row["plate_front"]["left_end"])
            dr = math.dist(corners["front_right"], row["plate_front"]["right_end"])
            plate_d.extend([dl, dr])
            entry["plate_end_px_diff"] = [round(dl, 2), round(dr, 2)]
        per_frame.append(entry)
    return {
        "frames_labeled": len(human_rows),
        "availability": availability,
        "mitt_pixels": {
            "n": len(px_d),
            "distance_median": _percentile(px_d, 0.5),
            "distance_p90": _percentile(px_d, 0.9),
            "distance_rms": _rms(px_d),
            "dx_assistant_minus_person": _axis(px_dx),
            "dy_assistant_minus_person": _axis(px_dy),
        },
        "mitt_feet_same_plate": {"x": _axis(ft_dx), "z": _axis(ft_dz)},
        "full_chain_feet": {"x": _axis(chain_dx), "z": _axis(chain_dz)},
        "output_feet": {
            "x": _axis(out_dx),
            "z": _axis(out_dz),
            "abs_x_median": _percentile([abs(v) for v in out_dx], 0.5),
            "abs_x_p90": _percentile([abs(v) for v in out_dx], 0.9),
            "abs_z_median": _percentile([abs(v) for v in out_dz], 0.5),
            "abs_z_p90": _percentile([abs(v) for v in out_dz], 0.9),
            "distance_median": _percentile(out_d, 0.5),
            "distance_p90": _percentile(out_d, 0.9),
        },
        "plate_front_end_pixels": {
            "n_ends": len(plate_d),
            "median": _percentile(plate_d, 0.5),
            "rms": _rms(plate_d),
        },
        "per_frame": per_frame,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--game", type=int, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--points", type=Path, default=None)
    parser.add_argument("--calibration", type=Path, default=None)
    parser.add_argument("--out-labels", type=Path, default=None)
    parser.add_argument("--out-report", type=Path, default=None)
    parser.add_argument("--jsonl", type=Path, default=None)
    args = parser.parse_args(argv)
    manifest = _load(args.manifest or RESULTS / f"game_{args.game}_intent_label_pack_v0.json")
    labels = _load(args.labels)
    rows = validate_labels(labels, manifest)
    points = _load(args.points or RESULTS / f"game_{args.game}_intent_points_v0.json")
    calibration = load_calibration(
        args.calibration or RESULTS / f"game_{args.game}_intent_plate_calibration_v0.json"
    )
    jsonl = args.jsonl or RESULTS / f"game_{args.game}_intent_v0.jsonl"
    records = {}
    if jsonl.is_file():
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                records[rec["pitch_id"]] = rec
    report = compare(rows, points, calibration, records)
    role = game_role(args.game)
    stored = {
        "schema": LABELS_SCHEMA,
        "game_pk": args.game,
        "pack_id": manifest["pack_id"],
        "labeler": labels.get("labeler"),
        "exported_at": labels.get("exported_at"),
        "elapsed_seconds": labels.get("elapsed_seconds"),
        "label_source": "human_manual_annotation",
        "frames": rows,
    }
    out_labels = args.out_labels or RESULTS / f"game_{args.game}_intent_human_labels_v0.json"
    out_labels.write_text(json.dumps(stored, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    full = {
        "schema": "intent_setup_check_v0",
        "game_pk": args.game,
        "pack_id": manifest["pack_id"],
        "role": role,
        "scope": f"{role} game: assistant setup-frame readings vs one person's hand labels on "
        "the same frames" + ("; not a held-out accuracy" if role != "evaluation" else ""),
        "jsonl": _display_path(jsonl) if records else None,
        "labeler": labels.get("labeler"),
        "elapsed_seconds": labels.get("elapsed_seconds"),
        **report,
    }
    out_report = args.out_report or RESULTS / f"game_{args.game}_intent_setup_check_v0.json"
    out_report.write_text(
        json.dumps(full, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in full.items() if k != "per_frame"}, ensure_ascii=False, indent=1
        )
    )


if __name__ == "__main__":
    main()
