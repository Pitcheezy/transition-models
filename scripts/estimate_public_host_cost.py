"""Read-only cost scenario calculator using a dated public pricing snapshot."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.operations.host_cost import EstimateError, report  # noqa: E402
from src.operations.release_bundle import BundleError, parse_json  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenarios")
    args = parser.parse_args()
    try:
        with Path(args.scenarios).open("rb") as handle:
            raw = handle.read(65537)
        if len(raw) > 65536:
            raise EstimateError("input_too_large")
        result = report(parse_json(raw, 65536))
    except (OSError, BundleError, EstimateError) as error:
        code = str(error) if isinstance(error, EstimateError) else "input_unavailable_or_invalid"
        print(json.dumps({"ok": False, "error": code}))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
