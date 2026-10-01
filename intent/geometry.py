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
