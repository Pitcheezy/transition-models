"""Image-only SNY player-name baseline using the locally installed Windows OCR engine.

No roster, pitch key or expected player name enters this reader. Fixed crops and presence
thresholds were developed on PA6 of game 747139; this is not a general broadcast recognizer.
The native adapter is optional: portable scoring and injected-reader tests need no Windows OCR.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from copy import deepcopy
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from src.vision.sny_scoreboard import bug_present, masks

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = Path(__file__).with_name("windows_ocr.ps1")
CONFIG = {
    "schema": "sny_player_names_v1",
    "frame_size": [1280, 720],
    "crops": {"pitcher": [64, 111, 168, 129], "batter": [64, 133, 252, 151]},
    "presence": {
        "count_bug": "sny_scoreboard_v2_default_gate",
        "min_neutral_bright_fraction": 0.5,
        "min_channel": 160,
        "max_channel_spread": 50,
    },
    "preprocessing": {"scale": 4, "resampling": "LANCZOS", "border": 16, "grayscale": True},
    "parser": "uppercase_latin_literal_names_optional_batter_slot_no_fuzzy_correction",
    "state": "current_frame_only_no_hold",
}
# v2 (pre-registered 2026-09-28, CHECKLIST F-4b) keeps every v1 crop, gate and preprocessing
# value and adds two image-side parser rules for this uppercase-only strip. Neither rule uses a
# roster, an expected player or any per-frame label; v1 stays the default reader.
CONFIG_V2 = {
    **deepcopy(CONFIG),
    "schema": "sny_player_names_v2",
    "parser": "v1_parser_plus_uppercase_context_l_to_I_and_decoupled_batter_slot",
    "options": {
        # The strip prints surnames in capitals, so a lowercase "l" returned by the engine can
        # only be a capital "I". Applied before upper-casing and only when "l" is the sole
        # lowercase letter in the raw text; other lowercase output is left to the v1 path.
        "uppercase_context_l_to_I": True,
        # When the batter slot position holds one unreadable character before "." or ":", read
        # the name after it and abstain on the lineup slot instead of abstaining on both.
        "decoupled_unreadable_batter_slot": True,
    },
}
# v3 (pre-registered 2026-09-28, CHECKLIST F-4d) keeps every v2 crop, gate, parser and state
# rule and changes only the preprocessing handed to the engine: a larger LANCZOS scale and a
# fixed-threshold binarization of the grayscale crop. The cumulative misread types on this
# strip (I->l, N->1V, apostrophe->t, slot digit->letter) are glyph-shape confusions, so the
# candidate targets the image the engine sees, not the parser or any roster/label input.
CONFIG_V3 = {
    **deepcopy(CONFIG_V2),
    "schema": "sny_player_names_v3",
    "preprocessing": {
        "scale": 6,
        "resampling": "LANCZOS",
        "border": 16,
        "grayscale": True,
        # Grayscale value strictly above the threshold becomes white, everything else black.
        # 100 (not the 128 midpoint) was chosen on the PA61 development sample among six
        # scale/threshold variants before any target frame was run; see PLAYER_IDENTITY_OCR.md.
        "binarize_threshold": 100,
    },
}
# v4 (pre-registered 2026-10-01, CHECKLIST F-4h) keeps the v2 parser and 4x grayscale
# preprocessing and adds two reader-side rules for the misread types that v2 still shares
# with v1: long surnames whose glyphs touch the pitcher crop's right edge (SCHWELLENBACH)
# and accented capitals the engine returns as other letters (BRAZOBÁN -> BRAZOBÅN). Both
# rules were shaped on this game's development frames, so their re-score here is not
# evidence; the pre-registered test is a different video (see PLAYER_IDENTITY_OCR.md).
CONFIG_V4 = {
    **deepcopy(CONFIG_V2),
    "schema": "sny_player_names_v4",
    "parser": "v2_parser_plus_nfkd_accent_fold",
    "options": {
        **CONFIG_V2["options"],
        # Decompose accented letters (NFKD) and drop the combining marks before the grammar,
        # so Á, Å, Í, É ... become A, A, I, E; the roster match already folds accents.
        "nfkd_accent_fold": True,
    },
    # The pitcher crop keeps the v2 box unless ink touches its last column; then the right
    # edge follows the ink (stopping at the navy pitch-clock box or the x limit) plus a
    # margin, so a long surname is no longer cut while short names keep the v2 crop. A fixed
    # wider crop was rejected in development: the engine returned nothing for MEGILL and
    # IGLESIAS in wide blank crops at some widths.
    "pitcher_dynamic_right_edge": {
        "max_x": 230,
        "ink_max_channel": 100,  # a pixel is ink when every channel is below this
        "ink_min_pixels": 3,  # a column has ink with at least this many ink pixels in the band
        "gap": 8,  # consecutive ink-free columns that end the scan
        "margin": 4,  # blank columns kept after the last ink column
        "box_blue_minus_red": 30,  # every band pixel this blue-dominant: the pitch-clock box
    },
}
NO_OPTIONS = {
    "uppercase_context_l_to_I": False,
    "decoupled_unreadable_batter_slot": False,
    "nfkd_accent_fold": False,
}
SCHEMAS = (
    "sny_player_names_v1",
    "sny_player_names_v2",
    "sny_player_names_v3",
    "sny_player_names_v4",
)


def parse_panel_text(raw_text, role, options=None):
    """Parse a fixed single-line panel, preserving raw OCR text without dictionary correction."""
    if role not in CONFIG["crops"]:
        raise ValueError("Unknown player role")
    if not isinstance(raw_text, str):
        raise ValueError("OCR text must be a string")
    options = {**NO_OPTIONS, **(options or {})}
    if set(options) != set(NO_OPTIONS):
        raise ValueError("Unknown parser option")
    text = " ".join(raw_text.split())
    slot, reason = None, "literal_name"
    if role == "batter":
        # The slot character is split off before any case rule so it cannot mask the name.
        match = re.match(r"^([1-9])\s*[.:]?\s*(.*)$", text)
        unreadable = (
            re.match(r"^[^\s.:]\s*[.:]\s*(.+)$", text)
            if match is None and options["decoupled_unreadable_batter_slot"]
            else None
        )
        if match:
            slot, text = int(match[1]), match[2]
        elif unreadable:
            text, reason = unreadable[1], "literal_name_slot_unreadable"
        else:
            return {
                "raw_text": raw_text,
                "name_text": None,
                "lineup_order": None,
                "status": "abstain",
                "reason": "batter_slot_missing",
            }
    if options["uppercase_context_l_to_I"] and {char for char in text if char.islower()} == {"l"}:
        text = text.replace("l", "I")
    if options["nfkd_accent_fold"]:
        text = "".join(
            char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char)
        )
    text = text.upper()
    valid = re.fullmatch(r"[A-Z][A-Z .'-]*[A-Z.]", text) is not None
    return {
        "raw_text": raw_text,
        "name_text": text if valid else None,
        "lineup_order": slot,
        "status": "read" if valid else "abstain",
        "reason": reason if valid else "name_syntax_or_empty",
    }


def dynamic_right_edge(pixels, box, rule):
    """Return the v4 pitcher crop's right edge: the fixed edge unless ink crosses it."""
    x0, y0, x1, y1 = box
    band = pixels[y0 + 3 : y1 - 3]

    def ink(x):
        dark = (band[:, x].max(axis=1) < rule["ink_max_channel"]).sum()
        return int(dark) >= rule["ink_min_pixels"]

    def clock_box(x):
        return bool(((band[:, x, 2] - band[:, x, 0]) >= rule["box_blue_minus_red"]).all())

    if not ink(x1 - 1):
        return x1
    last_ink = x1 - 1
    for x in range(x1, rule["max_x"]):
        if clock_box(x):
            return max(x1, min(last_ink + rule["margin"] + 1, x))
        if ink(x):
            last_ink = x
        elif x - last_ink > rule["gap"]:
            break
    return min(rule["max_x"], last_ink + rule["margin"] + 1)


def _abstain(reason, *, error=False):
    return {
        "raw_text": "",
        "name_text": None,
        "lineup_order": None,
        "status": "error" if error else "abstain",
        "reason": reason,
    }


class WindowsOCR:
    """Run the bundled bridge in Windows PowerShell 5.1 with no network or model download."""

    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError(
                "Prediction requires Windows OCR en-US; saved prediction scoring is portable"
            )
        self.executable = Path(os.environ.get("SystemRoot", "C:/Windows")) / (
            "System32/WindowsPowerShell/v1.0/powershell.exe"
        )
        if not self.executable.is_file():
            raise RuntimeError("Windows PowerShell 5.1 is unavailable")
        self.info = self._run(["-Info"])

    def _run(self, arguments):
        run = subprocess.run(
            [
                str(self.executable),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(BRIDGE),
                *arguments,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8-sig",
            timeout=60,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if run.returncode:
            raise RuntimeError("Windows OCR failed: " + run.stderr.strip()[-600:])
        result = json.loads(run.stdout)
        if result.get("engine") != "windows_ocr" or result.get("language") != "en-US":
            raise RuntimeError("Unexpected Windows OCR engine/language")
        return result

    def metadata(self):
        """Describe the native runtime; Windows updates can change its recognition behavior."""
        return {key: value for key, value in self.info.items() if key != "results"}

    def recognize(self, images):
        """Recognize ordered cropped images in one native process; fail explicitly on errors."""
        directory = ROOT / ".cache/player-name-ocr"
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="read-", dir=directory) as temporary:
            paths = []
            for index, image in enumerate(images):
                path = Path(temporary) / f"crop_{index}.png"
                image.save(path)
                paths.append(str(path))
            manifest = Path(temporary) / "inputs.json"
            manifest.write_text(json.dumps(paths), encoding="utf-8")
            result = self._run(["-InputJson", str(manifest)])
        records = result.get("results")
        if not isinstance(records, list) or len(records) != len(images):
            raise RuntimeError("Windows OCR returned an incomplete batch")
        texts = [record.get("text") for record in records]
        if any(not isinstance(text, str) for text in texts):
            raise RuntimeError("Windows OCR returned malformed text")
        return texts


class SNYPlayerNameReader:
    """Read literal names in a fixed SNY layout; never accept feed labels or roster candidates."""

    def __init__(self, backend=None, config=None):
        self.backend = WindowsOCR() if backend is None else backend
        self.config = deepcopy(CONFIG if config is None else config)
        if self.config["schema"] not in SCHEMAS:
            raise ValueError("Unknown player-name reader configuration")

    def metadata(self):
        return {"engine": self.backend.metadata(), "config": deepcopy(self.config)}

    def read(self, frame):
        """Return per-role text and abstentions; wrong dimensions and missing panels are explicit."""
        CONFIG = self.config  # noqa: N806 - the frozen v1 module constant is the default
        if frame.size != tuple(CONFIG["frame_size"]):
            return {role: _abstain("unsupported_frame_size") for role in CONFIG["crops"]}
        frame = frame.convert("RGB")
        white, _, navy = masks(frame)
        if not bug_present(navy, white):
            return {role: _abstain("count_bug_absent") for role in CONFIG["crops"]}
        result, crops, roles = {}, [], []
        dynamic = CONFIG.get("pitcher_dynamic_right_edge")
        frame_pixels = np.asarray(frame).astype(np.int16) if dynamic else None
        for role, box in CONFIG["crops"].items():
            if role == "pitcher" and dynamic:
                x0, y0, _, y1 = box
                box = (x0, y0, dynamic_right_edge(frame_pixels, box, dynamic), y1)
            crop = frame.crop(box)
            pixels = np.asarray(crop).astype(np.int16)
            gate = CONFIG["presence"]
            bright = (pixels.min(axis=2) > gate["min_channel"]) & (
                pixels.max(axis=2) - pixels.min(axis=2) < gate["max_channel_spread"]
            )
            if float(bright.mean()) < gate["min_neutral_bright_fraction"]:
                result[role] = _abstain("name_panel_absent")
                continue
            # A visible glyph touching the crop's right boundary may be a truncated name.
            if (pixels[3:-3, -1].max(axis=1) < 100).sum() >= 3:
                result[role] = _abstain("possible_truncated_name")
                continue
            prep = CONFIG["preprocessing"]
            crop = crop.convert("L").resize(
                (crop.width * prep["scale"], crop.height * prep["scale"]), Image.Resampling.LANCZOS
            )
            if prep.get("binarize_threshold") is not None:
                threshold = prep["binarize_threshold"]
                crop = crop.point(lambda value, limit=threshold: 255 if value > limit else 0)
            crops.append(ImageOps.expand(crop, border=prep["border"], fill=255).convert("RGB"))
            roles.append(role)
        if crops:
            try:
                texts = self.backend.recognize(crops)
                if len(texts) != len(roles):
                    raise ValueError("Incomplete OCR crop batch")
                for role, raw in zip(roles, texts, strict=True):
                    result[role] = parse_panel_text(raw, role, CONFIG.get("options"))
            except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
                # Keep these opportunities in reports; an engine failure is not a missing label.
                for role in roles:
                    result[role] = _abstain(f"engine_error:{type(exc).__name__}:{exc}", error=True)
        return result
