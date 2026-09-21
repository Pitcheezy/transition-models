"""Check all recorded game states through the same local HTTP API used by the demo."""

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import median, quantiles
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=Path("docs/results/mlb_p0/game_747139_manifest.json")
    )
    parser.add_argument("--server-url", default="http://127.0.0.1:8770")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    url = urlparse(args.server_url)
    if (
        url.scheme != "http"
        or url.hostname not in ("127.0.0.1", "localhost")
        or url.username
        or url.password
        or url.path not in ("", "/")
        or url.query
        or url.fragment
    ):
        parser.error("server-url must be a localhost HTTP origin")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    pitches = manifest["pitches"]
    if not pitches or any(p["identity_status"] != "verified" for p in pitches):
        parser.error("Every pitch identity must be verified before the service check")
    keys = [(p["game_pk"], p["at_bat_number"], p["pitch_number"]) for p in pitches]
    if len(set(keys)) != len(keys):
        parser.error("Duplicate pitch identities")
    counts, reasons, players = Counter(), Counter(), {}
    elapsed, server_elapsed = [], []
    model_versions = set()
    for pitch in pitches:
        request = Request(
            args.server_url.rstrip("/") + "/api/predict",
            data=json.dumps(pitch["pre_state"], allow_nan=False).encode(),
            headers={"Content-Type": "application/json"},
        )
        start = perf_counter()
        try:
            with urlopen(request, timeout=30) as response:
                result = json.load(response)
        except HTTPError as exc:
            raise SystemExit(
                f"Service rejected pitch {keys[len(elapsed)]}: {exc.read().decode()}"
            ) from exc
        except URLError as exc:
            raise SystemExit(
                "Start scripts/59_serve_manual_demo.py before this HTTP check"
            ) from exc
        elapsed.append((perf_counter() - start) * 1000)
        server_elapsed.append(result["elapsed_ms"])
        if result["schema"] != "manual_recommendation_v1" or len(result["candidates"]) != 9:
            raise ValueError("Unexpected response contract")
        model_versions.add((result["selected_model"], result["feature_schema"]))
        for candidate in result["candidates"]:
            values = list(candidate["legacy_probabilities"].values())
            if (
                len(values) != 10
                or any(not math.isfinite(value) or not 0 <= value <= 1 for value in values)
                or abs(sum(values) - 1) > 1e-5
            ):
                raise ValueError("Invalid probability distribution in HTTP response")
        recommended = result["recommendation"] is not None
        counts["recommended" if recommended else "withheld"] += 1
        if not recommended:
            reasons[result["reason"]] += 1
        player = players.setdefault(
            str(pitch["pre_state"]["pitcher"]), {"pitches": 0, "recommended": 0}
        )
        player["pitches"] += 1
        player["recommended"] += int(recommended)
        if len(elapsed) % 50 == 0:
            print(f"Checked {len(elapsed)}/{len(pitches)} states", flush=True)
    if len(model_versions) != 1:
        raise ValueError("Service model changed during the check")

    def timing(values):
        return {
            "median": median(values),
            "p95": quantiles(values, n=100, method="inclusive")[94]
            if len(values) > 1
            else values[0],
        }

    selected_model, feature_schema = model_versions.pop()
    report = {
        "game_pk": manifest["game_pk"],
        "checked_at": datetime.now(UTC).isoformat(),
        "source_manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "scope": "Real HTTP service check; development only, not accuracy or causal-policy evaluation.",
        "selected_model": selected_model,
        "feature_schema": feature_schema,
        "states_processed": len(elapsed),
        "probability_validation": "Nine candidates per state, ten finite normalized probabilities each.",
        "recommendations": dict(counts),
        "withheld_reasons": dict(reasons),
        "pitchers": players,
        "latency": {
            "unit": "ms",
            "server_computation": timing(server_elapsed),
            "http_round_trip": timing(elapsed),
            "scope": "Sequential local API calls; excludes startup, video, OCR and UI rendering.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
