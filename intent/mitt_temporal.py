"""CV-33 development: frame observation (A), causal temporal target candidate (B), conversion (C).

The three layers stay separate and each has its own success:

* A, one record per frame (``pitcheezy-mitt-frame-observation-dev-v1``): view, catcher posture,
  mitt visibility, occluder, mitt centre in pixels, and a pitcher phase. A low mitt is only a
  coordinate; A never says "resting" or "presented".
* B, a causal state machine over A in frame-time order. At frame t it uses only records with
  frame time <= t. It labels the step (held / raising / lowering / moving / unclear) and emits a
  *target-presentation candidate* when one usable held segment has lasted ``min_hold_seconds``.
  A candidate is a moment the mitt was held still while the catcher was set; it is not the
  pitcher's intent and not a verified target.
* C, pixels to front-edge units only from a plate front edge read on a frame at or before the
  candidate time inside the same uninterrupted live view. No feet, height or nine zones here.

The selector never receives release time or pitch outcome; ``summarize_pitch`` applies those
afterwards for evaluation only. ``run`` is prefix invariant: records for the first k frames do
not change when later frames are appended (tested).
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics

OBS_SCHEMA = "pitcheezy-mitt-frame-observation-dev-v1"
CANDIDATE_SCHEMA = "pitcheezy-mitt-temporal-candidate-dev-v1"

VIEWS = {"live_centre_field", "other_view", "replay", "graphic_or_transition", "unknown"}
CATCHER = {"set", "not_set", "not_visible", "unknown"}
VISIBILITY = {"full", "partial", "hidden", "out_of_view", "unknown"}
OCCLUDERS = {None, "batter", "umpire", "catcher_body", "pitcher", "motion_blur", "graphic", "other"}
PITCHER_PHASE = {"before_delivery", "delivery", "after_release", "not_visible", "unknown"}

# Development thresholds (720p broadcast pixels). Chosen on development data only; a copy is
# frozen with its SHA before any independent evaluation and must not change afterwards.
PARAMS_DEV_V1 = {
    "version": "dev-v1",
    "hold_radius_px": 8.0,
    "min_hold_seconds": 0.30,
    "move_px": 10.0,
    "max_gap_seconds": 0.25,
}


def params_sha256(params) -> str:
    return hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()


def validate_observation(obs) -> None:
    required = {
        "pitch_id",
        "frame_index",
        "frame_seconds",
        "view",
        "catcher",
        "mitt_visibility",
        "occluder",
        "mitt_center_px",
        "pitcher_phase",
    }
    missing = required - set(obs)
    if missing:
        raise ValueError(f"observation missing {sorted(missing)}")
    for field, allowed in (
        ("view", VIEWS),
        ("catcher", CATCHER),
        ("mitt_visibility", VISIBILITY),
        ("occluder", OCCLUDERS),
        ("pitcher_phase", PITCHER_PHASE),
    ):
        if obs[field] not in allowed:
            raise ValueError(f"{field}={obs[field]!r} not allowed")
    centre = obs["mitt_center_px"]
    if centre is not None:
        if len(centre) != 2 or not all(
            isinstance(v, (int, float)) and math.isfinite(v) for v in centre
        ):
            raise ValueError("mitt_center_px must be [x, y] or null")
        if obs["mitt_visibility"] not in ("full", "partial"):
            raise ValueError("a centre needs full or partial visibility")
    for key in ("resting", "presented", "target", "intent"):
        if key in obs:
            raise ValueError(f"layer A does not carry {key!r}")


def unusable_reason(obs):
    if obs["view"] != "live_centre_field":
        return "view_not_live_centre_field"
    if obs["catcher"] != "set":
        return "catcher_not_set" if obs["catcher"] == "not_set" else "catcher_unknown"
    if obs["mitt_visibility"] not in ("full", "partial"):
        return f"mitt_{obs['mitt_visibility']}"
    if obs["mitt_center_px"] is None:
        return "no_centre"
    return None


def run(observations, params=PARAMS_DEV_V1):
    """Per-frame causal records. ``observations`` must be one pitch in increasing frame time."""
    records, segment, previous, candidates = [], [], None, []
    last_time, censored = None, False
    for obs in observations:
        validate_observation(obs)
        t = obs["frame_seconds"]
        if last_time is not None and t <= last_time:
            raise ValueError("observations must be in strictly increasing frame time")
        last_time = t
        reason = unusable_reason(obs)
        state, event = None, None
        if (
            reason is None
            and previous is not None
            and t - previous["frame_seconds"] > params["max_gap_seconds"]
        ):
            segment = []
            previous = None
            reason_gap = "gap_before"
        else:
            reason_gap = None
        if reason is not None:
            state = f"unclear:{reason}"
            segment, previous = [], None
        else:
            x, y = obs["mitt_center_px"]
            if previous is None:
                step = "start"
            else:
                px, py = previous["mitt_center_px"]
                dx, dy = x - px, y - py
                if abs(dy) >= params["move_px"] and abs(dy) >= abs(dx):
                    step = "raising" if dy < 0 else "lowering"
                elif math.hypot(dx, dy) >= params["move_px"]:
                    step = "moving"
                else:
                    step = "still"
            anchor = segment[0]["mitt_center_px"] if segment else None
            if anchor is None or math.dist(anchor, (x, y)) > params["hold_radius_px"]:
                # a segment that starts with no usable frame before it may have begun earlier
                censored = previous is None
                segment = [obs]
            else:
                segment.append(obs)
            held_for = t - segment[0]["frame_seconds"]
            if len(segment) > 1 and held_for + 1e-9 >= params["min_hold_seconds"]:
                state = "held"
                if (
                    not candidates
                    or candidates[-1]["segment_start_frame"] != segment[0]["frame_index"]
                ):
                    xs = [s["mitt_center_px"][0] for s in segment]
                    ys = [s["mitt_center_px"][1] for s in segment]
                    event = {
                        "segment_start_frame": segment[0]["frame_index"],
                        "segment_start_seconds": segment[0]["frame_seconds"],
                        "emitted_frame": obs["frame_index"],
                        "emitted_seconds": t,
                        "point_px": [statistics.median(xs), statistics.median(ys)],
                        "frames_in_segment": len(segment),
                        "spread_px": round(
                            max(
                                math.dist(segment[0]["mitt_center_px"], s["mitt_center_px"])
                                for s in segment
                            ),
                            2,
                        ),
                        "reason": "held_within_radius_for_min_seconds",
                        "left_censored": censored,
                    }
                    candidates.append(event)
            else:
                state = step if step != "start" else "unclear:segment_start"
            if reason_gap:
                state = f"{state}|after_gap"
            previous = obs
        records.append(
            {
                "frame_index": obs["frame_index"],
                "frame_seconds": t,
                "state": state,
                "pitcher_phase": obs["pitcher_phase"],
                "event": event,
                "current_candidate": dict(candidates[-1]) if candidates else None,
                "candidates_so_far": len(candidates),
            }
        )
    return records


def first_phase_time(observations, phase):
    """Frame time of the first observation reporting ``phase``; causal (no later frame used)."""
    return next((o["frame_seconds"] for o in observations if o["pitcher_phase"] == phase), None)


def candidate_before(records, cutoff_seconds):
    """The current candidate at the last record strictly before the cutoff, or None."""
    if cutoff_seconds is None:
        return None
    before = [r for r in records if r["frame_seconds"] < cutoff_seconds]
    return before[-1]["current_candidate"] if before else None


def front_edge_units(point_px, plate_front):
    """Pixels -> front-edge units (u along the edge, v up from it) from one frame's edge only."""
    from intent.geometry import front_edge_similarity, project_point

    h, _ = front_edge_similarity(
        {"front_left": plate_front["left_end"], "front_right": plate_front["right_end"]}
    )
    u, v = project_point(h, point_px)
    return [round(float(u), 4), round(float(v), 4)]


def convert(candidate, observations):
    """Layer C for one candidate: latest plate edge at or before emission within the same live run."""
    if candidate is None:
        return {"status": "no_candidate"}
    plate = None
    for obs in observations:
        if obs["frame_seconds"] > candidate["emitted_seconds"]:
            break
        if obs["view"] != "live_centre_field":
            plate = None  # a cut or other view breaks the same-shot assumption
            continue
        if obs.get("plate_front"):
            plate = (obs["frame_index"], obs["plate_front"])
    if plate is None:
        return {"status": "pixels_only", "reason": "no_plate_front_edge_in_same_live_run"}
    return {
        "status": "front_edge_units",
        "plate_frame": plate[0],
        "uv": front_edge_units(candidate["point_px"], plate[1]),
        "units": "front-edge widths; u 0..1 across the 17-inch edge, v up from the edge line",
        "not_claimed": ["feet", "height", "nine zones", "strike-zone location"],
    }


def summarize_pitch(
    observations, release_seconds=None, delivery_start_seconds=None, params=PARAMS_DEV_V1
):
    """Post-hoc evaluation view of one pitch. Release and delivery start are used here only.

    ``delivery_start_seconds`` is an after-the-fact annotation when given; otherwise the first
    frame whose layer-A pitcher phase is "delivery" is used and the source says so.
    """
    records = run(observations, params)
    if delivery_start_seconds is not None:
        delivery, delivery_source = delivery_start_seconds, "posthoc_annotation"
    else:
        delivery = first_phase_time(observations, "delivery")
        delivery_source = "layer_a_pitcher_phase" if delivery is not None else None
    before_delivery = candidate_before(records, delivery)
    before_release = candidate_before(records, release_seconds)
    why_delivery = None if before_delivery else why_none_before(records, delivery)
    why_release = None if before_release else why_none_before(records, release_seconds)
    states = {}
    for r in records:
        key = r["state"].split("|")[0].split(":")[0]
        states[key] = states.get(key, 0) + 1
    unclear = {}
    for r in records:
        if r["state"].startswith("unclear:"):
            reason = r["state"].split("|")[0].split(":", 1)[1]
            unclear[reason] = unclear.get(reason, 0) + 1
    return {
        "schema": CANDIDATE_SCHEMA,
        "pitch_id": observations[0]["pitch_id"] if observations else None,
        "params_version": params["version"],
        "params_sha256": params_sha256(params),
        "frames": len(records),
        "state_counts": states,
        "unclear_reasons": unclear,
        "candidates": sum(1 for r in records if r["event"]),
        "delivery_start_seconds": delivery,
        "delivery_start_source": delivery_source,
        "candidate_before_delivery_start": before_delivery,
        "candidate_before_release": before_release,
        "conversion_before_delivery_start": convert(before_delivery, observations),
        "release_seconds_posthoc": release_seconds,
        "undeterminable_before_delivery_start": why_delivery,
        "undeterminable_before_release": why_release,
        "undeterminable_reason": why_release,
    }


def why_none_before(records, cutoff_seconds):
    """Why no candidate exists before a cut-off, from the records before that cut-off only."""
    if cutoff_seconds is None:
        return "no_cutoff"
    prefix = [r for r in records if r["frame_seconds"] < cutoff_seconds]
    if not prefix:
        return "no_observations_before_cutoff"
    unclear = {}
    for r in prefix:
        if r["state"].startswith("unclear:"):
            reason = r["state"].split("|")[0].split(":", 1)[1]
            unclear[reason] = unclear.get(reason, 0) + 1
    if unclear and sum(unclear.values()) == len(prefix):
        return "no_usable_frame:" + max(unclear, key=unclear.get)
    return "no_held_segment_reached_min_hold"
