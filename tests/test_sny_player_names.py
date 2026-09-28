"""Image-only name gates and literal parsing, independent of a native OCR installation."""

import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from src.vision.sny_player_names import (
    CONFIG,
    CONFIG_V2,
    CONFIG_V3,
    SNYPlayerNameReader,
    WindowsOCR,
    parse_panel_text,
)


class FakeOCR:
    def __init__(self, texts=None, error=None):
        self.texts = texts if texts is not None else ["SMITH", "7.JONES"]
        self.error = error
        self.calls = []

    def metadata(self):
        return {"engine": "synthetic_test"}

    def recognize(self, images):
        self.calls.append(images)
        if self.error:
            raise self.error
        return self.texts


def synthetic_frame(*, batter=True):
    image = Image.new("RGB", (1280, 720), (30, 80, 30))
    draw = ImageDraw.Draw(image)
    draw.rectangle((60, 32, 300, 33), fill="white")
    draw.rectangle((60, 34, 300, 108), fill=(20, 50, 100))
    for role, box in CONFIG["crops"].items():
        if role != "batter" or batter:
            draw.rectangle(box, fill=(220, 220, 220))
    return image


@pytest.mark.parametrize(
    "raw,role,name,slot",
    [
        ("SMITH", "pitcher", "SMITH", None),
        ("de la cruz", "pitcher", "DE LA CRUZ", None),
        ("6.O'NEILL", "batter", "O'NEILL", 6),
        ("2 JONES", "batter", "JONES", 2),
        ("7.SM1TH", "batter", None, 7),
        ("OZUN…", "pitcher", None, None),
        ("JONES", "batter", None, None),
        ("0.JONES", "batter", None, None),
        ("3.JONES .304", "batter", None, 3),
        ("", "pitcher", None, None),
    ],
)
def test_parser_preserves_raw_text_without_fuzzy_or_roster_correction(raw, role, name, slot):
    result = parse_panel_text(raw, role)
    assert result["raw_text"] == raw
    assert result["name_text"] == name and result["lineup_order"] == slot
    assert result["status"] == ("read" if name else "abstain")


@pytest.mark.parametrize(
    "raw,role,name,slot,reason",
    [
        # Uppercase-only context: the engine's lowercase "l" is a capital "I"; "1" is untouched.
        ("3.VlENTOS", "batter", "VIENTOS", 3, "literal_name"),
        ("MEGlLL", "pitcher", "MEGILL", None, "literal_name"),
        ("7.SM1TH", "batter", None, 7, "name_syntax_or_empty"),
        # Any other lowercase letter means the text is not an uppercase strip: v1 path only.
        ("VlENTOs", "pitcher", "VLENTOS", None, "literal_name"),
        ("de la cruz", "pitcher", "DE LA CRUZ", None, "literal_name"),
        # One unreadable slot character before the separator: name read, slot abstains.
        ("a.VlENTOS", "batter", "VIENTOS", None, "literal_name_slot_unreadable"),
        ("?:JONES", "batter", "JONES", None, "literal_name_slot_unreadable"),
        # A zero is not a lineup slot: it is treated as an unreadable slot character.
        ("0.JONES", "batter", "JONES", None, "literal_name_slot_unreadable"),
        # No separator at all, or nothing after it, keeps the v1 outcome.
        ("JONES", "batter", None, None, "batter_slot_missing"),
        ("a.", "batter", None, None, "batter_slot_missing"),
        ("3.JONES .304", "batter", None, 3, "name_syntax_or_empty"),
    ],
)
def test_v2_parser_options_are_image_side_rules_without_roster_correction(
    raw, role, name, slot, reason
):
    result = parse_panel_text(raw, role, CONFIG_V2["options"])
    assert result["raw_text"] == raw
    assert result["name_text"] == name and result["lineup_order"] == slot
    assert result["status"] == ("read" if name else "abstain") and result["reason"] == reason


@pytest.mark.parametrize("raw,role", [("3.VlENTOS", "batter"), ("a.VlENTOS", "batter")])
def test_v1_parser_is_unchanged_by_the_v2_options(raw, role):
    assert parse_panel_text(raw, role) == parse_panel_text(raw, role, None)
    assert parse_panel_text("3.VlENTOS", "batter")["name_text"] == "VLENTOS"
    assert parse_panel_text("a.VlENTOS", "batter")["reason"] == "batter_slot_missing"
    with pytest.raises(ValueError):
        parse_panel_text(raw, role, {"unknown_option": True})


def test_v2_reader_shares_v1_crops_and_reports_its_own_schema():
    backend = FakeOCR(["MEGlLL", "a.VlENTOS"])
    reader = SNYPlayerNameReader(backend, config=CONFIG_V2)
    result = reader.read(synthetic_frame())
    assert result["pitcher"]["name_text"] == "MEGILL"
    assert result["batter"]["name_text"] == "VIENTOS" and result["batter"]["lineup_order"] is None
    metadata = reader.metadata()["config"]
    assert metadata["schema"] == "sny_player_names_v2" and metadata["crops"] == CONFIG["crops"]
    assert metadata["presence"] == CONFIG["presence"]
    assert "options" not in CONFIG and CONFIG["schema"] == "sny_player_names_v1"
    with pytest.raises(ValueError):
        SNYPlayerNameReader(backend, config={**CONFIG, "schema": "sny_player_names_v9"})


def test_v3_changes_only_the_preprocessing_handed_to_the_engine():
    backend = FakeOCR(["MEGlLL", "a.VlENTOS"])
    frame = synthetic_frame()
    ImageDraw.Draw(frame).rectangle((80, 115, 90, 125), fill=(90, 90, 90))  # mid-gray glyph
    reader = SNYPlayerNameReader(backend, config=CONFIG_V3)
    result = reader.read(frame)
    # Parser rules are the v2 ones; only the images differ.
    assert result["pitcher"]["name_text"] == "MEGILL" and result["batter"]["name_text"] == "VIENTOS"
    metadata = reader.metadata()["config"]
    assert (
        metadata["schema"] == "sny_player_names_v3" and metadata["options"] == CONFIG_V2["options"]
    )
    assert metadata["crops"] == CONFIG["crops"] and metadata["presence"] == CONFIG["presence"]
    assert (
        metadata["preprocessing"]["scale"] == 6
        and metadata["preprocessing"]["binarize_threshold"] == 100
    )
    images = backend.calls[0]
    x0, y0, x1, y1 = CONFIG["crops"]["pitcher"]
    assert images[0].size == ((x1 - x0) * 6 + 32, (y1 - y0) * 6 + 32)
    assert set(images[0].convert("L").getdata()) == {0, 255}
    # v1 and v2 keep the 4x grayscale image with intermediate values.
    v2 = FakeOCR(["SMITH", "7.JONES"])
    SNYPlayerNameReader(v2, config=CONFIG_V2).read(frame)
    assert v2.calls[0][0].size == ((x1 - x0) * 4 + 32, (y1 - y0) * 4 + 32)
    assert len(set(v2.calls[0][0].convert("L").getdata())) > 2
    assert "binarize_threshold" not in CONFIG["preprocessing"]


def test_reader_gets_only_image_crops_and_keeps_a_wrong_literal():
    backend = FakeOCR(["WRONGNAME", "7.JONES"])
    result = SNYPlayerNameReader(backend).read(synthetic_frame())
    assert result["pitcher"]["name_text"] == "WRONGNAME"
    assert result["batter"]["lineup_order"] == 7
    assert len(backend.calls) == 1 and len(backend.calls[0]) == 2
    assert all(isinstance(image, Image.Image) for image in backend.calls[0])


def test_absent_batter_panel_never_calls_ocr_for_batter():
    backend = FakeOCR(["SMITH"])
    result = SNYPlayerNameReader(backend).read(synthetic_frame(batter=False))
    assert result["batter"]["name_text"] is None
    assert result["batter"]["reason"] == "name_panel_absent"
    assert len(backend.calls[0]) == 1


@pytest.mark.parametrize("frame", [Image.new("RGB", (1280, 720)), Image.new("RGB", (640, 360))])
def test_missing_bug_or_unsupported_size_never_calls_engine(frame):
    backend = FakeOCR()
    result = SNYPlayerNameReader(backend).read(frame)
    assert all(item["status"] == "abstain" for item in result.values())
    assert not backend.calls


def test_truncated_edge_is_not_accepted_as_a_complete_name():
    backend = FakeOCR(["7.JONES"])
    frame = synthetic_frame()
    x0, y0, x1, y1 = CONFIG["crops"]["pitcher"]
    ImageDraw.Draw(frame).line((x1 - 1, y0 + 4, x1 - 1, y1 - 5), fill="black", width=1)
    result = SNYPlayerNameReader(backend).read(frame)
    assert result["pitcher"]["reason"] == "possible_truncated_name"


def test_engine_errors_retain_both_role_opportunities():
    result = SNYPlayerNameReader(FakeOCR(error=RuntimeError("test failure"))).read(
        synthetic_frame()
    )
    assert set(result) == {"pitcher", "batter"}
    assert all(item["status"] == "error" and item["name_text"] is None for item in result.values())


def test_metadata_cannot_mutate_reader_configuration():
    reader = SNYPlayerNameReader(FakeOCR())
    reader.metadata()["config"]["crops"]["pitcher"][0] = 0
    assert CONFIG["crops"]["pitcher"][0] == 64


def test_cached_absent_and_context_frames_are_gated_without_native_ocr():
    root = Path(__file__).resolve().parents[1]
    paths = [
        root / "outputs/frames/evalset_481.00.jpg",
        root
        / "outputs/frames/source_17c052ca18fba3dfb2c99b6954e3ff7c9a3acbc4f3d03662cd9917a32af1b23d/neg_470.000.jpg",
    ]
    if not all(path.is_file() for path in paths):
        pytest.skip("Local development frames are not stored in Git")
    backend = FakeOCR(["SMITH"])
    reader = SNYPlayerNameReader(backend)
    with Image.open(paths[0]) as frame:
        assert reader.read(frame)["batter"]["reason"] == "name_panel_absent"
    with Image.open(paths[1]) as frame:
        assert all(item["reason"] == "count_bug_absent" for item in reader.read(frame).values())
    assert len(backend.calls) == 1


@pytest.mark.skipif(sys.platform != "win32", reason="Optional native Windows OCR bridge")
def test_native_bridge_preserves_empty_singleton_and_multi_image_batches():
    try:
        engine = WindowsOCR()
    except RuntimeError as exc:
        pytest.skip(f"Optional Windows OCR en-US engine unavailable: {exc}")
    blank = Image.new("RGB", (128, 64), "white")
    assert engine.recognize([]) == []
    assert engine.recognize([blank]) == [""]
    assert engine.recognize([blank, blank]) == ["", ""]
