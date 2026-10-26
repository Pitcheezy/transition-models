"""Qualify one saved-observation seed per pitch using only the current prefix.

This exposed-development rule checks AI-reported input support, not mitt identity. A
consistently misidentified object can pass. Frame-time causality does not establish online
availability: the saved observations do not include their real arrival times.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math

from intent.mitt_temporal import CATCHER, OBS_SCHEMA, OCCLUDERS, PITCHER_PHASE, VIEWS, VISIBILITY

POLICY = {
    "version": "seed-gate-dev-v1",
    "view": "live_centre_field",
    "catcher": "set",
    "mitt_visibility": "full",
    "occluder": None,
    "pitcher_phase": "before_delivery",
    "max_uncertainty_px": 10.0,
    "min_observations": 3,
    "max_gap_seconds": 0.25,
    "min_span_seconds": 0.30,
    "max_diameter_px": 8.0,
    "source_width": 1280,
    "source_height": 720,
}
POLICY_SHA256 = "a6a1022497f31bf80251fe240a07bc4d80d26b81b0500f0cda3c7622eee90581"
SCHEMA = "pitcheezy-mitt-seed-gate-dev-v1"
MAX_SAFE_INTEGER = 2**53 - 1
# Roundoff tolerance for subtracting saved floating-point timestamps, not a policy margin.
TIME_EPSILON = 1e-9
OBS_REQUIRED = {
    "pitch_id",
    "frame_index",
    "frame_seconds",
    "view",
    "catcher",
    "mitt_visibility",
    "occluder",
    "mitt_center_px",
    "pitcher_phase",
    "uncertainty_px",
}
OBS_ALLOWED = OBS_REQUIRED | {"schema", "plate_front"}


def _finite(value):
    return type(value) in (int, float) and abs(value) <= MAX_SAFE_INTEGER and math.isfinite(value)


def _frame_key(pitch_id, frame_index, frame_seconds):
    if not isinstance(pitch_id, str) or not pitch_id.strip():
        raise ValueError("pitch_id must be a nonempty string")
    if type(frame_index) is not int or not 0 <= frame_index <= MAX_SAFE_INTEGER:
        raise ValueError("frame_index must be a nonnegative safe integer")
    if not _finite(frame_seconds) or frame_seconds < 0:
        raise ValueError("frame_seconds must be finite and nonnegative")


class SeedGate:
    """A fixed-policy gate, reset at each new pitch and never re-entering a finished pitch.

    Invalid inputs raise before state mutation, so a corrected input can be retried at the
    same frame. An eligible current observation starts fresh support after a gap or excessive
    accumulated motion. Missing observations never add support or emit a seed.
    """

    def __init__(self):
        digest = hashlib.sha256(json.dumps(POLICY, sort_keys=True).encode()).hexdigest()
        if digest != POLICY_SHA256:
            raise ValueError("the frozen development policy was modified")
        self._policy = copy.deepcopy(POLICY)
        self._seen = set()
        self._pitch = self._index = self._seconds = None
        self._seeded = False
        self._support = []
        self._bounds = None

    def _validate(self, pitch_id, frame_index, frame_seconds, observation):
        _frame_key(pitch_id, frame_index, frame_seconds)
        if pitch_id == self._pitch:
            if frame_index <= self._index or frame_seconds <= self._seconds:
                raise ValueError("frame index and time must strictly increase within a pitch")
        elif pitch_id in self._seen:
            raise ValueError("a completed pitch cannot be re-entered")
        if observation is None:
            return
        if (
            not isinstance(observation, dict)
            or not OBS_REQUIRED <= observation.keys()
            or not observation.keys() <= OBS_ALLOWED
        ):
            raise ValueError("invalid saved-observation fields")
        _frame_key(
            observation["pitch_id"], observation["frame_index"], observation["frame_seconds"]
        )
        if (
            observation["pitch_id"] != pitch_id
            or observation["frame_index"] != frame_index
            or observation["frame_seconds"] != frame_seconds
        ):
            raise ValueError("observation must belong to the exact current frame")
        if "schema" in observation and observation["schema"] != OBS_SCHEMA:
            raise ValueError("unsupported observation schema")
        for name, allowed in (
            ("view", VIEWS),
            ("catcher", CATCHER),
            ("mitt_visibility", VISIBILITY),
            ("pitcher_phase", PITCHER_PHASE),
        ):
            if not isinstance(observation[name], str) or observation[name] not in allowed:
                raise ValueError(f"invalid observation {name}")
        occluder = observation["occluder"]
        if occluder is not None and (not isinstance(occluder, str) or occluder not in OCCLUDERS):
            raise ValueError("invalid observation occluder")
        point = observation["mitt_center_px"]
        if point is not None and (
            not isinstance(point, (list, tuple))
            or len(point) != 2
            or not all(_finite(value) for value in point)
            or not 0 <= point[0] < self._policy["source_width"]
            or not 0 <= point[1] < self._policy["source_height"]
        ):
            raise ValueError("centre must be a finite point inside the source image")
        uncertainty = observation["uncertainty_px"]
        if uncertainty is not None and (not _finite(uncertainty) or uncertainty < 0):
            raise ValueError("uncertainty must be finite and nonnegative, or unavailable")

    def _ineligible_reason(self, observation):
        for field, reason in (
            ("view", "view_not_live_centre_field"),
            ("catcher", "catcher_not_set"),
            ("mitt_visibility", "mitt_not_full"),
            ("occluder", "occluded"),
            ("pitcher_phase", "pitcher_not_before_delivery"),
        ):
            if observation[field] != self._policy[field]:
                return reason
        if observation["mitt_center_px"] is None:
            return "no_centre"
        uncertainty = observation["uncertainty_px"]
        if uncertainty is None:
            return "uncertainty_unavailable"
        if uncertainty > self._policy["max_uncertainty_px"]:
            return "uncertainty_exceeds_limit"
        return None

    def _clear_support(self):
        self._support, self._bounds = [], None

    def _snapshot(self, reason, seed=None):
        return {
            "schema": SCHEMA,
            "pitch_id": self._pitch,
            "frame_index": self._index,
            "frame_seconds": self._seconds,
            "state": "seeded" if self._seeded else "collecting" if self._support else "waiting",
            "reason": reason,
            "seed": copy.deepcopy(seed),
            "support_keys": copy.deepcopy(self._support),
            "mitt_identity": "unverified",
            "policy_sha256": POLICY_SHA256,
        }

    def update(self, pitch_id, frame_index, frame_seconds, observation=None):
        """Consume the current frame, emitting a seed event at most once for this pitch."""
        self._validate(pitch_id, frame_index, frame_seconds, observation)
        if pitch_id != self._pitch:
            self._seen.add(pitch_id)
            self._pitch, self._seeded = pitch_id, False
            self._clear_support()
        self._index, self._seconds = frame_index, frame_seconds
        if self._seeded:
            return self._snapshot("already_seeded")

        gap = bool(
            self._support
            and frame_seconds - self._support[-1]["frame_seconds"]
            > self._policy["max_gap_seconds"] + TIME_EPSILON
        )
        if gap:
            self._clear_support()
        if observation is None:
            return self._snapshot("gap_expired" if gap else "no_saved_observation")
        reason = self._ineligible_reason(observation)
        if reason is not None:
            self._clear_support()
            return self._snapshot(reason)

        x, y = observation["mitt_center_px"]
        bounds = (
            [x, y, x, y]
            if self._bounds is None
            else [
                min(x, self._bounds[0]),
                min(y, self._bounds[1]),
                max(x, self._bounds[2]),
                max(y, self._bounds[3]),
            ]
        )
        reason = "gap_restart" if gap else "collecting_support"
        if (
            math.hypot(bounds[2] - bounds[0], bounds[3] - bounds[1])
            > self._policy["max_diameter_px"]
        ):
            self._clear_support()
            bounds, reason = [x, y, x, y], "movement_restart"
        self._bounds = bounds
        self._support.append(
            {
                "pitch_id": pitch_id,
                "frame_index": frame_index,
                "frame_seconds": frame_seconds,
            }
        )
        span = frame_seconds - self._support[0]["frame_seconds"]
        if (
            len(self._support) >= self._policy["min_observations"]
            and span + TIME_EPSILON >= self._policy["min_span_seconds"]
        ):
            self._seeded = True
            return self._snapshot(
                "seed_qualified",
                {
                    "frame_index": frame_index,
                    "frame_seconds": frame_seconds,
                    "point_px": [x, y],
                    "support_keys": self._support,
                },
            )
        return self._snapshot(reason)
