"""Synthetic image-only reader tests; no native OCR, external model or video calls."""

import copy
import hashlib
import json

import pytest
from PIL import Image

from intent.mitt_frame_ocr import run
from src.vision.sny_player_names import CONFIG_V2


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def seal(args):
    pack = args["pack"]
    files = {
        p.relative_to(pack).as_posix(): {"sha256": sha(p), "bytes": p.stat().st_size}
        for p in pack.rglob("*")
        if p.is_file() and p.name != "receipt.json"
    }
    save(
        pack / "receipt.json",
        {
            "schema": "pitcheezy-track-frame-view-receipt-v1",
            "independent_decoded_pts_verified": False,
            "files": files,
        },
    )
    args["receipt_sha256"] = sha(pack / "receipt.json")


def fixture_pack(tmp_path, count=5, indices=None):
    pack = tmp_path / "source"
    folder = pack / "frames/747139_3_1"
    folder.mkdir(parents=True)
    frames = []
    for i, index in enumerate(indices or [600 + 6 * i for i in range(count)]):
        path = folder / f"{index}.jpg"
        Image.new("RGB", (1280, 720), (i * 20, 30, 50)).save(path)
        seconds = index * 1001 / 60000
        frames.append(
            {
                "frame_index": index,
                "frame_seconds": seconds,
                "image": path.relative_to(pack).as_posix(),
                "sha256": sha(path),
                "width": 1280,
                "height": 720,
                "selection": {
                    "pitch_id": "747139:3:1",
                    "frame_index": index,
                    "frame_seconds": seconds,
                },
            }
        )
    save(
        pack / "payload.json",
        {
            "schema": "pitcheezy-track-frame-view-dev-v1",
            "time_basis": "manifest_index_timebase",
            "independent_decoded_pts_verified": False,
            "pitches": [{"pitch_id": "747139:3:1", "frames": frames}],
        },
    )
    args = {"pack": pack, "out": tmp_path / "new-output"}
    seal(args)
    return args


def reading(name="MEGILL", *, status=None, reason=None):
    status = status or ("read" if name else "abstain")
    return {
        "raw_text": name or "",
        "name_text": name,
        "lineup_order": None,
        "status": status,
        "reason": reason or ("literal_name" if name else "name_panel_absent"),
    }


class Reader:
    def __init__(self, outputs=None):
        self.outputs = outputs
        self.calls = self.metadata_calls = 0

    def metadata(self):
        self.metadata_calls += 1
        return {
            "config": copy.deepcopy(CONFIG_V2),
            "engine": {"engine": "synthetic", "language": "en-US", "path": "PRIVATE_SECRET"},
        }

    def read(self, image):
        assert isinstance(image, Image.Image) and image.size == (1280, 720)
        i = self.calls
        self.calls += 1
        output = (
            self.outputs[i] if self.outputs else {role: reading() for role in ("pitcher", "batter")}
        )
        if isinstance(output, Exception):
            raise output
        return output


def rows(args):
    return read(args["out"] / "observations.json")["rows"]


def test_current_literal_observations_preserve_inputs_and_do_not_infer_identity(tmp_path):
    args = fixture_pack(tmp_path)
    original = {p: p.read_bytes() for p in args["pack"].rglob("*") if p.is_file()}
    reader = Reader()
    report = run(**args, reader=reader)
    assert reader.calls == report["frames"] == 5
    assert report["input_unchanged"] is True
    assert report["independent_decoded_pts_verified"] is False
    assert report["evidence_kind"] == "injected reader test"
    assert report["observations_sha256"] == sha(args["out"] / "observations.json")
    assert all(path.read_bytes() == content for path, content in original.items())
    observed = rows(args)
    assert observed[0]["roles"]["pitcher"]["temporal_relation"] == "not_compared"
    assert all(
        row["roles"]["pitcher"]["temporal_relation"] == "literal_same" for row in observed[1:]
    )
    assert observed[1]["roles"]["pitcher"]["compared_to_frame"] == 600
    assert "PRIVATE_SECRET" not in (args["out"] / "report.json").read_text()
    assert not any(
        "player_id" in role or "continuity" in role
        for row in observed
        for role in row["roles"].values()
    )


def test_literal_changes_and_role_specific_abstentions_reset_only_that_role(tmp_path):
    args = fixture_pack(tmp_path)
    pitcher = ["MEGILL", "MEGILL", None, "MEGILL", "IGLESIAS"]
    batter = ["OZUNA", "OLSON", "OLSON", "OLSON", "OLSON"]
    outputs = [
        {"pitcher": reading(p), "batter": reading(b)} for p, b in zip(pitcher, batter, strict=True)
    ]
    run(**args, reader=Reader(outputs))
    observed = rows(args)
    assert [r["roles"]["pitcher"]["temporal_relation"] for r in observed] == [
        "not_compared",
        "literal_same",
        "not_compared",
        "not_compared",
        "literal_changed",
    ]
    assert observed[2]["roles"]["pitcher"]["name_text"] is None
    assert observed[1]["roles"]["batter"]["temporal_relation"] == "literal_changed"
    assert observed[2]["roles"]["batter"]["temporal_relation"] == "literal_same"


def test_time_gap_breaks_comparison_without_filling_missing_frames(tmp_path):
    args = fixture_pack(tmp_path, indices=[600, 614, 629, 635])
    run(**args, reader=Reader())
    assert [r["roles"]["pitcher"]["temporal_relation"] for r in rows(args)] == [
        "not_compared",
        "literal_same",
        "not_compared",
        "literal_same",
    ]


def test_reader_exceptions_and_error_messages_are_sanitized_and_remain_in_denominator(tmp_path):
    args = fixture_pack(tmp_path)
    error = reading(
        None, status="error", reason=r"engine_error:RuntimeError:C:\private\TOKEN_VALUE"
    )
    outputs = [
        {"pitcher": reading(), "batter": reading()},
        RuntimeError(r"C:\private\TOKEN_VALUE"),
        {"pitcher": error, "batter": reading()},
        {"pitcher": reading(), "batter": reading()},
        {"pitcher": reading(), "batter": reading()},
    ]
    report = run(**args, reader=Reader(outputs))
    observed = rows(args)
    assert report["frames"] == 5
    assert report["roles"]["pitcher"]["error"] == 2
    assert report["roles"]["batter"]["error"] == 1
    assert observed[1]["roles"]["pitcher"]["reason"] == "reader_exception:RuntimeError"
    assert observed[2]["roles"]["pitcher"]["reason"] == "engine_error:RuntimeError"
    assert observed[3]["roles"]["pitcher"]["temporal_relation"] == "not_compared"
    for filename in ("observations.json", "report.json"):
        text = (args["out"] / filename).read_text()
        assert "TOKEN_VALUE" not in text and "private" not in text


def test_prefix_outputs_do_not_depend_on_later_reads(tmp_path):
    full = fixture_pack(tmp_path / "full", count=5)
    prefix = fixture_pack(tmp_path / "prefix", count=3)
    run(**full, reader=Reader())
    run(**prefix, reader=Reader())
    assert rows(prefix) == rows(full)[:3]


@pytest.mark.parametrize(
    "change",
    [
        "receipt",
        "payload_bytes",
        "last_image",
        "path_escape",
        "duplicate",
        "reverse",
        "wrong_pitch",
        "bad_ticks",
        "wrong_size",
    ],
)
def test_bad_inputs_are_rejected_before_any_reader_metadata_or_read(tmp_path, change):
    args = fixture_pack(tmp_path)
    payload_path = args["pack"] / "payload.json"
    payload = read(payload_path)
    frames = payload["pitches"][0]["frames"]
    if change == "receipt":
        args["receipt_sha256"] = "0" * 64
    elif change == "payload_bytes":
        payload_path.write_bytes(payload_path.read_bytes() + b" ")
    elif change == "last_image":
        path = args["pack"] / frames[-1]["image"]
        path.write_bytes(path.read_bytes() + b"changed")
    else:
        if change == "path_escape":
            frames[0]["image"] = "../../outside.jpg"
        elif change == "duplicate":
            frames.insert(1, frames[0])
        elif change == "reverse":
            frames[0], frames[1] = frames[1], frames[0]
        elif change == "wrong_pitch":
            frames[0]["selection"]["pitch_id"] = "747139:3:2"
        elif change == "bad_ticks":
            frames[0]["frame_seconds"] += 0.001
        else:
            path = args["pack"] / frames[0]["image"]
            Image.new("RGB", (640, 360)).save(path)
            frames[0]["sha256"] = sha(path)
        save(payload_path, payload)
        seal(args)
    reader = Reader()
    with pytest.raises(ValueError):
        run(**args, reader=reader)
    assert reader.calls == reader.metadata_calls == 0
    assert not args["out"].exists()


def test_existing_output_is_not_replaced(tmp_path):
    args = fixture_pack(tmp_path)
    args["out"].mkdir()
    sentinel = args["out"] / "keep.txt"
    sentinel.write_text("keep")
    reader = Reader()
    with pytest.raises(FileExistsError):
        run(**args, reader=reader)
    assert sentinel.read_text() == "keep" and reader.calls == reader.metadata_calls == 0


def test_reader_cannot_mutate_an_input_and_still_get_success(tmp_path):
    args = fixture_pack(tmp_path)

    class Mutator(Reader):
        def read(self, image):
            result = super().read(image)
            path = args["pack"] / "payload.json"
            path.write_bytes(path.read_bytes() + b" ")
            return result

    with pytest.raises(ValueError, match="input changed"):
        run(**args, reader=Mutator())
    assert not args["out"].exists()


def test_malformed_one_role_is_an_error_without_discarding_valid_other_role(tmp_path):
    args = fixture_pack(tmp_path, count=1)
    report = run(
        **args, reader=Reader([{"pitcher": {"status": "read"}, "batter": reading("OZUNA")}])
    )
    assert report["roles"]["pitcher"]["error"] == 1
    assert rows(args)[0]["roles"]["batter"]["name_text"] == "OZUNA"
