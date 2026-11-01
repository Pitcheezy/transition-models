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
    statepath = log / "registration.private.json"
    state = json.loads(statepath.read_text(encoding="utf-8")) if statepath.exists() else {
        "initial_version": manifest["expected_initial_version"], "steps": [], "pending": None
    }
    require(state["initial_version"] == manifest["expected_initial_version"], "journal_target_mismatch")
    require(state.get("pending") is None, "previous_step_uncertain_do_not_retry")
    require([r["name"] for r in state["steps"]] == list(NAMES[:len(state["steps"])]), "journal_order_invalid")
    env = os.environ.copy()
    # These commands use the approved Wrangler login, not user-inherited API tokens.
    for key in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_API_KEY", "CLOUDFLARE_EMAIL", "CF_API_TOKEN", "CF_API_KEY", "CF_EMAIL"):
        env.pop(key, None)
    env.update(CI="true", WRANGLER_SEND_METRICS="false", WRANGLER_SEND_ERROR_REPORTS="false",
               CLOUDFLARE_LOAD_DEV_VARS_FROM_DOT_ENV="false", NO_COLOR="1", CLOUDFLARE_ACCOUNT_ID=manifest["account_id"],
               WRANGLER_LOG="warn", WRANGLER_LOG_SANITIZE="true", WRANGLER_LOG_PATH=str(log / "wrangler-sanitized.private.log"))

    def save():
        statepath.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def call(label, args, value=None):
        command = ["node", str(cli), *args, "--config", str(cfgpath), "--env-file", manifest["empty_env_file"]]
        try:
            result = runner(command, cwd=log, env=env, input=None if value is None else value + "\n",
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        except Exception:
            raise RuntimeError("command_uncertain_do_not_retry") from None
        output = result.stdout + "\n" + result.stderr
        if value:
            output = output.replace(value, "<redacted>")
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
