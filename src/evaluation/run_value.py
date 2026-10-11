"""Historical run expectancy and observed one-pitch run-value costs."""

import numpy as np
import pandas as pd

from src.data.operational import state_codes, valid_states
from src.data.preprocess import extract_labels_10class

HALF_KEYS = ["game_pk", "inning", "inning_topbot"]
OUT_COUNTS = {
    "strikeout": 1,
    "field_out": 1,
    "force_out": 1,
    "fielders_choice_out": 1,
    "sac_fly": 1,
    "sac_bunt": 1,
    "caught_stealing_2b": 1,
    "caught_stealing_3b": 1,
    "caught_stealing_home": 1,
    "pickoff_1b": 1,
    "pickoff_2b": 1,
    "pickoff_3b": 1,
    "pickoff_caught_stealing_2b": 1,
    "pickoff_caught_stealing_3b": 1,
    "pickoff_caught_stealing_home": 1,
    "grounded_into_double_play": 2,
    "double_play": 2,
    "strikeout_double_play": 2,
    "sac_fly_double_play": 2,
    "sac_bunt_double_play": 2,
    "triple_play": 3,
}


def observed_transitions(raw: pd.DataFrame) -> pd.DataFrame:
    """Extract adjacent observed states from completed half innings, before feature filtering."""
    raw = raw.loc[raw["inning"].between(1, 8)]
    frame = raw.sort_values(HALF_KEYS + ["at_bat_number", "pitch_number"]).copy()
    groups = frame.groupby(HALF_KEYS, sort=False, dropna=False)
    last = groups.tail(1).copy()
    last["complete"] = last["outs_when_up"] + last["events"].map(OUT_COUNTS).fillna(0) >= 3
    last["end_score"] = last["post_bat_score"]
    frame = frame.merge(
        last[HALF_KEYS + ["complete", "end_score"]],
        on=HALF_KEYS,
        how="left",
        validate="many_to_one",
        sort=False,
    )
    legal = valid_states(frame)
    code = np.full(len(frame), -1, dtype=int)
    code[legal] = state_codes(frame.loc[legal])
    frame["state_code"] = code
    frame["next_state"] = (
        frame.groupby(HALF_KEYS, sort=False)["state_code"].shift(-1).fillna(288).astype(int)
    )
    next_score = frame.groupby(HALF_KEYS, sort=False)["bat_score"].shift(-1)
    consistent_score = next_score.isna() | (next_score == frame["post_bat_score"])
    frame["runs"] = frame["post_bat_score"] - frame["bat_score"]
    frame["remaining_runs"] = frame["end_score"] - frame["bat_score"]
    frame["label_10"] = extract_labels_10class(frame)
    valid = (
        legal
        & frame["complete"]
        & frame["next_state"].ge(0)
        & consistent_score
        & frame["runs"].between(0, 4)
        & frame["remaining_runs"].ge(0)
        & frame["label_10"].ge(0)
    )
    return frame.loc[valid].reset_index(drop=True)


def fit_run_expectancy(history: pd.DataFrame, strength=100.0) -> np.ndarray:
    """Fit base-out-count expectancy with base-out shrinkage from earlier completed innings."""
    state = history["state_code"].to_numpy(dtype=int)
    future = history["remaining_runs"].to_numpy(dtype=float)
    base = state // 12
    base_n = np.bincount(base, minlength=24)
    base_sum = np.bincount(base, weights=future, minlength=24)
    base_mean = np.divide(base_sum, base_n, out=np.full(24, future.mean()), where=base_n > 0)
    n = np.bincount(state, minlength=288)
    sums = np.bincount(state, weights=future, minlength=288)
    values = (sums + strength * np.repeat(base_mean, 12)) / (n + strength)
    return np.r_[values, 0.0]


def transition_cost(frame: pd.DataFrame, expectancy: np.ndarray) -> np.ndarray:
    """Return runs plus next-state expectancy minus current expectancy; lower is better."""
    return (
        frame["runs"].to_numpy(dtype=float)
        + expectancy[frame["next_state"].to_numpy(dtype=int)]
        - expectancy[frame["state_code"].to_numpy(dtype=int)]
    )


def fallback_transition(state: int, outcome: int) -> tuple[int, float]:
    """Supply a legal baseball fallback for unobserved state/outcome cells."""
    base, count = divmod(state, 12)
    outs, runners = divmod(base, 8)
    balls, strikes = divmod(count, 3)
    runs = 0
    if outcome == 0 and balls < 3:
        balls += 1
    elif outcome == 1:
        strikes = min(strikes + 1, 2)
    else:
        balls = strikes = 0
        if outcome in (0, 8, 9):
            if runners & 1:
                if runners & 2:
                    if runners & 4:
                        runs += 1
                    runners |= 4
                runners |= 2
            runners |= 1
        elif outcome in (6, 7):
            outs += 1
        elif outcome == 5:
            runs = runners.bit_count() + 1
            runners = 0
        elif outcome in (2, 3, 4):
            advance = outcome - 1
            moved = runners << advance
            runs = (moved >> 3).bit_count()
            runners = (moved & 7) | (1 << (advance - 1))
    if outs >= 3:
        return 288, float(runs)
    return ((outs * 8 + runners) * 4 + balls) * 3 + strikes, float(runs)


def fit_outcome_costs(history: pd.DataFrame, expectancy: np.ndarray, strength=20.0) -> np.ndarray:
    """Estimate outcome-conditioned costs from independent earlier-season observations."""
    prior = np.zeros((288, 10))
    for state in range(288):
        for outcome in range(10):
            nxt, runs = fallback_transition(state, outcome)
            prior[state, outcome] = runs + expectancy[nxt] - expectancy[state]
    indices = history["state_code"].to_numpy(dtype=int) * 10 + history["label_10"].to_numpy(
        dtype=int
    )
    n = np.bincount(indices, minlength=2880).reshape(288, 10)
    sums = np.bincount(
        indices, weights=transition_cost(history, expectancy), minlength=2880
    ).reshape(288, 10)
    return (sums + strength * prior) / (n + strength)
