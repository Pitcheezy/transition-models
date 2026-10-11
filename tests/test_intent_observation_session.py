"""Synthetic contracts for measured AI observations; no AI results or accuracy are fabricated."""

import json

import pytest
from PIL import Image

from intent import observation_session as obs


def write(path, document):
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


@pytest.fixture
def source(tmp_path, monkeypatch):
    frame = tmp_path / "private_pitch_1.jpg"
    Image.new("RGB", (100, 80)).save(frame)
    receipt = write(
        frame.with_suffix(".jpg.json"),
        dict(
            schema=obs.CACHE_SCHEMA,
            media_url="https://example.test/video",
            frame_seconds=12.5,
            sha256=obs._sha256(frame.read_bytes()),
        ),
    )
    monkeypatch.setattr(obs.time, "monotonic_ns", lambda: 10_000_000_000)
    monkeypatch.setattr(obs.time, "time_ns", lambda: 1_700_000_000_000_000_000)
    return frame, receipt, tmp_path / "outputs/cv_observation_test"


def start(source):
    frame, receipt, out = source
    return obs.begin(frame, 12.5, out, receipt)


def response(source, request, **changes):
    doc = dict(
        schema=obs.RESPONSE_SCHEMA,
        observation_id=request["observation_id"],
        image_sha256=request["image_sha256"],
        status="marked",
        mitt=[20.0, 30.0],
        visibility="partial",
        pose="resting",
        reason="synthetic contract fixture",
    )
    doc.update(changes)
    return write(source[2] / "response.json", doc)


def test_begin_is_source_only_and_exclusive(source):
    request = start(source)
    assert request.keys() == {
        "schema",
        "observation_id",
        "image_sha256",
        "width",
        "height",
        "source_time_seconds",
        "prompt",
        "response_schema",
    }
    assert request["observation_id"] not in str(source[0])
    assert (source[2] / "request/image.jpg").read_bytes() == source[0].read_bytes()
    assert "private_pitch_1" not in (source[2] / "request/request.json").read_text()
    with pytest.raises(FileExistsError):
        start(source)


@pytest.mark.parametrize("mutation", ["time", "hash", "schema", "url"])
def test_rejects_invalid_receipt(source, mutation):
    receipt = json.loads(source[1].read_text())
    receipt[
        {"time": "frame_seconds", "hash": "sha256", "schema": "schema", "url": "media_url"}[
            mutation
        ]
    ] = {"time": 13, "hash": "invalid", "schema": "wrong", "url": ""}[mutation]
    write(source[1], receipt)
    with pytest.raises(ValueError, match="receipt"):
        start(source)
    assert not source[2].exists()


def test_finish_records_elapsed_and_keeps_raw_response(source, monkeypatch):
    request = start(source)
    path = response(source, request)
    monkeypatch.setattr(obs.time, "monotonic_ns", lambda: 13_000_000_000)
    monkeypatch.setattr(obs.time, "time_ns", lambda: 1_700_000_003_000_000_000)
    result = obs.finish(source[2] / "session.json", path)
    assert result["elapsed_seconds"] == 3
    assert result["raw_response_sha256"] == obs._sha256(path.read_bytes())
    assert result["raw_response"] == json.loads(path.read_bytes())
    assert result["source_kind"] == "ai_visual_observation"
    assert result["availability_not_measured"] and not result["human_label"]
    assert "orchestration" in result["elapsed_scope"]
    with pytest.raises(FileExistsError):
        obs.finish(source[2], path)


@pytest.mark.parametrize(
    "relative", ["request/image.jpg", "request/request.json", "receipt", "frame"]
)
def test_finish_rechecks_immutable_source_and_request(source, relative):
    request = start(source)
    path = response(source, request)
    victim = (
        source[{"frame": 0, "receipt": 1}[relative]]
        if relative in {"frame", "receipt"}
        else source[2] / relative
    )
    victim.write_bytes(victim.read_bytes() + b" ")
    with pytest.raises(ValueError):
        obs.finish(source[2], path)
    assert not (source[2] / "result.json").exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"pitch_id": "forbidden"},
        {"observation_id": "other"},
        {"image_sha256": "other"},
        {"mitt": [100, 20]},
        {"mitt": [float("nan"), 20]},
        {"mitt": [True, 20]},
        {"visibility": "hidden"},
        {"status": "unknown", "mitt": None, "reason": " "},
        {"status": "unavailable"},
        {"status": "unreviewed"},
        {"pose": "guessed"},
    ],
)
def test_invalid_response_never_writes_result(source, changes):
    path = response(source, start(source), **changes)
    with pytest.raises(ValueError):
        obs.finish(source[2], path)
    assert not (source[2] / "result.json").exists()


@pytest.mark.parametrize("status", ["unavailable", "unknown"])
def test_abstentions_are_real_responses_not_fallbacks(source, status):
    path = response(
        source, start(source), status=status, mitt=None, visibility="unknown", pose="unknown"
    )
    assert obs.finish(source[2], path)["raw_response"]["status"] == status


@pytest.mark.parametrize("monotonic,utc", [(9, 1), (20, 1), (11, -1)])
def test_clock_mismatch_rejected(source, monkeypatch, monotonic, utc):
    path = response(source, start(source))
    monkeypatch.setattr(obs.time, "monotonic_ns", lambda: monotonic * 1_000_000_000)
    monkeypatch.setattr(
        obs.time, "time_ns", lambda: 1_700_000_000_000_000_000 + utc * 1_000_000_000
    )
    with pytest.raises(ValueError, match="clock mismatch"):
        obs.finish(source[2], path)


def test_output_boundary_and_no_symlinks(source, monkeypatch):
    with pytest.raises(ValueError, match="outputs/cv_observation"):
        obs.begin(source[0], 12.5, source[2].parent / "bad", source[1])
    original = obs.Path.is_symlink
    monkeypatch.setattr(obs.Path, "is_symlink", lambda p: p == source[0] or original(p))
    with pytest.raises(ValueError, match="symlink"):
        start(source)


@pytest.mark.parametrize("reason", ["", " \n\t "])
def test_new_partial_response_requires_reason_before_result_publication(source, reason):
    path = response(source, start(source), visibility="partial", reason=reason)
    with pytest.raises(ValueError, match="partial requires an explicit reason"):
        obs.finish(source[2], path)
    assert not (source[2] / "result.json").exists()


def test_full_response_may_still_have_blank_reason(source):
    path = response(source, start(source), visibility="full", reason="")
    assert obs.finish(source[2], path)["raw_response"]["reason"] == ""


@pytest.mark.parametrize("legacy", [False, True])
def test_saved_request_policy_uses_an_exact_contract_pair(legacy):
    request = {
        "prompt": obs.LEGACY_PROMPT if legacy else obs.PROMPT,
        "response_schema": obs.LEGACY_RESPONSE_FIELDS if legacy else obs.RESPONSE_FIELDS,
    }
    assert obs._partial_reason_required(request) is not legacy
    request["prompt"] = obs.PROMPT if legacy else obs.LEGACY_PROMPT
    with pytest.raises(ValueError, match="prompt/response contract"):
        obs._partial_reason_required(request)


def test_live_validator_does_not_relax_for_a_legacy_request(source):
    request = start(source)
    request.update(prompt=obs.LEGACY_PROMPT, response_schema=obs.LEGACY_RESPONSE_FIELDS)
    path = response(source, request, visibility="partial", reason="")
    with pytest.raises(ValueError, match="partial requires an explicit reason"):
        obs._validate_response(json.loads(path.read_bytes()), request)
