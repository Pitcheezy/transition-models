"""Pre-pitch features built exclusively from a frozen, earlier-season profile."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from src.data.features import CONTINUOUS_FEATURES, PITCH_TYPES
from src.data.preprocess import extract_labels_10class

FEATURE_SCHEMA = "prepitch_profiles_2022_v1"
ACTION_TYPES = ["FF", "SI", "FC", "SL", "ST", "CU", "KC", "CH", "FS"]
STATE_COLUMNS = [
    "pitcher",
    "game_date",
    "balls",
    "strikes",
    "outs_when_up",
    "inning",
    "on_1b",
    "on_2b",
    "on_3b",
    "stand",
    "p_throws",
]


def state_codes(frame: pd.DataFrame) -> np.ndarray:
    """Encode base/out/count in 288 states; inning termination is a separate state."""
    runners = sum(
        frame[f"on_{base}b"].notna().to_numpy(dtype=int) * bit
        for base, bit in ((1, 1), (2, 2), (3, 4))
    )
    return (
        (frame["outs_when_up"].to_numpy(dtype=int) * 8 + runners) * 4
        + frame["balls"].to_numpy(dtype=int)
    ) * 3 + frame["strikes"].to_numpy(dtype=int)


def valid_states(frame: pd.DataFrame) -> np.ndarray:
    """Check availability and legal ranges of pre-pitch state fields."""
    return (
        (
            frame["balls"].isin(range(4))
            & frame["strikes"].isin(range(3))
            & frame["outs_when_up"].isin(range(3))
            & frame["inning"].ge(1)
            & frame["stand"].isin(["L", "R"])
            & frame["p_throws"].isin(["L", "R"])
            & frame["pitcher"].notna()
            & frame["pitch_type"].isin(PITCH_TYPES)
        )
        .fillna(False)
        .to_numpy(dtype=bool)
    )


@dataclass
class OperationalFeatureBuilder:
    """Freeze profile construction before every modeled pitch and share inference code."""

    cutoff: str
    scaler: StandardScaler
    action_profiles: pd.DataFrame
    global_actions: pd.DataFrame
    pitcher_profiles: pd.DataFrame
    global_profiles: dict
    repertoire_counts: pd.DataFrame
    schema: str = FEATURE_SCHEMA

    @classmethod
    def fit(cls, history: pd.DataFrame, cutoff="2022-12-31", shrinkage=50.0):
        """Fit all statistics on past data only; reject accidental future rows."""
        if pd.to_datetime(history["game_date"]).max() > pd.Timestamp(cutoff):
            raise ValueError("Future rows in profile fit")
        history = history.loc[valid_states(history)].copy()
        history = history.dropna(subset=CONTINUOUS_FEATURES + ["zone"])
        history = history.loc[history["zone"].isin(range(1, 15))].copy()
        y = extract_labels_10class(history)
        history = history.loc[y >= 0].reset_index(drop=True)
        y = y[y >= 0]
        if not len(history):
            raise ValueError("Empty profile history")
        scaler = StandardScaler().fit(history[CONTINUOUS_FEATURES].to_numpy())
        z = scaler.transform(history[CONTINUOUS_FEATURES].to_numpy())
        zone = np.eye(14)[history["zone"].to_numpy(dtype=int) - 1]
        features = pd.DataFrame(np.column_stack([z, zone]))
        features["pitcher"] = history["pitcher"].to_numpy(dtype=int)
        features["pitch_type"] = history["pitch_type"].to_numpy()
        features["p_throws"] = history["p_throws"].to_numpy()
        numeric = list(range(29))
        global_actions = features.groupby(["p_throws", "pitch_type"])[numeric].mean()
        action_means = features.groupby(["pitcher", "pitch_type"])[numeric].mean()
        action_counts = features.groupby(["pitcher", "pitch_type"]).size()
        pitcher_hands = history.groupby("pitcher")["p_throws"].first()
        for (pitcher, action), row in action_means.iterrows():
            prior = global_actions.loc[(pitcher_hands.loc[pitcher], action)].to_numpy()
            n = action_counts.loc[(pitcher, action)]
            action_means.loc[(pitcher, action)] = (n * row.to_numpy() + shrinkage * prior) / (
                n + shrinkage
            )
        action_ids = (
            history["pitch_type"].map(dict(zip(PITCH_TYPES, range(17), strict=True))).to_numpy()
        )
        profile_rows = pd.DataFrame(
            np.column_stack([np.eye(17)[action_ids], z, z * z, np.eye(10)[y]])
        )
        profile_rows["pitcher"] = history["pitcher"].to_numpy(dtype=int)
        profile_rows["p_throws"] = history["p_throws"].to_numpy()
        counts = profile_rows.groupby("pitcher").size()
        raw_profiles = profile_rows.groupby("pitcher")[list(range(57))].mean()
        global_profiles = {}
        global_raw = {}
        for hand in ("L", "R"):
            prior = (
                profile_rows.loc[profile_rows["p_throws"] == hand, list(range(57))]
                .mean()
                .to_numpy()
            )
            if not np.isfinite(prior).all():
                prior = profile_rows[list(range(57))].mean().to_numpy()
            global_raw[hand] = prior
            std = np.sqrt(np.maximum(prior[32:47] - prior[17:32] ** 2, 1e-6))
            global_profiles[hand] = np.r_[prior[:32], std, prior[47:57], 0.0]
        result = []
        for pitcher, row in raw_profiles.iterrows():
            hand = pitcher_hands.loc[pitcher]
            prior_row = global_raw[hand]
            n = counts.loc[pitcher]
            mean = (n * row.to_numpy() + shrinkage * prior_row) / (n + shrinkage)
            std = np.sqrt(np.maximum(mean[32:47] - mean[17:32] ** 2, 1e-6))
            result.append(np.r_[mean[:32], std, mean[47:57], np.log1p(n) / 10])
        profiles = pd.DataFrame(result, index=raw_profiles.index)
        repertoire = pd.crosstab(history["pitcher"], history["pitch_type"]).reindex(
            columns=PITCH_TYPES, fill_value=0
        )
        return cls(
            cutoff, scaler, action_means, global_actions, profiles, global_profiles, repertoire
        )

    def build(self, frame: pd.DataFrame, action=None, input_dim=135) -> np.ndarray:
        """Build features without reading any current pitch physics, location, or outcome."""
        if input_dim not in (77, 135):
            raise ValueError("Operational inputs support only 77 or 135 dimensions")
        dates = pd.to_datetime(frame["game_date"])
        if dates.isna().any():
            raise ValueError("Missing decision date")
        if (dates <= pd.Timestamp(self.cutoff)).any():
            raise ValueError("Profile is not earlier than the requested decision")
        action_values = (
            frame["pitch_type"].to_numpy()
            if action is None
            else np.broadcast_to(action, (len(frame),))
        )
        view = frame.copy()
        view["pitch_type"] = action_values
        if not valid_states(view).all():
            raise ValueError("Missing or invalid pre-pitch state/action")
        n = len(frame)
        pitchers = frame["pitcher"].to_numpy(dtype=int)
        hands = frame["p_throws"].to_numpy()
        action_index = pd.MultiIndex.from_arrays([pitchers, action_values])
        estimated = self.action_profiles.reindex(action_index).to_numpy(copy=True)
        missing = ~np.isfinite(estimated).all(axis=1)
        if missing.any():
            fallback = self.global_actions.reindex(
                pd.MultiIndex.from_arrays([hands[missing], action_values[missing]])
            ).to_numpy(copy=True)
            fallback[~np.isfinite(fallback).all(axis=1)] = self.global_actions.mean().to_numpy()
            estimated[missing] = fallback
        x = np.zeros((n, input_dim), dtype=np.float32)
        x[:, :15] = estimated[:, :15]
        action_ids = (
            pd.Series(action_values)
            .map(dict(zip(PITCH_TYPES, range(17), strict=True)))
            .to_numpy(dtype=int)
        )
        x[np.arange(n), 15 + action_ids] = 1
        x[:, 32:46] = estimated[:, 15:29]
        for column, offset in (("balls", 46), ("strikes", 50), ("outs_when_up", 53)):
            x[np.arange(n), offset + frame[column].to_numpy(dtype=int)] = 1
        runners = sum(
            frame[f"on_{base}b"].notna().to_numpy(dtype=int) * bit
            for base, bit in ((1, 1), (2, 2), (3, 4))
        )
        x[np.arange(n), 56 + runners] = 1
        x[np.arange(n), 64 + (frame["stand"].to_numpy() == "R")] = 1
        x[np.arange(n), 66 + (hands == "R")] = 1
        x[np.arange(n), 68 + np.clip(frame["inning"].to_numpy(dtype=int), 1, 9) - 1] = 1
        if input_dim == 135:
            profiles = self.pitcher_profiles.reindex(pitchers).to_numpy(copy=True)
            missing = ~np.isfinite(profiles).all(axis=1)
            for hand in ("L", "R"):
                profiles[missing & (hands == hand)] = self.global_profiles[hand]
            x[:, 77:] = profiles
        if not np.isfinite(x).all():
            raise ValueError("Nonfinite operational features")
        return x

    def available_actions(self, frame: pd.DataFrame, min_count=30) -> np.ndarray:
        """Restrict recommendations to repertoires supported by the earlier season."""
        counts = self.repertoire_counts.reindex(frame["pitcher"].to_numpy(dtype=int)).fillna(0)
        return counts[ACTION_TYPES].to_numpy() >= min_count
