"""User-run one-shot PUBLISH_TOKEN_SHA256 registration or rotation; no upload/deployment.
Only --register plus the user's Enter can mutate. CLI raw output is discarded.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess

HASH = re.compile(r"[a-f0-9]{64}\Z")
UUID = re.compile(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}\Z")
BASE_NAMES = {"ACCESS_CODE_SHA256", "NOTICE_TOKEN_SHA256", "ACCESS_SESSION_SECRET"}
NAME = "PUBLISH_TOKEN_SHA256"
FIELDS = {"schema", "phase", "repository_root", "configuration_file", "configuration_sha256", "node_executable", "node_sha256", "guard_sha256", "base_guard_sha256", "wrangler_sha256", "account_id", "worker_name", "expected_version", "token_file", "token_sha256", "empty_env_file", "output_directory"}


def require(ok, code):
    if not ok:
        raise RuntimeError(code)


def plain_path(value):
    require(isinstance(value, str) and Path(value).is_absolute(), "absolute_path_required")
    p = Path(value)
    for candidate in (p, *p.parents):
        require(not candidate.is_symlink() and not getattr(candidate, "is_junction", lambda: False)(), "linked_path_refused")
    return p


def file_sha(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_inputs(manifest_path, manifest_sha):
    require(HASH.fullmatch(manifest_sha or ""), "manifest_sha_required")
    mp = plain_path(manifest_path)
    raw = mp.read_bytes()
    require(0 < len(raw) <= 65536 and hashlib.sha256(raw).hexdigest() == manifest_sha, "manifest_sha_mismatch")
    m = json.loads(raw.decode("utf-8"))
    require(isinstance(m, dict) and set(m) == FIELDS, "manifest_fields_invalid")
    require(m["schema"] == "pitcheezy-stage3-publisher-registration-v1" and m["phase"] in {"initial", "rotate"}, "manifest_invalid")
    require(re.fullmatch(r"[a-f0-9]{32}", m["account_id"] or "") and re.fullmatch(r"[a-z0-9][a-z0-9-]*", m["worker_name"] or ""), "target_invalid")
    require(UUID.fullmatch(m["expected_version"] or ""), "version_invalid")
    root, cfgpath, node = (plain_path(m[k]) for k in ["repository_root", "configuration_file", "node_executable"])
    require(root.is_dir(), "repository_missing")
    guard = root / "scripts/exhibit_stage3_cli_guard.cjs"
    base_guard = root / "scripts/exhibit_stage2_cli_guard.cjs"
    cli = root / "ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js"
    for path, pin in [(cfgpath,"configuration_sha256"),(node,"node_sha256"),(guard,"guard_sha256"),(base_guard,"base_guard_sha256"),(cli,"wrangler_sha256")]:
        plain_path(str(path))
        require(HASH.fullmatch(m[pin] or "") and path.is_file() and file_sha(path) == m[pin], "pinned_file_changed")
    require(json.loads((cli.parent.parent / "package.json").read_text(encoding="utf-8"))["version"] == "4.151.0", "pinned_cli_version_mismatch")
    cfg = json.loads(cfgpath.read_bytes())
    require(cfg["name"] == m["worker_name"] and cfg["vars"]["UPLOAD_ENABLED"] == "false", "configuration_not_expected_off_target")
    require(all(isinstance(k, str) and isinstance(v, str) for k, v in cfg["vars"].items()), "configuration_vars_invalid")
    require(cfg["workers_dev"] is False and cfg["preview_urls"] is False and "routes" not in cfg, "unexpected_public_binding")
    require(plain_path(m["empty_env_file"]).read_bytes() == b"", "env_file_not_empty")
    plain_path(m["output_directory"])
    if m["phase"] == "initial":
        plain_path(m["token_file"])
        require(HASH.fullmatch(m["token_sha256"] or ""), "token_pin_required")
    else:
        require(m["token_file"] is None and m["token_sha256"] is None, "rotation_has_token_file")
    return m, cfg, raw


def latest_version(rows):
    require(isinstance(rows, list) and rows, "deployment_list_invalid")
    def instant(row):
        value = datetime.fromisoformat(row["created_on"].replace("Z", "+00:00"))
        require(value.tzinfo is not None, "deployment_timestamp_invalid")
        return value
    latest = max(rows, key=instant)
    active = [r for r in latest["versions"] if r["percentage"] > 0]
    require(len(active) == 1 and active[0]["percentage"] == 100 and UUID.fullmatch(active[0]["version_id"]), "split_or_invalid_deployment")
    return active[0]["version_id"]


def write_json(path, obj, *, exclusive=False):
    with path.open("x" if exclusive else "w", encoding="utf-8") as target:
        target.write(json.dumps(obj, indent=2) + "\n")
        target.flush()
        os.fsync(target.fileno())


def register(manifest_path, manifest_sha, runner=None):
    runner = runner or subprocess.run
    m, cfg, raw = load_inputs(manifest_path, manifest_sha)
    out = plain_path(m["output_directory"])
    try:
        out.mkdir(exist_ok=False)
    except FileExistsError:
        raise RuntimeError("registration_already_started_do_not_retry") from None
    state = {"phase":m["phase"], "initial_version":m["expected_version"], "pending":None, "completed":False}
    statepath = out / "registration.private.json"
    write_json(out / "started.private.json", {"manifest_sha256":manifest_sha,"started_utc":datetime.now(timezone.utc).isoformat()}, exclusive=True)
    with (out / "manifest.private.json").open("xb") as target:
        target.write(raw)
        target.flush()
        os.fsync(target.fileno())
    allowed = {"SYSTEMROOT", "WINDIR", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "HOMEDRIVE", "HOMEPATH"}
    env = {key:value for key,value in os.environ.items() if key.upper() in allowed}
    node = Path(m["node_executable"])
    root = Path(m["repository_root"])
    cli = root / "ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js"
    guard = root / "scripts/exhibit_stage3_cli_guard.cjs"
    env.update(CI="true", WRANGLER_SEND_METRICS="false", WRANGLER_SEND_ERROR_REPORTS="false", CLOUDFLARE_LOAD_DEV_VARS_FROM_DOT_ENV="false", NO_COLOR="1", CLOUDFLARE_ACCOUNT_ID=m["account_id"], WRANGLER_LOG="log", WRANGLER_LOG_SANITIZE="true", WRANGLER_WRITE_LOGS="false", PITCHEEZY_STAGE3_MANIFEST=str(manifest_path), PITCHEEZY_STAGE3_MANIFEST_SHA256=manifest_sha, PATH=str(node.parent))

    def save():
        pending = out / "state.pending.private.json"
        write_json(pending, state)
        os.replace(pending, statepath)

    def call(label, args, value=None):
        command = [str(node), "--require", str(guard), str(cli), *args, "--config", m["configuration_file"], "--env-file", m["empty_env_file"]]
        try:
            result = runner(command, cwd=out, env=env, input=None if value is None else value + "\n", capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        except Exception:
            raise RuntimeError("command_uncertain_do_not_retry") from None
        metadata = {"returncode":result.returncode, "raw_output_discarded":True}
        parsed = None
        if result.returncode == 0 and value is None:
            try:
                data = json.loads(result.stdout)
                if args[:2] == ["deployments", "list"]:
                    require(isinstance(data, list), "metadata_invalid")
                    parsed = [{"created_on":r["created_on"],"versions":[{"version_id":v["version_id"],"percentage":v["percentage"]} for v in r["versions"]]} for r in data]
                elif args[:2] == ["secret", "list"]:
                    require(isinstance(data, list), "metadata_invalid")
                    parsed = [{"name":r["name"]} for r in data]
                elif args[:2] == ["versions", "view"]:
                    bindings = data["resources"]["bindings"]
                    require(isinstance(bindings,list), "metadata_invalid")
                    pairs = [(r["name"],r["text"]) for r in bindings if r["type"] == "plain_text"]
                    require(len(pairs) == len(dict(pairs)) and all(isinstance(k,str) and isinstance(v,str) for k,v in pairs), "metadata_invalid")
                    parsed = {"id":data["id"],"vars":dict(pairs)}
                else:
                    raise RuntimeError("unexpected_metadata_command")
                metadata["result"] = parsed
            except (ValueError, TypeError, KeyError, RuntimeError):
                parsed = None
                metadata["metadata_invalid"] = True
        write_json(out / (label + ".private.json"), metadata, exclusive=True)
        require(result.returncode == 0, "command_failed_do_not_retry")
        require(value is not None or parsed is not None, "metadata_invalid")
        return parsed

    def names(rows):
        values = [r["name"] for r in rows]
        require(len(values) == len(set(values)), "duplicate_secret_names")
        return set(values)

    def check_off_version(version, label):
        data = call(label, ["versions", "view", version, "--json"])
        require(data["id"] == version and data["vars"] == cfg["vars"] and data["vars"].get("UPLOAD_ENABLED") == "false", "remote_version_or_vars_changed")

    save()
    version = latest_version(call("deployments-before", ["deployments", "list", "--json"]))
    require(version == m["expected_version"], "active_version_changed")
    check_off_version(version, "version-before")
    expected = BASE_NAMES if m["phase"] == "initial" else BASE_NAMES | {NAME}
    require(names(call("names-before", ["secret", "list", "--format", "json"])) == expected, "unexpected_secret_names")
    if m["phase"] == "initial":
        raw_token = plain_path(m["token_file"]).read_bytes()
        require(0 < len(raw_token) <= 256 and hashlib.sha256(raw_token).hexdigest() == m["token_sha256"], "token_file_changed")
        token = raw_token.decode("ascii").strip()
        require(re.fullmatch(r"[A-Za-z0-9_-]{43}", token), "token_invalid")
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        raw_token = token = None
    else:
        digest = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    # Recheck pinned local files before the single mutation; remote preconditions are recorded above.
    load_inputs(manifest_path, manifest_sha)
    state["pending"] = NAME
    save()
    call("put-publisher", ["secret", "put", NAME], digest)
    digest = None
    new_version = latest_version(call("deployments-after", ["deployments", "list", "--json"]))
    require(new_version != version, "secret_version_not_observed")
    check_off_version(new_version, "version-after")
    require(names(call("names-after", ["secret", "list", "--format", "json"])) == BASE_NAMES | {NAME}, "secret_names_mismatch")
    state.update(pending=None, completed=True, version=new_version, completed_utc=datetime.now(timezone.utc).isoformat())
    save()
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args(argv)
    try:
        m, _, _ = load_inputs(args.manifest, args.manifest_sha256)
        if not args.register:
            print("Dry-run passed. No network, secret registration, or output directory created.")
            return 0
        if input("Register only the approved publisher secret? Press Enter to continue, or type q to cancel: ").strip():
            print("Cancelled; no changes made.")
            return 0
        result = register(args.manifest, args.manifest_sha256)
        print("Publisher " + ("registered" if m["phase"] == "initial" else "rotated") + "; upload remains OFF.")
        print("Final version: " + result["version"])
        return 0
    except Exception as exc:
        code = str(exc) if isinstance(exc, RuntimeError) else "registration_failed_details_private"
        print("STOP: " + code)
        print("Do not rerun or roll back; tell Codex registration stopped. Never paste credentials.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
