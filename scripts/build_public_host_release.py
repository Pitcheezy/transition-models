"""Assemble/check an offline host release candidate; never deploy or execute a supplied build."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.operations.release_bundle import (  # noqa: E402
    BundleError,
    assemble,
    check_bundle,
    read_frontend,
    read_host_commit,
    read_provenance,
    write_bundle,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--frontend", type=Path, required=True)
    build.add_argument("--provenance", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--mode", choices=("synthetic", "candidate"), required=True)
    build.add_argument("--host-commit", required=True)
    check = commands.add_parser("check")
    check.add_argument("bundle", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            result = check_bundle(args.bundle)
        else:
            provenance = read_provenance(args.provenance)
            payload = read_host_commit(ROOT, args.host_commit)
            payload.update(read_frontend(args.frontend))
            files = assemble(payload, provenance, args.host_commit, args.mode)
            result = write_bundle(args.output, files, args.frontend)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except BundleError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 2
    except OSError as exc:
        # OSError text carries file system paths; only the errno is reported.
        print(json.dumps({"ok": False, "error": "io_error", "errno": exc.errno}), file=sys.stderr)
        return 2
    except subprocess.SubprocessError:
        print(json.dumps({"ok": False, "error": "subprocess_error"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
