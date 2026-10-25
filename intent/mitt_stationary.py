"""Causal geometric stationarity of a tracked patch; never a verified mitt or target.

Consumes one PatchTracker stream in source pixel coordinates. No image, release time,
outcome, future label or coordinate conversion is used. Old temporal/AI observations are
not rewritten. A stationary wrong seed is still a wrong seed. Source resolution and any
current external view gate are the caller's responsibility (development defaults: 720p).
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import asdict, dataclass


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


@dataclass(frozen=True)
class StationaryParams:
    """Predeclared development thresholds, not tuned against the saved replay."""

    max_diameter_px: float = 8.0
    min_hold_seconds: float = 0.30
    min_observations: int = 4
    min_continuity: int = 2
    max_gap_seconds: float = 0.25

    def __post_init__(self):
        for name in ("max_diameter_px", "min_hold_seconds", "max_gap_seconds"):
            value = getattr(self, name)
            if not _number(value) or value <= 0:
                raise ValueError(f"invalid {name}")
        if type(self.min_observations) is not int or self.min_observations < 2:
            raise ValueError("min_observations must be an integer >= 2")
        if (
            type(self.min_continuity) is not int
            or not 1 <= self.min_continuity < self.min_observations
        ):
            raise ValueError("min_continuity must be positive and below min_observations")

    def digest(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


class StationarySelector:
    """One tracker stream, with constant-memory segment bounds and immutable snapshots.

    Loss is terminal for this stream. A false external gate clears the geometric segment,
    but cannot resurrect a lost tracker. A later true gate needs fresh stationary support.
    Bounds cover the ENTIRE segment: slow accumulated drift cannot move the anchor forever.
    The diagonal of an axis-aligned bounding box is a conservative diameter upper bound.
    """

    def __init__(self, params=None):
        self._params = StationaryParams() if params is None else params
        if not isinstance(self.params, StationaryParams):
            raise ValueError("params must be StationaryParams")
        self._digest = self.params.digest()
        self._pitch = self._index = self._time = None
        self._tracker_state = "unseeded"
        self._segment = self._history = None

    @property
    def params(self):
        """The parameter object cannot be rebound while its evidence digest stays fixed."""
        return self._params

    def _validate(self, row, usable):
        if not isinstance(row, dict) or type(usable) is not bool:
            raise ValueError("row must be a dict and usable must be bool")
        required = {
            "pitch_id",
            "frame_index",
            "frame_seconds",
            "state",
            "reason",
            "point_px",
            "mitt_identity",
        }
        if not required <= row.keys():
            raise ValueError("missing tracker fields")
        pitch, index, seconds = row["pitch_id"], row["frame_index"], row["frame_seconds"]
        if not isinstance(pitch, str) or not pitch.strip():
            raise ValueError("pitch_id required")
        if self._pitch is not None and pitch != self._pitch:
            raise ValueError("one selector cannot cross pitch_id")
        if type(index) is not int or index < 0 or not _number(seconds) or seconds < 0:
            raise ValueError("invalid frame index or seconds")
        if self._time is not None and (seconds <= self._time or index <= self._index):
            raise ValueError("frame index and time must strictly increase")
        state, reason, point = row["state"], row["reason"], row["point_px"]
        if not isinstance(state, str) or state not in ("unseeded", "tracking", "lost"):
            raise ValueError("invalid tracker state")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason required")
        if row["mitt_identity"] != "unverified":
            raise ValueError("tracker rows do not verify mitt identity")
        if state == "tracking":
            if (
                not isinstance(point, (list, tuple))
                or len(point) != 2
                or not all(_number(v) and v >= 0 for v in point)
                or reason not in ("external_seed", "patch_continuity")
            ):
                raise ValueError("tracking requires a finite point and valid tracking reason")
            expected = "external_seed" if self._tracker_state == "unseeded" else "patch_continuity"
            if self._tracker_state == "lost" or reason != expected:
                raise ValueError("no implicit initialization or reseeding")
        elif point is not None:
            raise ValueError("inactive tracking must not carry a point")
        elif state == "unseeded":
            if self._tracker_state != "unseeded" or reason not in ("no_seed", "external_view_gate"):
                raise ValueError("invalid unseeded state")
        elif reason in ("external_seed", "patch_continuity", "no_seed"):
            raise ValueError("invalid loss reason")
        if self._tracker_state == "lost" and state != "lost":
            raise ValueError("lost tracker is terminal")

    def step(self, row, *, usable=True):
        """Validate fully before mutation; return an independent JSON-safe snapshot."""
        self._validate(row, usable)
        t, index, point = row["frame_seconds"], row["frame_index"], row["point_px"]
        gap = self._time is not None and t - self._time > self.params.max_gap_seconds
        self._pitch, self._index, self._time = row["pitch_id"], index, t
        self._tracker_state = row["state"]
        current = event = None
        visible_point = None
        if row["state"] != "tracking" or not usable:
            self._segment = None
            selection_state = "unavailable"
            reason = "external_view_gate" if not usable else row["reason"]
        else:
            visible_point = list(point)
            reason = "collecting_support"
            if gap:
                self._segment = None
                reason = "gap_restart"
            if self._segment is not None:
                bounds = self._bounds(self._segment["bounds"], point)
                if self._diameter(bounds) > self.params.max_diameter_px:
                    self._segment = None
                    reason = "motion_restart"
            if self._segment is None:
                self._segment = {
                    "bounds": [point[0], point[1], point[0], point[1]],
                    "start_frame": index,
                    "start_seconds": t,
                    "observations": 0,
                    "continuity": 0,
                    "available_frame": None,
                    "available_seconds": None,
                }
            segment = self._segment
            segment["bounds"] = self._bounds(segment["bounds"], point)
            segment["observations"] += 1
            segment["continuity"] += row["reason"] == "patch_continuity"
            span = t - segment["start_seconds"]
            # Absolute seconds in long videos suffer subtraction rounding. 1ns is numerical
            # tolerance only; no frame is backdated to the start of a successful segment.
            qualified = (
                span + 1e-9 >= self.params.min_hold_seconds
                and segment["observations"] >= self.params.min_observations
                and segment["continuity"] >= self.params.min_continuity
            )
            selection_state = "stationary" if qualified else "warming"
            if qualified:
                first = segment["available_frame"] is None
                if first:
                    segment["available_frame"], segment["available_seconds"] = index, t
                current = {
                    "candidate_id": f"{self._pitch}:{segment['available_frame']}",
                    "pitch_id": self._pitch,
                    "frame_index": index,
                    "frame_seconds": t,
                    "point_px": list(point),
                    "segment_start_frame": segment["start_frame"],
                    "segment_start_seconds": segment["start_seconds"],
                    "available_frame": segment["available_frame"],
                    "available_seconds": segment["available_seconds"],
                    "observations": segment["observations"],
                    "continuity_observations": segment["continuity"],
                    "span_seconds": span,
                    "diameter_px": self._diameter(segment["bounds"]),
                    "mitt_identity": "unverified",
                    "params_sha256": self._digest,
                }
                reason = "geometric_stationary_patch"
                if first:
                    event = copy.deepcopy(current)
                    self._history = copy.deepcopy(event)
        return {
            "schema": "pitcheezy-tracked-stationary-candidate-dev-v1",
            "pitch_id": self._pitch,
            "frame_index": index,
            "frame_seconds": t,
            "tracker_state": self._tracker_state,
            "selection_state": selection_state,
            "reason": reason,
            "current_track_point_px": visible_point,
            "current_candidate": current,
            "event": event,
            "last_historical_candidate": copy.deepcopy(self._history),
            "mitt_identity": "unverified",
            "params_sha256": self._digest,
        }

    @staticmethod
    def _bounds(bounds, point):
        return [
            min(bounds[0], point[0]),
            min(bounds[1], point[1]),
            max(bounds[2], point[0]),
            max(bounds[3], point[1]),
        ]

    @staticmethod
    def _diameter(bounds):
        return math.hypot(bounds[2] - bounds[0], bounds[3] - bounds[1])
