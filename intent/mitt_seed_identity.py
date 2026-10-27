"""Conservative identity cue for a seed patch on its own RGB frame; not mitt identification.

CV46. A seed point can be geometrically stable and still sit on the catcher's bare hand or on an
unidentifiable blob (development cases 747139:3:1, 3:3, 5:1). This cue looks only at the 21 px
RGB patch of the current frame around the proposed seed and answers ``mitt_like``,
``hand_like`` or ``unclear`` with its evidence. It assumes a dark leather mitt, so a light or
tan mitt is refused as ``unclear``/``hand_like``: the cue abstains, it never confirms identity.
Thresholds were fixed before the development replay and are not tuned on the known cases.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass

import numpy as np

SCHEMA = "pitcheezy-seed-identity-cue-dev-v1"
VERDICTS = ("mitt_like", "hand_like", "unclear")


def _number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


@dataclass(frozen=True)
class IdentityParams:
    """Published RGB skin rule (Kovac et al. 2003) plus dark-object and texture gates."""

    patch_size: int = 21
    skin_r_min: int = 95
    skin_g_min: int = 40
    skin_b_min: int = 20
    skin_spread_min: int = 15
    skin_rg_diff_min: int = 15
    hand_skin_fraction_min: float = 0.50
    mitt_skin_fraction_max: float = 0.10
    mitt_max_luminance: float = 110.0
    min_texture: float = 0.03

    def __post_init__(self):
        for key, value in asdict(self).items():
            if key.startswith("skin_") or key == "patch_size":
                if type(value) is not int or value < 0:
                    raise ValueError(f"invalid {key}")
            elif isinstance(value, bool) or not _number(value) or value < 0:
                raise ValueError(f"invalid {key}")
        if self.patch_size < 3 or self.patch_size % 2 != 1:
            raise ValueError("patch_size must be an odd integer >= 3")
        if not 0 <= self.mitt_skin_fraction_max < self.hand_skin_fraction_min <= 1:
            raise ValueError("skin fraction gates must be ordered inside [0, 1]")
        if self.mitt_max_luminance > 255 or self.min_texture > 1:
            raise ValueError("luminance is 0..255 and texture is 0..1")

    def digest(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


def skin_mask(rgb, params=None):
    """Boolean mask of pixels that satisfy the fixed RGB skin rule."""
    p = IdentityParams() if params is None else params
    if (
        not isinstance(rgb, np.ndarray)
        or rgb.dtype != np.uint8
        or rgb.ndim != 3
        or rgb.shape[2] != 3
    ):
        raise ValueError("uint8 RGB array required")
    r, g, b = (rgb[..., i].astype(np.int16) for i in range(3))
    spread = rgb.max(axis=2).astype(np.int16) - rgb.min(axis=2).astype(np.int16)
    return (
        (r > p.skin_r_min)
        & (g > p.skin_g_min)
        & (b > p.skin_b_min)
        & (spread > p.skin_spread_min)
        & (np.abs(r - g) > p.skin_rg_diff_min)
        & (r > g)
        & (r > b)
    )


def luminance(rgb):
    """ITU-R BT.601 luma on 0..255, the same weights PIL uses for mode L."""
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


def assess_patch(image_rgb, point_px, params=None):
    """Judge the patch around ``point_px`` on ``image_rgb`` (uint8 HxWx3, source pixels).

    Returns a JSON-safe dict. Only this frame's pixels inside the patch are read: no other
    frame, observation, tracking result or outcome enters the decision.
    """
    p = IdentityParams() if params is None else params
    if not isinstance(p, IdentityParams):
        raise ValueError("params must be IdentityParams")
    if (
        not isinstance(image_rgb, np.ndarray)
        or image_rgb.dtype != np.uint8
        or image_rgb.ndim != 3
        or image_rgb.shape[2] != 3
    ):
        raise ValueError("uint8 RGB array required")
    if (
        not isinstance(point_px, (list, tuple))
        or len(point_px) != 2
        or not all(_number(v) for v in point_px)
    ):
        raise ValueError("point_px must contain two finite numbers")
    height, width = image_rgb.shape[:2]
    x, y = (int(math.floor(v + 0.5)) for v in point_px)
    half = p.patch_size // 2
    result = {
        "schema": SCHEMA,
        "verdict": "unclear",
        "reason": None,
        "point_px": [x, y],
        "patch_box": None,
        "skin_fraction": None,
        "mean_rgb": None,
        "mean_luminance": None,
        "texture_std": None,
        "params_sha256": p.digest(),
        "mitt_identity": "unverified",
    }
    if x - half < 0 or y - half < 0 or x + half >= width or y + half >= height:
        return {**result, "reason": "patch_border"}
    patch = image_rgb[y - half : y + half + 1, x - half : x + half + 1]
    skin = float(skin_mask(patch, p).mean())
    luma = luminance(patch.astype(np.float64))
    texture = float((luma / 255.0).std())
    mean_luma = float(luma.mean())
    result.update(
        patch_box=[x - half, y - half, x + half, y + half],
        skin_fraction=skin,
        mean_rgb=[float(v) for v in patch.reshape(-1, 3).mean(axis=0)],
        mean_luminance=mean_luma,
        texture_std=texture,
    )
    if skin >= p.hand_skin_fraction_min:
        return {**result, "verdict": "hand_like", "reason": "skin_fraction_high"}
    if texture < p.min_texture:
        return {**result, "verdict": "unclear", "reason": "low_texture"}
    if skin <= p.mitt_skin_fraction_max and mean_luma <= p.mitt_max_luminance:
        return {**result, "verdict": "mitt_like", "reason": "dark_low_skin_textured"}
    return {**result, "verdict": "unclear", "reason": "mixed"}


def accepts(cue):
    """Only ``mitt_like`` may seed; every other verdict abstains."""
    if not isinstance(cue, dict) or cue.get("verdict") not in VERDICTS:
        raise ValueError("cue dict with a known verdict required")
    return cue["verdict"] == "mitt_like"
