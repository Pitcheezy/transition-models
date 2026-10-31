from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import stat
import zipfile
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("exhibition_intake", Path(__file__).parents[1] / "scripts/intake_exhibition_bundle.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def fixture_files():
    pitches = []
    for pa in range(1, 72):
        for pitch in range(1, 4 + (49 if pa == 71 else 0)):
            pitches.append({"key": f"849843:{pa}:{pitch}", "pa_key": f"849843:{pa}",
                            "rec": {"status": "ready" if len(pitches) < 246 else "unsupported"}})
    game = {"pitches": pitches, "pas": [{"pa_key": f"849843:{pa}"} for pa in range(1, 72)],
            "source": {"kind": "archive"}, "next": None}
    files = {
        "index.html": b"<!doctype html>\r\n<html></html>\r\n",
        "v1/manifest.json": json.dumps({"commit": mod.EXPECTED_COMMIT, "commit_dirty": False, "contract": "v1"}).encode(),
        "v1/game/849843.json": json.dumps(game).encode(),
        "v1/dates.json": json.dumps({"dates": ["2026-09-30", "2026-10-01"]}).encode(),
        "v1/games/2026-09-30.json": b"{}",
        # Locked file is deliberately not JSON: only byte checks may touch it.
        "v1/game/849844.json": b"locked evaluation bytes, not parsed",
    }
    return files


def manifest(files):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
    writer.writerow(["path", "bytes", "sha256_raw", "sha256_lf_normalized"])
    for path, content in files.items():
        writer.writerow([path, len(content), mod.digest(content), mod.digest(content.replace(b"\r\n", b"\n").replace(b"\r", b"\n"))])
    return stream.getvalue().encode()


def write_zip(tmp_path, files=None, extras=None, manifest_override=None):
    files = files or fixture_files()
    archive = tmp_path / "received.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for name, content in files.items():
            bundle.writestr("site/" + name, content)
        bundle.writestr("TOOLS.txt", "Python fixture")
        bundle.writestr("MANIFEST.tsv", manifest_override if manifest_override is not None else manifest(files))
        for name, content in extras or []:
            bundle.writestr(name, content)
    return archive


def inspect(archive, count=6):
    raw = archive.read_bytes()
    return mod.inspect_bundle(archive, expected_bytes=len(raw), expected_sha256=hashlib.sha256(raw).hexdigest(), expected_site_files=count)


def test_intake_exact_bytes_and_missing_catalogue_are_preserved(tmp_path):
    archive = write_zip(tmp_path)
    receipt, payloads = inspect(archive)
    assert receipt["game"]["pitches"] == 262
    assert receipt["game"]["recommendation_status"] == {"ready": 246, "unsupported": 16}
    assert receipt["catalogue"]["missing_date_files"] == ["2026-10-01"]
    assert receipt["deployment_approved"] is False
    output = tmp_path / "output"
    mod.extract_verified(payloads, receipt, output)
    assert (output / "site/index.html").read_bytes() == fixture_files()["index.html"]
    assert (output / "site/v1/game/849844.json").read_bytes().startswith(b"locked")
    assert json.loads((output / "intake-receipt.json").read_text())["site_files"] == 6


def test_original_zip_pin_rejects_wrong_input_before_output(tmp_path):
    with pytest.raises(mod.IntakeError, match="ZIP byte count"):
        mod.inspect_bundle(write_zip(tmp_path))


@pytest.mark.parametrize("path", ["../escape", "site/../escape", "/absolute", "C:/bad", "site/file:secret", "site/CON.txt", "site/foo. "])
def test_unsafe_paths_rejected(tmp_path, path):
    with pytest.raises(mod.IntakeError, match="unsafe"):
        inspect(write_zip(tmp_path, extras=[(path, b"bad")]))


def test_case_collision_is_rejected_on_all_platforms(tmp_path):
    with pytest.raises(mod.IntakeError, match="colliding"):
        inspect(write_zip(tmp_path, extras=[("site/INDEX.HTML", b"x")]))


def test_symlink_is_rejected(tmp_path):
    info = zipfile.ZipInfo("site/link")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with pytest.raises(mod.IntakeError, match="non-regular"):
        inspect(write_zip(tmp_path, extras=[(info, b"../../outside")]))


def test_manifest_missing_or_extra_file_rejected(tmp_path):
    files = fixture_files()
    omitted = dict(files)
    omitted.pop("index.html")
    with pytest.raises(mod.IntakeError, match="file set"):
        inspect(write_zip(tmp_path, files, manifest_override=manifest(omitted)))


def test_manifest_hash_mismatch_rejected(tmp_path):
    files = fixture_files()
    original = manifest(files)
    files["index.html"] += b"tampered"
    with pytest.raises(mod.IntakeError, match="byte/hash"):
        inspect(write_zip(tmp_path, files, manifest_override=original))


def test_duplicate_manifest_rejected(tmp_path):
    original = manifest(fixture_files())
    duplicate = original + original.splitlines(keepends=True)[1]
    with pytest.raises(mod.IntakeError, match="duplicate manifest"):
        inspect(write_zip(tmp_path, manifest_override=duplicate))


@pytest.mark.parametrize("change", ["commit", "duplicate_pitch", "wrong_pa", "counts"])
def test_semantic_delivery_mismatch_rejected(tmp_path, change):
    files = fixture_files()
    if change == "commit":
        files["v1/manifest.json"] = json.dumps({"commit": "0" * 40, "commit_dirty": False}).encode()
    else:
        game = json.loads(files["v1/game/849843.json"])
        if change == "duplicate_pitch":
            game["pitches"][1]["key"] = game["pitches"][0]["key"]
        elif change == "wrong_pa":
            game["pitches"][0]["pa_key"] = "849843:2"
        else:
            game["pitches"][0]["rec"]["status"] = "unsupported"
        files["v1/game/849843.json"] = json.dumps(game).encode()
    with pytest.raises(mod.IntakeError):
        inspect(write_zip(tmp_path, files))


def test_existing_output_is_never_overwritten(tmp_path):
    receipt, payloads = inspect(write_zip(tmp_path))
    out = tmp_path / "existing"
    out.mkdir()
    sentinel = out / "keep.txt"
    sentinel.write_text("preserve")
    with pytest.raises(FileExistsError):
        mod.extract_verified(payloads, receipt, out)
    assert sentinel.read_text() == "preserve"
    assert list(out.iterdir()) == [sentinel]


def test_backslash_path_rejected_before_windows_zip_normalization():
    with pytest.raises(mod.IntakeError, match="unsafe"):
        mod.safe_path("site\\bad")


def test_file_cannot_be_another_files_parent(tmp_path):
    files = fixture_files()
    files["a"] = b"file"
    files["a/child"] = b"child"
    with pytest.raises(mod.IntakeError, match="file used as directory"):
        inspect(write_zip(tmp_path, files), count=8)


def test_date_file_counts_only_exact_games_json_directly_under_v1_games(tmp_path):
    # The app fetches games/<date>.json; a stem match with another extension or depth is not a supplied date.
    files = fixture_files()
    files["v1/games/2026-10-01.txt"] = b"{}"
    files["v1/games/old/2026-09-30.json"] = b"{}"
    receipt, _ = inspect(write_zip(tmp_path, files), count=8)
    assert receipt["catalogue"]["missing_date_files"] == ["2026-10-01"]
    assert receipt["catalogue"]["supplied_date_files"] == 1
    assert receipt["catalogue"]["unlisted_games_files"] == ["v1/games/2026-10-01.txt", "v1/games/old/2026-09-30.json"]


def test_receipt_marks_source_commit_as_sender_declared(tmp_path):
    receipt, _ = inspect(write_zip(tmp_path))
    assert receipt["source_commit"] == mod.EXPECTED_COMMIT
    assert receipt["source_commit_basis"] == "sender_declared_manifest_unverified"
    assert receipt["declared_commit_dirty"] is False
    assert any("sender's declaration" in line and "no rebuild" in line for line in receipt["limitations"])


def test_malformed_manifest_row_rejected(tmp_path):
    raw = manifest(fixture_files())
    malformed = raw.replace(b"index.html\t", b"index.html\textra\t", 1)
    with pytest.raises(mod.IntakeError, match="malformed"):
        inspect(write_zip(tmp_path, manifest_override=malformed))
