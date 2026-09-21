"""Strict pre-pitch inputs and honest presentation of the legacy ten-class model."""

from dataclasses import asdict, dataclass, fields
from datetime import date
from math import isfinite
from numbers import Real

import pandas as pd

from src.data.point_data import CLASS_NAMES


@dataclass(frozen=True)
class PrePitchState:
    """Represent only facts available before a pitch; actual pitch data is forbidden."""

    game_date: str
    pitcher: int
    balls: int
    strikes: int
    outs_when_up: int
    inning: int
    stand: str
    p_throws: str
    batter: int | None = None
    on_1b: int | None = None
    on_2b: int | None = None
    on_3b: int | None = None
    inning_topbot: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    home_team: str | None = None
    away_team: str | None = None

    @classmethod
    def from_dict(cls, payload):
        """Reject coercion, post-pitch fields, missing required values and invalid states."""
        if not isinstance(payload, dict):
            raise ValueError("State must be a JSON object")
        unknown = set(payload) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown or post-pitch fields: {', '.join(sorted(unknown))}")
        try:
            state = cls(**payload)
        except TypeError as exc:
            raise ValueError(f"Missing required state fields: {exc}") from exc
        if not isinstance(state.game_date, str):
            raise ValueError("game_date must be YYYY-MM-DD")
        try:
            parsed = date.fromisoformat(state.game_date)
        except ValueError as exc:
            raise ValueError("game_date must be YYYY-MM-DD") from exc
        if parsed.isoformat() != state.game_date:
            raise ValueError("game_date must be YYYY-MM-DD")
        ranges = {
            "pitcher": (1, 2**31 - 1),
            "balls": (0, 3),
            "strikes": (0, 2),
            "outs_when_up": (0, 2),
            "inning": (1, 30),
        }
        for name, (low, high) in ranges.items():
            value = getattr(state, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} must be an integer from {low} to {high}")
        for name in ("batter", "on_1b", "on_2b", "on_3b", "home_score", "away_score"):
            value = getattr(state, name)
            low = 0 if name.endswith("score") else 1
            if value is not None and (type(value) is not int or not low <= value < 2**31):
                raise ValueError(f"{name} must be null or an integer >= {low}")
        for name in ("stand", "p_throws"):
            if getattr(state, name) not in ("L", "R"):
                raise ValueError(f"{name} must be L or R")
        if state.inning_topbot not in (None, "Top", "Bot"):
            raise ValueError("inning_topbot must be Top, Bot, or null")
        for name in ("home_team", "away_team"):
            value = getattr(state, name)
            if value is not None and (
                not isinstance(value, str)
                or not 1 <= len(value) <= 8
                or not value.isascii()
                or not value.isalpha()
            ):
                raise ValueError(f"{name} must be a short ASCII team code or null")
        runners = [v for v in (state.on_1b, state.on_2b, state.on_3b) if v is not None]
        if len(set(runners)) != len(runners) or state.batter in runners:
            raise ValueError("Runner IDs must be distinct and cannot equal the batter")
        return state

    def to_frame(self):
        """Create the one-row input expected by the frozen operational feature builder."""
        return pd.DataFrame([asdict(self)])


def present_legacy_probabilities(probabilities):
    """Preserve class semantics; unavailable requested marginals remain null."""
    if not isinstance(probabilities, dict) or set(probabilities) != set(CLASS_NAMES):
        raise ValueError("Expected exactly the canonical ten probability classes")
    values = list(probabilities.values())
    if any(
        isinstance(v, bool) or not isinstance(v, Real) or not isfinite(v) or not 0 <= v <= 1
        for v in values
    ):
        raise ValueError("Probabilities must be finite numbers in [0, 1]")
    if abs(sum(values) - 1) > 1e-5:
        raise ValueError("Probabilities must sum to 1")
    raw = {name: float(probabilities[name]) for name in CLASS_NAMES}
    return {
        "schema": "prepitch_probabilities_v1",
        "legacy_probabilities": raw,
        "display_probabilities": {
            "strike": None,
            "ball": None,
            "foul": None,
            "hit": sum(raw[k] for k in ("Single", "Double", "Triple", "HomeRun")),
        },
        "limitations": [
            "Legacy Strike includes nonterminal fouls; terminal strikeouts are separate.",
            "Legacy Ball excludes terminal walks; requested strike/ball/foul marginals are unavailable.",
            "Hit means an unconditional recorded hit on the next pitch, not hit given contact.",
        ],
    }
