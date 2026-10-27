"""The seed identity cue abstains unless a dark, textured, non-skin patch is present."""

import numpy as np
import pytest

from intent.mitt_seed_identity import (
    SCHEMA,
    IdentityParams,
    accepts,
    assess_patch,
    luminance,
    skin_mask,
)

# Recorded development colours from the CV37b observation sheets (AI readings, not truth):
# the tracked bare-hand blob of 747139:3:1 and the dark object beside it.
HAND_RGB = (188, 152, 144)
MITT_RGB = (84, 81, 96)


def scene(colour, *, noise=20, size=(120, 160), background=(60, 110, 60), seed=3):
    rng = np.random.default_rng(seed)
    image = np.empty((*size, 3), np.uint8)
    image[...] = background
    # Shading-like texture: one brightness offset per pixel keeps the patch's hue intact.
    patch = np.array(colour, np.int16) + rng.integers(-noise, noise + 1, (21, 21, 1), np.int16)
    image[50:71, 70:91] = np.clip(patch, 0, 255).astype(np.uint8)
    return image


def test_recorded_bare_hand_colour_is_hand_like_and_dark_object_is_mitt_like():
    hand = assess_patch(scene(HAND_RGB), [80, 60])
    mitt = assess_patch(scene(MITT_RGB), [80, 60])
    assert (hand["verdict"], hand["reason"]) == ("hand_like", "skin_fraction_high")
    assert (mitt["verdict"], mitt["reason"]) == ("mitt_like", "dark_low_skin_textured")
    assert hand["skin_fraction"] >= 0.5 and mitt["skin_fraction"] <= 0.1
    assert mitt["mean_luminance"] <= 110 and mitt["texture_std"] >= 0.03
    assert hand["schema"] == mitt["schema"] == SCHEMA
    assert hand["mitt_identity"] == mitt["mitt_identity"] == "unverified"
    assert not accepts(hand) and accepts(mitt)


def test_flat_patch_is_unclear_even_when_dark():
    cue = assess_patch(scene(MITT_RGB, noise=0), [80, 60])
    assert (cue["verdict"], cue["reason"]) == ("unclear", "low_texture")
    assert cue["texture_std"] < 0.03 and not accepts(cue)


def test_mixed_patch_and_bright_patch_are_unclear():
    image = scene(MITT_RGB)
    image[50:71, 70:80] = HAND_RGB  # roughly half skin, half dark
    mixed = assess_patch(image, [80, 60])
    assert mixed["verdict"] == "unclear" and mixed["reason"] == "mixed"
    bright = assess_patch(scene((200, 200, 210)), [80, 60])
    assert bright["verdict"] == "unclear" and bright["reason"] == "mixed"
    assert bright["mean_luminance"] > 110


def test_border_point_abstains_without_statistics():
    cue = assess_patch(scene(MITT_RGB), [5, 60])
    assert (cue["verdict"], cue["reason"], cue["patch_box"]) == ("unclear", "patch_border", None)
    assert cue["skin_fraction"] is None and not accepts(cue)


def test_only_the_patch_is_read_and_rounding_is_half_up():
    image = scene(MITT_RGB)
    cue = assess_patch(image, [80.4, 59.6])
    assert cue["point_px"] == [80, 60] and cue["patch_box"] == [70, 50, 90, 70]
    altered = image.copy()
    altered[:40] = HAND_RGB  # skin far away from the patch
    altered[90:] = 250
    assert assess_patch(altered, [80.4, 59.6]) == cue
    shifted = assess_patch(image, [80.5, 60])
    assert shifted["point_px"] == [81, 60] and shifted != cue


def test_invalid_inputs_are_rejected():
    image = scene(MITT_RGB)
    with pytest.raises(ValueError, match="RGB"):
        assess_patch(image[..., 0], [80, 60])
    with pytest.raises(ValueError, match="RGB"):
        assess_patch(image.astype(np.float32), [80, 60])
    with pytest.raises(ValueError, match="point_px"):
        assess_patch(image, [80])
    with pytest.raises(ValueError, match="point_px"):
        assess_patch(image, [float("nan"), 60])
    with pytest.raises(ValueError, match="point_px"):
        assess_patch(image, [True, 60])
    with pytest.raises(ValueError, match="params"):
        assess_patch(image, [80, 60], params={"patch_size": 21})
    with pytest.raises(ValueError, match="RGB"):
        skin_mask(np.zeros((4, 4), np.uint8))
    with pytest.raises(ValueError, match="verdict"):
        accepts({"verdict": "mitt"})


def test_params_are_validated_and_digested():
    assert IdentityParams().digest() == IdentityParams(patch_size=21).digest()
    assert IdentityParams().digest() != IdentityParams(mitt_max_luminance=100).digest()
    with pytest.raises(ValueError):
        IdentityParams(patch_size=20)
    with pytest.raises(ValueError):
        IdentityParams(hand_skin_fraction_min=0.1, mitt_skin_fraction_max=0.5)
    with pytest.raises(ValueError):
        IdentityParams(mitt_max_luminance=300)
    with pytest.raises(ValueError):
        IdentityParams(skin_r_min=-1)
    with pytest.raises(ValueError):
        IdentityParams(min_texture=True)


def test_skin_rule_and_luminance_match_their_definitions():
    pixels = np.array([[[188, 152, 144], [84, 81, 96], [96, 41, 21], [200, 190, 180]]], np.uint8)
    # (96, 41, 21) satisfies every clause of the published rule; (200, 190, 180) fails |R-G|.
    assert skin_mask(pixels).tolist() == [[True, False, True, False]]
    assert luminance(np.array([[[255, 255, 255]]], np.float64))[0, 0] == pytest.approx(255.0)
    assert luminance(np.array([[[0, 255, 0]]], np.float64))[0, 0] == pytest.approx(0.587 * 255)
