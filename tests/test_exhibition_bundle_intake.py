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


def exhibition_payloads():
    """Synthetic new delivery, including a non-executable received script fixture."""
    site = fixture_files()
    site.pop("v1/game/849844.json")
    site["v1/dates.json"] = json.dumps({"dates": ["2026-09-30"]}).encode()
    site["v1/manifest.json"] = json.dumps({
        "commit": mod.EXHIBITION_DATA_COMMIT, "commit_dirty": False,
        "contract": "v1", "live_dates": ["2026-09-30"],
    }).encode()
    game = json.loads(site["v1/game/849843.json"])
    game["game"] = {"game_pk": 849843, "date_kst": "2026-09-30"}
    site["v1/game/849843.json"] = json.dumps(game).encode()
    site["v1/games/2026-09-30.json"] = json.dumps({
        "date": "2026-09-30", "games": [{"game_pk": 849843, "date_kst": "2026-09-30"}],
    }).encode()
    site.update({"assets/index-X1sSTTQ4.js": b"/* inert fixture */\r\n",
                 "assets/index-ks_hu7Ji.css": b"/* inert fixture */\r",
                 "favicon.svg": b"<svg/>", "v1/health.json": b"{}",
                 "v1/setup/849843.json": b"{}"})
    assert set(site) == mod.EXHIBITION_SITE_FILES
    files = {"site/" + name: data for name, data in site.items()}
    files.update({name: b"synthetic metadata\r\n" for name in mod.EXHIBITION_METADATA})
    files["PROVENANCE.json"] = json.dumps({
        "release_id": mod.EXHIBITION_ROOT,
        "web_build_source_commit": mod.EXHIBITION_WEB_COMMIT,
        "public_data_generation_source_commit": mod.EXHIBITION_DATA_COMMIT,
        "v1_manifest_commit_observed": mod.EXHIBITION_DATA_COMMIT,
    }).encode()
    files["TOOLS.json"] = json.dumps({"source_commit": mod.EXHIBITION_WEB_COMMIT}).encode()
    files["verify_bundle.py"] = b"raise RuntimeError('received code must never run')\n"
    return files


def exhibition_manifest(files):
    # New manifest covers metadata and site, root-relative, excluding itself.
    return manifest(files).replace(b"sha256_lf_normalized\n", b"sha256_lf\n", 1)


def write_exhibition_zip(tmp_path, files=None, extras=None, manifest_override=None, root=None):
    files = exhibition_payloads() if files is None else files
    root = mod.EXHIBITION_ROOT if root is None else root
    archive = tmp_path / "new-delivery.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for name, content in files.items():
            bundle.writestr(root + "/" + name, content)
        bundle.writestr(root + "/MANIFEST.tsv", exhibition_manifest(files) if manifest_override is None else manifest_override)
        for name, content in extras or []:
            bundle.writestr(name, content)
    return archive


def inspect_exhibition(archive):
    raw = archive.read_bytes()
    return mod.inspect_bundle(archive, profile=mod.EXHIBITION_PROFILE,
                              expected_bytes=len(raw), expected_sha256=mod.digest(raw))


def test_new_profile_preserves_bytes_separates_commits_and_retains_all_evidence(tmp_path):
    files = exhibition_payloads()
    receipt, payloads = inspect_exhibition(write_exhibition_zip(tmp_path, files))
    assert receipt["source_commit"] == mod.EXHIBITION_WEB_COMMIT
    assert receipt["data_generation_commit"] == mod.EXHIBITION_DATA_COMMIT
    assert receipt["source_commit_basis"] == "sender_declared_provenance_unverified"
    assert receipt["data_generation_commit_basis"] == "sender_declared_manifest_unverified"
    assert receipt["manifest_entries"] == 19
    assert receipt["site_files"] == 10
    assert receipt["site_bytes"] == sum(len(data) for path, data in files.items() if path.startswith("site/"))
    assert {entry["path"] for entry in receipt["files"]} == mod.EXHIBITION_SITE_FILES
    assert {entry["path"] for entry in receipt["metadata_files"]} == mod.EXHIBITION_METADATA
    assert len(payloads) == 20
    assert receipt["archive_root"] == mod.EXHIBITION_ROOT
    assert receipt["game"]["recommendation_status"] == {"ready": 246, "unsupported": 16}
    assert receipt["catalogue"]["missing_date_files"] == []
    assert receipt["deployment_approved"] is False
    assert any("no rebuild" in line for line in receipt["limitations"])
    index = next(entry for entry in receipt["files"] if entry["path"] == "index.html")
    assert index["sha256_raw"] != index["sha256_lf_normalized"]
    assert receipt["manifest_file"]["sha256_raw"] == mod.digest(payloads["MANIFEST.tsv"])
    output = tmp_path / "accepted"
    mod.extract_verified(payloads, receipt, output)
    for name, content in payloads.items():
        assert (output / name).read_bytes() == content
    assert not (output / mod.EXHIBITION_ROOT).exists()
    assert (output / "verify_bundle.py").read_bytes().startswith(b"raise RuntimeError")


def test_new_profile_still_requires_its_pinned_zip(tmp_path):
    archive = write_exhibition_zip(tmp_path)
    with pytest.raises(mod.IntakeError, match="ZIP byte count"):
        mod.inspect_bundle(archive, profile=mod.EXHIBITION_PROFILE)


def test_legacy_and_new_layouts_require_explicit_matching_profiles(tmp_path):
    new_archive = write_exhibition_zip(tmp_path)
    with pytest.raises(mod.IntakeError, match="unexpected archive member"):
        inspect(new_archive, count=10)
    with pytest.raises(mod.IntakeError, match="unexpected archive root"):
        inspect_exhibition(write_zip(tmp_path))
    legacy_receipt, _ = inspect(write_zip(tmp_path))
    assert legacy_receipt["source_commit"] == mod.EXPECTED_COMMIT
    assert "data_generation_commit" not in legacy_receipt


@pytest.mark.parametrize("path", [
    "../escape", "different-root/site/index.html", "site/index.html",
    mod.EXHIBITION_ROOT + "/../escape",
    mod.EXHIBITION_ROOT + "/site/../README.txt",
    mod.EXHIBITION_ROOT + "/site/CON.txt",
    mod.EXHIBITION_ROOT + "/site/name. ",
    mod.EXHIBITION_ROOT + "/site/index.html:stream",
])
def test_new_profile_rejects_original_path_escape_before_root_stripping(tmp_path, path):
    with pytest.raises(mod.IntakeError, match="unsafe|unexpected archive root"):
        inspect_exhibition(write_exhibition_zip(tmp_path, extras=[(path, b"bad")]))


def test_new_profile_checks_all_raw_paths_before_processing_any_payload(tmp_path):
    # The first member already has a wrong root, but a later unsafe original path
    # must be checked before any root stripping or archive member reading.
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("wrong-root/file", b"x")
        bundle.writestr(mod.EXHIBITION_ROOT + "/site/../escape", b"x")
    with pytest.raises(mod.IntakeError, match="unsafe archive path"):
        inspect_exhibition(archive)


@pytest.mark.parametrize("path", [
    "site/v1/game/849844.json", "site/v1/games/2026-10-01.json",
    "site/assets/extra.js", "extra-metadata.txt",
])
def test_new_profile_rejects_extra_files_even_with_matching_manifest(tmp_path, path):
    files = exhibition_payloads()
    files[path] = b"unexpected file must not be analysed"
    with pytest.raises(mod.IntakeError, match="unexpected archive member"):
        inspect_exhibition(write_exhibition_zip(tmp_path, files))


def test_new_profile_rejects_missing_metadata(tmp_path):
    files = exhibition_payloads()
    files.pop("REVIEW.txt")
    with pytest.raises(mod.IntakeError, match="bundle file set"):
        inspect_exhibition(write_exhibition_zip(tmp_path, files))


@pytest.mark.parametrize("path", ["REVIEW.txt", "site/index.html"])
def test_new_profile_checks_metadata_and_site_raw_hashes(tmp_path, path):
    files = exhibition_payloads()
    declared = exhibition_manifest(files)
    files[path] += b"tampered"
    with pytest.raises(mod.IntakeError, match="byte/hash mismatch"):
        inspect_exhibition(write_exhibition_zip(tmp_path, files, manifest_override=declared))


def test_new_profile_requires_all_nineteen_manifest_rows(tmp_path):
    files = exhibition_payloads()
    site_only = {path: value for path, value in files.items() if path.startswith("site/")}
    with pytest.raises(mod.IntakeError, match="file set"):
        inspect_exhibition(write_exhibition_zip(tmp_path, files, manifest_override=exhibition_manifest(site_only)))


def test_new_profile_lf_column_and_rule_are_explicit(tmp_path):
    files = exhibition_payloads()
    with pytest.raises(mod.IntakeError, match="manifest columns"):
        inspect_exhibition(write_exhibition_zip(tmp_path, files, manifest_override=manifest(files)))
    # A wrong LF digest cannot be hidden by the correct raw digest.
    declared = exhibition_manifest(files)
    css = files["site/assets/index-ks_hu7Ji.css"]
    declared = declared.replace(mod.digest(css.replace(b"\r", b"\n")).encode(), b"0" * 64, 1)
    with pytest.raises(mod.IntakeError, match="byte/hash mismatch"):
        inspect_exhibition(write_exhibition_zip(tmp_path, files, manifest_override=declared))


@pytest.mark.parametrize("path,field,value", [
    ("PROVENANCE.json", "web_build_source_commit", mod.EXHIBITION_DATA_COMMIT),
    ("PROVENANCE.json", "public_data_generation_source_commit", mod.EXHIBITION_WEB_COMMIT),
    ("PROVENANCE.json", "v1_manifest_commit_observed", mod.EXHIBITION_WEB_COMMIT),
    ("PROVENANCE.json", "release_id", "other-delivery"),
    ("TOOLS.json", "source_commit", mod.EXHIBITION_DATA_COMMIT),
    ("site/v1/manifest.json", "commit", mod.EXHIBITION_WEB_COMMIT),
    ("site/v1/manifest.json", "commit_dirty", True),
])
def test_new_profile_does_not_confuse_web_and_data_commits(tmp_path, path, field, value):
    files = exhibition_payloads()
    data = json.loads(files[path])
    data[field] = value
    files[path] = json.dumps(data).encode()
    with pytest.raises(mod.IntakeError, match="provenance|source commit"):
        inspect_exhibition(write_exhibition_zip(tmp_path, files))


@pytest.mark.parametrize("change", ["extra_date", "duplicate_date", "manifest_date", "extra_game", "wrong_game_date", "wrong_game", "wrong_catalogue_date"])
def test_new_profile_checks_single_game_and_date_contents(tmp_path, change):
    files = exhibition_payloads()
    if change in ("extra_date", "duplicate_date"):
        files["site/v1/dates.json"] = json.dumps({"dates": ["2026-09-30", "2026-10-01" if change == "extra_date" else "2026-09-30"]}).encode()
    elif change == "manifest_date":
        data = json.loads(files["site/v1/manifest.json"])
        data["live_dates"] = ["2026-10-01"]
        files["site/v1/manifest.json"] = json.dumps(data).encode()
    elif change == "wrong_game":
        data = json.loads(files["site/v1/game/849843.json"])
        data["game"]["game_pk"] = 849844
        files["site/v1/game/849843.json"] = json.dumps(data).encode()
    else:
        data = json.loads(files["site/v1/games/2026-09-30.json"])
        if change == "extra_game":
            data["games"].append({"game_pk": 849844, "date_kst": "2026-09-30"})
        elif change == "wrong_game_date":
            data["games"][0]["date_kst"] = "2026-10-01"
        else:
            data["date"] = "2026-10-01"
        files["site/v1/games/2026-09-30.json"] = json.dumps(data).encode()
    with pytest.raises(mod.IntakeError, match="only 849843"):
        inspect_exhibition(write_exhibition_zip(tmp_path, files))


@pytest.mark.parametrize("change", ["duplicate_pitch", "wrong_pa", "counts"])
def test_new_profile_keeps_pitch_ledger_validation(tmp_path, change):
    files = exhibition_payloads()
    data = json.loads(files["site/v1/game/849843.json"])
    if change == "duplicate_pitch":
        data["pitches"][1]["key"] = data["pitches"][0]["key"]
    elif change == "wrong_pa":
        data["pitches"][0]["pa_key"] = "849843:2"
    else:
        data["pitches"][0]["rec"]["status"] = "unsupported"
    files["site/v1/game/849843.json"] = json.dumps(data).encode()
    with pytest.raises(mod.IntakeError):
        inspect_exhibition(write_exhibition_zip(tmp_path, files))


def test_new_profile_existing_output_is_never_overwritten(tmp_path):
    receipt, payloads = inspect_exhibition(write_exhibition_zip(tmp_path))
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "preserve"
    sentinel.write_bytes(b"old data")
    with pytest.raises(FileExistsError):
        mod.extract_verified(payloads, receipt, output)
    assert list(output.iterdir()) == [sentinel]
    assert sentinel.read_bytes() == b"old data"
