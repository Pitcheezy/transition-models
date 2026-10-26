"""Limited causal re-search after a patch-tracking loss; still not mitt recognition.

Research baseline kept apart from PatchTracker and StationarySelector, whose default behaviour
is unchanged. After a confirmed tracking segment is lost, the last confirmed patch is searched
around the last confirmed point for a bounded number of frames with the ordinary acceptance
thresholds. A match is only a *candidate*: it becomes a new tracking segment when the next frame
passes the ordinary continuity checks, forward-backward check included. No future frame, release
annotation or outcome is used, a lost segment never keeps showing its last point, stationary
support never crosses a loss, and a geometric re-match never verifies that the patch is a mitt.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace

import numpy as np
import torch
import torch.nn.functional as F

from intent.mitt_stationary import StationaryParams, StationarySelector
from intent.mitt_tracking import PatchTracker, TrackParams, match_template

STATES = ("unseeded", "tracking", "reacquire_search", "reacquire_candidate", "lost")
SEGMENT_START_REASONS = ("external_seed", "reacquired_continuity")
# A gated, broken or cut frame stream ends the pitch: the last confirmed patch is not searched.
TERMINAL_LOSSES = ("external_view_gate", "time_gap", "appearance_discontinuity")
ROW_KEYS = (
    "pitch_id",
    "frame_index",
    "frame_seconds",
    "state",
    "reason",
    "point_px",
    "reacquire_candidate_px",
    "segment_id",
    "segment_end_reason",
    "reacquisitions",
    "mitt_identity",
)


def _number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _point(value):
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(_number(v) and v >= 0 for v in value)
    )


@dataclass(frozen=True)
class ReacquireParams:
    """Fixed before the saved-frame comparison; acceptance thresholds stay in TrackParams.

    ``max_attempt_frames`` counts search frames per loss, the loss frame itself being the
    first. A candidate found on the last search frame is still checked on the following frame.
    """

    max_attempt_frames: int = 5
    search_radius: int = 32
    max_reacquisitions: int = 3

    def __post_init__(self):
        for key, value in asdict(self).items():
            if type(value) is not int or value < 1:
                raise ValueError(f"invalid {key}")

    def digest(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


def _tensor(image, device):
    return torch.as_tensor(np.ascontiguousarray(image), device=device).float()[None, None] / 255.0


def _appearance_change(current, reference):
    pooled = F.adaptive_avg_pool2d(current, (32, 32)) - F.adaptive_avg_pool2d(reference, (32, 32))
    return float(pooled.abs().mean().item())


def _patch(image, point, size):
    x, y = point
    half = size // 2
    return image[..., y - half : y + half + 1, x - half : x + half + 1].clone()


def _zncc(a, b):
    """Diagnostic similarity of two patches; reported, never used to accept a candidate."""
    a, b = a - a.mean(), b - b.mean()
    scale = math.sqrt(float((a * a).sum().item()) * float((b * b).sum().item()))
    return float((a * b).sum().item()) / scale if scale > 0 else None


class ReacquiringTracker:
    """unseeded -> tracking -> (reacquire_search | reacquire_candidate)* -> tracking | lost.

    Composes PatchTracker instances: the first segment is the ordinary tracker, and each
    confirmed re-acquisition is a fresh PatchTracker seeded at the candidate, so a reacquired
    segment is tracked exactly like a seeded one. ``point_px`` is set only while a segment is
    confirmed tracking; a pending candidate is reported as ``reacquire_candidate_px`` and is
    never a tracked point. ``lost`` is terminal. Points are source pixels.
    """

    def __init__(self, *, origin=(0, 0), device="cpu", params=None, reacquire=None):
        self.params = TrackParams() if params is None else params
        self.reacquire = ReacquireParams() if reacquire is None else reacquire
        if not isinstance(self.params, TrackParams) or not isinstance(
            self.reacquire, ReacquireParams
        ):
            raise ValueError("params must be TrackParams and reacquire must be ReacquireParams")
        self._search_params = replace(self.params, search_radius=self.reacquire.search_radius)
        self._inner = PatchTracker(origin=origin, device=device, params=self.params)
        self.origin, self.device = self._inner.origin, self._inner.device
        self.state, self.reason = "unseeded", "no_seed"
        self.pitch_id = self.last_index = self.last_time = None
        self.segment_id, self.reacquisitions, self._segments = None, 0, 0
        self._anchor = self._seed_template = self._window = self._candidate = None
        self._previous = None

    def step(self, image, *, pitch_id, frame_index, frame_seconds, seed=None, usable=True):
        """Process one current frame; validation and matching are the inner tracker's."""
        if seed is not None and self.state != "unseeded":
            raise ValueError("reseed requires a new tracker")
        prior = self.state
        inner = self._inner.step(
            image,
            pitch_id=pitch_id,
            frame_index=frame_index,
            frame_seconds=frame_seconds,
            seed=seed,
            usable=usable,
        )
        if self.pitch_id is not None and pitch_id != self.pitch_id:
            raise ValueError("one tracker cannot cross pitch_id")
        if self.last_time is not None and (
            frame_seconds <= self.last_time or frame_index <= self.last_index
        ):
            raise ValueError("frame time and index must increase")
        previous_time = self.last_time
        self.pitch_id, self.last_index, self.last_time = pitch_id, frame_index, frame_seconds
        record = {
            "pitch_id": pitch_id,
            "frame_index": frame_index,
            "frame_seconds": frame_seconds,
            "state": self.state,
            "reason": self.reason,
            "point_px": None,
            "reacquire_candidate_px": None,
            "segment_id": None,
            "segment_end_reason": None,
            "reacquisitions": self.reacquisitions,
            "mitt_identity": "unverified",
            "quality": dict(inner["quality"]),
            "inner_state": inner["state"],
            "inner_reason": inner["reason"],
        }
        if "seed_requested_px" in inner:
            record["seed_requested_px"] = inner["seed_requested_px"]
        if prior == "lost":
            return record
        if prior == "reacquire_search":
            return self._search(record, image, usable, previous_time)
        if inner["state"] == "tracking":
            return self._confirmed(record, image, inner, prior)
        if inner["state"] == "unseeded":
            return {**record, "reason": inner["reason"]}
        loss = inner["reason"]
        if prior == "unseeded":
            return self._terminal(record, loss)
        if prior == "tracking":
            record["segment_end_reason"] = loss
            if loss in TERMINAL_LOSSES:
                return self._terminal(record, loss)
            if self.reacquisitions >= self.reacquire.max_reacquisitions:
                return self._terminal(record, "reacquire_limit")
            self._window = {"attempts": 0, "loss_frame_index": frame_index, "loss_reason": loss}
            self.segment_id = None
            self.state = "reacquire_search"
            return self._search(record, image, usable, previous_time)
        # A pending candidate failed the ordinary continuity checks on its next frame.
        self._candidate = None
        if loss == "external_view_gate":
            return self._terminal(record, loss)
        if loss == "time_gap":
            return self._terminal(record, "reacquire_gap")
        if loss == "appearance_discontinuity":
            return self._terminal(record, "reacquire_appearance_discontinuity")
        # A candidate found on the last search frame is checked on one extra frame; that
        # frame is not a search and must not be counted beyond the window budget.
        if self._window["attempts"] < self.reacquire.max_attempt_frames:
            self._window["attempts"] += 1
        record["quality"]["reacquire_attempt"] = self._window["attempts"]
        self._previous = _tensor(image, self.device)
        return self._abstain(record, "reacquire_candidate_" + loss)

    def _confirmed(self, record, image, inner, prior):
        tensor = _tensor(image, self.device)
        point = tuple(inner["point_px"][i] - self.origin[i] for i in range(2))
        if prior == "reacquire_candidate":
            self.reacquisitions += 1
            self._segments += 1
            self.segment_id = self._segments
            self.state, self.reason = "tracking", "reacquired_continuity"
            record["quality"]["candidate_frame_index"] = self._candidate["frame_index"]
            record["reacquisitions"] = self.reacquisitions
            self._window = self._candidate = None
        else:
            if prior == "unseeded":
                self.segment_id = self._segments = 1
                self._seed_template = _patch(tensor, point, self.params.patch_size)
            self.state, self.reason = "tracking", inner["reason"]
        self._anchor = {
            "tensor": tensor,
            "template": _patch(tensor, point, self.params.patch_size),
            "point": point,
            "seconds": record["frame_seconds"],
        }
        self._previous = tensor
        record.update(
            state="tracking",
            reason=self.reason,
            point_px=list(inner["point_px"]),
            segment_id=self.segment_id,
        )
        return record

    def _search(self, record, image, usable, previous_time):
        """One bounded search per frame; the anchor ages by frames, the stream gap by seconds."""
        if not usable:
            return self._terminal(record, "external_view_gate")
        anchor, window = self._anchor, self._window
        if record["frame_seconds"] - previous_time > self.params.max_gap_seconds:
            return self._terminal(record, "reacquire_gap")
        tensor = _tensor(image, self.device)
        # The same cut test as PatchTracker between consecutive frames, plus the anchor frame
        # so that slow accumulated change inside the window is also refused.
        change = _appearance_change(tensor, self._previous)
        anchor_change = _appearance_change(tensor, anchor["tensor"])
        record["quality"]["appearance_change"] = change
        record["quality"]["anchor_appearance_change"] = anchor_change
        self._previous = tensor
        if max(change, anchor_change) > self.params.max_appearance_change:
            return self._terminal(record, "reacquire_appearance_discontinuity")
        window["attempts"] += 1
        record["quality"]["reacquire_attempt"] = window["attempts"]
        record["quality"]["reacquire_searched"] = True
        point, evidence = match_template(
            tensor, anchor["template"], anchor["point"], self._search_params
        )
        record["quality"].update(
            {"reacquire_" + key: value for key, value in evidence.items() if key != "reason"}
        )
        if point is None:
            return self._abstain(record, "reacquire_" + evidence["reason"])
        candidate = [point[i] + self.origin[i] for i in range(2)]
        fresh = PatchTracker(origin=self.origin, device=self.device, params=self.params)
        seeded = fresh.step(
            image,
            pitch_id=record["pitch_id"],
            frame_index=record["frame_index"],
            frame_seconds=record["frame_seconds"],
            seed=candidate,
        )
        if seeded["state"] != "tracking":
            return self._abstain(record, "reacquire_candidate_" + seeded["reason"])
        self._inner = fresh
        self._candidate = {"frame_index": record["frame_index"], "point_px": candidate}
        self.state = self.reason = "reacquire_candidate"
        record["quality"]["anchor_distance_px"] = math.dist(point, anchor["point"])
        record["quality"]["seed_template_ncc_diagnostic_only"] = _zncc(
            self._seed_template, _patch(tensor, point, self.params.patch_size)
        )
        return {
            **record,
            "state": self.state,
            "reason": self.reason,
            "reacquire_candidate_px": candidate,
        }

    def _abstain(self, record, reason):
        if self._window["attempts"] >= self.reacquire.max_attempt_frames:
            record["quality"]["last_attempt_reason"] = reason
            return self._terminal(record, "reacquire_exhausted")
        self.state, self.reason = "reacquire_search", reason
        return {**record, "state": self.state, "reason": reason}

    def _terminal(self, record, reason):
        self.state, self.reason = "lost", reason
        self.segment_id = None
        self._anchor = self._window = self._candidate = None
        return {
            **record,
            "state": "lost",
            "reason": reason,
            "point_px": None,
            "reacquire_candidate_px": None,
            "segment_id": None,
        }


class SegmentedStationarySelector:
    """One StationarySelector per confirmed segment; stationary support never crosses a loss.

    Rows come from ReacquiringTracker. Each confirmed segment starts a fresh selector, so hold
    time, observation counts and bounds restart from the re-acquired point instead of being
    stitched onto the lost segment. Frozen past events are kept with their segment id; the
    current candidate is cleared whenever no segment is confirmed tracking.
    """

    def __init__(self, params=None):
        self._params = StationaryParams() if params is None else params
        if not isinstance(self._params, StationaryParams):
            raise ValueError("params must be StationaryParams")
        self._digest = self._params.digest()
        self._pitch = self._index = self._time = None
        self._selector = self._segment_id = self._history = None
        self._events = 0

    @property
    def params(self):
        return self._params

    def _validate(self, row, usable):
        if not isinstance(row, dict) or type(usable) is not bool:
            raise ValueError("row must be a dict and usable must be bool")
        if not set(ROW_KEYS) <= row.keys():
            raise ValueError("missing reacquiring tracker fields")
        pitch, index, seconds = row["pitch_id"], row["frame_index"], row["frame_seconds"]
        if not isinstance(pitch, str) or not pitch.strip():
            raise ValueError("pitch_id required")
        if self._pitch is not None and pitch != self._pitch:
            raise ValueError("one selector cannot cross pitch_id")
        if type(index) is not int or index < 0 or not _number(seconds) or seconds < 0:
            raise ValueError("invalid frame index or seconds")
        if self._time is not None and (seconds <= self._time or index <= self._index):
            raise ValueError("frame index and time must strictly increase")
        state, reason, segment = row["state"], row["reason"], row["segment_id"]
        if state not in STATES or not isinstance(reason, str) or not reason.strip():
            raise ValueError("invalid tracker state or reason")
        if row["mitt_identity"] != "unverified":
            raise ValueError("tracker rows do not verify mitt identity")
        if state == "tracking":
            if not _point(row["point_px"]) or type(segment) is not int or segment < 1:
                raise ValueError("tracking requires a finite point and a segment id")
            if reason in SEGMENT_START_REASONS:
                if self._segment_id is not None and segment <= self._segment_id:
                    raise ValueError("a new segment needs a new segment id")
            elif reason != "patch_continuity" or segment != self._segment_id or not self._selector:
                raise ValueError("continuity without a started segment")
        elif row["point_px"] is not None or segment is not None:
            raise ValueError("inactive tracking must not carry a point or segment")
        candidate = row["reacquire_candidate_px"]
        if state == "reacquire_candidate":
            if not _point(candidate):
                raise ValueError("candidate state requires a finite candidate point")
        elif candidate is not None:
            raise ValueError("candidate point only in the candidate state")
        if self._selector is None and state == "tracking" and reason == "patch_continuity":
            raise ValueError("continuity without a started segment")

    def step(self, row, *, usable=True):
        """Validate fully before mutation; return an independent JSON-safe snapshot."""
        self._validate(row, usable)
        self._pitch, self._index, self._time = (
            row["pitch_id"],
            row["frame_index"],
            row["frame_seconds"],
        )
        state = row["state"]
        if state == "tracking":
            first = row["reason"] in SEGMENT_START_REASONS
            if first:
                self._selector, self._segment_id = (
                    StationarySelector(self._params),
                    row["segment_id"],
                )
            mapped = {
                key: row[key]
                for key in ("pitch_id", "frame_index", "frame_seconds", "state", "point_px")
            }
            mapped.update(
                reason="external_seed" if first else "patch_continuity", mitt_identity="unverified"
            )
            out = self._selector.step(mapped, usable=usable)
            if out["event"] is not None:
                self._events += 1
                out["event"]["segment_id"] = self._segment_id
                self._history = copy.deepcopy(out["event"])
            if out["current_candidate"] is not None:
                out["current_candidate"]["segment_id"] = self._segment_id
        else:
            # The lost segment's selector is discarded; a later segment must requalify.
            self._selector = None
            out = {
                "pitch_id": self._pitch,
                "frame_index": self._index,
                "frame_seconds": self._time,
                "selection_state": "unavailable",
                "reason": row["reason"],
                "current_track_point_px": None,
                "current_candidate": None,
                "event": None,
                "mitt_identity": "unverified",
                "params_sha256": self._digest,
            }
        return {
            **out,
            "schema": "pitcheezy-segmented-stationary-candidate-dev-v1",
            "tracker_state": state,
            "segment_id": row["segment_id"],
            "events_total": self._events,
            "last_historical_candidate": copy.deepcopy(self._history),
        }
