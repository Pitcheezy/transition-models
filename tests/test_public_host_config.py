"""Verify deploy-time invariants without accounts or executing supplied artifacts."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.operations import release_bundle as rb
from src.operations.host_config import CLIENT_PATH, CONFIG_PATH, ConfigError, check_release_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def candidate(tmp_path):
    root = tmp_path / "candidate"
    provenance = json.loads(
        (ROOT / "ops/public-host/examples/synthetic-provenance.json").read_text()
    )
    payload = {
        **{"host/" + n: b"synthetic fixture\n" for n in rb.HOST_FILES},
        "public/index.html": b"<!doctype html><title>synthetic</title>",
    }
    files = rb.assemble(payload, provenance, "3" * 40)
    for name, raw in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    config = json.loads((ROOT / "ops/public-host/wrangler.example.jsonc").read_text())
    config["assets"]["directory"] = "../public"
    config["r2_buckets"][0]["bucket_name"] = "offline-fixture-private"
    config["d1_databases"][0].update(
        database_name="offline-fixture-private", database_id="11111111-1111-4111-8111-111111111111"
    )
    client = {
        "telemetryEnabled": False,
        "feedbackEnabled": False,
        "retainDays": 30,
        "accessGate": False,
    }

    def write(c=None, u=None):
        (root / CONFIG_PATH).write_text(json.dumps(config if c is None else c), encoding="utf-8")
        (root / CLIENT_PATH).write_text(json.dumps(client if u is None else u), encoding="utf-8")

    write()
    return root, config, client, write


def test_good_candidate_only_certifies_local_bytes(candidate):
    root, _, _, _ = candidate
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    report = check_release_config(root)
    assert report["ok"] is True and report["deployable"] is False
    assert report["mode"] == "synthetic"
    assert "secret_installation" in report["unverified"]
    assert "frontend_build_provenance_and_settings_consumption" in report["unverified"]
    assert len(report["config_sha256"]) == 64
    assert "offline-fixture" not in json.dumps(report)
    assert {p: p.read_bytes() for p in before} == before


@pytest.mark.parametrize("mode", ["session", "feedback", "both"])
def test_independent_active_settings_match(candidate, mode):
    root, config, client, write = candidate
    config["vars"]["COLLECTION_ORIGIN"] = "https://example.test"
    for env, key, active in [
        ("TELEMETRY_ENABLED", "telemetryEnabled", mode != "feedback"),
        ("FEEDBACK_ENABLED", "feedbackEnabled", mode != "session"),
    ]:
        config["vars"][env] = str(active).lower()
        client[key] = active
    client["retainDays"] = 7
    config["vars"]["TELEMETRY_RETAIN_DAYS"] = "7"
    write()
    assert check_release_config(root)["ok"]


def set_value(config, keys, value):
    target = config
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value


@pytest.mark.parametrize(
    ("keys", "value", "code"),
    [
        (["env"], {}, "environment_overrides"),
        (["workers_dev"], True, "unexpected_public_endpoint"),
        (["preview_urls"], True, "unexpected_public_endpoint"),
        (["main"], "../worker.mjs", "wrong_worker_path"),
        (["assets", "directory"], "./public", "wrong_assets_path"),
        (["assets", "directory"], "../../private", "wrong_assets_path"),
        (["assets", "run_worker_first"], False, "unsafe_asset_routing"),
        (["assets", "run_worker_first"], ["/v1/*"], "unsafe_asset_routing"),
        (["assets", "binding"], "PUBLISH_BUCKET", "unsafe_asset_routing"),
        (["vars", "UPLOAD_ENABLED"], True, "invalid_gate"),
        (["vars", "PUBLISH_TOKEN_SHA256"], "secret-must-not-print", "inline_secret"),
        (["vars", "TELEMETRY_RATE_SECRET"], "secret-must-not-print", "inline_secret"),
        (["vars", "NOTICE_TOKEN_SHA256"], "secret-must-not-print", "inline_secret"),
        (["vars", "ACCESS_CODE_SHA256"], "secret-must-not-print", "inline_secret"),
        (["vars", "ACCESS_SESSION_SECRET"], "secret-must-not-print", "inline_secret"),
        (["vars", "ACCESS_GATE_ENABLED"], True, "invalid_gate"),
        (["vars", "ACCESS_SESSION_SECONDS"], "0", "invalid_numeric_setting"),
        (["vars", "ACCESS_SESSION_SECONDS"], "604801", "invalid_numeric_setting"),
        (["vars", "TELEMETRY_RETAIN_DAYS"], "91", "invalid_numeric_setting"),
        (["vars", "TELEMETRY_RETAIN_DAYS"], 30, "invalid_numeric_setting"),
        (["vars", "SESSION_WRITES_PER_DAY"], "0", "invalid_numeric_setting"),
        (["vars", "READ_ORIGIN"], "https://secret@host.example.test", "invalid_origin"),
        (["vars", "READ_ORIGIN"], "https://example.test/path", "invalid_origin"),
        (["vars", "READ_ORIGIN"], "https://example.test?key=secret", "invalid_origin"),
        (["triggers", "crons"], [], "cleanup_cron_required"),
        (["ratelimits", 1, "namespace_id"], "1001", "namespace_collision"),
        (["ratelimits", 1, "name"], "TELEMETRY_LIMITER", "invalid_rate_bindings"),
        (["ratelimits", 1, "simple", "period"], 30, "invalid_rate_limit"),
        (["ratelimits", 1, "simple", "limit"], True, "invalid_rate_limit"),
        (["r2_buckets", 0, "binding"], "ASSETS", "invalid_r2_bindings"),
        (["r2_buckets", 0, "bucket_name"], "replace-with-bucket", "invalid_bucket_name"),
        (["d1_databases", 0, "database_id"], "replace-after-setup", "invalid_database_id"),
        (["compatibility_date"], "2020-01-01", "untested_compatibility"),
        (["services"], [], "unsupported_or_missing_fields"),
    ],
)
def test_unsafe_or_unsupported_config_fails(candidate, keys, value, code):
    root, config, _, write = candidate
    set_value(config, keys, value)
    write()
    with pytest.raises(ConfigError, match=code):
        check_release_config(root)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("telemetryEnabled", True),
        ("feedbackEnabled", True),
        ("retainDays", 7),
        ("retainDays", True),
        ("retainDays", "30"),
        ("accessGate", True),
        ("accessGate", "false"),
        ("accessGate", 0),
        ("extra", "not-allowed"),
    ],
)
def test_client_settings_must_match_without_type_coercion(candidate, key, value):
    root, _, client, write = candidate
    client[key] = value
    write()
    with pytest.raises(ConfigError):
        check_release_config(root)


def test_enabling_collection_requires_origin(candidate):
    root, config, client, write = candidate
    config["vars"]["FEEDBACK_ENABLED"] = "true"
    client["feedbackEnabled"] = True
    write()
    with pytest.raises(ConfigError, match="invalid_origin"):
        check_release_config(root)


@pytest.mark.parametrize("name", ["public/private.mp4", "public/extra.json", "host/notes.txt"])
def test_unlisted_file_cannot_be_silently_deployed(candidate, name):
    root, _, _, _ = candidate
    (root / name).write_text("private")
    with pytest.raises(ConfigError, match="unexpected_release_file"):
        check_release_config(root)


def test_tracked_bytes_cannot_change_after_package_verification(candidate):
    root, _, _, _ = candidate
    p = root / "public/index.html"
    p.write_bytes(p.read_bytes().replace(b"title", b"TITLE"))
    with pytest.raises(rb.BundleError, match="inventory_mismatch"):
        check_release_config(root)


def test_missing_and_linked_assets_are_refused(candidate, tmp_path):
    root, _, _, _ = candidate
    original = root / "public/index.html"
    raw = original.read_bytes()
    original.unlink()
    with pytest.raises(OSError):
        check_release_config(root)
    target = tmp_path / "outside.html"
    target.write_bytes(raw)
    try:
        os.symlink(target, original)
    except OSError:
        pytest.skip("symlink creation unavailable on this OS/account")
    with pytest.raises(rb.BundleError, match="linked_path"):
        check_release_config(root)


def test_client_cannot_be_smuggled_into_declared_inventory(candidate):
    root, _, _, _ = candidate
    manifest = json.loads((root / rb.MANIFEST).read_text())
    manifest["files"].append({"path": CLIENT_PATH, "bytes": 1, "sha256": "0" * 64})
    (root / rb.MANIFEST).write_text(json.dumps(manifest))
    with pytest.raises(ConfigError, match="duplicate_or_reserved"):
        check_release_config(root)


@pytest.mark.parametrize("content", ['{"name":"one","name":"two"}', "/*comment*/{}", "{}", "["])
def test_invalid_config_json_is_rejected(candidate, content):
    root, _, _, _ = candidate
    (root / CONFIG_PATH).write_text(content)
    with pytest.raises((ConfigError, rb.BundleError)):
        check_release_config(root)


def test_bound_input_and_cli_errors_never_echo_private_values(candidate):
    root, config, _, write = candidate
    config["vars"]["TELEMETRY_RATE_SECRET"] = "sensitive-value"
    write()
    command = [
        sys.executable,
        "-B",
        "-S",
        str(ROOT / "scripts/check_public_host_config.py"),
        str(root),
    ]
    p = subprocess.run(command, capture_output=True, text=True)
    assert p.returncode == 2 and json.loads(p.stdout)["deployable"] is False
    assert "sensitive-value" not in p.stdout + p.stderr
    assert str(root) not in p.stdout + p.stderr
    (root / CONFIG_PATH).write_bytes(b"x" * 65537)
    with pytest.raises(rb.BundleError, match="not_regular_or_too_large"):
        check_release_config(root)


def test_cli_success_and_unknown_input_preservation(candidate):
    root, _, _, _ = candidate
    command = [
        sys.executable,
        "-B",
        "-S",
        str(ROOT / "scripts/check_public_host_config.py"),
        str(root),
    ]
    p = subprocess.run(command, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    assert json.loads(p.stdout)["ok"]
    p = subprocess.run(
        command[:-1] + [str(root / "missing-secret-location")], capture_output=True, text=True
    )
    assert p.returncode == 2
    assert "missing-secret-location" not in p.stdout + p.stderr


@pytest.mark.parametrize(
    "value",
    [
        "https://EXAMPLE.test",
        "https://example.test:443",
        "https://@example.test",
        "https://example.test/",
        "https://example.test#",
        "https://exa%6dple.test",
        "https://example.test:0",
        "https://example.test:bad",
        "https://0x7f000001",
        "https://[fe80::1%25eth0]",
        "https://xn--a.test",
    ],
)
def test_noncanonical_origins_cannot_falsely_pass(candidate, value):
    root, config, _, write = candidate
    config["vars"]["READ_ORIGIN"] = value
    write()
    with pytest.raises(ConfigError, match="invalid_origin"):
        check_release_config(root)


@pytest.mark.parametrize(
    "value",
    ["https://example.test", "https://example.test:8443", "https://127.0.0.1", "https://[::1]"],
)
def test_supported_canonical_origin_forms(candidate, value):
    root, config, _, write = candidate
    config["vars"]["READ_ORIGIN"] = value
    write()
    assert check_release_config(root)["ok"]


def test_client_access_gate_must_follow_the_server_gate(candidate):
    """WS-access3: gate ON needs accessGate true (same-origin cookie on collection), and vice versa."""
    root, config, client, write = candidate
    config["vars"]["ACCESS_GATE_ENABLED"] = "true"
    config["vars"]["READ_ORIGIN"] = ""
    write()
    with pytest.raises(ConfigError, match="client_server_settings_mismatch"):
        check_release_config(root)
    client["accessGate"] = True
    write()
    assert check_release_config(root)["ok"] is True
    config["vars"]["ACCESS_GATE_ENABLED"] = "false"
    write()
    with pytest.raises(ConfigError, match="client_server_settings_mismatch"):
        check_release_config(root)
    del client["accessGate"]
    write()
    with pytest.raises(ConfigError):
        check_release_config(root)
