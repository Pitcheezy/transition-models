"""Feature mapping and label conversion for transition probability models.

This module provides:
- Label mapping functions (4-class for Otremba 2022, 10-class for MIT Sloan 2025)
- Hit location mapping (9-class)
- Feature definitions (continuous, categorical, one-hot dimensions)
- Pitch vector builder skeleton (87-dim for Model C)
"""

import numpy as np
import pandas as pd


# =============================================================================
# 1. Label classes
# =============================================================================


class PitchResult4:
    """Otremba 2022의 4-class pitch outcome."""

    BALL = 0
    STRIKE = 1
    FOUL = 2
    IN_PLAY = 3

    NAMES = {0: "Ball", 1: "Strike", 2: "Foul", 3: "InPlay"}
    NUM_CLASSES = 4


class PitchResult10:
    """MIT Sloan 2025의 10-class pitch outcome."""

    BALL = 0
    STRIKE = 1
    SINGLE = 2
    DOUBLE = 3
    TRIPLE = 4
    HOME_RUN = 5
    FIELD_OUT = 6
    STRIKEOUT = 7
    WALK = 8
    HIT_BY_PITCH = 9

    NAMES = {
        0: "Ball",
        1: "Strike",
        2: "Single",
        3: "Double",
        4: "Triple",
        5: "HomeRun",
        6: "FieldOut",
        7: "Strikeout",
        8: "Walk",
        9: "HitByPitch",
    }
    NUM_CLASSES = 10


# =============================================================================
# 2. Label mapping dictionaries
# =============================================================================

# description → 4-class (Otremba 2022)
# 주의: hit_by_pitch → Ball (논문 따름, 사사구와 동일 취급)
DESCRIPTION_TO_4CLASS: dict[str, int] = {
    "ball": PitchResult4.BALL,
    "blocked_ball": PitchResult4.BALL,
    "pitchout": PitchResult4.BALL,
    "automatic_ball": PitchResult4.BALL,
    "hit_by_pitch": PitchResult4.BALL,
    "called_strike": PitchResult4.STRIKE,
    "swinging_strike": PitchResult4.STRIKE,
    "swinging_strike_blocked": PitchResult4.STRIKE,
    "foul_tip": PitchResult4.STRIKE,
    "missed_bunt": PitchResult4.STRIKE,
    "bunt_foul_tip": PitchResult4.STRIKE,
    "automatic_strike": PitchResult4.STRIKE,
    "foul": PitchResult4.FOUL,
    "foul_bunt": PitchResult4.FOUL,
    "hit_into_play": PitchResult4.IN_PLAY,
}

# events → 10-class (MIT Sloan 2025)
# field_error → FIELD_OUT (수비 에러지만 투구 결과 관점에서 InPlay 아웃 시도)
# catcher_interf → WALK (타자 출루, 사사구와 유사)
# intent_walk → WALK
# truncated_pa는 매핑하지 않음 (비정상 타석, 제거 대상)
EVENTS_TO_10CLASS: dict[str, int] = {
    "single": PitchResult10.SINGLE,
    "double": PitchResult10.DOUBLE,
    "triple": PitchResult10.TRIPLE,
    "home_run": PitchResult10.HOME_RUN,
    "field_out": PitchResult10.FIELD_OUT,
    "force_out": PitchResult10.FIELD_OUT,
    "grounded_into_double_play": PitchResult10.FIELD_OUT,
    "double_play": PitchResult10.FIELD_OUT,
    "fielders_choice": PitchResult10.FIELD_OUT,
    "fielders_choice_out": PitchResult10.FIELD_OUT,
    "sac_fly": PitchResult10.FIELD_OUT,
    "sac_bunt": PitchResult10.FIELD_OUT,
    "sac_fly_double_play": PitchResult10.FIELD_OUT,
    "triple_play": PitchResult10.FIELD_OUT,
    "field_error": PitchResult10.FIELD_OUT,
    "strikeout": PitchResult10.STRIKEOUT,
    "strikeout_double_play": PitchResult10.STRIKEOUT,
    "walk": PitchResult10.WALK,
    "intent_walk": PitchResult10.WALK,
    "catcher_interf": PitchResult10.WALK,
    "hit_by_pitch": PitchResult10.HIT_BY_PITCH,
}

# description → 10-class fallback (events가 NaN인 mid-AB pitches용)
# Foul → Strike에 매핑 (MIT Sloan 논문에 별도 Foul 클래스 없음)
_DESCRIPTION_TO_10CLASS: dict[str, int] = {
    "called_strike": PitchResult10.STRIKE,
    "swinging_strike": PitchResult10.STRIKE,
    "swinging_strike_blocked": PitchResult10.STRIKE,
    "foul_tip": PitchResult10.STRIKE,
    "missed_bunt": PitchResult10.STRIKE,
    "bunt_foul_tip": PitchResult10.STRIKE,
    "automatic_strike": PitchResult10.STRIKE,
    "foul": PitchResult10.STRIKE,
    "foul_bunt": PitchResult10.STRIKE,
    "ball": PitchResult10.BALL,
    "blocked_ball": PitchResult10.BALL,
    "pitchout": PitchResult10.BALL,
    "automatic_ball": PitchResult10.BALL,
    "hit_by_pitch": PitchResult10.HIT_BY_PITCH,
    "hit_into_play": None,  # events 컬럼으로만 분류 가능
}


# =============================================================================
# 3. Mapping functions
# =============================================================================


def map_to_4class(description: str | None) -> int | None:
    """Map Statcast description to Otremba 2022 4-class label.

    Args:
        description: Statcast ``description`` column value.

    Returns:
        0-3 (Ball/Strike/Foul/InPlay) or None if unmappable.
    """
    if description is None or pd.isna(description):
        return None
    return DESCRIPTION_TO_4CLASS.get(description)


def map_to_10class(description: str | None, events: str | None) -> int | None:
    """Map Statcast description + events to MIT Sloan 2025 10-class label.

    Priority: events > description.
    Foul is mapped to Strike (no separate Foul class in the paper).

    Args:
        description: Statcast ``description`` column value.
        events: Statcast ``events`` column value (non-null only on AB-ending pitches).

    Returns:
        0-9 label or None if unmappable.
    """
    # 1순위: events (타석 종료 pitch에만 존재)
    if events is not None and not pd.isna(events):
        if events in EVENTS_TO_10CLASS:
            return EVENTS_TO_10CLASS[events]
        # truncated_pa 등 매핑 불가 events
        return None

    # 2순위: description (mid-AB pitches)
    if description is None or pd.isna(description):
        return None
    return _DESCRIPTION_TO_10CLASS.get(description)


def map_hit_location(hit_location: float | None) -> int | None:
    """Map Statcast hit_location (1-9) to 0-indexed class (0-8).

    Args:
        hit_location: Statcast ``hit_location`` column value (1-9 or NaN).

    Returns:
        0-8 or None if not available.
    """
    if hit_location is None or pd.isna(hit_location):
        return None
    return int(hit_location) - 1


# =============================================================================
# 4. Feature definitions
# =============================================================================

# Model C (MIT Sloan 2025) 87차원 pitch vector 구성 요소
CONTINUOUS_FEATURES: list[str] = [
    # 투구 물리량 (15개)
    "release_speed",
    "release_pos_x",
    "release_pos_y",
    "release_pos_z",
    "pfx_x",
    "pfx_z",
    "release_spin_rate",
    "plate_x",
    "plate_z",
    "vx0",
    "vy0",
    "vz0",
    "ax",
    "ay",
    "az",
]

# 구종 one-hot (17종, Statcast 2023-2024 기준)
PITCH_TYPES: list[str] = [
    "CH",  # Changeup
    "CS",  # Slow Curve
    "CU",  # Curveball
    "EP",  # Eephus
    "FA",  # Fastball (generic)
    "FC",  # Cutter
    "FF",  # Four-Seam Fastball
    "FO",  # Forkball
    "FS",  # Splitter
    "KC",  # Knuckle Curve
    "KN",  # Knuckleball
    "PO",  # Pitchout
    "SC",  # Screwball
    "SI",  # Sinker
    "SL",  # Slider
    "ST",  # Sweeper
    "SV",  # Slurve
]

ZONES: list[int] = list(range(1, 15))  # 1~14 (14개)
COUNTS_BALLS: list[int] = [0, 1, 2, 3]  # 4개
COUNTS_STRIKES: list[int] = [0, 1, 2]  # 3개
OUTS: list[int] = [0, 1, 2]  # 3개
HANDEDNESS: list[str] = ["L", "R"]  # 2개 (투수/타자 각각)

# 차원 합계:
# 연속 15 + pitch_type 17 + zone 14 + balls 4 + strikes 3 + outs 3
# + stand 2 + p_throws 2 + 기타(inning, score 등) ≈ 87
# 정확한 87차원 구성은 논문 재확인 후 build_pitch_vector에서 확정


# =============================================================================
# 5. Vector builder (skeleton)
# =============================================================================


def build_pitch_vector(row: pd.Series, scaler=None) -> np.ndarray:
    """Convert a single pitch row into an 87-dim feature vector.

    Composition (approximate):
    - Continuous features (15) — standardized if scaler provided
    - pitch_type one-hot (17)
    - zone one-hot (14)
    - balls one-hot (4)
    - strikes one-hot (3)
    - outs one-hot (3)
    - stand one-hot (2)
    - p_throws one-hot (2)
    - Additional context features (~27)

    Args:
        row: A single row from Statcast DataFrame.
        scaler: Optional fitted scaler for continuous features.

    Returns:
        1-D numpy array of shape (87,).

    Raises:
        NotImplementedError: 현재 골격만 존재, Phase 4에서 구현 예정.
    """
    raise NotImplementedError("Phase 4에서 구현 예정")
