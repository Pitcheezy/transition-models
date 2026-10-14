"""Synthetic checks for the received-contract verifier; no network, no Song files."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.verify_publish_contract import (  # noqa: E402
    VerifyError,
    check_envelope,
    load_expected,
    verify,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_publish_contract.py"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


GAME_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "synthetic-game",
    "type": "object",
    "required": ["game", "publish"],
    "properties": {
        "game": {
            "type": "object",
            "required": ["game_pk"],
            "properties": {"game_pk": {"type": "integer"}},
        },
        "display_state": {"type": "object"},
        "publish": {"type": "object"},
    },
}
HEALTH_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["sequence"],
}


def publish(seq, final=None):
    value = {"contract": "v1", "sequence": seq, "published_at": "2026-10-05T10:21:00Z"}
    if final is not None:
        value["final"] = final
    return value


@pytest.fixture
def pack(tmp_path):
    received = tmp_path / "received"
    (received / "examples").mkdir(parents=True)
    (received / "schema").mkdir()
    live = json.dumps(
        {
            "game": {"game_pk": 900200, "status": "live"},
            "display_state": {"state": "recommended", "label": "다음 공 추천"},
            "publish": publish(4, False),
        }
    ).encode()
    health = json.dumps({"sequence": 4, "publish": publish(4)}).encode()
    files = {
        "examples/game-live.json": live,
        "examples/health-live.json": health,
        "schema/game.schema.json": json.dumps(GAME_SCHEMA).encode(),
        "schema/health.schema.json": json.dumps(HEALTH_SCHEMA).encode(),
    }
    for name, raw in files.items():
        (received / name).write_bytes(raw)
    expected = {
        "schema": "pitcheezy-collab001-expected-files-v1",
        "commit": "d" * 40,
        "contract": "v1",
        "files": [
            {
                "path": "examples/game-live.json",
                "sha256": sha(live),
                "schema": "game",
                "target": "v1/game/900200.json",
                "stage": 2,
            },
            {
                "path": "examples/health-live.json",
                "sha256": sha(health),
                "schema": "health",
                "target": "v1/health.json",
            },
            {"path": "schema/game.schema.json", "sha256": sha(files["schema/game.schema.json"])},
            {
                "path": "schema/health.schema.json",
                "sha256": sha(files["schema/health.schema.json"]),
            },
        ],
        "known_gaps": ["synthetic"],
    }
    expected_path = tmp_path / "expected.json"
    expected_path.write_text(json.dumps(expected), encoding="utf-8")
    return received, expected, expected_path, files


def test_good_pack_verifies_hashes_schemas_envelopes_and_host_targets(pack):
    received, expected, _, _ = pack
    report = verify(received, load_expected(json.dumps(expected).encode()))
    assert report["ok"] is True
    assert report["files_hash_matched"] == 4
    assert report["all_examples_valid_against_schema"] is True
    assert report["all_examples_have_v1_publish_envelope"] is True
    assert report["display_states_seen"] == ["recommended"]
    assert report["unsupported_state_example_present"] is False
    live = next(r for r in report["files"] if r["path"] == "examples/game-live.json")
    assert (
        live["game_pk"] == 900200 and live["stage"] == 2 and live["target_allowed_by_host"] is True
    )
    assert "received" not in json.dumps(report)


def test_hash_mismatch_schema_error_and_missing_file_are_reported_not_hidden(pack):
    received, expected, _, _ = pack
    (received / "examples" / "game-live.json").write_bytes(
        json.dumps({"game": {"game_pk": "x"}, "publish": publish(4, False)}).encode()
    )
    (received / "examples" / "health-live.json").unlink()
    report = verify(received, load_expected(json.dumps(expected).encode()))
    assert report["ok"] is False
    live = next(r for r in report["files"] if r["path"] == "examples/game-live.json")
    assert live["hash_matches_pack"] is False and live["schema_errors"] >= 1
    assert live["schema_error_paths"][0].startswith("/game/game_pk")
    health = next(r for r in report["files"] if r["path"] == "examples/health-live.json")
    assert health["status"] == "missing"


def test_envelope_rules_distinguish_final_placement():
    assert check_envelope("x", {"publish": publish(1, True)}, "game")["ok"] is True
    assert check_envelope("x", {"publish": publish(1)}, "game")["issues"] == ["final_missing"]
    assert check_envelope("x", {"publish": publish(1, False)}, "health")["issues"] == [
        "final_unexpected"
    ]
    assert check_envelope(
        "x", {"publish": {"contract": "v2", "sequence": -1, "published_at": "today"}}, "dates"
    )["issues"] == [
        "contract_not_v1",
        "sequence_invalid",
        "published_at_invalid",
    ]
    assert check_envelope("x", {}, "dates")["issue"] == "publish_missing"
    assert check_envelope(
        "x",
        {"publish": {"contract": "v1", "sequence": True, "published_at": "2026-10-13T00:00:00Z"}},
        "dates",
    )["issues"] == ["sequence_invalid"], "a boolean is not a sequence number"


def test_expected_list_is_validated_before_use():
    base = {
        "schema": "pitcheezy-collab001-expected-files-v1",
        "commit": "d" * 40,
        "files": [
            {
                "path": "examples/a.json",
                "sha256": "a" * 64,
                "schema": "game",
                "target": "v1/game/1.json",
            }
        ],
    }
    load_expected(json.dumps(base).encode())
    for bad in [
        {**base, "commit": "short"},
        {**base, "files": []},
        {**base, "files": [{"path": "../x.json", "sha256": "a" * 64}]},
        {
            **base,
            "files": [
                {
                    "path": "examples/a.json",
                    "sha256": "a" * 64,
                    "schema": "game",
                    "target": "v1/game/0.json",
                }
            ],
        },
        {
            **base,
            "files": [
                {
                    "path": "examples/a.json",
                    "sha256": "a" * 64,
                    "schema": "other",
                    "target": "v1/game/1.json",
                }
            ],
        },
    ]:
        with pytest.raises(VerifyError):
            load_expected(json.dumps(bad).encode())


def test_cli_writes_receipt_once_and_fails_on_mismatch(pack, tmp_path):
    received, _, expected_path, _ = pack
    out = tmp_path / "receipt.json"
    first = subprocess.run(
        [
            sys.executable,
            "-B",
            str(SCRIPT),
            "--received",
            str(received),
            "--expected",
            str(expected_path),
            "--output",
            str(out),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert first.returncode == 0, first.stdout + first.stderr
    assert json.loads(out.read_text(encoding="utf-8"))["ok"] is True
    second = subprocess.run(
        [
            sys.executable,
            "-B",
            str(SCRIPT),
            "--received",
            str(received),
            "--expected",
            str(expected_path),
            "--output",
            str(out),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert second.returncode == 2
    (received / "examples" / "game-live.json").write_bytes(b"{}")
    third = subprocess.run(
        [
            sys.executable,
            "-B",
            str(SCRIPT),
            "--received",
            str(received),
            "--expected",
            str(expected_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert third.returncode == 1
    assert json.loads(third.stdout)["all_hashes_match_pack"] is False


def test_trailing_newline_values_are_not_certified():
    assert check_envelope(
        "x",
        {"publish": {"contract": "v1", "sequence": 1, "published_at": "2026-10-13T00:00:00Z\n"}},
        "dates",
    )["issues"] == ["published_at_invalid"]
    bad = {
        "schema": "pitcheezy-collab001-expected-files-v1",
        "commit": "d" * 40,
        "files": [
            {
                "path": "examples/health.json",
                "sha256": "0" * 64,
                "schema": "health",
                "target": "v1/health.json\n",
            }
        ],
    }
    with pytest.raises(VerifyError, match="expected_invalid"):
        load_expected(json.dumps(bad).encode())


def test_unusable_received_schema_is_a_reported_row_not_a_crash(pack):
    received, expected, _, _ = pack
    (received / "schema" / "game.schema.json").write_bytes(b'{"type": 12}')
    report = verify(received, expected)
    row = next(r for r in report["files"] if r["path"] == "examples/game-live.json")
    assert row["status"] == "schema_unusable"
    assert row["code"] == "schema_evaluation_failed"
    assert report["all_examples_valid_against_schema"] is False
    assert report["ok"] is False


def test_each_received_file_is_read_once(pack, monkeypatch):
    import scripts.verify_publish_contract as vpc

    received, expected, _, files = pack
    reads = []
    original = vpc._read

    def counting(path, limit=vpc.MAX_JSON_BYTES):
        reads.append(path)
        return original(path, limit)

    monkeypatch.setattr(vpc, "_read", counting)
    assert verify(received, expected)["ok"] is True
    assert len(reads) == len(files), "hashing and schema checks share one read per file"


@pytest.mark.parametrize(
    "reference", ["https://schemas.example.test/private", "file:///synthetic-secret.json"]
)
def test_received_schema_never_retrieves_external_references(pack, monkeypatch, reference):
    import io
    import urllib.request

    received, expected, _, _ = pack
    schema = {"$schema": GAME_SCHEMA["$schema"], "$ref": reference}
    raw = json.dumps(schema).encode()
    (received / "schema" / "game.schema.json").write_bytes(raw)
    for row in expected["files"]:
        if row["path"] == "schema/game.schema.json":
            row["sha256"] = sha(raw)
    fetched = []

    def fake_urlopen(request):
        fetched.append(request.full_url)
        return io.BytesIO(b"{}")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    report = verify(received, expected)
    assert fetched == [], "offline verification must not read unlisted remote or local resources"
    row = next(r for r in report["files"] if r["path"] == "examples/game-live.json")
    assert row["status"] == "schema_unusable"
    assert report["ok"] is False


def test_received_schema_local_definitions_still_validate(pack):
    received, expected, _, _ = pack
    schema = {
        "$schema": GAME_SCHEMA["$schema"],
        "$defs": {"game": GAME_SCHEMA},
        "$ref": "#/$defs/game",
    }
    raw = json.dumps(schema).encode()
    (received / "schema" / "game.schema.json").write_bytes(raw)
    for row in expected["files"]:
        if row["path"] == "schema/game.schema.json":
            row["sha256"] = sha(raw)
    assert verify(received, expected)["ok"] is True


def test_symlinked_received_directory_is_refused(pack, tmp_path):
    received, expected, _, _ = pack
    link = tmp_path / "linked-received"
    try:
        link.symlink_to(received, target_is_directory=True)
    except OSError:
        pytest.skip("OS does not permit creating a symlink in this test account")
    with pytest.raises(VerifyError, match="linked_path"):
        verify(link, expected)


def test_committed_expected_list_matches_the_pack_shape():
    expected = load_expected(
        (ROOT / "ops/public-host/examples/collab001-expected-files.json").read_bytes()
    )
    assert expected["commit"] == "d5a1dd98003672235cc50509391fd4c41b28be32"
    assert len(expected["files"]) == 19
    stages = [r["stage"] for r in expected["files"] if r.get("stage")]
    assert stages == [1, 2, 3, 4, 5, 6]
