"""Hop 2 of the coordinate chain: annotated image zone (v1) -> plate feet.

Hop 1 v1 (``intent.geometry.front_edge_similarity``) expresses a pixel as ``u`` = position
along the plate's 17-inch front edge (0 = front-left end, 1 = front-right end) and ``v`` =
height above that ground line in plate widths. Hop 2 is a constant affine matrix for the
camera:

    plate_x_ft = -(17/12) * (u - 0.5)
    plate_z_ft =  (17/12) * v / cos(tilt) - d0 * tan(tilt)

- x: Statcast plate_x from the catcher's view, positive toward first base. The centre-field
  camera looks from the pitcher toward the catcher, so image right is the third-base side,
  the catcher's left, negative plate_x: hence the minus sign.
- z: a vertical segment at the plate front projects with the lateral scale times cos(tilt)
  (pinhole camera; the source has a 1:1 sample aspect ratio), and a point d0 ft farther from
  the camera than the plate front appears d0*sin(tilt) higher on the ground scale, i.e.
  d0*tan(tilt) of extra height. The mitt sits behind the plate front, so the matrix removes
  that depth-parallax term for a nominal mitt depth d0 (camera tilt and d0 come from the
  calibration file). Without a calibration file the uncorrected matrix (tilt 0, d0 0) is used
  and the transform step says so.
- The target quantity is the mitt's own position at its depth, not the plate-front crossing
  point of a pitch that would hit it; the ball's drop between the plate front and the mitt is
  never netted against this term.
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path

import numpy as np

PLATE_WIDTH_FEET = 17.0 / 12.0
X_CONVENTION = "statcast_plate_x_catcher_view"
METHOD = "plate_front_edge_affine_with_depth_parallax"
VERSION = "v0"
CALIBRATION_SCHEMA = "intent_plate_calibration_v0"
NOMINAL_MITT_DEPTH_FEET = 2.5


def zone_to_feet_matrix(tilt_sin=0.0, mitt_depth_feet=0.0):
    """Return the 3x3 affine matrix for the given camera tilt and nominal mitt depth."""
    if not (0.0 <= tilt_sin < 1.0):
        raise ValueError("tilt_sin must be in [0, 1)")
    if mitt_depth_feet < 0.0:
        raise ValueError("mitt depth must be nonnegative")
    cos_t = math.sqrt(1.0 - tilt_sin * tilt_sin)
    tan_t = tilt_sin / cos_t
    return (
        (-PLATE_WIDTH_FEET, 0.0, PLATE_WIDTH_FEET / 2.0),
        (0.0, PLATE_WIDTH_FEET / cos_t, -mitt_depth_feet * tan_t),
        (0.0, 0.0, 1.0),
    )


UNCORRECTED_MATRIX = zone_to_feet_matrix()


def zone_to_plate_feet(uv, matrix=UNCORRECTED_MATRIX):
    """Map hop-1 v1 zone coordinates (u, v) to (plate_x_ft, plate_z_ft) with ``matrix``."""
    vec = np.asarray(matrix, dtype=float) @ np.array([float(uv[0]), float(uv[1]), 1.0])
    return float(vec[0]), float(vec[1])


def load_calibration(path):
    """Return the measured calibration document, or None when the file does not exist."""
    path = Path(path)
    if not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if doc.get("schema") != CALIBRATION_SCHEMA:
        raise ValueError("unexpected plate calibration schema")
    hop2 = doc.get("hop2", {})
    expected = zone_to_feet_matrix(hop2.get("tilt_sin", 0.0), hop2.get("mitt_depth_feet", 0.0))
    if not np.allclose(np.asarray(hop2.get("matrix", []), dtype=float), np.asarray(expected)):
        raise ValueError("calibration matrix does not match its tilt/depth parameters")
    return doc


def hop2_parameters(calibration):
    """Matrix and parameters to use: the calibration's, or the uncorrected default."""
    if calibration is None:
        return {
            "matrix": UNCORRECTED_MATRIX,
            "tilt_sin": 0.0,
            "mitt_depth_feet": 0.0,
            "source": "no calibration file: uncorrected (tilt 0, depth 0)",
        }
    hop2 = calibration["hop2"]
    return {
        "matrix": tuple(tuple(float(v) for v in row) for row in hop2["matrix"]),
        "tilt_sin": float(hop2["tilt_sin"]),
        "mitt_depth_feet": float(hop2["mitt_depth_feet"]),
        "source": hop2.get("source", "calibration file"),
    }


def feet_transform_step(frame_px_per_foot, diagnostics, calibration):
    """Build the transform_chain entry for hop 2 on one frame."""
    params = hop2_parameters(calibration)
    measured = calibration is not None and calibration.get("rms_error_feet") is not None
    tilt_sin = params["tilt_sin"]
    evidence = {
        "matrix": [list(row) for row in params["matrix"]],
        "x_convention": X_CONVENTION,
        "plate_width_feet": PLATE_WIDTH_FEET,
        "frame_px_per_foot": float(frame_px_per_foot),
        "camera_tilt_sin": tilt_sin,
        "camera_tilt_degrees": math.degrees(math.asin(tilt_sin)),
        "nominal_mitt_depth_feet": params["mitt_depth_feet"],
        "parameters_source": params["source"],
        "target_quantity": "the mitt's own position at its depth behind the plate front "
        "(depth parallax removed for the nominal depth); not the plate-front crossing point "
        "of a pitch into the mitt, and never netted against the ball's drop",
        "uncorrected_terms": {
            "depth_parallax_z_feet_per_foot_of_depth_error": math.tan(math.asin(tilt_sin)),
            "depth_parallax_x_feet": "d*tan(pan); pan ~0.3 deg from 165 plate quads -> ~0.01 ft "
            "at 2.5 ft, not applied",
            "tilt_sin_estimate_this_frame_from_plate_quad": diagnostics.get("tilt_sin_estimate"),
        },
        "calibration": None
        if calibration is None
        else {k: deepcopy(calibration[k]) for k in calibration if k != "per_item"},
    }
    return {
        "source_frame": "annotated_image_zone",
        "target_frame": "plate_feet",
        "method": METHOD,
        "version": VERSION,
        "error": float(calibration["rms_error_feet"]) if measured else None,
        "error_units": "feet",
        "error_status": "measured" if measured else "unmeasured",
        "evidence": evidence,
    }
