"""Offline checks for a bounded release directory and our supported single-environment config."""

import ipaddress
import os
import re
import stat
from pathlib import Path
from urllib.parse import urlsplit

from . import release_bundle as rb

MAX_CONFIG_BYTES = 64 * 1024
CONFIG_PATH = "host/wrangler.deploy.json"
CLIENT_PATH = "public/collection-settings.json"
GATES = ("DATA_READ_ENABLED", "UPLOAD_ENABLED", "TELEMETRY_ENABLED", "FEEDBACK_ENABLED")
VARIABLES = (
    *GATES,
    "READ_ORIGIN",
    "COLLECTION_ORIGIN",
    "TELEMETRY_RETAIN_DAYS",
    "SESSION_WRITES_PER_DAY",
    "FEEDBACK_ROWS_PER_DAY",
)
UNVERIFIED = (
    "account_and_provider_configuration",
    "r2_private_access",
    "d1_migration_and_backups",
    "secret_installation",
    "cron_execution",
    "namespace_isolation_across_account",
    "frontend_build_provenance_and_settings_consumption",
    "song_contract",
    "public_rights",
    "deployed_bytes_and_routes",
    "live_browser_and_load",
)


class ConfigError(ValueError):
    """A fixed diagnostic code; never interpolate source data."""


def require(condition, code):
    if not condition:
        raise ConfigError(code)


def fields(value, required, optional=()):
    require(isinstance(value, dict), "object_required")
    require(
        set(required) <= value.keys() <= set(required) | set(optional),
        "unsupported_or_missing_fields",
    )


def origin(value, allow_empty=False):
    if allow_empty and value == "":
        return
    require(isinstance(value, str) and len(value) <= 2048, "invalid_origin")
    try:
        parsed = urlsplit(value)
        port = parsed.port
        host = parsed.hostname or ""
        try:
            address = ipaddress.ip_address(host)
            authority = f"[{address}]" if address.version == 6 else str(address)
            host_valid = "%" not in host
        except ValueError:
            # Supported origin subset: canonical ASCII DNS, or canonical IP above.
            host_valid = bool(
                re.fullmatch(
                    r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
                    r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?",
                    host,
                )
            ) and not any(label.startswith("xn--") for label in host.split("."))
            authority = host
        if port is not None and port != 443:
            authority += f":{port}"
        valid = (
            parsed.scheme == "https"
            and host_valid
            and parsed.username is None
            and parsed.password is None
            and value == "https://" + authority
            and (port is None or 1 <= port <= 65535)
        )
    except ValueError:
        valid = False
    require(valid, "invalid_origin")


def positive_setting(value, maximum):
    require(
        isinstance(value, str)
        and re.fullmatch(r"[1-9][0-9]{0,8}", value) is not None
        and int(value) <= maximum,
        "invalid_numeric_setting",
    )
    return int(value)


def _release_files(root):
    root = rb._plain_path(root)
    require(root.is_dir(), "release_directory_required")
    manifest_raw = rb._read_regular(root / rb.MANIFEST, rb.MAX_MANIFEST_BYTES)
    manifest = rb.parse_json(manifest_raw)
    require(
        isinstance(manifest, dict) and isinstance(manifest.get("files"), list), "invalid_inventory"
    )
    rows = manifest["files"]
    require(1 <= len(rows) <= rb.MAX_FILES, "invalid_inventory")
    files = {rb.MANIFEST: manifest_raw}
    expected = {rb.MANIFEST, CONFIG_PATH, CLIENT_PATH}
    total = 0
    for row in rows:
        fields(row, ("path", "bytes", "sha256"))
        name = rb.safe_path(row["path"])
        require(name not in expected, "duplicate_or_reserved_file")
        require(
            type(row["bytes"]) is int and 0 <= row["bytes"] <= rb.MAX_FILE_BYTES,
            "invalid_inventory",
        )
        total += row["bytes"]
        require(total <= rb.MAX_TOTAL_BYTES, "release_too_large")
        expected.add(name)
        files[name] = rb._read_regular(root / name, row["bytes"])
    receipt = rb.verify_files(files)
    # Wrangler serves every asset in public/, so reject unlisted extra files too.
    stack = [root]
    found = set()
    entries = 0
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as children:
            for child in children:
                entries += 1
                require(entries <= rb.MAX_FILES * 3, "too_many_entries")
                path = Path(child.path)
                name = rb.safe_path(path.relative_to(root).as_posix())
                rb._plain_path(path)
                info = path.lstat()
                if stat.S_ISDIR(info.st_mode):
                    stack.append(path)
                else:
                    require(
                        stat.S_ISREG(info.st_mode) and name in expected, "unexpected_release_file"
                    )
                    found.add(name)
    require(found == expected, "release_file_missing")
    return root, receipt


def validate_config(config, client, root):
    require(isinstance(config, dict), "object_required")
    require("env" not in config, "environment_overrides_unsupported")
    fields(
        config,
        (
            "name",
            "main",
            "compatibility_date",
            "workers_dev",
            "preview_urls",
            "vars",
            "r2_buckets",
            "assets",
            "d1_databases",
            "ratelimits",
            "triggers",
        ),
        ("$schema", "account_id", "limits"),
    )
    require(
        isinstance(config["name"], str) and re.fullmatch(r"[a-z][a-z0-9-]{2,62}", config["name"]),
        "invalid_worker_name",
    )
    require(config["compatibility_date"] == "2026-07-30", "untested_compatibility_date")
    require(
        config["workers_dev"] is False and config["preview_urls"] is False,
        "unexpected_public_endpoint",
    )
    if "account_id" in config:
        require(
            isinstance(config["account_id"], str)
            and re.fullmatch(r"[a-f0-9]{32}", config["account_id"]),
            "invalid_account_id",
        )
    if "limits" in config:
        fields(config["limits"], ("cpu_ms",))
        value = config["limits"]["cpu_ms"]
        require(type(value) is int and 1 <= value <= 300000, "invalid_cpu_limit")
    require(config["main"] == "worker.mjs", "wrong_worker_path")
    require(
        rb._plain_path(root / "host" / config["main"]) == root / "host/worker.mjs",
        "wrong_worker_path",
    )
    assets = config["assets"]
    fields(assets, ("directory", "binding", "run_worker_first", "not_found_handling"))
    require(assets["directory"] == "../public", "wrong_assets_path")
    require(
        rb._plain_path(root / "host" / assets["directory"]) == root / "public", "wrong_assets_path"
    )
    require(
        assets["binding"] == "ASSETS"
        and assets["run_worker_first"] is True
        and assets["not_found_handling"] == "single-page-application",
        "unsafe_asset_routing",
    )
    variables = config["vars"]
    require(isinstance(variables, dict), "object_required")
    require(
        not {"PUBLISH_TOKEN_SHA256", "TELEMETRY_RATE_SECRET", "NOTICE_TOKEN_SHA256"}
        & variables.keys(),
        "inline_secret_not_allowed",
    )
    fields(variables, VARIABLES)
    for gate in GATES:
        require(variables[gate] in ("true", "false"), "invalid_gate")
    origin(variables["READ_ORIGIN"], allow_empty=True)
    active = variables["TELEMETRY_ENABLED"] == "true" or variables["FEEDBACK_ENABLED"] == "true"
    origin(variables["COLLECTION_ORIGIN"], allow_empty=not active)
    days = positive_setting(variables["TELEMETRY_RETAIN_DAYS"], 90)
    positive_setting(variables["SESSION_WRITES_PER_DAY"], 1000000)
    positive_setting(variables["FEEDBACK_ROWS_PER_DAY"], 1000000)
    fields(client, ("telemetryEnabled", "feedbackEnabled", "retainDays"))
    require(
        type(client["telemetryEnabled"]) is bool
        and type(client["feedbackEnabled"]) is bool
        and type(client["retainDays"]) is int,
        "invalid_client_settings",
    )
    require(
        client["telemetryEnabled"] == (variables["TELEMETRY_ENABLED"] == "true")
        and client["feedbackEnabled"] == (variables["FEEDBACK_ENABLED"] == "true")
        and client["retainDays"] == days,
        "client_server_settings_mismatch",
    )
    r2 = config["r2_buckets"]
    require(isinstance(r2, list) and len(r2) == 1, "invalid_r2_bindings")
    fields(r2[0], ("binding", "bucket_name"))
    require(r2[0]["binding"] == "PUBLISH_BUCKET", "invalid_r2_bindings")
    bucket = r2[0]["bucket_name"]
    require(
        isinstance(bucket, str)
        and re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket)
        and not bucket.startswith("replace-"),
        "invalid_bucket_name",
    )
    d1 = config["d1_databases"]
    require(isinstance(d1, list) and len(d1) == 1, "invalid_d1_bindings")
    fields(d1[0], ("binding", "database_name", "database_id", "migrations_dir"))
    require(
        d1[0]["binding"] == "TELEMETRY_DB" and d1[0]["migrations_dir"] == "migrations",
        "invalid_d1_bindings",
    )
    require(
        isinstance(d1[0]["database_name"], str)
        and re.fullmatch(r"[a-zA-Z0-9_-]{3,64}", d1[0]["database_name"])
        and not d1[0]["database_name"].startswith("replace-"),
        "invalid_database_name",
    )
    require(
        isinstance(d1[0]["database_id"], str)
        and re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", d1[0]["database_id"]),
        "invalid_database_id",
    )
    rates = config["ratelimits"]
    require(isinstance(rates, list) and len(rates) == 2, "invalid_rate_bindings")
    names, namespaces = set(), set()
    for rate in rates:
        fields(rate, ("name", "namespace_id", "simple"))
        require(
            rate["name"] in ("TELEMETRY_LIMITER", "PUBLISH_LIMITER") and rate["name"] not in names,
            "invalid_rate_bindings",
        )
        names.add(rate["name"])
        namespace = rate["namespace_id"]
        require(
            isinstance(namespace, str)
            and re.fullmatch(r"[1-9][0-9]{0,14}", namespace)
            and namespace not in namespaces,
            "namespace_collision_or_invalid",
        )
        namespaces.add(namespace)
        fields(rate["simple"], ("limit", "period"))
        limit, period = rate["simple"]["limit"], rate["simple"]["period"]
        require(
            type(limit) is int
            and 1 <= limit <= 1000000
            and type(period) is int
            and period in (10, 60),
            "invalid_rate_limit",
        )
    fields(config["triggers"], ("crons",))
    # Cleanup remains mandatory while collection is off: existing rows still expire.
    require(config["triggers"]["crons"] == ["17 3 * * *"], "cleanup_cron_required")


def check_release_config(release_directory):
    """Check supplied bytes only; do not execute, change files, contact accounts or deploy."""
    root, package = _release_files(Path(release_directory))
    config_raw = rb._read_regular(root / CONFIG_PATH, MAX_CONFIG_BYTES)
    client_raw = rb._read_regular(root / CLIENT_PATH, MAX_CONFIG_BYTES)
    config = rb.parse_json(config_raw, MAX_CONFIG_BYTES)
    client = rb.parse_json(client_raw, MAX_CONFIG_BYTES)
    validate_config(config, client, root)
    return {
        "schema": "pitcheezy-host-config-check-v1",
        "ok": True,
        "deployable": False,
        "mode": package["mode"],
        "manifest_sha256": package["manifest_sha256"],
        "host_commit": package["host_commit"],
        "frontend_commit": package["frontend_commit"],
        "config_sha256": rb.digest(config_raw),
        "client_settings_sha256": rb.digest(client_raw),
        "checks": [
            "inventory_bytes",
            "single_environment_config",
            "package_paths",
            "worker_first",
            "private_endpoint_defaults",
            "bindings_and_local_namespaces",
            "collection_settings_match",
            "cleanup_cron_present",
        ],
        "unverified": list(UNVERIFIED),
    }
