"""Frame-window selection for broadcast clips (no ffmpeg needed)."""

from fractions import Fraction

from intent.broadcast_windows import window_indices

FPS = Fraction(60000, 1001)


def test_window_keeps_every_third_source_frame_around_release():
    keep = window_indices(60.0, FPS)
    assert keep[0] == round(Fraction("58.5") * FPS)
    assert all(b - a == 3 for a, b in zip(keep, keep[1:], strict=False))
    assert keep[-1] <= round(Fraction("61.5") * FPS)
    assert len(keep) in (60, 61)


def test_window_never_starts_before_the_first_frame():
    assert window_indices(0.5, FPS)[0] == 0
