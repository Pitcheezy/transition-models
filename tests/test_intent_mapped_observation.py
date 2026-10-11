"""Mapped-session contracts with a mocked verified-frame boundary; no AI or decoding."""

import json
from fractions import Fraction

import pytest
from PIL import Image

from intent import observation_session as obs


def write(path, document):
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


@pytest.fixture
def mapped(tmp_path, monkeypatch):
    directory = tmp_path / "private_game_849843_pa_3"
    directory.mkdir()
    image = directory / "image.jpg"
    Image.new("RGB", (100, 80)).save(image)
    receipt = write(
        directory / "receipt.json",
        {
            "schema": "synthetic_mapped_frame_fixture",
            "artifacts": {"image.jpg": {"sha256": obs._sha256(image.read_bytes())}},
        },
    )
    mapping = write(directory / "mapping_private.json", {"source_seconds_exact": "1001/6"})
    capture = write(directory / "capture_private.json", {"synthetic_capture": True})
    hashes = {path: obs._sha256(path.read_bytes()) for path in (image, receipt, mapping, capture)}
    verified = {
        "image_path": image,
        "receipt_path": receipt,
        "receipt_sha256": hashes[receipt],
        "source_seconds": Fraction(1001, 6),
        "requested_source_seconds": Fraction(167),
        "dimensions": (100, 80),
    }
    state = {
        "helper_sha": {
            name: "a" * 64
            for name in ("intent.clip_frames", "intent.clip_clock", "intent.clip_capture")
        },
        "calls": 0,
    }

    def loader(path):
        assert path == directory
        state["calls"] += 1
        for bound_path, digest in hashes.items():
            if obs._sha256(bound_path.read_bytes()) != digest:
                raise ValueError("mock verified-frame boundary rejects tampered bound evidence")
        return dict(verified), state["helper_sha"]

    monkeypatch.setattr(obs, "_load_mapped", loader)
    monkeypatch.setattr(obs.time, "monotonic_ns", lambda: 10_000_000_000)
    monkeypatch.setattr(obs.time, "time_ns", lambda: 1_700_000_000_000_000_000)
    return {
        "directory": directory,
        "image": image,
        "receipt": receipt,
        "mapping": mapping,
        "capture": capture,
        "verified": verified,
        "state": state,
        "out": tmp_path / "outputs/cv_observation_mapped",
    }


def begin(mapped):
    return obs.begin_mapped(mapped["directory"], mapped["out"])


def response(mapped, request, **changes):
    document = {
        "schema": obs.RESPONSE_SCHEMA,
        "observation_id": request["observation_id"],
        "image_sha256": request["image_sha256"],
        "status": "marked",
        "mitt": [20, 30],
        "visibility": "partial",
        "pose": "resting",
        "reason": "synthetic response",
    }
    document.update(changes)
    return write(mapped["out"] / "response.json", document)


def test_mapped_begin_anonymous_exact_time_and_private_bindings(mapped):
    request = begin(mapped)
    assert request["schema"] == obs.MAPPED_REQUEST_SCHEMA
    assert request["source_time_basis"] == "decoded_pts"
    assert request["source_time_seconds_exact"] == "1001/6"
    assert request["requested_cutoff_seconds_exact"] == "167"
    assert request["source_time_seconds"] == float(Fraction(1001, 6))
    public_text = (mapped["out"] / "request/request.json").read_text()
    assert "private_game_849843" not in public_text and str(mapped["directory"]) not in public_text
    assert request.keys() == {
        "schema",
        "observation_id",
        "image_sha256",
        "width",
        "height",
        "source_time_seconds",
        "source_time_basis",
        "source_time_seconds_exact",
        "requested_cutoff_seconds_exact",
        "prompt",
        "response_schema",
    }
    assert {p.name for p in (mapped["out"] / "request").iterdir()} == {"image.jpg", "request.json"}
    session = json.loads((mapped["out"] / "session.json").read_text())
    assert session["schema"] == obs.MAPPED_SESSION_SCHEMA
    assert session["mapped_frame_helper_code_sha256"] == mapped["state"]["helper_sha"]
    assert session["source_receipt_sha256"] == mapped["verified"]["receipt_sha256"]
    assert session["mapped_frame_directory"] == str(mapped["directory"])
    assert obs.CACHE_SCHEMA not in public_text


def test_mapped_finish_revalidates_records_real_response_and_host_elapsed(mapped, monkeypatch):
    request = begin(mapped)
    path = response(mapped, request)
    monkeypatch.setattr(obs.time, "monotonic_ns", lambda: 13_000_000_000)
    monkeypatch.setattr(obs.time, "time_ns", lambda: 1_700_000_003_000_000_000)
    result = obs.finish(mapped["out"], path)
    assert mapped["state"]["calls"] == 2
    assert result["schema"] == "intent_visual_observation_result_v2"
    assert result["source_time_seconds_exact"] == "1001/6"
    assert result["requested_cutoff_seconds_exact"] == "167"
    assert result["source_time_basis"] == "decoded_pts"
    assert result["elapsed_seconds"] == 3
    assert result["raw_response"] == json.loads(path.read_bytes())
    assert result["raw_response_sha256"] == obs._sha256(path.read_bytes())
    assert result["availability_not_measured"] and not result["live_availability_verified"]
    assert result["human_label"] is False and result["independent_validation"] is False
    with pytest.raises(FileExistsError):
        obs.finish(mapped["out"], path)


@pytest.mark.parametrize("stage", ["before", "after"])
@pytest.mark.parametrize("part", ["image", "receipt", "mapping", "capture"])
def test_bound_evidence_tampering_rejected_at_begin_and_finish(mapped, stage, part):
    if stage == "after":
        path = response(mapped, begin(mapped))
    victim = mapped[part]
    victim.write_bytes(victim.read_bytes() + b" ")
    with pytest.raises(ValueError, match="tampered"):
        obs.finish(mapped["out"], path) if stage == "after" else begin(mapped)
    assert not (mapped["out"] / "result.json").exists()
    if stage == "before":
        assert not mapped["out"].exists()


@pytest.mark.parametrize("part", ["source_seconds", "requested_source_seconds"])
def test_returned_exact_time_changed_after_begin_is_rejected(mapped, part):
    path = response(mapped, begin(mapped))
    mapped["verified"][part] += Fraction(1, 100)
    with pytest.raises(ValueError, match="binding"):
        obs.finish(mapped["out"], path)
    assert not (mapped["out"] / "result.json").exists()


@pytest.mark.parametrize("field", list(obs.MAPPED_TIME_FIELDS))
def test_request_exact_time_cannot_change_even_with_recomputed_request_hash(mapped, field):
    request = begin(mapped)
    path = response(mapped, request)
    request[field] = "other" if field == "source_time_basis" else "168"
    request_path = write(mapped["out"] / "request/request.json", request)
    session_path = mapped["out"] / "session.json"
    session = json.loads(session_path.read_text())
    session["request_sha256"] = obs._sha256(request_path.read_bytes())
    write(session_path, session)
    with pytest.raises(ValueError, match="exact-time"):
        obs.finish(mapped["out"], path)


@pytest.mark.parametrize(
    "helper", ["intent.clip_frames", "intent.clip_clock", "intent.clip_capture"]
)
def test_helper_code_binding_rechecked(mapped, helper):
    path = response(mapped, begin(mapped))
    mapped["state"]["helper_sha"][helper] = "b" * 64
    with pytest.raises(ValueError, match="helper binding"):
        obs.finish(mapped["out"], path)


def test_mapped_evidence_cannot_be_passed_as_legacy_cache_receipt(mapped):
    with pytest.raises(ValueError, match="receipt"):
        obs.begin(mapped["image"], 167, mapped["out"], mapped["receipt"])
    assert mapped["state"]["calls"] == 0


@pytest.mark.parametrize("schema", [obs.SESSION_SCHEMA, "unknown_schema"])
def test_mapped_session_cannot_downgrade_or_use_unknown_schema(mapped, schema):
    path = response(mapped, begin(mapped))
    session_path = mapped["out"] / "session.json"
    session = json.loads(session_path.read_text())
    session["schema"] = schema
    write(session_path, session)
    with pytest.raises(ValueError):
        obs.finish(mapped["out"], path)


def test_legacy_session_cannot_be_relabelled_as_mapped(mapped):
    legacy = write(
        mapped["directory"] / "legacy.json",
        {
            "schema": obs.CACHE_SCHEMA,
            "media_url": "https://example.test/legacy",
            "frame_seconds": 12.5,
            "sha256": obs._sha256(mapped["image"].read_bytes()),
        },
    )
    request = obs.begin(mapped["image"], 12.5, mapped["out"], legacy)
    path = response(mapped, request)
    session_path = mapped["out"] / "session.json"
    session = json.loads(session_path.read_text())
    session["schema"] = obs.MAPPED_SESSION_SCHEMA
    write(session_path, session)
    with pytest.raises(ValueError, match="mapped-frame directory"):
        obs.finish(mapped["out"], path)


@pytest.mark.parametrize("status", ["unknown", "unavailable"])
def test_mapped_abstention_is_retained_without_synthetic_coordinates(mapped, status):
    path = response(
        mapped, begin(mapped), status=status, mitt=None, visibility="unknown", pose="unknown"
    )
    result = obs.finish(mapped["out"], path)
    assert result["raw_response"]["status"] == status and result["raw_response"]["mitt"] is None


def test_mapped_clock_mismatch_still_rejected(mapped, monkeypatch):
    path = response(mapped, begin(mapped))
    monkeypatch.setattr(obs.time, "monotonic_ns", lambda: 8_000_000_000)
    with pytest.raises(ValueError, match="clock mismatch"):
        obs.finish(mapped["out"], path)


@pytest.mark.parametrize("actual", [Fraction(168), 166.0])
def test_helper_requires_exact_causal_time_before_publication(mapped, actual):
    mapped["verified"]["source_seconds"] = actual
    with pytest.raises(ValueError, match="exact Fraction"):
        begin(mapped)
    assert not mapped["out"].exists()


def test_begin_mapped_cli_explicitly_selects_v2(mapped, capsys):
    obs.main(
        ["begin-mapped", "--mapped-frame", str(mapped["directory"]), "--out", str(mapped["out"])]
    )
    request = json.loads(capsys.readouterr().out)
    assert request["schema"] == obs.MAPPED_REQUEST_SCHEMA
