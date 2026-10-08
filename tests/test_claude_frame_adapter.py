"""Subscription adapter tests use fake CLI streams; no provider calls are made."""

import copy
import importlib.util
import io
import json
import subprocess
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from intent.observation_session import _request

SCRIPT = Path(__file__).parents[1] / "scripts" / "observe_claude_frame.py"
SPEC = importlib.util.spec_from_file_location("claude_frame_adapter", SCRIPT)
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


@pytest.fixture
def case(tmp_path, monkeypatch):
    for key in adapter.FORBIDDEN_ENV:
        monkeypatch.delenv(key, raising=False)
    buffer = io.BytesIO()
    Image.new("RGB", (20, 12)).save(buffer, format="JPEG")
    image = tmp_path / "image.jpg"
    image.write_bytes(buffer.getvalue())
    request = _request(buffer.getvalue(), (20, 12), 4.0, adapter.REQUEST_SCHEMA)
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    response = {
        "schema": "intent_visual_observation_v1",
        "observation_id": request["observation_id"],
        "image_sha256": request["image_sha256"],
        "status": "marked",
        "mitt": [9, 8],
        "visibility": "partial",
        "pose": "resting",
        "reason": "The mitt is partly hidden by the knee.",
    }
    state = SimpleNamespace(
        request=request,
        response=response,
        calls=[],
        returncode=0,
        auth_method="claude.ai",
        timeout=False,
        events=None,
    )
    state.paths = (request_path, image, tmp_path / "response.json")

    @contextmanager
    def temporary(**kwargs):
        empty = tmp_path / "isolated"
        empty.mkdir()
        yield str(empty)

    def run(argv, **kwargs):
        state.calls.append((argv, kwargs))
        assert kwargs["shell"] is False
        assert not list(Path(kwargs["cwd"]).iterdir())
        if argv[1:] == ["auth", "status"]:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"loggedIn": True, "authMethod": state.auth_method}).encode(),
            )
        reported_model = (
            argv[argv.index("--model") + 1] if "--model" in argv else "provider-reported-model"
        )
        assistant_model = reported_model[:-4] if reported_model.endswith("[1m]") else reported_model
        events = (
            state.events
            if state.events is not None
            else [
                {"type": "system", "subtype": "init", "model": reported_model},
                {
                    "type": "assistant",
                    "parent_tool_use_id": None,
                    "message": {"role": "assistant", "model": assistant_model, "content": []},
                },
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "result": json.dumps(state.response),
                    "usage": {"input_tokens": 123},
                },
            ]
        )
        raw = events if isinstance(events, str) else "\n".join(map(json.dumps, events))
        kwargs["stdout"].write(raw.encode())
        kwargs["stderr"].write(b"private CLI diagnostic")
        if state.timeout:
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        return SimpleNamespace(returncode=state.returncode)

    monkeypatch.setattr(adapter.tempfile, "TemporaryDirectory", temporary)
    monkeypatch.setattr(adapter.subprocess, "run", run)
    return state


def test_valid_pixel_call_is_anonymous_and_tool_free(case):
    metadata = adapter.observe(*case.paths)
    assert json.loads(case.paths[2].read_text()) == case.response
    argv, kwargs = case.calls[1]
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--mcp-config") + 1] == '{"mcpServers":{}}'
    assert "--strict-mcp-config" in argv and "--no-session-persistence" in argv
    assert "--bare" not in argv and "--dangerously-skip-permissions" not in argv
    payload = json.loads(kwargs["input"])
    assert payload["parent_tool_use_id"] is None
    content = payload["message"]["content"]
    assert json.loads(content[0]["text"]) == case.request
    assert content[1]["source"]["media_type"] == "image/jpeg"
    assert metadata["reported"]["reported_models"] == ["provider-reported-model"]
    assert metadata["reported"]["usage"] == {"input_tokens": 123}
    assert metadata["status"] == "accepted"
    assert "--model" not in argv and metadata["requested_model"] is None
    assert metadata["result_format"] == "bare_json"


def test_single_whole_json_fence_accepted_with_raw_log_preserved(case):
    raw_result = "  \n```json\n" + json.dumps(case.response) + "\n```\n "
    case.events = [
        {"type": "result", "subtype": "success", "is_error": False, "result": raw_result}
    ]
    metadata = adapter.observe(*case.paths)
    assert metadata["result_format"] == "fenced_json"
    assert json.loads(case.paths[2].read_text()) == case.response
    logged = json.loads((case.paths[2].parent / "provider_stdout.jsonl").read_text())
    assert logged["result"] == raw_result


@pytest.mark.parametrize("wrapper", ["Explanation\n{}", "{}\nExplanation", "{}\n{}"])
def test_json_fence_with_prose_or_multiple_fences_is_rejected(case, wrapper):
    fenced = "```json\n" + json.dumps(case.response) + "\n```"
    case.events = [
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": wrapper.format(fenced, fenced),
        }
    ]
    with pytest.raises(ValueError):
        adapter.observe(*case.paths)
    assert not case.paths[2].exists()


@pytest.mark.parametrize(
    "events",
    [
        "not json",
        [],
        [{"type": "result", "subtype": "error", "is_error": True}],
        [{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read"}]}}],
        [{"type": "result", "subtype": "success", "is_error": False, "result": "```json\n{}\n```"}],
    ],
)
def test_bad_stream_preserved_without_response(case, events):
    case.events = events
    with pytest.raises((ValueError, KeyError)):
        adapter.observe(*case.paths)
    assert not case.paths[2].exists()
    assert (case.paths[2].parent / "provider_stdout.jsonl").exists()
    metadata = json.loads((case.paths[2].parent / "provider_metadata.json").read_text())
    assert metadata["status"] == "failed"


@pytest.mark.parametrize(
    "field,value",
    [("observation_id", "wrong"), ("image_sha256", "wrong"), ("mitt", [20, 1]), ("extra", "field")],
)
def test_invalid_observation_rejected(case, field, value):
    case.response[field] = value
    with pytest.raises(ValueError):
        adapter.observe(*case.paths)
    assert not case.paths[2].exists()


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize("reason", ["", " \n\t "])
def test_partial_reason_required_in_plain_and_structured_provider_output(case, structured, reason):
    case.response["reason"] = reason
    if structured:
        case.events = structured_events(case.response)
    with pytest.raises(ValueError, match="partial requires an explicit reason"):
        adapter.observe(*case.paths, structured_output=structured)
    assert not case.paths[2].exists()
    metadata = json.loads((case.paths[2].parent / "provider_metadata.json").read_text())
    assert metadata["status"] == "failed"


@pytest.mark.parametrize(
    "field,value",
    [
        ("width", 19),
        ("image_sha256", "wrong"),
        ("pitch_id", "secret"),
        ("source_time_seconds", float("nan")),
    ],
)
def test_bad_request_rejected_before_cli(case, field, value):
    request = copy.deepcopy(case.request)
    request[field] = value
    case.paths[0].write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(ValueError):
        adapter.observe(*case.paths)
    assert not case.calls


@pytest.mark.parametrize("failure", ["nonzero", "timeout", "auth", "key", "existing"])
def test_fail_closed_without_retry_or_overwrite(case, monkeypatch, failure):
    if failure == "nonzero":
        case.returncode = 1
    elif failure == "timeout":
        case.timeout = True
    elif failure == "auth":
        case.auth_method = "api_key"
    elif failure == "key":
        monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-test-key")
    else:
        case.paths[2].write_text("keep")
    with pytest.raises((ValueError, subprocess.TimeoutExpired)):
        adapter.observe(*case.paths)
    assert len(case.calls) == (
        1 if failure == "auth" else 0 if failure in ("key", "existing") else 2
    )
    if failure == "existing":
        assert case.paths[2].read_text() == "keep"
    else:
        assert not case.paths[2].exists()


def test_unknown_abstention_is_valid(case):
    case.response.update(
        status="unknown",
        mitt=None,
        visibility="unknown",
        pose="unknown",
        reason="Mitt cannot be located in this frame.",
    )
    assert adapter.observe(*case.paths)["status"] == "accepted"


def test_mapped_request_retains_actual_time_and_requested_cutoff(case):
    case.request.update(
        schema=adapter.MAPPED_REQUEST_SCHEMA,
        source_time_basis="decoded_pts",
        source_time_seconds_exact="4",
        requested_cutoff_seconds_exact="9/2",
    )
    case.paths[0].write_text(json.dumps(case.request), encoding="utf-8")
    assert adapter.observe(*case.paths)["status"] == "accepted"


def test_explicit_model_preserves_requested_and_reported_separately(case):
    model = "claude-opus-4-8[1m]"
    metadata = adapter.observe(*case.paths, model=model)
    argv = case.calls[1][0]
    assert argv[-2:] == ["--model", model]
    assert metadata["requested_model"] == model
    assert metadata["reported"]["reported_models"] == [model]
    check = metadata["reported"]["primary_model_check"]
    assert check["requested_model"] == model
    assert check["initialization_models"] == [model]
    assert check["assistant_models"] == ["claude-opus-4-8"]
    saved = json.loads((case.paths[2].parent / "provider_metadata.json").read_text())
    assert saved["requested_model"] == model and saved["reported"] == metadata["reported"]
    assert len(case.calls) == 2  # One authentication check, one observation, no substitution/retry.


@pytest.mark.parametrize("model", ["", " ", "opus extra", "opus\n", "\x00opus", "--help", "-p", 42])
def test_invalid_explicit_model_rejected_before_any_cli_call(case, model):
    with pytest.raises(ValueError, match="Explicit model"):
        adapter.observe(*case.paths, model=model)
    assert not case.calls
    assert not case.paths[2].exists()


def structured_events(response):
    return [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "serialization-1",
                        "name": "StructuredOutput",
                        "input": response,
                        "caller": {"type": "direct"},
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "serialization-1",
                        "content": "Structured output provided successfully",
                    }
                ]
            },
        },
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "",
            "structured_output": response,
        },
    ]


def primary_events(response, model):
    events = structured_events(response)
    events[0]["message"]["model"] = model[:-4] if model.endswith("[1m]") else model
    events.insert(0, {"type": "system", "subtype": "init", "model": model})
    return events


def test_structured_mode_binds_schema_and_accepts_only_matched_serialization(case):
    case.events = primary_events(case.response, "claude-opus-4-8[1m]")
    metadata = adapter.observe(*case.paths, structured_output=True, model="claude-opus-4-8[1m]")
    argv = case.calls[1][0]
    schema = json.loads(argv[argv.index("--json-schema") + 1])
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(adapter.RESPONSE_FIELDS)
    assert schema["properties"]["observation_id"]["const"] == case.request["observation_id"]
    assert schema["properties"]["image_sha256"]["const"] == case.request["image_sha256"]
    point = schema["properties"]["mitt"]["anyOf"][0]
    assert point["minItems"] == point["maxItems"] == 2
    assert point["items"][0]["exclusiveMaximum"] == 20
    assert point["items"][1]["exclusiveMaximum"] == 12
    assert metadata["output_protocol"] == "structured_json_schema_v1"
    assert metadata["reported"]["serialization_pairs"] == 1
    assert metadata["requested_model"] == "claude-opus-4-8[1m]"
    assert metadata["provider_schema_retry_note"]
    assert json.loads(case.paths[2].read_text()) == case.response
    raw = (case.paths[2].parent / "provider_stdout.jsonl").read_text()
    assert [json.loads(line) for line in raw.splitlines()] == case.events


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "string",
        "mitt_string",
        "wrong_id",
        "extra_field",
        "out_of_bounds",
        "unmatched_use",
        "unmatched_result",
        "wrong_input",
        "extra_tool",
        "failed_result",
    ],
)
def test_structured_mode_fails_closed_without_text_fallback(case, change):
    case.events = copy.deepcopy(structured_events(case.response))
    final = case.events[-1]
    final["result"] = json.dumps(case.response)  # Valid legacy JSON must never become a fallback.
    if change == "missing":
        final.pop("structured_output")
    elif change == "string":
        final["structured_output"] = json.dumps(case.response)
    elif change == "mitt_string":
        final["structured_output"]["mitt"] = "[9,8]"
    elif change == "wrong_id":
        final["structured_output"]["observation_id"] = "wrong"
    elif change == "extra_field":
        final["structured_output"]["extra"] = "forbidden"
    elif change == "out_of_bounds":
        final["structured_output"]["mitt"] = [20, 8]
    elif change == "unmatched_use":
        case.events.pop(1)
    elif change == "unmatched_result":
        case.events[1]["message"]["content"][0]["tool_use_id"] = "unknown"
    elif change == "wrong_input":
        case.events[0]["message"]["content"][0]["input"] = {**case.response, "mitt": [8, 8]}
    elif change == "extra_tool":
        case.events[0]["message"]["content"].append(
            {"type": "tool_use", "id": "other", "name": "Read", "input": {"file_path": "secret"}}
        )
    else:
        case.events[1]["message"]["content"][0]["is_error"] = True
    with pytest.raises(ValueError):
        adapter.observe(*case.paths, structured_output=True)
    assert not case.paths[2].exists()
    assert len(case.calls) == 2
    assert (case.paths[2].parent / "provider_stdout.jsonl").exists()


def test_legacy_mode_still_rejects_structured_serialization_tools(case):
    case.events = structured_events(case.response)
    case.events[-1]["result"] = json.dumps(case.response)
    with pytest.raises(ValueError, match="forbidden tool"):
        adapter.observe(*case.paths)
    assert "--json-schema" not in case.calls[1][0]


@pytest.mark.parametrize(
    "change", ["marked_null", "hidden_marked", "abstention_point", "blank_reason"]
)
def test_provider_schema_avoids_top_combinators_but_cross_field_rules_remain(case, change):
    schema = adapter._output_schema(case.request)
    assert not {"allOf", "anyOf", "oneOf", "if", "then", "else"} & schema.keys()
    assert schema["properties"]["mitt"]["anyOf"][1] == {"type": "null"}
    response = copy.deepcopy(case.response)
    if change == "marked_null":
        response["mitt"] = None
    elif change == "hidden_marked":
        response["visibility"] = "hidden"
    elif change == "abstention_point":
        response.update(status="unavailable", reason="hidden")
    else:
        response.update(status="unavailable", mitt=None, reason="   ")
    case.events = structured_events(response)
    with pytest.raises(ValueError):
        adapter.observe(*case.paths, structured_output=True)
    assert not case.paths[2].exists()


class StageClock:
    def __init__(self):
        self.now = 1_000_000_000

    def monotonic_ns(self):
        value = self.now
        self.now += 100_000_000
        return value


def assert_timing_chronology(metadata):
    timing = metadata["timing_v1"]
    assert timing["clock"] == "monotonic_ns"
    assert "interpreter/import startup" in timing["scope"]
    assert "final metadata write" in timing["scope"]
    assert set(timing["stages"]) == {
        "input_validation",
        "auth_status",
        "cli_call",
        "parse_validate_write",
        "total",
    }
    stages = timing["stages"]
    total = stages["total"]
    previous = total["started_monotonic_ns"]
    for name in ("input_validation", "auth_status", "cli_call", "parse_validate_write"):
        record = stages[name]
        if record is None:
            continue
        start, end = record["started_monotonic_ns"], record["finished_monotonic_ns"]
        assert type(start) is int and type(end) is int
        assert 0 <= previous <= start <= end <= total["finished_monotonic_ns"]
        assert record["elapsed_seconds"] == (end - start) / 1e9
        assert record["elapsed_seconds"] >= 0
        previous = end
    assert (
        total["elapsed_seconds"]
        == (total["finished_monotonic_ns"] - total["started_monotonic_ns"]) / 1e9
    )


def test_timing_records_chronology_without_changing_calls_or_response(case):
    metadata = adapter.observe(*case.paths, clock=StageClock())
    assert_timing_chronology(metadata)
    stages = metadata["timing_v1"]["stages"]
    assert all(stage["status"] == "completed" for stage in stages.values())
    assert stages["total"]["elapsed_seconds"] == 0.9
    assert all(stages[name]["elapsed_seconds"] == 0.1 for name in stages if name != "total")
    assert len(case.calls) == 2
    assert json.loads(case.paths[2].read_text()) == case.response
    saved = json.loads((case.paths[2].parent / "provider_metadata.json").read_text())
    assert saved == metadata
    encoded = json.dumps(metadata["timing_v1"])
    assert case.request["observation_id"] not in encoded
    assert case.request["image_sha256"] not in encoded
    assert str(case.paths[0]) not in encoded


@pytest.mark.parametrize(
    "failure,failed_stage,expected_calls",
    [
        ("input", "input_validation", 0),
        ("auth_rejected", "auth_status", 1),
        ("auth_timeout", "auth_status", 1),
        ("cli_timeout", "cli_call", 2),
        ("cli_nonzero", "cli_call", 2),
        ("parse", "parse_validate_write", 2),
    ],
)
def test_failure_timings_are_retained_without_retry(
    case, monkeypatch, failure, failed_stage, expected_calls
):
    if failure == "input":
        case.paths[0].write_text("{}", encoding="utf-8")
    elif failure == "auth_rejected":
        case.auth_method = "api_key"
    elif failure == "auth_timeout":
        original = adapter.subprocess.run

        def timed_out_auth(argv, **kwargs):
            original(argv, **kwargs)
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

        monkeypatch.setattr(adapter.subprocess, "run", timed_out_auth)
    elif failure == "cli_timeout":
        case.timeout = True
    elif failure == "cli_nonzero":
        case.returncode = 1
    else:
        case.events = "not JSON"
    with pytest.raises((ValueError, subprocess.TimeoutExpired)):
        adapter.observe(*case.paths, clock=StageClock())
    metadata = json.loads((case.paths[2].parent / "provider_metadata.json").read_text())
    assert_timing_chronology(metadata)
    stages = metadata["timing_v1"]["stages"]
    assert metadata["status"] == "failed" and stages["total"]["status"] == "failed"
    assert stages[failed_stage]["status"] == "failed"
    names = ["input_validation", "auth_status", "cli_call", "parse_validate_write"]
    index = names.index(failed_stage)
    assert all(stages[name]["status"] == "completed" for name in names[:index])
    assert all(stages[name] is None for name in names[index + 1 :])
    assert len(case.calls) == expected_calls
    assert not case.paths[2].exists()
    if failed_stage in ("cli_call", "parse_validate_write"):
        assert (case.paths[2].parent / "provider_stdout.jsonl").exists()
    else:
        assert not (case.paths[2].parent / "provider_stdout.jsonl").exists()


def test_existing_metadata_is_never_overwritten_even_for_input_error(case):
    path = case.paths[2].parent / "provider_metadata.json"
    path.write_bytes(b"keep existing metadata")
    case.paths[0].write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="fresh"):
        adapter.observe(*case.paths, clock=StageClock())
    assert path.read_bytes() == b"keep existing metadata"
    assert not case.calls


def test_total_timing_includes_temporary_directory_cleanup(case, monkeypatch):
    clock = StageClock()
    original = adapter.tempfile.TemporaryDirectory

    @contextmanager
    def cleanup_delay(**kwargs):
        with original(**kwargs) as cwd:
            yield cwd
            clock.now += 2_000_000_000

    monkeypatch.setattr(adapter.tempfile, "TemporaryDirectory", cleanup_delay)
    metadata = adapter.observe(*case.paths, clock=clock)
    assert_timing_chronology(metadata)
    stages = metadata["timing_v1"]["stages"]
    assert stages["total"]["elapsed_seconds"] == 2.9
    assert stages["parse_validate_write"]["elapsed_seconds"] == 0.1


@pytest.mark.parametrize("requested", ["claude-haiku-4-5-20251001", "claude-opus-4-8[1m]"])
def test_explicit_primary_model_matches_without_trusting_auxiliary_usage(case, requested):
    case.events = primary_events(case.response, requested)
    case.events[-1]["modelUsage"] = {"auxiliary-model": {"inputTokens": 1}}
    metadata = adapter.observe(*case.paths, model=requested, structured_output=True)
    proof = metadata["reported"]["primary_model_check"]
    assert proof["requested_model"] == requested
    assert proof["initialization_models"] == [requested]
    assert proof["assistant_models"] == [
        requested[:-4] if requested.endswith("[1m]") else requested
    ]
    assert metadata["reported"]["modelUsage"] == {"auxiliary-model": {"inputTokens": 1}}
    assert len(case.calls) == 2


@pytest.mark.parametrize(
    "problem",
    [
        "wrong_init",
        "missing_init",
        "duplicate_init",
        "wrong_assistant",
        "missing_assistant",
        "missing_assistant_model",
        "mixed_primary_models",
        "child_only",
        "assistant_version_alias",
        "unrequested_context_suffix",
    ],
)
def test_primary_model_mismatch_refused_even_with_matching_model_usage(case, problem):
    requested = "claude-haiku-4-5-20251001"
    case.events = primary_events(case.response, requested)
    case.events[-1]["modelUsage"] = {requested: {"inputTokens": 123}}
    init, assistant = case.events[0], case.events[1]
    if problem == "wrong_init":
        init["model"] = "claude-opus-4-8"
    elif problem == "missing_init":
        case.events.pop(0)
    elif problem == "duplicate_init":
        case.events.insert(0, dict(init))
    elif problem == "wrong_assistant":
        assistant["message"]["model"] = "claude-opus-4-8"
    elif problem == "missing_assistant":
        # Preserve a valid structured response, with no serialization/tool events.
        case.events = [init, case.events[-1]]
    elif problem == "missing_assistant_model":
        assistant["message"].pop("model")
    elif problem == "mixed_primary_models":
        case.events.insert(-1, {"type": "assistant", "message": {"model": "other"}})
    elif problem == "child_only":
        assistant["parent_tool_use_id"] = "child-session"
    elif problem == "assistant_version_alias":
        assistant["message"]["model"] = "claude-haiku-4-5"
    else:
        assistant["message"]["model"] = requested + "[1m]"
    with pytest.raises(ValueError, match="requested model"):
        adapter.observe(*case.paths, model=requested, structured_output=True)
    assert not case.paths[2].exists()
    assert len(case.calls) == 2
    path = case.paths[2].parent
    assert [json.loads(line) for line in (path / "provider_stdout.jsonl").read_text().splitlines()]
    metadata = json.loads((path / "provider_metadata.json").read_text())
    assert metadata["status"] == "failed"
    assert metadata["timing_v1"]["stages"]["parse_validate_write"]["status"] == "failed"
    assert metadata["timing_v1"]["stages"]["total"]["status"] == "failed"


def test_context_suffix_still_requires_exact_initialization(case):
    requested = "claude-opus-4-8[1m]"
    case.events = primary_events(case.response, requested)
    case.events[0]["model"] = "claude-opus-4-8"
    with pytest.raises(ValueError, match="requested model"):
        adapter.observe(*case.paths, model=requested, structured_output=True)
    assert not case.paths[2].exists()


def test_configured_context_suffix_may_also_be_present_in_assistant(case):
    requested = "claude-opus-4-8[1m]"
    case.events = primary_events(case.response, requested)
    case.events[1]["message"]["model"] = requested
    metadata = adapter.observe(*case.paths, model=requested, structured_output=True)
    assert metadata["reported"]["primary_model_check"]["assistant_models"] == [requested]


def test_legacy_unspecified_model_preserves_acceptance_without_primary_evidence(case):
    case.events = structured_events(case.response)
    metadata = adapter.observe(*case.paths, structured_output=True)
    assert metadata["requested_model"] is None
    assert "primary_model_check" not in metadata["reported"]
    assert len(case.calls) == 2
