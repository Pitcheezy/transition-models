"""Prepare private development frames and expose monotone source-time prefixes.

This is a trusted local runner, not a filesystem security sandbox. The package contains
future frames and a separate evaluator manifest. Give the processor only advance() results.
The evaluator's prepared processor-manifest hash is a consistency anchor, not a signature;
joint modification of both manifests is outside this trusted-package integrity model.
No CV inference, automatic pitch synchronization, or end-to-end availability is measured.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import uuid
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAME_KEYS = {"observation_id", "source_time_seconds", "image_sha256", "path"}


def _no_links(path):
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
            raise ValueError(f"symlink/junction is not allowed: {part}")


def _inside(root, relative):
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise ValueError("source path must be a portable relative path")
    path = Path(relative)
    if path.is_absolute() or any(p in ("", ".", "..") for p in relative.split("/")):
        raise ValueError("source path escapes its root")
    path = root / path
    _no_links(path)
    if not path.resolve().is_relative_to(root):
        raise ValueError("source path escapes its root")
    return path.resolve()


def _load(path):
    _no_links(path)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"invalid {name}")
    return value


def _write_new(path, document):
    _no_links(path)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def _inputs(root, game, pa, windows_path, timing_path):
    windows, timing = _load(windows_path), _load(timing_path)
    if windows.get("schema") != "intent_broadcast_windows_v0" or windows.get("game_pk") != game:
        raise ValueError("windows schema/game mismatch")
    if timing.get("schema") != "intent_broadcast_timing_v0" or timing.get("game_pk") != game:
        raise ValueError("timing schema/game mismatch")
    source = timing.get("source", {})
    if not windows.get("media_url") or windows["media_url"] != source.get("media_url"):
        raise ValueError("windows/timing source URL mismatch")
    try:
        fps = Fraction(windows["fps"])
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        raise ValueError("invalid source fps") from exc
    if fps <= 0 or windows["fps"] != source.get("fps"):
        raise ValueError("windows/timing source clock mismatch")
    by_key = {}
    for row in timing["annotations"]:
        key = (
            _integer(row.get("at_bat_number"), "PA", 1),
            _integer(row.get("pitch_number"), "pitch", 1),
        )
        if row.get("game_pk", game) != game or key in by_key:
            raise ValueError("timing duplicate pitch key or game mismatch")
        by_key[key] = row
    seen_keys, seen_indices, selected = set(), set(), []
    for window in windows["windows"]:
        if not re.fullmatch(r"[1-9]\d*:[1-9]\d*", window.get("pitch", "")):
            raise ValueError("invalid window pitch key")
        key = tuple(map(int, window["pitch"].split(":")))
        if key in seen_keys:
            raise ValueError("duplicate window pitch key")
        seen_keys.add(key)
        if key[0] != pa:
            continue
        row = by_key.get(key)
        if row is None or row.get("status") != "annotated":
            raise ValueError(f"selected pitch timing not available: {key}")
        release = _number(row.get("release_seconds"), "release_seconds")
        decision = _number(row.get("decision_seconds"), "decision_seconds")
        decision_index = _integer(row.get("decision_frame_index"), "decision_frame_index")
        if not 0 <= decision < release or abs(decision - float(decision_index / fps)) > 1e-6:
            raise ValueError("timing/source frame clock mismatch")
        if abs(release * float(fps) - round(release * float(fps))) > 1e-4:
            raise ValueError("release/source frame clock mismatch")
        directory = _inside(root, window["dir"])
        frames = []
        for frame in window["frames"]:
            index = _integer(frame.get("frame_index"), "frame_index")
            timestamp = _number(frame.get("frame_time"), "frame_time")
            if index in seen_indices or abs(timestamp - float(index / fps)) > 1e-6:
                raise ValueError("duplicate frame index or source clock mismatch")
            seen_indices.add(index)
            path = _inside(root, frame["path"])
            if path.parent != directory or path.name != f"frame_{index:06d}.jpg":
                raise ValueError("frame path/index/window mismatch")
            digest = frame.get("image_sha256")
            if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                raise ValueError("invalid frame SHA256")
            if _sha(path.read_bytes()) != digest:
                raise ValueError(f"frame SHA256 mismatch: {path}")
            frames.append((timestamp, index, path, digest))
        if decision_index not in {frame[1] for frame in frames}:
            raise ValueError("decision frame index is absent from selected window")
        if not frames or not min(f[0] for f in frames) <= decision < release <= max(
            f[0] for f in frames
        ):
            raise ValueError("timing does not fall within selected window")
        selected.append((key, release, decision, frames))
    if not selected:
        raise ValueError("no windows for selected PA")
    return windows, selected


def prepare(root, game, pa, out, *, windows=None, timing=None):
    """Build new anonymous image copies plus an evaluator-only identity/timing map."""
    root, out = Path(root).absolute(), Path(out).absolute()
    _no_links(root)
    _no_links(out)
    root, out = root.resolve(), out.resolve()
    _integer(game, "game", 1)
    _integer(pa, "PA", 1)
    if out.exists():
        raise ValueError("output already exists; choose a new private output directory")
    if out.is_relative_to(root) and (
        len(out.relative_to(root).parts) < 2 or out.relative_to(root).parts[0] != "outputs"
    ):
        raise ValueError("inside the repository, output must be a new child of outputs/")
    windows_path = _inside(
        root, windows or f"docs/results/mlb_p0/game_{game}_condensed_windows_v0.json"
    )
    timing_path = _inside(root, timing or f"docs/results/mlb_p0/game_{game}_timing.json")
    source_hashes = {
        "windows_sha256": _sha(windows_path.read_bytes()),
        "timing_sha256": _sha(timing_path.read_bytes()),
    }
    metadata, selected = _inputs(root, game, pa, windows_path, timing_path)
    out.mkdir(parents=True, exist_ok=False)
    (out / "processor/images").mkdir(parents=True)
    frames, mapping = [], []
    for key, release, decision, source_frames in selected:
        for timestamp, index, path, digest in source_frames:
            obs = "obs_" + _sha(f"{index}:{digest}".encode("ascii"))[:24]
            relative = f"images/{obs}.jpg"
            data = path.read_bytes()
            if _sha(data) != digest:
                raise ValueError("source frame changed during package creation")
            with (out / "processor" / relative).open("xb") as stream:
                stream.write(data)
            frames.append(
                {
                    "observation_id": obs,
                    "source_time_seconds": timestamp,
                    "image_sha256": digest,
                    "path": relative,
                }
            )
            mapping.append(
                {
                    "observation_id": obs,
                    "pitch_id": f"{game}:{key[0]}:{key[1]}",
                    "release_seconds": release,
                    "decision_seconds": decision,
                    "source_frame_index": index,
                    "source_path": path.relative_to(root).as_posix(),
                }
            )
    frames.sort(key=lambda row: row["source_time_seconds"])
    if source_hashes != {
        "windows_sha256": _sha(windows_path.read_bytes()),
        "timing_sha256": _sha(timing_path.read_bytes()),
    }:
        raise ValueError("source metadata changed during package creation")
    _write_new(
        out / "processor/manifest.json", {"schema": "intent_frame_prefix_v1", "frames": frames}
    )
    summary = {
        "only_development": True,
        "cv_inference_performed": False,
        "frame_count": len(frames),
        "window_count": len(selected),
        **source_hashes,
        "processor_manifest_sha256": _sha((out / "processor/manifest.json").read_bytes()),
        "scope": "sampled discontinuous windows; not a complete plate appearance or live feed",
        "sampling": metadata.get("window"),
        "fps": metadata["fps"],
    }
    _write_new(
        out / "evaluator_manifest.json",
        {
            "schema": "intent_replay_evaluator_v1",
            **summary,
            "game_pk": game,
            "at_bat_number": pa,
            "media_url": metadata["media_url"],
            "sources": {
                "windows": windows_path.relative_to(root).as_posix(),
                "timing": timing_path.relative_to(root).as_posix(),
            },
            "mapping": mapping,
            "limitations": "Retrospectively selected windows. Trusted runner structural separation, "
            "not a sandbox: future images exist on disk. Source time is not arrival or "
            "output time. No CV inference or pre-pitch availability success is measured.",
        },
    )
    return summary


class PrefixStream:
    """A trusted processor receives only returned prefixes, not the package directory."""

    def __init__(self, package):
        self.root = Path(package).absolute() / "processor"
        _no_links(self.root)
        self.root = self.root.resolve()
        self.manifest = self.root / "manifest.json"
        _no_links(self.manifest)
        raw = self.manifest.read_bytes()
        self.manifest_sha256 = _sha(raw)
        # Only the runner reads evaluator metadata. Its contents never enter prefix results.
        evaluator = _load(self.root.parent / "evaluator_manifest.json")
        expected = evaluator.get("processor_manifest_sha256")
        if (
            not isinstance(expected, str)
            or not re.fullmatch(r"[a-f0-9]{64}", expected)
            or self.manifest_sha256 != expected
        ):
            raise ValueError("processor manifest disagrees with prepared evaluator hash")
        document = json.loads(raw)
        if document.get("schema") != "intent_frame_prefix_v1":
            raise ValueError("invalid processor manifest")
        self.frames = document["frames"]
        seen, previous = set(), -1.0
        for row in self.frames:
            if set(row) != FRAME_KEYS or not re.fullmatch(
                r"obs_[a-f0-9]{24}", row["observation_id"]
            ):
                raise ValueError("invalid or identifying processor fields")
            timestamp = _number(row["source_time_seconds"], "source_time_seconds")
            if timestamp <= previous or row["observation_id"] in seen:
                raise ValueError("duplicate/non-monotone processor frames")
            previous = timestamp
            seen.add(row["observation_id"])
            if row["path"] != f"images/{row['observation_id']}.jpg":
                raise ValueError("processor image path is not anonymous")
            _inside(self.root, row["path"])
            if not re.fullmatch(r"[a-f0-9]{64}", row["image_sha256"]):
                raise ValueError("invalid processor frame hash")
        self.last_cutoff = None

    def advance(self, cutoff):
        """Return all frames at/before cutoff; reject backward time and verify bytes."""
        cutoff = _number(cutoff, "cutoff")
        if cutoff < 0 or (self.last_cutoff is not None and cutoff < self.last_cutoff):
            raise ValueError("cutoff must be nonnegative and cannot decrease")
        _no_links(self.manifest)
        if _sha(self.manifest.read_bytes()) != self.manifest_sha256:
            raise ValueError("processor manifest changed during replay")
        result = []
        for row in self.frames:
            if row["source_time_seconds"] > cutoff:
                break
            path = _inside(self.root, row["path"])
            if _sha(path.read_bytes()) != row["image_sha256"]:
                raise ValueError("processor frame SHA256 mismatch")
            result.append(dict(row))
        self.last_cutoff = cutoff
        return result


def prefix(package, cutoff):
    """Persist monotone CLI progress for one sequential local runner (not concurrent)."""
    package = Path(package).absolute()
    stream = PrefixStream(package)
    state_path = package / "prefix_state.json"
    if state_path.exists():
        state = _load(state_path)
        if state.get("manifest_sha256") != stream.manifest_sha256:
            raise ValueError("prefix state belongs to a different processor manifest")
        stream.last_cutoff = _number(state["last_cutoff"], "saved cutoff")
    frames = stream.advance(cutoff)
    _no_links(state_path)
    temporary = package / f"prefix_state.{uuid.uuid4().hex}.next.json"
    _write_new(temporary, {"manifest_sha256": stream.manifest_sha256, "last_cutoff": cutoff})
    temporary.replace(state_path)
    return {
        "only_development": True,
        "cv_inference_performed": False,
        "processor_manifest_sha256": stream.manifest_sha256,
        "frame_count": len(frames),
        "frames": frames,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("prepare")
    make.add_argument("--repo-root", type=Path, default=ROOT)
    make.add_argument("--game", type=int, required=True)
    make.add_argument("--pa", type=int, required=True)
    make.add_argument("--out", type=Path, required=True)
    make.add_argument("--windows", help="relative source path under repo-root")
    make.add_argument("--timing", help="relative source path under repo-root")
    read = commands.add_parser("prefix")
    read.add_argument("--package", type=Path, required=True)
    read.add_argument("--cutoff", type=float, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare(
            args.repo_root, args.game, args.pa, args.out, windows=args.windows, timing=args.timing
        )
    else:
        result = prefix(args.package, args.cutoff)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
