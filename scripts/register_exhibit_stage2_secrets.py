"""User-run registration of exactly three stage-2 secrets via stdin, never arguments.
No Worker deployment, publisher token, route mutation, or service HTTP requests.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from datetime import datetime, timezone

NAMES = ("ACCESS_CODE_SHA256", "NOTICE_TOKEN_SHA256", "ACCESS_SESSION_SECRET")
EXPECTED_GUARD_SHA = "9a592f799ba65acc5ae36d59062cd2fe2e63a0542e488d92efad3fc5f2dd4faa"
EXPECTED_INITIAL_VERSION = "aeef75d8-7d43-4603-82c9-ebc408f184b2"
EXPECTED_MANIFEST_SHA = "2f8ae745122b04e2d6eef025db0841de46f6f672407a0d8b6c00b85b502f5e6b"
EXPECTED_MANIFEST_CONTENT_SHA = "d85eeb171d7609ec746915e37e0dc87a077e74b3ede979aa3bf9bf716b720307"
EXPECTED_SHA = "a7c4464ed07c29830a508b612c45baf00eb9faf60e4806d76fc50d35c5097b77"


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def latest_version(deployments):
    require(isinstance(deployments, list) and bool(deployments), "deployment_list_invalid")
    latest = max(deployments, key=lambda row: row["created_on"])
    active = [row for row in latest["versions"] if row["percentage"] > 0]
    require(len(active) == 1 and active[0]["percentage"] == 100, "split_deployment_refused")
    return active[0]["version_id"]


def credential_value(name, manifest):
    if name == "ACCESS_SESSION_SECRET":
        return secrets.token_urlsafe(32)
    require(name in NAMES[:2], "unexpected_secret_name")
    key = "access_code_file" if name == NAMES[0] else "notice_token_file"
    value = Path(manifest[key]).read_text(encoding="utf-8-sig").strip()
    require(8 <= len(value) <= 512 and not any(c.isspace() for c in value), "credential_file_invalid")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def register(manifest, runner=None):
    runner = runner or subprocess.run
    require(hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest() == EXPECTED_MANIFEST_CONTENT_SHA, "manifest_content_changed")
    require(manifest["expected_initial_version"] == EXPECTED_INITIAL_VERSION, "initial_version_mismatch")
    manifest_path = Path(manifest["log_directory"]).parent / "secret-registration-input.private.json"
    require(hashlib.sha256(manifest_path.read_bytes()).hexdigest() == EXPECTED_MANIFEST_SHA, "manifest_file_changed")
    require(manifest["schema"] == "pitcheezy-stage2-secret-registration-private-v1", "manifest_invalid")
    cfgpath = Path(manifest["configuration_file"])
    cfgbytes = cfgpath.read_bytes()
    require(manifest["expected_configuration_sha256"] == EXPECTED_SHA, "unexpected_configuration_pin")
    require(hashlib.sha256(cfgbytes).hexdigest() == EXPECTED_SHA, "configuration_changed")
    cfg = json.loads(cfgbytes)
    require(cfg["name"] == manifest["worker_name"] and cfg["vars"]["UPLOAD_ENABLED"] == "false", "target_mismatch")
    require(cfg["workers_dev"] is False and cfg["preview_urls"] is False and "routes" not in cfg, "unexpected_public_binding")
    root = Path(manifest["repository_root"])
    cli = root / "ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js"
    require(cli.is_file(), "pinned_cli_missing")
    require(json.loads((cli.parent.parent / "package.json").read_text(encoding="utf-8"))["version"] == "4.151.0", "pinned_cli_version_mismatch")
    require(Path(manifest["empty_env_file"]).read_bytes() == b"", "env_file_not_empty")
    log = Path(manifest["log_directory"])
    log.mkdir(exist_ok=True)
    node = Path(manifest["node_executable"])
    require(node.is_absolute() and node.is_file() and hashlib.sha256(node.read_bytes()).hexdigest() == manifest["node_sha256"], "node_pin_changed")
    guard = root / "scripts/exhibit_stage2_cli_guard.cjs"
    require(guard.is_file() and hashlib.sha256(guard.read_bytes()).hexdigest() == EXPECTED_GUARD_SHA, "request_guard_missing_or_changed")
    statepath = log / "registration.private.json"
    state = json.loads(statepath.read_text(encoding="utf-8")) if statepath.exists() else {
        "initial_version": manifest["expected_initial_version"], "steps": [], "pending": None
    }
    require(state["initial_version"] == manifest["expected_initial_version"], "journal_target_mismatch")
    require(state.get("pending") is None, "previous_step_uncertain_do_not_retry")
    require([r["name"] for r in state["steps"]] == list(NAMES[:len(state["steps"])]), "journal_order_invalid")
    # Do not inherit API destinations, proxies, Node preload, credentials or CLI overrides.
    allowed = {"SYSTEMROOT", "WINDIR", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "HOMEDRIVE", "HOMEPATH"}
    if len(state["steps"]) == len(NAMES):
        return state  # Completed run is read-only; never repeat registration.
    lockpath = log / "registration.started"
    try:
        fd = os.open(lockpath, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
    except FileExistsError:
        raise RuntimeError("registration_already_started_do_not_retry") from None
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    env.update(CI="true", WRANGLER_SEND_METRICS="false", WRANGLER_SEND_ERROR_REPORTS="false",
               CLOUDFLARE_LOAD_DEV_VARS_FROM_DOT_ENV="false", NO_COLOR="1", CLOUDFLARE_ACCOUNT_ID=manifest["account_id"],
               WRANGLER_LOG="warn", WRANGLER_LOG_SANITIZE="true", WRANGLER_WRITE_LOGS="false",
               PITCHEEZY_STAGE2_MANIFEST=str(manifest_path), PATH=str(node.parent))


    def save():
        temporary = statepath.with_suffix(".pending")
        with temporary.open("w", encoding="utf-8") as target:
            target.write(json.dumps(state, indent=2) + "\n")
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, statepath)

    def call(label, args, value=None):
        command = [str(node), "--require", str(guard), str(cli), *args, "--config", str(cfgpath), "--env-file", manifest["empty_env_file"]]
        try:
            result = runner(command, cwd=log, env=env, input=None if value is None else value + "\n",
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        except Exception:
            raise RuntimeError("command_uncertain_do_not_retry") from None
        # No mutation stdout/stderr is persisted, even if a provider echoes a partial value.
        output = json.dumps({"returncode": result.returncode, "output_discarded": True}) if value is not None else result.stdout + "\n" + result.stderr
        (log / (label + ".private.txt")).write_text(output, encoding="utf-8")
        require(result.returncode == 0, "command_failed_do_not_retry")
        return result.stdout

    version = latest_version(json.loads(call("deployments-before", ["deployments", "list", "--json"])))
    expected_version = state["steps"][-1]["version"] if state["steps"] else state["initial_version"]
    require(version == expected_version, "active_version_changed")
    existing = json.loads(call("secret-names-before", ["secret", "list", "--format", "json"]))
    require({row["name"] for row in existing} == {r["name"] for r in state["steps"]}, "unexpected_secret_names")
    for index in range(len(state["steps"]), len(NAMES)):
        name = NAMES[index]
        value = credential_value(name, manifest)
        require(hashlib.sha256(cfgpath.read_bytes()).hexdigest() == EXPECTED_SHA, "configuration_changed")
        state["pending"] = name
        save()
        call(f"put-{index+1}", ["secret", "put", name], value)
        value = None
        new_version = latest_version(json.loads(call(f"version-{index+1}", ["deployments", "list", "--json"])))
        require(new_version != version, "secret_version_not_observed")
        listed = json.loads(call(f"names-{index+1}", ["secret", "list", "--format", "json"]))
        require({r["name"] for r in listed} == set(NAMES[:index+1]), "secret_names_mismatch")
        state["steps"].append({"name": name, "version": new_version, "recorded_at_utc": datetime.now(timezone.utc).isoformat()})
        state["pending"] = None
        save()
        print(name + " registered; version: " + new_version)
        version = new_version
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--register-secrets", action="store_true")
    args = parser.parse_args()
    if not args.register_secrets:
        print("No changes made. User registration requires --register-secrets.")
        return 0
    try:
        if input("Register only 3 approved secrets? Press Enter to continue, or type q to cancel: ").strip():
            print("Cancelled; no changes made.")
            return 0
        result = register(json.loads(Path(args.manifest).read_text(encoding="utf-8-sig")))
        print("All 3 registered. No publisher token, route, upload, or Worker deployment performed.")
        print("Final version: " + result["steps"][-1]["version"])
        return 0
    except Exception as exc:
        safe = str(exc) if isinstance(exc, RuntimeError) else "registration_failed_details_private"
        print("STOP: " + safe)
        print("Do not rerun or roll back. Tell Codex registration stopped; never paste credentials.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
