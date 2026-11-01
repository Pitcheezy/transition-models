import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import register_exhibit_stage2_secrets as op


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    cfg = {"name": "unit-test-only", "vars": {"UPLOAD_ENABLED": "false"}, "workers_dev": False, "preview_urls": False}
    config = tmp_path / "config.json"
    config.write_text(json.dumps(cfg), encoding="utf-8")
    digest = hashlib.sha256(config.read_bytes()).hexdigest()
    monkeypatch.setattr(op, "EXPECTED_SHA", digest)
    cli = tmp_path / "ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js"
    cli.parent.mkdir(parents=True)
    cli.write_text("// mocked, never executed", encoding="utf-8")
    (cli.parent.parent / "package.json").write_text(json.dumps({"version": "4.151.0"}), encoding="utf-8")
    (tmp_path / "empty").write_bytes(b"")
    (tmp_path / "access.txt").write_text("unit-access-code\n", encoding="utf-8")
    (tmp_path / "notice.txt").write_text("unit-notice-token\n", encoding="utf-8")
    monkeypatch.setattr(op.secrets, "token_urlsafe", lambda size: "s" * 43)
    guard = tmp_path / "scripts/exhibit_stage2_cli_guard.cjs"
    guard.parent.mkdir()
    guard.write_text("// mock only", encoding="utf-8")
    monkeypatch.setattr(op, "EXPECTED_GUARD_SHA", hashlib.sha256(guard.read_bytes()).hexdigest())
    node = tmp_path / "node.exe"
    node.write_bytes(b"mock node")
    manifest = {"schema": "pitcheezy-stage2-secret-registration-private-v1", "configuration_file": str(config),
            "expected_configuration_sha256": digest, "worker_name": "unit-test-only", "repository_root": str(tmp_path),
            "log_directory": str(tmp_path / "logs"), "account_id": "unit-account", "empty_env_file": str(tmp_path / "empty"),
            "access_code_file": str(tmp_path / "access.txt"), "notice_token_file": str(tmp_path / "notice.txt"),
            "expected_initial_version": "v0", "node_executable": str(node), "node_sha256": hashlib.sha256(node.read_bytes()).hexdigest()}
    raw = json.dumps(manifest).encode()
    (tmp_path / "secret-registration-input.private.json").write_bytes(raw)
    monkeypatch.setattr(op, "EXPECTED_MANIFEST_SHA", hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(op, "EXPECTED_MANIFEST_CONTENT_SHA", hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(",", ":")).encode()).hexdigest())
    monkeypatch.setattr(op, "EXPECTED_INITIAL_VERSION", "v0")
    return manifest


class FakeCloud:
    def __init__(self):
        self.names = []
        self.calls = []
        self.puts = []
        self.version = 0
        self.fail_after_put = False

    def __call__(self, command, **kwargs):
        args = command[4:]
        assert command[1] == "--require"
        self.calls.append((args, kwargs))
        assert kwargs["env"].get("CLOUDFLARE_API_TOKEN") is None
        assert kwargs["env"]["WRANGLER_LOG_SANITIZE"] == "true"
        assert kwargs["env"]["WRANGLER_WRITE_LOGS"] == "false"
        for key in ("CLOUDFLARE_API_BASE_URL", "CF_API_BASE_URL", "NODE_OPTIONS", "HTTPS_PROXY"):
            assert key not in kwargs["env"]
        if args[:2] == ["deployments", "list"]:
            out = [{"created_on": "2026-11-01", "versions": [{"percentage": 100, "version_id": f"v{self.version}"}]}]
        elif args[:2] == ["secret", "list"]:
            out = [{"name": n} for n in self.names]
        elif args[:2] == ["secret", "put"]:
            value = kwargs["input"].strip()
            assert value not in command
            self.puts.append((args[2], value))
            self.names.append(args[2])
            self.version += 1
            if self.fail_after_put:
                raise TimeoutError("ambiguous mutation")
            return SimpleNamespace(returncode=0, stdout="accepted " + value, stderr="")
        else:
            raise AssertionError("unexpected command")
        return SimpleNamespace(returncode=0, stdout=json.dumps(out), stderr="")


def test_exactly_three_stdin_secrets_and_versions_no_raw_logs(prepared, monkeypatch, capsys):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "not-inherited")
    for key in ("CLOUDFLARE_API_BASE_URL", "CF_API_BASE_URL", "NODE_OPTIONS", "HTTPS_PROXY"):
        monkeypatch.setenv(key, "not-inherited")
    cloud = FakeCloud()
    state = op.register(prepared, cloud)
    assert [n for n, _ in cloud.puts] == list(op.NAMES)
    assert cloud.puts[0][1] == hashlib.sha256(b"unit-access-code").hexdigest()
    assert cloud.puts[1][1] == hashlib.sha256(b"unit-notice-token").hexdigest()
    assert cloud.puts[2][1] == "s" * 43
    assert [r["version"] for r in state["steps"]] == ["v1", "v2", "v3"]
    assert state["pending"] is None
    displayed = capsys.readouterr().out
    persisted = "".join(p.read_text(encoding="utf-8") for p in Path(prepared["log_directory"]).glob("*"))
    for value in ["unit-access-code", "unit-notice-token", *[v for _, v in cloud.puts]]:
        assert value not in displayed and value not in persisted
    before = len(cloud.puts)
    op.register(prepared, cloud)
    assert len(cloud.puts) == before  # resume completed journal does not register again


def test_uncertain_put_stops_and_is_not_retried(prepared):
    cloud = FakeCloud()
    cloud.fail_after_put = True
    with pytest.raises(RuntimeError, match="uncertain"):
        op.register(prepared, cloud)
    assert len(cloud.puts) == 1
    with pytest.raises(RuntimeError, match="previous_step_uncertain"):
        op.register(prepared, cloud)
    assert len(cloud.puts) == 1


def test_configuration_drift_prevents_any_cli_call(prepared):
    Path(prepared["configuration_file"]).write_text("{}", encoding="utf-8")
    cloud = FakeCloud()
    with pytest.raises(RuntimeError, match="configuration_changed"):
        op.register(prepared, cloud)
    assert cloud.calls == []


def test_unexpected_publisher_secret_blocks_all_puts(prepared):
    cloud = FakeCloud()
    cloud.names = ["PUBLISH_TOKEN_SHA256"]
    with pytest.raises(RuntimeError, match="unexpected_secret_names"):
        op.register(prepared, cloud)
    assert cloud.puts == []


def test_changed_active_version_blocks_all_puts(prepared):
    cloud = FakeCloud()
    cloud.version = 9
    with pytest.raises(RuntimeError, match="active_version_changed"):
        op.register(prepared, cloud)
    assert cloud.puts == []


def test_invalid_credential_file_stops_before_put(prepared):
    Path(prepared["access_code_file"]).write_text("has spaces", encoding="utf-8")
    cloud = FakeCloud()
    with pytest.raises(RuntimeError, match="credential_file_invalid"):
        op.register(prepared, cloud)
    assert cloud.puts == []


def test_wrong_cli_version_prevents_cli_calls(prepared):
    package = Path(prepared["repository_root"]) / "ops/public-host-tooling/node_modules/wrangler/package.json"
    package.write_text('{"version":"0.0.0"}', encoding="utf-8")
    cloud = FakeCloud()
    with pytest.raises(RuntimeError, match="pinned_cli_version"):
        op.register(prepared, cloud)
    assert cloud.calls == []


def test_nonempty_env_file_prevents_cli_calls(prepared):
    Path(prepared["empty_env_file"]).write_text("UNEXPECTED=1", encoding="utf-8")
    cloud = FakeCloud()
    with pytest.raises(RuntimeError, match="env_file_not_empty"):
        op.register(prepared, cloud)
    assert cloud.calls == []


def test_manifest_account_tamper_blocks_cli(prepared):
    prepared["account_id"] = "other-account"
    cloud = FakeCloud()
    with pytest.raises(RuntimeError, match="manifest_content_changed"):
        op.register(prepared, cloud)
    assert cloud.calls == []


def test_node_binary_tamper_blocks_cli(prepared):
    Path(prepared["node_executable"]).write_bytes(b"changed node")
    cloud = FakeCloud()
    with pytest.raises(RuntimeError, match="node_pin_changed"):
        op.register(prepared, cloud)
    assert cloud.calls == []


def test_existing_start_guard_blocks_concurrent_execution(prepared):
    log = Path(prepared["log_directory"])
    log.mkdir()
    (log / 'registration.started').write_text('', encoding='utf-8')
    cloud = FakeCloud()
    with pytest.raises(RuntimeError, match='already_started'):
        op.register(prepared, cloud)
    assert cloud.calls == []
