"""Synthetic reviews verify denominators, binding, exclusions and read-only reporting."""

import json
from copy import deepcopy

import pytest
from PIL import Image

from intent import review_summary
from intent.replay import _sha
from intent.review_queue import MANIFEST_SCHEMA, PROTOCOL, RESPONSE_SCHEMA


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


@pytest.fixture
def package(tmp_path):
    package = tmp_path / "package"
    reviewer = package / "reviewer"
    reviewer.mkdir(parents=True)
    image = reviewer / "frame.jpg"
    Image.new("RGB", (100, 80)).save(image)
    sha = _sha(image.read_bytes())
    frames = [
        dict(observation_id=f"obs_{i}", path=image.name, image_sha256=sha, width=100, height=80)
        for i in range(4)
    ]
    manifest = write(
        reviewer / "manifest.json",
        dict(schema=MANIFEST_SCHEMA, protocol_version=PROTOCOL, frames=frames),
    )
    digest = _sha(manifest.read_bytes())
    write(package / "private_selection.json", dict(reviewer_manifest_sha256=digest))
    template = dict(
        schema=RESPONSE_SCHEMA,
        protocol_version=PROTOCOL,
        manifest_sha256=digest,
        reviewer_id="",
        rows=[
            dict(
                observation_id=f["observation_id"],
                image_sha256=sha,
                status="unreviewed",
                mitt=None,
                visibility="unknown",
                pose="unknown",
                reason="",
            )
            for f in frames
        ],
    )
    write(reviewer / "response_template.json", template)
    return package, template


def response(package, identity, statuses, name="response.json", offset=0):
    directory, template = package
    doc = deepcopy(template)
    doc["reviewer_id"] = identity
    for row, status in zip(doc["rows"], statuses, strict=True):
        row["status"] = status
        if status == "marked":
            row.update(mitt=[10 + offset, 20 + offset], visibility="full", pose="resting")
        elif status in {"unknown", "unavailable"}:
            row["reason"] = "synthetic fixture"
    return write(directory.parent / name, doc)


def test_no_responses_waits_without_comparison(package):
    report = review_summary.summarize(package[0])
    assert report["status"] == "awaiting_human_responses"
    assert report["coverage"]["denominator_observations"] == 4
    assert report["coverage"]["reviewed_union"] == 0
    assert report["coverage"]["unreviewed_by_all"] == 4
    assert report["pairwise"] == []
    assert not report["accuracy_measured"] and not report["independent_validation"]


def test_one_partial_response_preserves_all_denominators(package):
    path = response(package, " Ada ", ["marked", "unknown", "unreviewed", "unreviewed"])
    report = review_summary.summarize(package[0], [path])
    assert report["coverage"]["reviewed_union"] == 2
    assert report["coverage"]["decided_union"] == 1
    assert report["coverage"]["only_unknown_union"] == 1
    reviewer = report["reviewers"][0]
    assert reviewer["reviewer_id"] == "Ada"
    assert reviewer["counts"] == dict(marked=1, unavailable=0, unknown=1, unreviewed=2)
    assert reviewer["pose_among_reviewed"] == dict(resting=1, unknown=1)
    assert reviewer["response_sha256"] == _sha(path.read_bytes())


def test_pairwise_only_decided_and_distance_is_descriptive(package):
    a = response(package, "Ada", ["marked", "marked", "unknown", "unreviewed"])
    b = response(package, "Bea", ["marked", "unavailable", "unreviewed", "unknown"], "b.json", 3)
    report = review_summary.summarize(package[0], [a, b])
    pair = report["pairwise"][0]
    assert pair["eligible_both_decided"] == 2
    assert pair["same_status"] == pair["different_status"] == 1
    assert pair["same_status_rate"] == 0.5
    assert pair["excluded_observations"] == 2
    assert pair["excluded_with_unknown"] == pair["excluded_with_unreviewed"] == 2
    assert pair["status_conflict_observation_ids"] == ["obs_1"]
    assert pair["both_marked_pixel_distance"]["median"] == pytest.approx(18**0.5)
    assert pair["both_marked_pixel_distance"]["n"] == 1
    assert report["coverage"]["reviewed_union"] == 4
    assert report["coverage"]["decided_union"] == 2


def test_no_eligible_pairs_has_null_metrics(package):
    a = response(package, "Ada", ["marked", "unreviewed", "unreviewed", "unreviewed"])
    b = response(package, "Bea", ["unknown", "marked", "unknown", "unknown"], "b.json")
    pair = review_summary.summarize(package[0], [a, b])["pairwise"][0]
    assert pair["same_status_rate"] is None
    assert pair["both_marked_pixel_distance"]["median"] is None
    assert pair["both_marked_pixel_distance"]["p90"] is None


@pytest.mark.parametrize("kind", ["path", "hash", "identity"])
def test_duplicate_responses_rejected(package, kind):
    a = response(package, "Ada", ["marked"] * 4)
    b = response(package, " ADA ", ["unknown"] * 4, "b.json")
    if kind == "path":
        b = a
    elif kind == "hash":
        b.write_bytes(a.read_bytes())
    with pytest.raises(ValueError, match="duplicate"):
        review_summary.summarize(package[0], [a, b])


@pytest.mark.parametrize("kind", ["blank", "no_identity", "image", "manifest"])
def test_invalid_input_rejected(package, kind):
    a = response(package, "Ada", ["marked"] * 4)
    if kind == "blank":
        a = package[0] / "reviewer/response_template.json"
    elif kind == "no_identity":
        a = response(package, " ", ["marked"] * 4)
    elif kind == "image":
        (package[0] / "reviewer/frame.jpg").write_bytes(b"changed")
    else:
        path = package[0] / "reviewer/manifest.json"
        path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError):
        review_summary.summarize(package[0], [a])


def test_drift_during_validation_rejected(package, monkeypatch):
    a = response(package, "Ada", ["marked"] * 4)
    original = review_summary.check_response

    def mutate_after_validation(pack, path):
        result = original(pack, path)
        if path == a:
            a.write_bytes(a.read_bytes() + b" ")
        return result

    monkeypatch.setattr(review_summary, "check_response", mutate_after_validation)
    with pytest.raises(ValueError, match="changed during"):
        review_summary.summarize(package[0], [a])


def test_cli_never_overwrites_and_preserves_package(package, tmp_path):
    before = {p: p.read_bytes() for p in package[0].rglob("*") if p.is_file()}
    output = tmp_path / "summary.json"
    argv = ["--package", str(package[0]), "--out", str(output)]
    review_summary.main(argv)
    saved = output.read_bytes()
    with pytest.raises(FileExistsError):
        review_summary.main(argv)
    assert output.read_bytes() == saved
    assert all(path.read_bytes() == data for path, data in before.items())
