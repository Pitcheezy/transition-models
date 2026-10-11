"""Build a private video replay of a saved observation run; never invoke a model.

The browser replays recorded publication times on a declared source clock. It is
not a live observer, a human review, or evidence of a recognized catcher's target.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

from intent import clip_capture, clip_clock, clip_frames, replay_coverage, replay_pitch_deadlines
from intent import local_glove_observer_report as saved

SCHEMA = "intent_observation_playback_v1"
_ASSETS = ("index.html", "playback.js", "style.css")
_REFERENCE_TIMES = (
    "decision_seconds_exact",
    "decision_upper_seconds_exact",
    "release_lower_seconds_exact",
    "release_upper_seconds_exact",
)
_NOTICE = (
    "PRIVATE LOCAL DEVELOPMENT REPLAY. Do not publish or redistribute this media package.\n"
    "Serve only this generated directory: python -m intent.observation_playback_server "
    "--directory <package>\n"
    "Saved observations are replayed at their recorded publication times; no model runs here.\n"
    "Reference pitch windows are existing manual annotations, not independent human labels.\n"
    "Unknown/unavailable outputs are not verified mitt positions, intent or live accuracy.\n"
)


def _binding(path):
    path = clip_capture._plain_path(path)
    if not path.is_file():
        raise ValueError(f"Expected regular input file: {path.name}")
    return path, clip_capture._sha256(path), path.stat().st_size


def _unchanged(bindings, run, inventory):
    for path, _, _ in bindings:
        clip_capture._plain_path(path)
    clip_frames._verify_files(bindings)
    if saved._inventory(run) != inventory:
        raise ValueError("Saved run changed while building playback")


def _write(path, raw):
    path = clip_capture._plain_path(path)
    with path.open("xb") as stream:
        stream.write(raw)


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def _copy(source, destination, expected_hash):
    source, destination = map(clip_capture._plain_path, (source, destination))
    with source.open("rb") as incoming, destination.open("xb") as outgoing:
        for chunk in iter(lambda: incoming.read(1024 * 1024), b""):
            outgoing.write(chunk)
    if clip_capture._sha256(destination) != expected_hash:
        raise ValueError("Copied artifact differs from verified source bytes")


def _clock(mapping, start, end):
    offset = mapping.get("constant_offset")
    if not isinstance(offset, dict):
        raise ValueError("Playback requires one constant clip/source clock offset")
    offset = Fraction(offset["exact"])
    clip = mapping["clip"]
    if clip["first_pts"] != 0 or Fraction(clip["first_seconds_exact"]) != 0:
        raise ValueError("Playback requires clip first PTS zero")
    if not replay_coverage._coverage(mapping, start, end)["fully_covered"]:
        raise ValueError("Requested source interval is not fully covered")
    clip_end = Fraction(clip["end_seconds_exact"])
    if not 0 <= start - offset < end - offset <= clip_end:
        raise ValueError("Requested interval is outside the clip media clock")
    return offset, clip_end


def _projection(report, run, mapping, start, end, pa):
    references, associated, rows, games = [], {}, [], set()
    for pitch in report["pitches"]:
        parts = pitch["pitch_id"].split(":")
        if len(parts) != 3 or any(not p.isdigit() or int(p) <= 0 for p in parts):
            raise ValueError("Invalid reference pitch identity")
        if int(parts[1]) != pa:
            raise ValueError("Reference pitch differs from requested PA")
        games.add(int(parts[0]))
        if pitch.get("status") != "measured_reference":
            raise ValueError("Playback requires measured reference pitch times")
        reference = {"pitch_id": pitch["pitch_id"]}
        reference.update({key: str(replay_coverage._exact(pitch[key])) for key in _REFERENCE_TIMES})
        reference.update(
            conservative_temporal_ready=pitch["conservative_temporal_ready"],
            nominal_start_temporal_ready=pitch["nominal_start_temporal_ready"],
            usable_mitt=False,
        )
        references.append(reference)
        for row in pitch["observations"]:
            if row["index"] in associated:
                raise ValueError("Duplicate reference assignment")
            associated[row["index"]] = pitch["pitch_id"]
            rows.append(row)
    rows += report["unassigned_observations"]
    rows.sort(key=lambda row: row["index"])
    if len(games) != 1 or not rows:
        raise ValueError("Playback requires one game and nonempty observations")
    if [row["index"] for row in rows] != list(range(report["counts"]["planned_observations"])):
        raise ValueError("Saved observation indices/denominator are incomplete")
    images, observations = [], []
    for row in rows:
        index, status = row["index"], row["status"]
        if status not in {"accepted", "error", "not_attempted"}:
            raise ValueError("Unsupported observation status")
        cutoff = replay_coverage._exact(row["cutoff_seconds_exact"])
        frame = row.get("frame_seconds_exact")
        publication = row.get("publication_seconds_exact")
        frame = None if frame is None else replay_coverage._exact(frame)
        publication = None if publication is None else replay_coverage._exact(publication)
        image_path = None
        if frame is not None and frame > cutoff:
            raise ValueError("Saved input frame is later than its cutoff")
        if status == "accepted":
            if frame is None or publication is None or publication < cutoff:
                raise ValueError("Accepted output requires ordered cutoff/publication times")
            expected_status = {
                "candidate": "unknown",
                "ambiguous": "unknown",
                "no_candidate": "unavailable",
            }.get(row.get("candidate_status"))
            if expected_status is None or row.get("observation_status") != expected_status:
                raise ValueError("Only unverified local observer outcomes are supported")
            expected = clip_clock.latest_mapped_frame(mapping, str(cutoff))
            receipt, _ = replay_pitch_deadlines._read(
                run / "frames" / f"frame_{index:03d}" / "receipt.json"
            )
            if (
                Fraction(expected["source_seconds_exact"]) != frame
                or receipt.get("mapping") != expected
                or receipt.get("extraction_verified") is not True
                or receipt.get("bindings_verified") is not True
            ):
                raise ValueError("Saved input frame differs from verified causal mapping")
            image = run / "outputs" / f"cv_observation_{index:03d}" / "request/image.jpg"
            binding = _binding(image)
            if binding[1] != receipt["artifacts"]["image.jpg"]["sha256"]:
                raise ValueError("Saved input image differs from its frame receipt")
            image_path = f"frames/{index:03d}.jpg"
            images.append((binding, image_path))
        elif publication is not None:
            raise ValueError("Unaccepted observation cannot be published")
        observations.append(
            {
                "index": index,
                "cutoff_seconds_exact": str(cutoff),
                "frame_seconds_exact": str(frame) if frame is not None else None,
                "publication_seconds_exact": str(publication) if publication is not None else None,
                "status": status,
                "observation_status": row.get("observation_status"),
                "candidate_status": row.get("candidate_status"),
                "reference_pitch_id": associated.get(index),
                "image_path": image_path,
            }
        )
    states = Counter(row["status"] for row in observations)
    inside = sum(
        start <= Fraction(row["frame_seconds_exact"] or row["cutoff_seconds_exact"]) < end
        for row in observations
    )
    return {
        "schema": SCHEMA,
        "scope": {
            "game_pk": games.pop(),
            "pa": pa,
            "start_source_seconds_exact": str(start),
            "end_source_seconds_exact": str(end),
            "full_pa_verified": False,
            "live_availability_verified": False,
            "human_label": False,
        },
        "observations": observations,
        "references": references,
        "summary": {
            "planned_observations": len(observations),
            "interval_observations": inside,
            "outside_interval_observations": len(observations) - inside,
            "accepted": states["accepted"],
            "errors": states["error"],
            "not_attempted": states["not_attempted"],
            "verified_mitt": 0,
            "conservative_ready_pitches": sum(p["conservative_temporal_ready"] for p in references),
        },
    }, images


def build_package(
    *, run, capture_dir, timing, manifest, sources, pa, start, end, out_dir, asset_dir=None
):
    """Validate saved evidence and copy only allowlisted artifacts into a new directory.

    Times define [start,end); all saved observations remain in the denominator.
    A failed copy may leave an incomplete new directory, never a modified input.
    """
    if type(pa) is not int or pa <= 0:
        raise ValueError("PA must be a positive integer")
    start, end = replay_coverage._exact(start), replay_coverage._exact(end)
    if start >= end:
        raise ValueError("Requested interval must have positive duration")
    assets = asset_dir or Path(__file__).resolve().parents[1] / "web/observation-playback"
    run, capture_dir, output, assets = map(
        clip_capture._plain_path, (run, capture_dir, out_dir, assets)
    )
    if output.exists():
        raise FileExistsError("Playback output directory must be new")
    references = {
        key: clip_capture._plain_path(path)
        for key, path in (("timing", timing), ("manifest", manifest), ("sources", sources))
    }
    protected = [run, capture_dir, assets, *(path.parent for path in references.values())]
    if any(output.is_relative_to(root) or root.is_relative_to(output) for root in protected):
        raise ValueError("Playback output must not overlap input directories")
    if not output.parent.is_dir():
        raise ValueError("Playback output parent must already exist")
    inventory = saved._inventory(run)
    captured, clip, bindings, mapping = clip_frames._capture_inputs(capture_dir)
    if output.is_relative_to(clip.parent) or clip.is_relative_to(output):
        raise ValueError("Playback output must not overlap source media")
    reference_bindings = {key: _binding(path) for key, path in references.items()}
    assets_bindings = {name: _binding(assets / name) for name in _ASSETS}
    bindings += list(reference_bindings.values()) + list(assets_bindings.values())
    offset, clip_end = _clock(mapping, start, end)
    report = replay_pitch_deadlines.build_report(
        run,
        timing_path=references["timing"],
        manifest_path=references["manifest"],
        sources_path=references["sources"],
        capture_receipt=capture_dir / "receipt.json",
        pa=pa,
    )
    data, images = _projection(report, run, mapping, start, end, pa)
    clip_hash = captured["clip"]["sha256_before"]
    data["media"] = {
        "path": "media/clip.mp4",
        "sha256": clip_hash,
        "source_offset_seconds_exact": str(offset),
        "clip_end_seconds_exact": str(clip_end),
    }
    bindings += [binding for binding, _ in images]
    _unchanged(bindings, run, inventory)
    output.mkdir(exist_ok=False)
    (output / "media").mkdir()
    (output / "frames").mkdir()
    _write(output / "PRIVATE.txt", _NOTICE.encode())
    _copy(clip, output / data["media"]["path"], clip_hash)
    for binding, relative in images:
        _copy(binding[0], output / relative, binding[1])
    for name, binding in assets_bindings.items():
        _copy(binding[0], output / name, binding[1])
    _unchanged(bindings, run, inventory)
    _write(output / "replay-data.json", _json_bytes(data))
    artifacts = {
        path.relative_to(output).as_posix(): {
            "sha256": clip_capture._sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(output.rglob("*"))
        if path.is_file()
    }
    evidence = {
        "schema": "intent_observation_playback_package_v1",
        "private": True,
        "input_files_unchanged": True,
        "input_evidence_sha256": {
            "saved_run_inventory": clip_clock._sha(_json_bytes(inventory)),
            **clip_frames._input_hashes(captured, bindings, mapping),
            **{key: value[1] for key, value in reference_bindings.items()},
            "deadline_report": clip_clock._sha(_json_bytes(report)),
        },
        "artifacts": artifacts,
    }
    _unchanged(bindings, run, inventory)
    _write(output / "manifest.json", _json_bytes(evidence))
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run", "capture-dir", "timing", "manifest", "sources", "out-dir"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--pa", type=int, required=True)
    parser.add_argument("--start", required=True, help="exact source seconds, inclusive")
    parser.add_argument("--end", required=True, help="exact source seconds, exclusive")
    result = build_package(**vars(parser.parse_args(argv)))
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
