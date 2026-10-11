"""Versioned pitch-observation targets, separate from terminal PA transitions."""

import numpy as np
import pandas as pd

from src.data.mlb_video import PITCH_KEYS

OBSERVATION_SCHEMA = "pitch_observation_v1"
OBSERVATION_CLASSES = [
    "ball",
    "called_strike",
    "swinging_strike",
    "foul",
    "caught_foul_tip",
    "hit",
    "in_play_no_hit",
    "hit_by_pitch",
]
DESCRIPTION_LABELS = {
    "ball": "ball",
    "blocked_ball": "ball",
    "pitchout": "ball",
    "intent_ball": "ball",
    "called_strike": "called_strike",
    "swinging_strike": "swinging_strike",
    "swinging_strike_blocked": "swinging_strike",
    "missed_bunt": "swinging_strike",
    "foul": "foul",
    "foul_bunt": "foul",
    "foul_tip": "caught_foul_tip",
    "bunt_foul_tip": "caught_foul_tip",
    "hit_by_pitch": "hit_by_pitch",
}
HIT_EVENTS = {"single", "double", "triple", "home_run"}
NO_HIT_EVENTS = {
    "field_out",
    "force_out",
    "grounded_into_double_play",
    "sac_fly",
    "field_error",
    "sac_bunt",
    "fielders_choice",
    "double_play",
    "fielders_choice_out",
    "sac_fly_double_play",
    "triple_play",
    "sac_bunt_double_play",
}


def build_observation_targets(frame):
    """Return keyed targets; unrecognized/administrative rows are explicitly excluded."""
    keys = frame[PITCH_KEYS]
    if (
        keys.isna().any().any()
        or keys.duplicated().any()
        or not np.isfinite(keys.to_numpy(dtype=float)).all()
        or (keys.to_numpy(dtype=float) % 1 != 0).any()
        or (keys.to_numpy(dtype=float) <= 0).any()
    ):
        raise ValueError("Pitch targets require unique positive integral pitch IDs")
    result = keys.astype("int64").copy()
    description, events = frame["description"], frame["events"]
    label = description.map(DESCRIPTION_LABELS)
    in_play = description.eq("hit_into_play")
    label.loc[in_play & events.isin(HIT_EVENTS)] = "hit"
    label.loc[in_play & events.isin(NO_HIT_EVENTS)] = "in_play_no_hit"
    reason = pd.Series("", index=frame.index, dtype=object)
    reason.loc[label.isna()] = "unknown_description_or_inplay_event"
    administrative = description.isin(["automatic_ball", "automatic_strike"])
    reason.loc[administrative] = "administrative_no_physical_pitch"
    interference = events.eq("catcher_interf")
    label.loc[interference] = None
    reason.loc[interference] = "catcher_interference_requires_separate_transition"
    result["observation"] = label
    result["target"] = (
        label.map({name: i for i, name in enumerate(OBSERVATION_CLASSES)}).fillna(-1).astype(int)
    )
    result["exclusion_reason"] = reason
    # Do not overwrite the observation with the terminal PA result (e.g. foul bunt K).
    result["pa_event"] = events
    return result
