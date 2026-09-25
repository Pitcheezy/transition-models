r"""Re-run the scoreboard OCR reports for every OCR version and record their provenance (H-4).

Usage::

    uv run --frozen python scripts/70_refresh_ocr_reports.py --reference ca76e65 \
        --label pa27_32 --date 2026-09-26 --no-grab
    uv run --frozen python scripts/70_refresh_ocr_reports.py --version v2 --reference HEAD \
        --label check --date 2026-09-26 --out-dir outputs/verification/h4 --no-grab

For each version in ``src.vision.ocr_reports.VERSIONS`` this runs, through ``sys.executable``,
the documented ``scripts/66_sny_scoreboard_ocr.py`` commands: ``predict`` with the version's
templates, ``score --exclude-pas <template PAs>``, ``negatives`` and a repeat ``predict
--no-grab`` into ``outputs/verification/ocr_<version>_repeat.json``.

Written files (names from ``VERSIONS``, per version, into ``--out-dir``)::

    game_747139_scoreboard_ocr_<version>_predictions.json   predict
    game_747139_scoreboard_ocr_<version>.json               held-out score
    game_747139_scoreboard_negatives_score_<version>.json   negatives
        (v1 keeps its legacy name game_747139_scoreboard_negatives_score_v0.json)
    game_747139_scoreboard_ocr_<version>_provenance.json    provenance (unless --skip-provenance)

Which ``--reference`` to pass: the last commit whose ``docs/results`` predictions this refresh
replaces, usually ``HEAD`` when the merge that changed the eval set is not committed yet
(the annotations are in the working tree, the old reports are still at HEAD). It is resolved
once with ``git rev-parse`` to a short commit SHA before anything runs; a name git cannot
resolve is a usage error, and the SHA (never a moving name such as ``HEAD``) is what the
provenance records. The predictions of that commit (``git show <sha>:docs/results/mlb_p0/
<predictions>``) count as previous: shared rows must not change or disappear, new rows are
compared against confirmed labels and must all be in the eval set. When the predictions file
does not exist at the reference every row counts as new (a NOTE says so); when nothing is
new, a NOTE says that no new pitch was checked (the reference may already contain them).

The provenance document (``mlb_scoreboard_ocr_provenance_v1``) is rebuilt from the existing
one: its ``limitations`` and the version-wide ``preregistration`` stay in place, other keys the
refresh does not recompute (e.g. ``unchanged_since_reference``) move under
``carried_from_previous`` with the replaced document's ``git_reference``, its extra artifacts
that still exist on disk are re-hashed and kept with ``"carried": true``, ``historical_audit``
gets one entry for the replaced document, and the per-unit new-row comparison lives under
``new_rows_comparison``.

Inputs are always read from ``docs/results/mlb_p0``; ``--out-dir`` only chooses where the
files above are written. The default is that same directory, i.e. the committed reports are
overwritten. Run into a scratch ``--out-dir`` first when in doubt. If a default-directory run
fails, restore ONLY the report files it wrote (names above), for example
``git checkout -- docs/results/mlb_p0/game_747139_scoreboard_ocr_v*`` plus the negatives score
files; never check out the whole directory, because the eval set, review and timing inputs of an
uncommitted annotation merge live there too. The exit status is non-zero when the repeat prediction
differs, when a shared prediction changed or was removed (``--allow-changed`` turns both into
a warning), when a new row is missing from the eval set, or on any wrong read: a wrong field
in the held-out score (checked per field, because ``all_fields`` skips every pitch with an
abstention), a false or wrong read in the negatives, or a wrong field on a new pitch. The
files are written in every case so the reason can be inspected.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.scoreboard_evalset import read_json  # noqa: E402
from src.vision import ocr_reports as reports  # noqa: E402

RESULTS = ROOT / reports.RESULTS_DIR
SCRIPT_66 = ROOT / "scripts" / "66_sny_scoreboard_ocr.py"
VERIFICATION = Path("outputs/verification")


def write(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def run_66(mode, *flags):
    """Run one ``scripts/66`` command from the repository root; echo its output only on failure."""
    command = [sys.executable, str(SCRIPT_66), mode, *map(str, flags)]
    run = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    if run.returncode != 0:
        sys.stderr.write(run.stdout + run.stderr)
        raise RuntimeError(f"scripts/66 {mode} failed with exit code {run.returncode}")


def git(*args):
    """Run a git command in the repository; stdout and stderr are captured as bytes."""
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True)


def resolve_reference(ref):
    """Short SHA of the commit ``ref`` names, or ``None`` when git cannot resolve it."""
    run = git("rev-parse", "--verify", "--quiet", "--short", f"{ref}^{{commit}}")
    sha = run.stdout.decode("ascii", "replace").strip()
    return sha if run.returncode == 0 and sha else None


def reference_bytes(commit, path):
    """Bytes of ``path`` at ``commit`` (a resolved SHA), ``None`` when the file is not there."""
    run = git("show", f"{commit}:{path}")
    return run.stdout if run.returncode == 0 else None


def last_commit_touching(path, fallback):
    run = git("log", "-1", "--format=%h", "--", path)
    text = run.stdout.decode("utf-8", "replace").strip()
    return text if run.returncode == 0 and text else fallback


def rel(path):
    """Repository-relative posix path for a file inside the repository."""
    return Path(os.path.relpath(Path(path).resolve(), ROOT)).as_posix()


def refresh_version(version, args):
    """Run predict/score/negatives/repeat for one version; return (summary, problems)."""
    files = reports.VERSIONS[version]
    templates_path = RESULTS / files["templates"]
    template_pas = reports.template_plate_appearances(read_json(templates_path))
    out = {name: args.out_dir / files[name] for name in ("predictions", "score", "negatives")}
    repeat_path = VERIFICATION / f"ocr_{version}_repeat.json"
    grab = ["--no-grab"] if args.no_grab else []

    run_66("predict", "--templates", templates_path, *grab, "--output", out["predictions"])
    run_66(
        "score",
        "--predictions",
        out["predictions"],
        "--exclude-pas",
        *template_pas,
        "--output",
        out["score"],
    )
    run_66("negatives", "--templates", templates_path, *grab, "--output", out["negatives"])
    run_66("predict", "--templates", templates_path, "--no-grab", "--output", ROOT / repeat_path)

    predictions = read_json(out["predictions"])
    score = read_json(out["score"])
    negatives = read_json(out["negatives"])
    repeat_rows = read_json(ROOT / repeat_path)
    repeat = reports.repeat_check(
        predictions, repeat_rows, reports.digest_file(ROOT, repeat_path.as_posix())
    )
    previous_rel = f"{reports.RESULTS_DIR}/{files['predictions']}"
    previous_raw = reference_bytes(args.reference, previous_rel)
    if previous_raw is None:
        print(
            f"NOTE: {version}: {previous_rel} does not exist at {args.reference}; "
            "every prediction row counts as new"
        )
    previous = json.loads(previous_raw.decode("utf-8-sig")) if previous_raw else []
    comparison = reports.compare_predictions(previous, predictions)
    evalset = read_json(RESULTS / "game_747139_scoreboard_evalset.json")
    new_rows = reports.new_rows_comparison(
        evalset, predictions, reports.new_row_keys(previous, predictions)
    )
    if comparison["new_rows"] == 0:
        print(
            f"NOTE: {version}: no new prediction row against {args.reference}; nothing new was "
            "checked (the reference may already contain these predictions)"
        )

    problems = []
    if not repeat["parsed_documents_equal"]:
        problems.append(
            f"{version}: repeat prediction differs "
            f"({repeat['matching_rows']}/{repeat['prediction_rows']} rows match)"
        )
    if comparison["changed_shared_rows"]:
        message = f"{version}: {comparison['changed_shared_rows']} shared prediction(s) changed"
        (print if args.allow_changed else problems.append)(message)
        for change in comparison["changes"]:
            print("  changed:", json.dumps(change, ensure_ascii=False))
    if comparison["removed_rows"]:
        message = (
            f"{version}: {comparison['removed_rows']} prediction row(s) of {args.reference} "
            "are gone (removed from the eval set?)"
        )
        (print if args.allow_changed else problems.append)(message)
    missing = new_rows["totals"]["new_rows_missing_from_evalset"]
    if missing:
        problems.append(
            f"{version}: {missing} new prediction row(s) are not in the eval set "
            "(was it rebuilt after the merge?)"
        )
    summary = reports.score_summary(score)
    problems += reports.wrong_read_problems(version, score, negatives, new_rows)

    if not args.skip_provenance:
        provenance_rel = f"{reports.RESULTS_DIR}/{files['provenance']}"
        existing_path = RESULTS / files["provenance"]
        existing = read_json(existing_path) if existing_path.exists() else None
        code_paths = (f"{reports.RESULTS_DIR}/{files['templates']}", *reports.CODE_PATHS)
        artifact_paths = [
            f"{reports.RESULTS_DIR}/{reports.SHARED_INPUTS[0]}",
            *(rel(out[name]) for name in ("predictions", "score", "negatives")),
            *(f"{reports.RESULTS_DIR}/{name}" for name in reports.SHARED_INPUTS[1:]),
        ]
        artifacts = [reports.digest_file(ROOT, p) for p in artifact_paths]
        artifacts += reports.carried_artifacts(existing, artifacts, ROOT)
        document = reports.build_provenance(
            existing,
            version=version,
            recorded_at=args.date,
            recorded_by=args.recorded_by,
            label=args.label,
            reference_commit=args.reference,
            replaced_commit=last_commit_touching(provenance_rel, args.reference),
            evalset=evalset,
            template_pas=template_pas,
            code_and_templates=[
                reports.code_entry(ROOT, p, reference_bytes(args.reference, p)) for p in code_paths
            ],
            artifacts=artifacts,
            frame_cache=reports.frame_cache(evalset, ROOT),
            repeat=repeat,
            comparison=comparison,
            new_rows=new_rows,
            commands=reports.reproduction_commands(
                version,
                template_pas,
                out_dir=rel(args.out_dir),
                no_grab=args.no_grab,
                repeat_path=repeat_path.as_posix(),
            ),
        )
        write(args.out_dir / files["provenance"], document)

    print(
        json.dumps(
            {
                "version": version,
                "template_plate_appearances": template_pas,
                "score_all_fields": summary,
                "negatives": {
                    k: negatives[k] for k in ("frames", "unreadable_fields", "readable_fields")
                }
                | negatives["totals"],
                "repeat_check": {k: repeat[k] for k in ("prediction_rows", "matching_rows")}
                | {"equal": repeat["parsed_documents_equal"]},
                "previous_prediction_comparison": {
                    k: comparison[k]
                    for k in (
                        "previous_rows",
                        "current_rows",
                        "changed_shared_rows",
                        "new_rows",
                        "removed_rows",
                    )
                },
                "new_rows": new_rows["totals"],
                "written": [rel(p) for p in out.values()]
                + ([] if args.skip_provenance else [rel(args.out_dir / files["provenance"])]),
            },
            indent=2,
        )
    )
    return problems


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--version",
        action="append",
        choices=sorted(reports.VERSIONS),
        help="OCR version to refresh (repeatable; default: every version)",
    )
    parser.add_argument(
        "--reference",
        required=True,
        help="git commit whose predictions count as previous: the last commit whose "
        "docs/results predictions this refresh replaces, usually HEAD when the merge is not "
        "committed yet (any ref; recorded as its SHA)",
    )
    parser.add_argument("--label", required=True, help="free text naming this refresh")
    parser.add_argument("--date", required=True, help="recorded_at, YYYY-MM-DD")
    parser.add_argument(
        "--recorded-by", default="70_refresh_ocr_reports.py", help="provenance recorded_by"
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=RESULTS,
        help=f"where the predictions, score, negatives and provenance files are written "
        f"(default: {reports.RESULTS_DIR}, which OVERWRITES the committed reports; if a run "
        "fails restore only the report files it wrote, never the whole directory, which also "
        "holds uncommitted eval-set/review/timing inputs). Inputs are always "
        f"read from {reports.RESULTS_DIR}",
    )
    parser.add_argument(
        "--no-grab", action="store_true", help="pass --no-grab to predict and negatives"
    )
    parser.add_argument(
        "--skip-provenance", action="store_true", help="write no provenance document"
    )
    parser.add_argument(
        "--allow-changed",
        action="store_true",
        help="changed or removed shared predictions only warn instead of failing",
    )
    args = parser.parse_args()
    resolved = resolve_reference(args.reference)
    if resolved is None:
        parser.error(f"--reference {args.reference!r} does not name a commit in this repository")
    if resolved != args.reference:
        print(f"reference {args.reference} resolved to {resolved}")
    args.reference = resolved
    args.out_dir = args.out_dir.resolve()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    problems = []
    for version in args.version or sorted(reports.VERSIONS):
        problems += refresh_version(version, args)
    for problem in problems:
        print("PROBLEM:", problem)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
