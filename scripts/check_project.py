"""Run the supported validation-path lint checks and full tests without downloading data."""

import argparse
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
QUALITY_PATHS = [
    "tests/test_service_review_server.py",
    "scripts/build_service_review.py",
    "tests/test_service_review_package.py",
    "scripts/audit_cv6b_saved_reasons.py",
    "tests/test_cv6b_audit.py",
    "scripts/build_operational_bundle.py",
    "tests/test_operational_bundle.py",
    "intent/review_point_data.py",
    "tests/test_review_point_data.py",
    "intent/replay_pitch_deadlines.py",
    "tests/test_replay_pitch_deadlines.py",
    "scripts/build_integration_handoff.py",
    "tests/test_integration_handoff.py",
    "src/integration",
    "scripts/inspect_service_game.py",
    "tests/test_service_game_contract.py",
    "tests/test_service_game_cli.py",
    "tests/test_intent_clip_frames_seek.py",
    "intent/replay_coverage.py",
    "tests/test_replay_coverage.py",
    "intent/local_glove_plan.py",
    "tests/test_local_glove_plan.py",
    "tests/test_intent_clip_clock_cache.py",
    "intent/local_glove_ready.py",
    "tests/test_local_glove_ready.py",
    "scripts/plot_local_replay_latency.py",
    "intent/local_glove_worker.py",
    "tests/test_local_glove_worker.py",
    "intent/local_point_review.py",
    "tests/test_local_point_review.py",
    "scripts/plot_local_point_comparison.py",
    "intent/local_point_model.py",
    "intent/local_point_experiment.py",
    "tests/test_local_point_model.py",
    "tests/test_local_point_experiment.py",
    "intent/local_glove_observer.py",
    "intent/local_glove_observer_report.py",
    "scripts/observe_local_glove_frame.py",
    "scripts/plot_local_glove_comparison.py",
    "tests/test_local_glove_observer.py",
    "tests/test_local_glove_observer_report.py",
    "intent/local_detector_data.py",
    "intent/local_glove_detector.py",
    "intent/local_glove_benchmark.py",
    "intent/local_glove_report.py",
    "tests/test_local_detector_data.py",
    "tests/test_local_glove_detector.py",
    "tests/test_local_glove_benchmark.py",
    "tests/test_local_glove_report.py",
    "intent/observation_loop.py",
    "intent/observation_report.py",
    "tests/test_intent_observation_report.py",
    "scripts/observe_claude_frame.py",
    "tests/test_intent_observation_loop.py",
    "tests/test_claude_frame_adapter.py",
    "tests/test_intent_mapped_observation.py",
    "intent/clip_frames.py",
    "tests/test_intent_clip_frames.py",
    "intent/clip_clock.py",
    "intent/clip_capture.py",
    "tests/test_intent_clip_clock.py",
    "tests/test_intent_clip_capture.py",
    "intent/observation_session.py",
    "tests/test_intent_observation_session.py",
    "intent/review_summary.py",
    "tests/test_intent_review_summary.py",
    "intent/review_server.py",
    "tests/test_review_server.py",
    "intent/reviewer_ui.py",
    "tests/test_intent_review_ui.py",
    "intent/review_queue.py",
    "tests/test_intent_review_queue.py",
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
    "tests/test_manual_ui.py",
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
