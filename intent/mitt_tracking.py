"""Causal development patch tracking, not mitt recognition or intent estimation.

An external point seeds one fixed appearance template. A successful match only establishes
patch continuity. It does not verify that the seed or the tracked patch is a mitt. No automatic
reacquisition, template adaptation, future frames, release annotation or pitch outcome is used.
Only unannotated grayscale uint8 pixels are accepted; the caller binds them to source hashes.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass

import numpy as np
import torch
import torch.nn.functional as F


@dataclass(frozen=True)
class TrackParams:
    """First development candidate, fixed before the saved-video pilot."""

    patch_size: int = 21
    search_radius: int = 24
    min_ncc: float = 0.65
    min_peak_margin: float = 0.05
    peak_exclusion: int = 4
    max_fb_error: float = 3.0
    min_texture: float = 0.03
    max_appearance_change: float = 0.22
    max_gap_seconds: float = 0.25

    def __post_init__(self):
        for key in ("patch_size", "search_radius", "peak_exclusion"):
            value = getattr(self, key)
            if type(value) is not int or value < 1:
                raise ValueError(f"invalid {key}")
        if self.patch_size % 2 != 1 or self.peak_exclusion >= self.search_radius:
            raise ValueError("odd patch size and smaller peak exclusion required")
        for key, value in asdict(self).items():
            if key in ("patch_size", "search_radius", "peak_exclusion"):
                continue
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"invalid {key}")
        if self.min_ncc > 1 or self.max_appearance_change > 1:
            raise ValueError("normalized threshold outside range")

    def digest(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class PatchTracker:
    """Single pitch/shot tracker: unseeded -> tracking -> lost; use a new instance to reseed.

    Images are plain crops without scaling. ``origin`` is their x/y offset in source pixels.
    All public points use source pixels, with rounding half-up recorded on initialization.
    Use one compute worker per process: cuDNN precision flags are process-global, so other
    threads must not change them concurrently. Their prior values are restored after matching.
    """

    def __init__(self, *, origin=(0, 0), device="cpu", params=None):
        if len(origin) != 2 or any(type(v) is not int or v < 0 for v in origin):
            raise ValueError("origin must be two nonnegative integers")
        self.origin, self.device = tuple(origin), torch.device(device)
        self.params = params if params is not None else TrackParams()
        self.state, self.reason = "unseeded", "no_seed"
        self.pitch_id = self.last_index = self.last_time = self.shape = None
        self.previous = self.template = self.position = None

    def _patch(self, image, point):
        x, y = point
        half = self.params.patch_size // 2
        height, width = image.shape[-2:]
        if x - half < 0 or y - half < 0 or x + half >= width or y + half >= height:
            return None
        return image[..., y - half : y + half + 1, x - half : x + half + 1].clone()

    def _match(self, image, template, around):
        """ZNCC using each candidate patch's variance, not search-region variance."""
        p = self.params
        half = p.patch_size // 2
        height, width = image.shape[-2:]
        x, y = around
        x0, x1 = max(half, x - p.search_radius), min(width - half - 1, x + p.search_radius)
        y0, y1 = max(half, y - p.search_radius), min(height - half - 1, y + p.search_radius)
        region = image[..., y0 - half : y1 + half + 1, x0 - half : x1 + half + 1]
        zero = template - template.mean()
        energy = (zero * zero).sum()
        means = F.avg_pool2d(region, p.patch_size, stride=1)
        variances = (
            F.avg_pool2d(region.square(), p.patch_size, stride=1) - means.square()
        ).clamp_min(0)
        # Do not inherit lower precision from a caller's autocast/TF32 settings.
        with torch.autocast(device_type=image.device.type, enabled=False):
            if image.is_cuda:
                with torch.backends.cudnn.flags(
                    enabled=torch.backends.cudnn.enabled,
                    benchmark=torch.backends.cudnn.benchmark,
                    benchmark_limit=torch.backends.cudnn.benchmark_limit,
                    deterministic=torch.backends.cudnn.deterministic,
                    allow_tf32=False,
                ):
                    numerator = F.conv2d(region, zero)
            else:
                numerator = F.conv2d(region, zero)
        score = numerator / (energy * variances * p.patch_size**2).sqrt().clamp_min(1e-12)
        score = score[0, 0].clamp(-1, 1)
        score = score.masked_fill(variances[0, 0] < p.min_texture**2, -torch.inf)
        flat = int(score.argmax().item())
        row, col = divmod(flat, score.shape[1])
        best = float(score[row, col].item())
        if not math.isfinite(best):
            return None, {"reason": "low_texture"}
        alternatives = score.clone()
        e = p.peak_exclusion
        alternatives[max(0, row - e) : row + e + 1, max(0, col - e) : col + e + 1] = -torch.inf
        second = float(alternatives.max().item())
        margin = best - second if math.isfinite(second) else None
        evidence = {"ncc": best, "peak_margin": margin}
        if best < p.min_ncc:
            return None, {**evidence, "reason": "low_similarity"}
        if margin is not None and margin < p.min_peak_margin:
            return None, {**evidence, "reason": "ambiguous_peak"}
        if row in (0, score.shape[0] - 1) or col in (0, score.shape[1] - 1):
            return None, {**evidence, "reason": "search_boundary"}
        return (x0 + col, y0 + row), evidence

    def step(self, image, *, pitch_id, frame_index, frame_seconds, seed=None, usable=True):
        """Process one current frame. ``usable`` is an optional current external view gate."""
        if not isinstance(pitch_id, str) or not pitch_id:
            raise ValueError("pitch_id required")
        if self.pitch_id is not None and pitch_id != self.pitch_id:
            raise ValueError("one tracker cannot cross pitch_id")
        if type(frame_index) is not int or frame_index < 0:
            raise ValueError("frame_index must be a nonnegative integer")
        if not _number(frame_seconds) or frame_seconds < 0:
            raise ValueError("frame_seconds must be finite and nonnegative")
        if self.last_time is not None and (
            frame_seconds <= self.last_time or frame_index <= self.last_index
        ):
            raise ValueError("frame time and index must increase")
        if not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.ndim != 2:
            raise ValueError("plain grayscale uint8 image required")
        if min(image.shape) < self.params.patch_size + 2:
            raise ValueError("image too small")
        if self.shape is not None and image.shape != self.shape:
            raise ValueError("frame shape changed")
        if type(usable) is not bool:
            raise ValueError("usable must be bool")
        if seed is not None:
            if self.state != "unseeded":
                raise ValueError("reseed requires a new tracker")
            if (
                not isinstance(seed, (list, tuple))
                or len(seed) != 2
                or not all(_number(v) for v in seed)
            ):
                raise ValueError("seed must contain two finite source pixel coordinates")
            local = [seed[i] - self.origin[i] for i in range(2)]
            if not (0 <= local[0] < image.shape[1] and 0 <= local[1] < image.shape[0]):
                raise ValueError("seed outside image")
            if not usable:
                raise ValueError("seed cannot be applied on a gated frame")
        old_time = self.last_time
        self.pitch_id, self.last_index, self.last_time, self.shape = (
            pitch_id,
            frame_index,
            frame_seconds,
            image.shape,
        )
        record = {
            "pitch_id": pitch_id,
            "frame_index": frame_index,
            "frame_seconds": frame_seconds,
            "state": self.state,
            "reason": self.reason,
            "point_px": None,
            "mitt_identity": "unverified",
            "quality": {},
        }
        if self.state == "lost":
            return record
        if not usable:
            if self.state == "tracking":
                return self._lost(record, "external_view_gate")
            return {**record, "reason": "external_view_gate"}
        if self.state == "unseeded" and seed is None:
            return record
        tensor = (
            torch.as_tensor(np.ascontiguousarray(image), device=self.device).float()[None, None]
            / 255.0
        )
        if self.state == "unseeded":
            point = tuple(int(math.floor(v + 0.5)) for v in local)
            template = self._patch(tensor, point)
            record["seed_requested_px"] = list(seed)
            if template is None:
                return self._lost(record, "seed_border")
            if float(template.std(unbiased=False).item()) < self.params.min_texture:
                return self._lost(record, "seed_low_texture")
            self.template, self.previous, self.position = template, tensor, point
            self.state, self.reason = "tracking", "external_seed"
        else:
            if frame_seconds - old_time > self.params.max_gap_seconds:
                return self._lost(record, "time_gap")
            change = float(
                (
                    F.adaptive_avg_pool2d(tensor, (32, 32))
                    - F.adaptive_avg_pool2d(self.previous, (32, 32))
                )
                .abs()
                .mean()
                .item()
            )
            record["quality"]["appearance_change"] = change
            if change > self.params.max_appearance_change:
                return self._lost(record, "appearance_discontinuity")
            point, quality = self._match(tensor, self.template, self.position)
            record["quality"].update(quality)
            if point is None:
                return self._lost(record, quality["reason"])
            current_patch = self._patch(tensor, point)
            back, backward = self._match(self.previous, current_patch, self.position)
            record["quality"]["backward_ncc"] = backward.get("ncc")
            if back is None:
                return self._lost(record, "backward_" + backward["reason"])
            error = math.dist(back, self.position)
            record["quality"]["fb_error_px"] = error
            if error > self.params.max_fb_error:
                return self._lost(record, "forward_backward_mismatch")
            self.previous, self.position, self.reason = tensor, point, "patch_continuity"
        record.update(
            state=self.state,
            reason=self.reason,
            point_px=[self.position[i] + self.origin[i] for i in range(2)],
        )
        return record

    def _lost(self, record, reason):
        self.state, self.reason = "lost", reason
        self.previous = self.template = self.position = None
        return {**record, "state": "lost", "reason": reason, "point_px": None}
