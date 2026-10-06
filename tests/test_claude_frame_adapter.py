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
        "reason": "",
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
        events = (
            state.events
            if state.events is not None
            else [
                {"type": "system", "model": "provider-reported-model"},
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
    assert metadata["reported"]["reported_models"] == ["provider-reported-model"]
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


def test_structured_mode_binds_schema_and_accepts_only_matched_serialization(case):
    case.events = structured_events(case.response)
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
