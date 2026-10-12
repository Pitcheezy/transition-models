"""Check one offline release directory; no account access, build execution or deployment."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.operations.host_config import ConfigError, check_release_config  # noqa: E402
from src.operations.release_bundle import BundleError  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_directory", type=Path)
    args = parser.parse_args(argv)
    try:
        report = check_release_config(args.release_directory)
    except (ConfigError, BundleError) as exc:
        print(json.dumps({"ok": False, "deployable": False, "error": str(exc)}))
        return 2
    except OSError:
        print(json.dumps({"ok": False, "deployable": False, "error": "input_unavailable"}))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
