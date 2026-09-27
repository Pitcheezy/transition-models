"""Keep blind exports answer-free and independent submissions source/identity bound."""

import json
from copy import deepcopy
from zipfile import ZipFile

import pytest

from src.data.blind_review import (
    INPUTS,
    REVIEWER_ASSETS,
    ROOT,
    build_package,
    check_package,
    core_sample,
    freeze_protocol,
    package_files,
    read_json,
    template_from_protocol,
    validate_response,
)


@pytest.fixture(scope="module")
def protocol():
    inputs = {name: read_json(ROOT / path) for name, path in INPUTS.items()}
    return freeze_protocol(inputs, "ed56f9b1ac7d943ec7ffa217fafeb31cfbbbb55d")


@pytest.fixture
def template(protocol):
    return template_from_protocol(protocol)


def reviewed(template):
    document = deepcopy(template)
    document["reviewer"] = {
        "name": "Test reviewer (synthetic)",
        "kind": "human",
        "reviewed_at": "2026-09-27",
        "prior_reference_exposure": False,
    }
    document["rows"][0].update(
        status="annotated",
        decision_seconds=10.25,
        release_seconds=12.5,
        uncertainty_seconds=0.15,
        readability="partial",
        note="Synthetic test data only: boundary, continuity and release inspected",
    )
    document["rows"][0]["observed"].update(balls=0, runner_on_1b=False)
    return document


def test_selection_is_answer_independent_and_order_independent(protocol):
    manifest = read_json(ROOT / INPUTS["manifest"])
    before = [(r["at_bat_number"], r["pitch_number"]) for r in core_sample(manifest["pitches"])]
    changed = deepcopy(manifest["pitches"])[::-1]
    for row in changed:
        row["pre_state"] = "CHANGED ANSWER"
        row["ground_truth"] = "CHANGED ANSWER"
    after = [(r["at_bat_number"], r["pitch_number"]) for r in core_sample(changed)]
    assert before == after
    assert len(set(before)) == 32
    assert len(protocol["selection"]["boundary"]) == 12


def test_template_and_archive_export_allowlist(protocol, tmp_path):
    polluted = deepcopy(protocol)
    polluted["source"]["pre_state"] = "SECRET_ANSWER_SENTINEL"
    polluted["verification_notes"] = "SECRET_ANSWER_SENTINEL"
    for row in polluted["selection"]["core"] + polluted["selection"]["boundary"]:
        row.update(decision_seconds=9001.234567, observed="SECRET_ANSWER_SENTINEL")
    exported = template_from_protocol(polluted)
    clean = template_from_protocol(protocol)
    assert exported["rows"] == clean["rows"]
    assert exported["source"] == clean["source"]
    assert exported["protocol_sha256"] != clean["protocol_sha256"]
    files = package_files(polluted)
    for content in files.values():
        assert b"SECRET_ANSWER_SENTINEL" not in content
        assert b"9001.234567" not in content
        assert b"__BLIND_REVIEW_" not in content
    result = build_package(protocol, tmp_path)
    assert result["unreviewed"] == result["selected"]
    assert result["complete"] is False
    assert result == check_package(protocol, tmp_path)
    assert build_package(protocol, tmp_path) == result
    with ZipFile(tmp_path / "reviewer.zip") as archive:
        assert set(archive.namelist()) == {"index.html", "README.md", "review.json"}
    (tmp_path / "review.json").write_text("reviewer's edited draft", encoding="utf-8")
    with pytest.raises(ValueError, match="overwrite"):
        build_package(protocol, tmp_path)
    with pytest.raises(ValueError, match="changed"):
        check_package(protocol, tmp_path)


def test_draft_complete_and_exposure_are_not_agreement(template):
    report = validate_response(template, template)
    assert not report["complete"]
    with pytest.raises(ValueError, match="Reviewer"):
        validate_response(template, template, require_complete=True)
    response = reviewed(template)
    with pytest.raises(ValueError, match="incomplete"):
        validate_response(response, template, require_complete=True)
    for row in response["rows"]:
        row.update(status="unavailable", note="Synthetic absence reason", readability=None)
        for name in ("decision_seconds", "release_seconds", "uncertainty_seconds"):
            row[name] = None
        row["observed"] = dict.fromkeys(row["observed"])
    response["reviewer"]["prior_reference_exposure"] = True
    response["rows"].reverse()
    report = validate_response(response, template, require_complete=True)
    assert report["complete"] and report["prior_reference_exposure"]
    assert "agreement" not in report


@pytest.mark.parametrize("change", ["missing", "duplicate", "wrong-play", "wrong-key", "bool-key"])
def test_response_requires_exact_identity_roster(template, change):
    response = deepcopy(template)
    if change == "missing":
        response["rows"].pop()
    elif change == "duplicate":
        response["rows"].append(deepcopy(response["rows"][0]))
    elif change == "wrong-play":
        response["rows"][0]["play_id"] = "another-play"
    elif change == "wrong-key":
        response["rows"][0]["at_bat_number"] = 999
    else:
        response["rows"][0]["pitch_number"] = True
    with pytest.raises(ValueError):
        validate_response(response, template)


@pytest.mark.parametrize(
    "change", ["source", "package", "assets", "top-extra", "row-extra", "reviewer-extra"]
)
def test_reject_source_changes_and_extra_fields(template, change):
    response = deepcopy(template)
    if change == "source":
        response["source"]["media_url"] += "?different"
    elif change == "package":
        response["package_id"] = "different"
    elif change == "assets":
        response["reviewer_assets_sha256"] = "0" * 64
    elif change == "top-extra":
        response["ground_truth"] = {}
    elif change == "row-extra":
        response["rows"][0]["pre_state"] = {}
    else:
        response["reviewer"]["unexpected"] = True
    with pytest.raises(ValueError):
        validate_response(response, template)


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -1, 10.3, 10000])
def test_reject_bad_decision_timing(template, value):
    response = reviewed(template)
    response["rows"][0]["decision_seconds"] = value
    with pytest.raises(ValueError):
        validate_response(response, template)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("balls", True),
        ("balls", 4),
        ("strikes", 3),
        ("outs", -1),
        ("inning", 0),
        ("runner_on_1b", 0),
        ("home_score", "0"),
        ("inning_topbot", "bottom"),
    ],
)
def test_readings_are_typed_and_bounded(template, field, value):
    response = reviewed(template)
    response["rows"][0]["observed"][field] = value
    with pytest.raises(ValueError, match="observed"):
        validate_response(response, template)


def test_status_readability_and_chronology(template):
    response = reviewed(template)
    assert validate_response(response, template)["annotated"] == 1
    for name, value in (("status", "unavailable"), ("readability", "readable"), ("note", "")):
        bad = deepcopy(response)
        bad["rows"][0][name] = value
        with pytest.raises(ValueError):
            validate_response(bad, template)
    bad = deepcopy(response)
    bad["rows"][1].update(
        {
            k: v
            for k, v in bad["rows"][0].items()
            if k not in ("game_pk", "at_bat_number", "pitch_number", "play_id")
        }
    )
    with pytest.raises(ValueError, match="chronological"):
        validate_response(bad, template)


def test_json_rejects_duplicate_fields_and_nonfinite_numbers(tmp_path):
    path = tmp_path / "input.json"
    for content in ('{"rows":[],"rows":[]}', '{"value":NaN}'):
        path.write_text(content, encoding="utf-8")
        with pytest.raises(ValueError):
            read_json(path)
    path.write_text(json.dumps({"zero": 0, "false": False, "unknown": None}), encoding="utf-8")
    assert read_json(path) == {"zero": 0, "false": False, "unknown": None}


@pytest.mark.parametrize("value", [-10, 0, True, float("nan"), float("inf"), "9340"])
def test_invalid_protocol_duration_is_rejected(protocol, value):
    bad = deepcopy(protocol)
    bad["source"]["duration_seconds"] = value
    with pytest.raises(ValueError, match="duration"):
        template_from_protocol(bad)


def test_empty_selection_and_changed_protocol_are_rejected(protocol, template):
    bad = deepcopy(protocol)
    bad["selection"]["core"] = []
    with pytest.raises(ValueError, match="stratum"):
        template_from_protocol(bad)
    bad = deepcopy(protocol)
    bad["comparison"]["threshold_role"] = "Changed after review"
    with pytest.raises(ValueError, match="match package"):
        validate_response(template, template_from_protocol(bad))


def copy_reviewer_assets(tmp_path, monkeypatch):
    """Use isolated assets so regressions never modify the actual reviewer package."""
    for name in REVIEWER_ASSETS:
        content = (ROOT / name).read_text(encoding="utf-8")
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode("utf-8"))
    monkeypatch.setattr("src.data.blind_review.ROOT", tmp_path)


@pytest.mark.parametrize("asset", REVIEWER_ASSETS)
def test_asset_changes_bind_package_and_reject_previous_response(
    protocol, tmp_path, monkeypatch, asset
):
    copy_reviewer_assets(tmp_path, monkeypatch)
    original_protocol = deepcopy(protocol)
    previous = template_from_protocol(protocol)
    target = tmp_path / asset
    target.write_bytes(target.read_bytes() + b"\nChanged reviewer instructions or renderer.\n")
    current = template_from_protocol(protocol)
    assert current["reviewer_assets_sha256"] != previous["reviewer_assets_sha256"]
    assert current["package_id"] != previous["package_id"]
    assert current["protocol_sha256"] == previous["protocol_sha256"]
    assert current["rows"] == previous["rows"]
    assert protocol == original_protocol
    assert json.loads(package_files(protocol)["review.json"]) == current
    with pytest.raises(ValueError, match="match package"):
        validate_response(previous, current)


def test_asset_binding_and_package_content_are_newline_independent(protocol, tmp_path, monkeypatch):
    copy_reviewer_assets(tmp_path, monkeypatch)
    lf_template = template_from_protocol(protocol)
    lf_files = package_files(protocol)
    for name in REVIEWER_ASSETS:
        target = tmp_path / name
        target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))
    assert template_from_protocol(protocol) == lf_template
    assert package_files(protocol) == lf_files


def test_unbound_v1_response_is_explicitly_rejected(template):
    old_response = deepcopy(template)
    old_response["schema"] = "mlb_blind_review_v1"
    old_response.pop("reviewer_assets_sha256")
    with pytest.raises(ValueError, match="unbound v1 responses are unsupported"):
        validate_response(old_response, template)
