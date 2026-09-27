"""Synthetic OCR outputs exercise frozen real opportunities; these are not measured OCR scores."""

import importlib.util
import json
import sys
from copy import deepcopy

import pytest
from PIL import Image

from src.data.blind_review import read_json
from src.data.player_identity import ROOT, bytes_hash
from src.evaluation import player_identity_ocr as ocr
from src.vision.frames import CACHE_SCHEMA

EVALSET = ROOT / "docs/results/mlb_p0/game_747139_player_identity_evalset_pa6.json"
SCRIPT = ROOT / "scripts/74_evaluate_player_identity_ocr.py"
TIMES = (481, 525.5, 548.95, 576.5, 611.45, 663.5, 470)


def reading(name=None, slot=None, *, status=None):
    return {
        "raw_text": name or "",
        "name_text": name,
        "lineup_order": slot,
        "status": status or ("read" if name else "abstain"),
        "reason": "synthetic_test",
    }


class SyntheticReader:
    """Use pixel markers only to make engine-independent, deterministic test outputs."""

    def __init__(self):
        self.calls = []

    def metadata(self):
        return {"engine": "synthetic_test_only", "version": "1", "config": {"marker_pixel": True}}

    def read(self, frame):
        assert isinstance(frame, Image.Image)
        marker = frame.getpixel((0, 0))[0]
        self.calls.append(marker)
        return {
            "pitcher": reading("MEGILL") if marker < 6 else reading(),
            "batter": reading("OZUNA", 3) if 0 < marker < 6 else reading(),
        }


@pytest.fixture
def sample(monkeypatch):
    evalset = read_json(EVALSET)
    monkeypatch.setattr(
        ocr,
        "_image",
        lambda evidence, root: Image.new(
            "RGB", (2, 2), (TIMES.index(evidence["frame_seconds"]), 0, 0)
        ),
    )
    reader = SyntheticReader()
    predictions = ocr.build_predictions(evalset, reader)
    return evalset, predictions, reader


def batter(predictions, pitch):
    return next(
        row
        for row in predictions["predictions"]
        if row["role"] == "batter" and row["pitch_number"] == pitch
    )


def test_image_only_reader_and_separate_denominators(sample):
    evalset, predictions, reader = sample
    assert reader.calls == list(range(7))  # Two roles use one image call; context is separate.
    assert all("resolved_player_id" not in row for row in predictions["predictions"])
    report = ocr.score_predictions(evalset, predictions)
    assert report["names"]["opportunities"] == report["identities"]["opportunities"] == 12
    for field in ("names", "identities"):
        assert report[field]["reference_evaluable"] == report[field]["correct"] == 11
        assert report[field]["abstain"] == 1
        assert report[field]["wrong"] == 0
    assert report["lineup"]["opportunities"] == 6
    assert report["lineup"]["correct"] == 5
    assert report["lineup"]["abstain"] == 1
    assert report["context_diagnostics"]["opportunities"] == 1
    assert report["pipeline_matches_current_code"]


@pytest.mark.parametrize("name,candidates", [("OZUNX", []), ("IGLESIAS", [578428, 628452])])
def test_wrong_literal_not_hidden_by_unresolved_identity(sample, name, candidates):
    evalset, predictions, _ = sample
    batter(predictions, 2).update(reading(name, 3))
    report = ocr.score_predictions(evalset, predictions)
    assert report["names"]["wrong"] == 1
    assert report["identities"]["abstain"] == 2
    row = next(row for row in report["rows"] if row["name_text"] == name)
    assert row["raw_text"] == name
    assert row["candidate_ids"] == candidates


def test_full_name_identity_and_literal_scores_are_distinct(sample):
    evalset, predictions, _ = sample
    batter(predictions, 2).update(reading("Marcell Ozuna", 3))
    report = ocr.score_predictions(evalset, predictions)
    assert report["names"]["wrong"] == 1
    assert report["identities"]["correct"] == 11


def test_absent_name_and_partial_context_cannot_be_successes_via_feed(sample):
    evalset, predictions, _ = sample
    batter(predictions, 1).update(reading("OZUNA", 3))
    predictions["context_predictions"][0].update(reading("OZUNA", 3))
    report = ocr.score_predictions(evalset, predictions)
    assert report["names"]["correct"] == report["identities"]["correct"] == 11
    assert report["names"]["false_reads_without_evaluable_reference"] == 1
    assert report["identities"]["false_reads_without_evaluable_reference"] == 1
    assert report["lineup"]["false_reads_without_evaluable_reference"] == 1
    row = next(
        row for row in report["rows"] if row["role"] == "batter" and row["pitch_number"] == 1
    )
    assert row["matches_hindsight_reference"] is True
    assert row["name_verdict"] == row["id_verdict"] == "wrong"
    assert report["context_diagnostics"]["name_false_read"] == 1
    assert report["context_diagnostics"]["id_false_read"] == 1
    assert report["names"]["opportunities"] == 12


def test_name_abstention_can_keep_independent_lineup_read(sample):
    evalset, predictions, _ = sample
    batter(predictions, 2).update(reading(None, 3))
    report = ocr.score_predictions(evalset, predictions)
    assert report["names"]["abstain"] == 2
    assert report["lineup"]["correct"] == 5


def test_engine_failures_retained_in_main_and_context(sample):
    evalset, predictions, _ = sample
    batter(predictions, 2).update(reading(status="error"))
    predictions["context_predictions"][0].update(reading(status="error"))
    report = ocr.score_predictions(evalset, predictions)
    assert report["reader_errors"] == 1
    assert report["context_diagnostics"]["reader_errors"] == 1
    assert report["names"]["opportunities"] == 12


def test_shuffled_records_score_by_pitch_identity(sample):
    evalset, predictions, _ = sample
    before = ocr.score_predictions(evalset, predictions)
    predictions["predictions"].reverse()
    after = ocr.score_predictions(evalset, predictions)
    assert before["rows"] == after["rows"]
    assert before["names"] == after["names"]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "extra_id",
        "play_id",
        "evidence",
        "source",
        "metadata",
        "evalset",
        "lineup_bool",
        "abstain_name",
        "error_lineup",
        "read_missing_name",
        "code_manifest",
    ],
)
def test_reject_unbound_incomplete_or_contradictory_predictions(sample, mutation):
    evalset, predictions, _ = sample
    row = batter(predictions, 2)
    if mutation == "missing":
        predictions["predictions"].pop()
    elif mutation == "duplicate":
        predictions["predictions"].append(deepcopy(row))
    elif mutation == "extra_id":
        row["resolved_player_id"] = 542303
    elif mutation == "play_id":
        row["play_id"] = "wrong"
    elif mutation == "evidence":
        row["evidence"]["image_sha256"] = "0" * 64
    elif mutation == "source":
        predictions["source"]["media_url"] = "https://example.invalid/wrong.mp4"
    elif mutation == "metadata":
        predictions["reader_metadata"]["version"] = "changed"
    elif mutation == "evalset":
        predictions["evalset_sha256"] = "0" * 64
    elif mutation == "lineup_bool":
        row["lineup_order"] = True
    elif mutation == "abstain_name":
        row["status"] = "abstain"
    elif mutation == "error_lineup":
        row.update(reading(None, 3, status="error"))
    elif mutation == "read_missing_name":
        row.update(reading(None, status="read"))
    elif mutation == "code_manifest":
        predictions["pipeline_code_sha256"].pop("src/data/player_identity.py")
    with pytest.raises(ValueError):
        ocr.score_predictions(evalset, predictions)


def test_exact_frame_proof_and_hash(tmp_path):
    path = tmp_path / "synthetic.jpg"
    Image.new("RGB", (3, 3), "blue").save(path)
    digest = bytes_hash(path.read_bytes())
    evidence = {
        "path": path.name,
        "image_sha256": digest,
        "media_url": "https://example.invalid/test.mp4",
        "frame_seconds": 10.5,
    }
    path.with_suffix(".jpg.json").write_text(
        json.dumps(
            {
                "schema": CACHE_SCHEMA,
                "media_url": evidence["media_url"],
                "frame_seconds": 10.5,
                "sha256": digest,
            }
        ),
        encoding="utf-8",
    )
    assert ocr._image(evidence, tmp_path).size == (3, 3)
    with pytest.raises(ValueError, match="proof"):
        ocr._image({**evidence, "media_url": "https://example.invalid/other.mp4"}, tmp_path)
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="bytes"):
        ocr._image(evidence, tmp_path)


def test_code_provenance_is_stable_across_checkout_line_endings(monkeypatch, tmp_path):
    path = tmp_path / ocr.CODE_PATHS[0]
    path.parent.mkdir(parents=True)
    monkeypatch.setattr(ocr, "ROOT", tmp_path)
    path.write_bytes(b"line one\nline two\n")
    unix = ocr._code_hashes()
    path.write_bytes(b"line one\r\nline two\r\n")
    assert ocr._code_hashes() == unix
    path.write_bytes(b"line changed\r\nline two\r\n")
    assert ocr._code_hashes() != unix


@pytest.fixture
def cli():
    spec = importlib.util.spec_from_file_location("player_ocr_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "command,option,protected",
    [
        ("predict", "--predictions", "DEFAULT_EVALSET"),
        ("predict", "--predictions", "DEFAULT_REPORT"),
        ("score", "--report", "DEFAULT_EVALSET"),
        ("score", "--report", "DEFAULT_PREDICTIONS"),
    ],
)
def test_cli_protects_inputs_before_engine_or_reads(cli, monkeypatch, command, option, protected):
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), command, option, str(getattr(cli, protected))])
    with pytest.raises(SystemExit) as caught:
        cli.main()
    assert caught.value.code == 2


@pytest.mark.parametrize(
    "command,output",
    [
        ("predict", None),
        ("score", None),
        ("predict", "DEFAULT_PREDICTIONS"),
        ("score", "DEFAULT_REPORT"),
    ],
)
def test_cli_custom_evalset_needs_separate_output(cli, monkeypatch, tmp_path, command, output):
    args = [str(SCRIPT), command, "--evalset", str(tmp_path / "custom.json")]
    if output:
        args.extend(
            ["--predictions" if command == "predict" else "--report", str(getattr(cli, output))]
        )
    monkeypatch.setattr(sys, "argv", args)
    with pytest.raises(SystemExit) as caught:
        cli.main()
    assert caught.value.code == 2


def test_cli_saved_predictions_score_and_check_without_ocr(cli, monkeypatch, tmp_path, sample):
    _, predictions, _ = sample
    prediction_path, report_path = tmp_path / "predictions.json", tmp_path / "report.json"
    prediction_path.write_text(json.dumps(predictions), encoding="utf-8")
    options = ["--predictions", str(prediction_path), "--report", str(report_path)]
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "score", *options])
    cli.main()
    assert read_json(report_path)["names"]["correct"] == 11
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "check", *options])
    cli.main()
    report = read_json(report_path)
    report["names"]["correct"] = 12
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="fresh keyed score"):
        cli.main()
