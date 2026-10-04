"""Run the supported validation-path lint checks and full tests without downloading data."""

import argparse
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
QUALITY_PATHS = [
    "intent/replay.py",
    "tests/test_intent_replay.py",
    "intent/batch.py",
    "intent/temporal_audit.py",
    "intent/quality_audit.py",
    "tests/test_intent_batch.py",
    "tests/test_intent_temporal_audit.py",
    "tests/test_intent_quality_audit.py",
    "src/data/point_data.py",
    "src/data/operational.py",
    "src/data/mlb_video.py",
    "src/data/broadcast_timing.py",
    "src/data/blind_review.py",
    "src/data/mlb_sources.py",
    "src/data/pitch_observation.py",
    "src/data/player_identity.py",
    "src/evaluation/point_metrics.py",
    "src/evaluation/player_identity_ocr.py",
    "src/evaluation/operational_metrics.py",
    "src/evaluation/policy_value.py",
    "src/evaluation/run_value.py",
    "src/inference/operational.py",
    "src/inference/prepitch_contract.py",
    "src/inference/outcome_contracts.py",
    "src/inference/recommendation.py",
    "src/web",
    "src/training/point_baselines.py",
    "src/utils/model_prediction.py",
    "src/utils/experiment_paths.py",
    "src/utils/pipeline.py",
    "src/vision",
    "src/data/scoreboard_evalset.py",
    "tests/test_point_data.py",
    "tests/test_operational.py",
    "tests/test_maintenance.py",
    "tests/test_mlb_video.py",
    "tests/test_broadcast_timing.py",
    "tests/test_blind_review.py",
    "tests/test_mlb_sources.py",
    "tests/test_pitch_observation.py",
    "tests/test_player_identity.py",
    "tests/test_player_identity_ocr.py",
    "tests/test_sny_player_names.py",
    "tests/test_prepitch_contract.py",
    "tests/test_outcome_contracts.py",
    "tests/test_recommendation.py",
    "tests/test_manual_server.py",
    "tests/conftest.py",
    "tests/test_sny_scoreboard.py",
    "tests/test_ocr_reports.py",
    "tests/test_review_sheet.py",
    "tests/test_frame_cache.py",
    "tests/test_grab_broadcast_frames.py",
    "tests/test_append_timing_rows.py",
    "tests/test_scoreboard_evalset.py",
    "tests/test_pitch_timing_join.py",
    "scripts/check_project.py",
    *[
        p.relative_to(ROOT).as_posix()
        for p in sorted((ROOT / "scripts").glob("*.py"))
        if p.name[:2].isdigit() and 48 <= int(p.name[:2]) <= 74
    ],
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lint-only", action="store_true")
    parser.add_argument(
        "--cpu-only", action="store_true", help="Use CPU inference and exclude MPS hardware tests."
    )
    parser.add_argument("--test-timeout", type=int, default=600, help="Maximum pytest seconds.")
    args = parser.parse_args()
    if args.test_timeout <= 0:
        parser.error("--test-timeout must be positive")
    for command in (("ruff", "check"), ("ruff", "format", "--check")):
        subprocess.run([sys.executable, "-m", *command, *QUALITY_PATHS], cwd=ROOT, check=True)
    if not args.lint_only:
        temporary = ROOT / ".cache" / "project-checks" / uuid4().hex
        temporary.parent.mkdir(parents=True, exist_ok=True)
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "-o",
                "faulthandler_timeout=120",
                "--durations=10",
                "--basetemp",
                str(temporary),
                *(["--cpu-only", "-m", "not mps"] if args.cpu_only else []),
            ],
            cwd=ROOT,
        )
        try:
            returncode = process.wait(timeout=args.test_timeout)
        except subprocess.TimeoutExpired:
            try:
                if sys.platform == "darwin":
                    sample = subprocess.run(
                        ["sample", str(process.pid), "1"],
                        capture_output=True,
                        text=True,
                        timeout=15,
                        check=False,
                    )
                    print(sample.stdout.partition("Binary Images:")[0], sample.stderr, flush=True)
            finally:
                process.kill()
                process.wait()
            raise SystemExit(f"pytest exceeded {args.test_timeout}s; process terminated.") from None
        if returncode:
            raise SystemExit(returncode)


if __name__ == "__main__":
    main()
