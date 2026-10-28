"""Materialize private evidence images from a fixed, explicitly reviewed decision file.

This copies verified bytes only. It neither creates visual judgments nor calls a model.
"""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(audit_dir, decisions, out_dir):
    audit_dir, decisions, out_dir = map(Path, (audit_dir, decisions, out_dir))
    repo = Path(__file__).resolve().parents[1]
    if out_dir.exists() or any(out_dir.resolve().is_relative_to(repo / x) for x in ("docs", "web")):
        raise ValueError("use a new private output directory")
    review = json.loads(decisions.read_text(encoding="utf-8"))
    if review["game_pk"] != 849843 or sha(audit_dir / "audit.json") != review["audit_sha256"]:
        raise ValueError("decisions do not match this development audit")
    audit = json.loads((audit_dir / "audit.json").read_text(encoding="utf-8"))
    frames = {f["image"]: (r, f) for r in audit["records"] for f in r.get("sampled_frames", [])}
    if len(frames) != sum(len(r.get("sampled_frames", [])) for r in audit["records"]):
        raise ValueError("duplicate decoded image identities")
    sidecar = review["package_sidecar"]
    entries = {e["image"]: e for e in sidecar["entries"]}
    bindings = review["image_bindings"]
    if len(entries) != len(sidecar["entries"]) or len(bindings) != len(entries):
        raise ValueError("evidence image bindings must be one to one")
    seen, copies = set(), []
    for binding in bindings:
        name, source_name = binding["image"], binding["source_image"]
        if name in seen:
            raise ValueError("duplicate evidence image")
        seen.add(name)
        source, target = (audit_dir / source_name).resolve(), (out_dir / name).resolve()
        if not source.is_relative_to(audit_dir.resolve()) or not target.is_relative_to(
            out_dir.resolve()
        ):
            raise ValueError("evidence path leaves its directory")
        row, frame = frames[source_name]
        entry = entries[name]
        if not (
            row["pitch_key"] == entry["pitch_key"]
            and row["play_id"] == entry["play_id"]
            and row["clip_sha256"] == entry["clip_sha256"]
            and row["first_pts"] == entry["clip_first_pts"]
            and row["time_base"] == entry["time_base"]
            and frame["pts"] == entry["frame_pts"]
            and frame["clip_seconds"] == entry["clip_seconds"]
            and entry["release_lower_bound_pts"] in {f["pts"] for f in row["sampled_frames"]}
            and sha(source) == frame["image_sha256"] == binding["sha256"] == entry["image_sha256"]
        ):
            raise ValueError("evidence frame identity or bytes mismatch")
        copies.append((source, target))
    out_dir.mkdir(parents=True)
    for source, target in copies:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (out_dir / "review-evidence.json").write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return len(copies)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    print(
        f"Prepared {prepare(args.audit_dir, args.decisions, args.out_dir)} existing evidence images"
    )


if __name__ == "__main__":
    main()
