"""Hop 1 of the coordinate chain: image pixels -> annotated image zone.

The annotated image zone is the unit square spanned by the four home-plate corners the
annotator marked on the same frame (front-left, front-right, back-right, back-left). A plane
homography maps those corners to (0,0), (1,0), (1,1), (0,1). The mitt is not on the plate
plane, so this hop is only an image-zone normalization; physical plate feet (hop 2) need a
separate calibration and stay blocked until it exists.
"""

from __future__ import annotations

import numpy as np

CORNER_ORDER = ("front_left", "front_right", "back_right", "back_left")
UNIT_SQUARE = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))


def homography_from_corners(corners):
    """Return the 3x3 matrix sending the four pixel corners (dict by CORNER_ORDER) to the unit square."""
    src = [tuple(map(float, corners[name])) for name in CORNER_ORDER]
    rows = []
    for (x, y), (u, v) in zip(src, UNIT_SQUARE, strict=True):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    matrix = np.asarray(rows, dtype=float)
    _, singular, vt = np.linalg.svd(matrix)
    # Four points in general position give rank 8 (one null vector = the homography); any
    # repeated or collinear corner drops the rank and the smallest singular value to ~0.
    if singular[-1] < 1e-9 * singular[0]:
        raise ValueError("plate corners are degenerate (collinear or repeated)")
    h = vt[-1].reshape(3, 3)
    if abs(h[2, 2]) < 1e-12:
        raise ValueError("plate corners give a degenerate homography")
    return h / h[2, 2]


def project_point(h, point):
    """Apply the homography to an (x, y) pixel point; returns (u, v)."""
    vec = h @ np.array([float(point[0]), float(point[1]), 1.0])
    if abs(vec[2]) < 1e-12:
        raise ValueError("point maps to infinity under the plate homography")
    return float(vec[0] / vec[2]), float(vec[1] / vec[2])


def front_edge_similarity(corners, *, roll_radians=None, width_px=None):
    """Hop 1 v1: a 2-D similarity anchored on the plate's front edge.

    Returns ``(h, diagnostics)``: ``h`` is a 3x3 matrix (last row 0 0 1) sending a pixel to
    ``(u, v)`` with ``u`` = position along the front edge in front-edge widths (0 at
    front_left, 1 at front_right, 0.5 at the midpoint) and ``v`` = distance above that line,
    also in front-edge widths (positive = up in the image). The origin is the front-edge
    midpoint. ``roll_radians`` fixes the edge direction (a camera constant pooled over many
    frames) instead of the noisy per-frame direction; ``width_px`` fixes the scale (for
    example a per-plate-appearance pooled width) instead of this frame's own edge length. The
    back corners only feed the diagnostics: the plate's apparent depth in pixels, the lateral
    shift of the back edge, and the implied camera tilt
    sin(theta) = (depth_px / 8.5 in) / (width_px / 17 in) = 2 * depth_px / width_px.
    """
    fl = np.array(corners["front_left"], dtype=float)
    fr = np.array(corners["front_right"], dtype=float)
    edge = fr - fl
    measured_width = float(np.hypot(edge[0], edge[1]))
    if measured_width < 1e-9:
        raise ValueError("plate front edge has zero length")
    measured_roll = float(np.arctan2(edge[1], edge[0]))
    roll = measured_roll if roll_radians is None else float(roll_radians)
    width = measured_width if width_px is None else float(width_px)
    if width <= 0:
        raise ValueError("front edge width must be positive")
    e = np.array([np.cos(roll), np.sin(roll)])
    n = np.array([e[1], -e[0]])
    if n[1] > 0:  # make n point up in image coordinates (negative y)
        n = -n
    mid = (fl + fr) / 2.0
    h = np.array(
        [
            [e[0] / width, e[1] / width, 0.5 - float(mid @ e) / width],
            [n[0] / width, n[1] / width, -float(mid @ n) / width],
            [0.0, 0.0, 1.0],
        ]
    )
    diagnostics = {
        "front_edge_px": measured_width,
        "width_used_px": width,
        "roll_measured_radians": measured_roll,
        "roll_used_radians": roll,
    }
    if all(corners.get(name) for name in ("back_left", "back_right")):
        bl = np.array(corners["back_left"], dtype=float)
        br = np.array(corners["back_right"], dtype=float)
        mid_back = (bl + br) / 2.0
        depth_px = float((mid_back - mid) @ n)
        diagnostics.update(
            {
                "plate_depth_px": depth_px,
                "back_edge_lateral_shift_px": float((mid_back - mid) @ e),
                "back_edge_px": float(np.hypot(*(br - bl))),
                "tilt_sin_estimate": 2.0 * depth_px / width,
            }
        )
    return h, diagnostics


def inside_unit_square(uv, tolerance=1e-9):
    return -tolerance <= uv[0] <= 1 + tolerance and -tolerance <= uv[1] <= 1 + tolerance


def reprojection_error_pixels(h, corners):
    """RMS pixel error of mapping the unit square back onto the marked corners (sanity only)."""
    inv = np.linalg.inv(h)
    errors = []
    for name, (u, v) in zip(CORNER_ORDER, UNIT_SQUARE, strict=True):
        back = project_point(inv, (u, v))
        x, y = map(float, corners[name])
        errors.append((back[0] - x) ** 2 + (back[1] - y) ** 2)
    return float(np.sqrt(np.mean(errors)))
