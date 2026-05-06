"""Unit tests for src/data/features.py label mapping functions."""

import pytest

from src.data.features import (
    DESCRIPTION_TO_4CLASS,
    EVENTS_TO_10CLASS,
    PitchResult4,
    PitchResult10,
    map_hit_location,
    map_to_4class,
    map_to_10class,
)


# =============================================================================
# map_to_4class
# =============================================================================


class TestMapTo4Class:
    """4-class 매핑 테스트 (Otremba 2022)."""

    def test_strike_types(self):
        """모든 strike 유형이 STRIKE로 매핑."""
        strike_descs = [
            "called_strike",
            "swinging_strike",
            "swinging_strike_blocked",
            "foul_tip",
            "missed_bunt",
            "bunt_foul_tip",
            "automatic_strike",
        ]
        for desc in strike_descs:
            assert map_to_4class(desc) == PitchResult4.STRIKE, f"{desc} should be STRIKE"

    def test_ball_types(self):
        """모든 ball 유형이 BALL로 매핑."""
        ball_descs = ["ball", "blocked_ball", "pitchout", "automatic_ball"]
        for desc in ball_descs:
            assert map_to_4class(desc) == PitchResult4.BALL, f"{desc} should be BALL"

    def test_hbp_is_ball(self):
        """HBP는 Ball 그룹 (Otremba 논문 따름)."""
        assert map_to_4class("hit_by_pitch") == PitchResult4.BALL

    def test_foul_types(self):
        """Foul 유형이 FOUL로 매핑."""
        assert map_to_4class("foul") == PitchResult4.FOUL
        assert map_to_4class("foul_bunt") == PitchResult4.FOUL

    def test_in_play(self):
        """hit_into_play가 IN_PLAY로 매핑."""
        assert map_to_4class("hit_into_play") == PitchResult4.IN_PLAY

    def test_none_returns_none(self):
        assert map_to_4class(None) is None

    def test_nan_returns_none(self):
        import math

        assert map_to_4class(float("nan")) is None
        assert map_to_4class(math.nan) is None

    def test_unknown_returns_none(self):
        """알 수 없는 description은 None."""
        assert map_to_4class("unknown_value") is None

    def test_all_15_descriptions_covered(self):
        """Statcast의 15개 description 값 모두 매핑 가능."""
        all_descs = [
            "ball", "blocked_ball", "pitchout", "automatic_ball", "hit_by_pitch",
            "called_strike", "swinging_strike", "swinging_strike_blocked",
            "foul_tip", "missed_bunt", "bunt_foul_tip", "automatic_strike",
            "foul", "foul_bunt", "hit_into_play",
        ]
        for desc in all_descs:
            result = map_to_4class(desc)
            assert result is not None, f"{desc} should be mappable"
            assert 0 <= result <= 3, f"{desc} mapped to invalid value {result}"


# =============================================================================
# map_to_10class
# =============================================================================


class TestMapTo10Class:
    """10-class 매핑 테스트 (MIT Sloan 2025)."""

    def test_events_priority_over_description(self):
        """events가 있으면 description보다 우선."""
        assert map_to_10class("hit_into_play", "single") == PitchResult10.SINGLE
        assert map_to_10class("hit_into_play", "home_run") == PitchResult10.HOME_RUN
        assert map_to_10class("hit_into_play", "field_out") == PitchResult10.FIELD_OUT

    def test_description_fallback_strike(self):
        """events NaN이면 description 기반 매핑."""
        assert map_to_10class("called_strike", None) == PitchResult10.STRIKE
        assert map_to_10class("swinging_strike", None) == PitchResult10.STRIKE

    def test_foul_maps_to_strike(self):
        """Foul은 Strike로 매핑 (논문에 별도 Foul 클래스 없음)."""
        assert map_to_10class("foul", None) == PitchResult10.STRIKE
        assert map_to_10class("foul_bunt", None) == PitchResult10.STRIKE

    def test_ball_description(self):
        assert map_to_10class("ball", None) == PitchResult10.BALL
        assert map_to_10class("blocked_ball", None) == PitchResult10.BALL

    def test_hit_events(self):
        """안타 유형 매핑."""
        assert map_to_10class("hit_into_play", "single") == PitchResult10.SINGLE
        assert map_to_10class("hit_into_play", "double") == PitchResult10.DOUBLE
        assert map_to_10class("hit_into_play", "triple") == PitchResult10.TRIPLE
        assert map_to_10class("hit_into_play", "home_run") == PitchResult10.HOME_RUN

    def test_out_events_all_map_to_field_out(self):
        """아웃 관련 events가 모두 FIELD_OUT으로."""
        out_events = [
            "field_out", "force_out", "grounded_into_double_play",
            "double_play", "fielders_choice", "fielders_choice_out",
            "sac_fly", "sac_bunt", "sac_fly_double_play", "triple_play",
            "field_error",
        ]
        for ev in out_events:
            assert map_to_10class("hit_into_play", ev) == PitchResult10.FIELD_OUT, (
                f"{ev} should be FIELD_OUT"
            )

    def test_strikeout_events(self):
        assert map_to_10class(None, "strikeout") == PitchResult10.STRIKEOUT
        assert map_to_10class(None, "strikeout_double_play") == PitchResult10.STRIKEOUT

    def test_walk_events(self):
        assert map_to_10class(None, "walk") == PitchResult10.WALK
        assert map_to_10class(None, "intent_walk") == PitchResult10.WALK
        assert map_to_10class(None, "catcher_interf") == PitchResult10.WALK

    def test_hbp(self):
        assert map_to_10class(None, "hit_by_pitch") == PitchResult10.HIT_BY_PITCH

    def test_truncated_pa_returns_none(self):
        """truncated_pa는 매핑 불가 (제거 대상)."""
        assert map_to_10class(None, "truncated_pa") is None

    def test_none_none_returns_none(self):
        assert map_to_10class(None, None) is None


# =============================================================================
# map_hit_location
# =============================================================================


class TestMapHitLocation:
    """Hit location 매핑 테스트."""

    def test_valid_locations(self):
        for loc in range(1, 10):
            assert map_hit_location(loc) == loc - 1

    def test_none_returns_none(self):
        assert map_hit_location(None) is None

    def test_float_nan_returns_none(self):
        assert map_hit_location(float("nan")) is None


# =============================================================================
# Dictionary completeness
# =============================================================================


class TestDictionaryCompleteness:
    """매핑 사전 완전성 검증."""

    def test_4class_covers_all_descriptions(self):
        """15개 Statcast description 모두 포함."""
        assert len(DESCRIPTION_TO_4CLASS) == 15

    def test_10class_covers_all_events(self):
        """truncated_pa 제외 21개 events 모두 포함."""
        # 22개 events 중 truncated_pa 제외 = 21개
        assert len(EVENTS_TO_10CLASS) == 21

    def test_4class_values_valid(self):
        """4-class 매핑값이 모두 0~3 범위."""
        for val in DESCRIPTION_TO_4CLASS.values():
            assert 0 <= val <= 3

    def test_10class_values_valid(self):
        """10-class 매핑값이 모두 0~9 범위."""
        for val in EVENTS_TO_10CLASS.values():
            assert 0 <= val <= 9
