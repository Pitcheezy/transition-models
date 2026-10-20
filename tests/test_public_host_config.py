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


# Optional scoped publisher settings must never be mistaken for support in an old host bundle.
SCOPED_RUNTIME = ("worker.mjs", "gateway.mjs", "notice.mjs", "access.mjs", "telemetry.mjs")


def install_scoped_runtime(candidate, *, mutate=None, eol=None):
    root, config, _, write = candidate
    for name in SCOPED_RUNTIME:
        raw = (ROOT / "ops/public-host" / name).read_bytes()
        if eol:
            raw = raw.replace(b"\r\n", b"\n")
            if eol == "crlf":
                raw = raw.replace(b"\n", b"\r\n")
        if mutate == name:
            raw += b"\n// changed runtime, not the trusted checker source\n"
        (root / "host" / name).write_bytes(raw)
    # Rebuild the inventory too: matching an attacker-supplied SHA is not source identity.
    manifest_path = root / rb.MANIFEST
    manifest = json.loads(manifest_path.read_bytes())
    for row in manifest["files"]:
        raw = (root / row["path"]).read_bytes()
        row.update(bytes=len(raw), sha256=rb.digest(raw))
    manifest_path.write_bytes(rb.canonical(manifest))
    config["vars"].update(
        PUBLISH_KEY_SCOPE="v1/game/123.json", PUBLISH_EXPIRES_AT="2026-10-17T12:00:00.000Z"
    )
    write()
    return root, config, write


def test_scoped_current_runtime_requires_eol_source_identity(candidate):
    root, _, _ = install_scoped_runtime(candidate)
    report = check_release_config(root)
    assert report["ok"] and not report["deployable"]
    assert "scoped_upload_config" in report["checks"]
    assert "scoped_upload_runtime_eol_identity" in report["checks"]
    assert "v1/game/123.json" not in json.dumps(report)
    assert "2026-10-17T12:00:00.000Z" not in json.dumps(report)
    assert "deployed_bytes_and_routes" in report["unverified"]


def test_legacy_config_does_not_require_current_runtime(candidate):
    root, _, _, _ = candidate
    assert (root / "host/gateway.mjs").read_bytes() == b"synthetic fixture\n"
    assert "scoped_upload_config" not in check_release_config(root)["checks"]


def test_scoped_legacy_runtime_is_rejected_even_with_valid_inventory(candidate):
    root, config, _, write = candidate
    config["vars"].update(
        PUBLISH_KEY_SCOPE="v1/game/123.json", PUBLISH_EXPIRES_AT="2026-10-17T12:00:00.000Z"
    )
    write()
    with pytest.raises(ConfigError, match="scoped_upload_runtime_mismatch"):
        check_release_config(root)


@pytest.mark.parametrize("name", SCOPED_RUNTIME)
def test_scoped_modified_runtime_rejected_after_fresh_inventory(candidate, name):
    root, _, _ = install_scoped_runtime(candidate, mutate=name)
    with pytest.raises(ConfigError, match="scoped_upload_runtime_mismatch"):
        check_release_config(root)


@pytest.mark.parametrize("eol", ["lf", "crlf"])
def test_scoped_runtime_identity_allows_only_crlf_lf_equivalence(candidate, eol):
    root, _, _ = install_scoped_runtime(candidate, eol=eol)
    assert check_release_config(root)["ok"]


def test_scoped_runtime_inventory_is_verified_before_source_comparison(candidate):
    root, _, _ = install_scoped_runtime(candidate)
    target = root / "host/gateway.mjs"
    raw = target.read_bytes()
    target.write_bytes(b"X" + raw[1:])
    with pytest.raises(rb.BundleError, match="inventory_mismatch"):
        check_release_config(root)


@pytest.mark.parametrize("missing", ["PUBLISH_KEY_SCOPE", "PUBLISH_EXPIRES_AT"])
def test_publish_scope_requires_complete_pair(candidate, missing):
    root, config, write = install_scoped_runtime(candidate)
    del config["vars"][missing]
    write()
    with pytest.raises(ConfigError, match="incomplete_publish_scope"):
        check_release_config(root)


@pytest.mark.parametrize(
    "key",
    [
        "v1/manifest.json",
        "v1/health.json",
        "v1/dates.json",
        "v1/game/1.json",
        "v1/setup/999999999999.json",
        "v1/games/2024-02-29.json",
        "v1/games/0001-01-01.json",
    ],
)
def test_publish_scope_accepts_exact_existing_key_forms(candidate, key):
    root, config, write = install_scoped_runtime(candidate)
    config["vars"]["PUBLISH_KEY_SCOPE"] = key
    write()
    assert check_release_config(root)["ok"]


@pytest.mark.parametrize(
    "key",
    [
        None,
        False,
        123,
        "",
        "/v1/game/123.json",
        "v1/game/0.json",
        "v1/game/01.json",
        "v1/game/1234567890123.json",
        "v1/game/*.json",
        "v1/game/../health.json",
        "v1/game/%31.json",
        "v1/game/123.json?x=1",
        "v1/game/123.json#x",
        "v1/game/123.json/extra",
        "v1//game/123.json",
        "v1\\game\\123.json",
        "https://private.example/v1/game/123.json",
        "v1/health.json\n",
        "v1/HEALTH.json",
        "v1/games/0000-01-01.json",
        "v1/games/2026-02-29.json",
        "v1/games/2026-04-31.json",
        "v1/games/2026-13-01.json",
        "v1/games/2026-00-01.json",
        "v1/games/2026-01-00.json",
    ],
)
def test_publish_scope_rejects_noncanonical_or_invalid_keys(candidate, key):
    root, config, write = install_scoped_runtime(candidate)
    config["vars"]["PUBLISH_KEY_SCOPE"] = key
    write()
    with pytest.raises(ConfigError, match="invalid_publish_scope_key"):
        check_release_config(root)


@pytest.mark.parametrize(
    "expires",
    [
        "0001-01-01T00:00:00.000Z",
        "2024-02-29T23:59:59.999Z",
        "9999-12-31T23:59:59.999Z",
    ],
)
def test_publish_expiry_is_structural_and_does_not_extend_past_dates(candidate, expires):
    root, config, write = install_scoped_runtime(candidate)
    config["vars"]["PUBLISH_EXPIRES_AT"] = expires
    write()
    assert check_release_config(root)["ok"]


@pytest.mark.parametrize(
    "expires",
    [
        None,
        False,
        123,
        "",
        "2026-10-17T12:00:00Z",
        "2026-10-17T12:00:00.00Z",
        "2026-10-17T12:00:00.0000Z",
        "2026-10-17T12:00:00.000+00:00",
        "2026-10-17T12:00:00.000z",
        "2026-10-17 12:00:00.000Z",
        "2026-10-17T12:00:00.000Z\n",
        "0000-01-01T00:00:00.000Z",
        "2026-02-29T00:00:00.000Z",
        "2026-04-31T00:00:00.000Z",
        "2026-01-01T24:00:00.000Z",
        "2026-01-01T23:60:00.000Z",
        "2026-01-01T23:59:60.000Z",
        "2026-13-01T00:00:00.000Z",
    ],
)
def test_publish_expiry_rejects_ambiguous_and_impossible_utc_values(candidate, expires):
    root, config, write = install_scoped_runtime(candidate)
    config["vars"]["PUBLISH_EXPIRES_AT"] = expires
    write()
    with pytest.raises(ConfigError, match="invalid_publish_expiry"):
        check_release_config(root)


def test_scoped_runtime_comparison_uses_the_inventory_verified_snapshot(candidate, monkeypatch):
    from src.operations import host_config as hc

    root, config, _, write = candidate
    config["vars"].update(
        PUBLISH_KEY_SCOPE="v1/game/123.json", PUBLISH_EXPIRES_AT="2026-10-17T12:00:00.000Z"
    )
    write()
    original = hc.validate_config

    def swap_after_inventory(config, client, release_root):
        original(config, client, release_root)
        # Simulate a concurrent replacement after inventory verification. The old, verified
        # runtime must still be rejected rather than comparing the newly substituted source.
        for name in SCOPED_RUNTIME:
            (release_root / "host" / name).write_bytes(
                (ROOT / "ops/public-host" / name).read_bytes()
            )

    monkeypatch.setattr(hc, "validate_config", swap_after_inventory)
    with pytest.raises(ConfigError, match="scoped_upload_runtime_mismatch"):
        check_release_config(root)


def test_large_json_integer_config_cli_rejects_cleanly_without_changing_inputs(candidate):
    root, _, _, _ = candidate
    (root / CONFIG_PATH).write_bytes(b'{"number":' + b"1" * 5000 + b"}")
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-S",
            "-X",
            "int_max_str_digits=640",
            str(ROOT / "scripts/check_public_host_config.py"),
            str(root),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 2
    assert json.loads(result.stdout) == {
        "ok": False,
        "deployable": False,
        "error": "invalid_json",
    }
    assert result.stderr == ""
    assert str(root) not in result.stdout
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
