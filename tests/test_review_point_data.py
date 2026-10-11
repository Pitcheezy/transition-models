"""Synthetic current-protocol preparation preserves meaning, identity and nulls."""

import json
from copy import deepcopy

import pytest
from PIL import Image

from intent import local_detector_data, review_point_data
from intent.replay import _sha
from intent.review_queue import MANIFEST_SCHEMA, PROTOCOL, RESPONSE_SCHEMA


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    results = root / "docs/results/mlb_p0"
    results.mkdir(parents=True)
    monkeypatch.setattr(local_detector_data, "EXPECTED_COUNTS", {823407: 3, 849845: 3})
    for game, count in local_detector_data.EXPECTED_COUNTS.items():
        frames, labels, points = [], [], []
        for number in range(1, count + 1):
            path = root / f"outputs/frames/{game}/{number}.jpg"
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (16, 12), (game % 255, number * 60, 1)).save(path)
            frame = dict(
                pitch_id=f"{game}:1:{number}",
                frame_seconds=float(number),
                path=path.relative_to(root).as_posix(),
                image_sha256=_sha(path.read_bytes()),
            )
            frames.append(frame)
            labels.append(
                dict(
                    frame,
                    mitt_status="marked",
                    mitt=[5, 6],
                    plate_status="hidden",
                    plate_front=None,
                )
            )
            points.append(dict(frame, at_bat_number=1, pitch_number=number))
        pack_id = _sha(json.dumps([[f["pitch_id"], f["image_sha256"]] for f in frames]).encode())[
            :16
        ]
        write(
            results / f"game_{game}_intent_label_pack_v0.json",
            dict(
                schema="intent_label_pack_v0",
                game_pk=game,
                pack_id=pack_id,
                selection={"all_frames": True},
                frames=frames,
                crops={"main": {"box": [2, 2, 14, 10]}, "plate": {"box": [1, 7, 15, 12]}},
            ),
        )
        raw = dict(schema="intent_human_labels_v0", game_pk=game, pack_id=pack_id, frames=labels)
        raw_path = write(results / f"game_{game}_intent_human_labels_raw_v0.json", raw)
        write(
            results / f"game_{game}_intent_human_labels_v0.json",
            dict(raw, raw_sha256=_sha(raw_path.read_bytes())),
        )
        write(
            results / f"game_{game}_intent_points_v0.json",
            dict(schema="intent_points_v0", game_pk=game, frames=points),
        )
        write(
            results / f"game_{game}_condensed_source_v0.json",
            dict(
                schema="intent_condensed_source_v0",
                game_pk=game,
                condensed_game={"probe": {"width": 16, "height": 12}},
            ),
        )
    dataset = root / "outputs/cv12"
    audit = local_detector_data.prepare(results, root, dataset)
    package = root / "outputs/cv6"
    reviewer = package / "reviewer"
    reviewer.mkdir(parents=True)
    public, mapping = [], []
    for index, frame in enumerate(load(dataset / "manifest.json")["frames"]):
        obs = f"opaque_{index}"
        image_path = reviewer / f"{obs}.jpg"
        image_path.write_bytes(
            (root / "outputs/frames" / str(frame["game_pk"]) / f"{index % 3 + 1}.jpg").read_bytes()
        )
        public.append(
            dict(
                observation_id=obs,
                image_sha256=frame["image_sha256"],
                width=16,
                height=12,
                path=image_path.name,
            )
        )
        mapping.append(
            dict(
                observation_id=obs,
                pitch_id=frame["observation_id"],
                image_sha256=frame["image_sha256"],
                frame_seconds=float(index % 3 + 1),
                source_path=f"outputs/frames/{frame['game_pk']}/{index % 3 + 1}.jpg",
            )
        )
    manifest_path = write(
        reviewer / "manifest.json",
        dict(
            schema=MANIFEST_SCHEMA,
            protocol_version=PROTOCOL,
            scope="development_source_only_recheck",
            frames=public,
        ),
    )
    digest = _sha(manifest_path.read_bytes())
    template = dict(
        schema=RESPONSE_SCHEMA,
        protocol_version=PROTOCOL,
        manifest_sha256=digest,
        reviewer_id="",
        rows=[
            dict(
                observation_id=f["observation_id"],
                image_sha256=f["image_sha256"],
                status="unreviewed",
                mitt=None,
                visibility="unknown",
                pose="unknown",
                reason="",
            )
            for f in public
        ],
    )
    write(reviewer / "response_template.json", template)
    write(
        package / "private_selection.json",
        dict(
            schema="intent_review_selection_v1",
            reviewer_manifest_sha256=digest,
            mapping=mapping,
            sources=[
                dict(
                    game_pk=g["game_pk"],
                    sources={
                        name: dict(
                            path=f"game_{g['game_pk']}_{review_point_data.SOURCE_SUFFIXES[name]}",
                            sha256=g["source_sha256"][name],
                        )
                        for name in ("manifest", "points", "labels")
                    },
                )
                for g in audit["games"]
            ],
        ),
    )
    return root, package, dataset / "manifest.json", dataset / "audit.json", root / "outputs/new"


def response(prepared, name="human.json", reviewer="Reviewer-Synthetic-A", offset=0):
    document = load(prepared[1] / "reviewer/response_template.json")
    document["reviewer_id"] = reviewer
    document["rows"][0].update(
        status="marked", mitt=[5 + offset, 6], visibility="full", pose="resting"
    )
    document["rows"][1].update(
        status="marked", mitt=[8, 4], visibility="partial", reason="edge covered"
    )
    document["rows"][2].update(
        status="unavailable", visibility="hidden", reason="center unreadable"
    )
    document["rows"][3].update(status="unknown", reason="uncertain")
    return write(prepared[1] / name, document)


def test_zero_responses_never_imports_legacy_points(prepared):
    summary = review_point_data.prepare(*prepared)
    manifest = load(prepared[-1] / "manifest.json")
    assert summary["status"] == "awaiting_human_responses"
    assert summary["source_frames"] == summary["unreviewed_by_all"] == 6
    assert summary["point_annotations"] == summary["annotation_rows"] == 0
    assert not summary["ready_for_training"] and not summary["training_performed"]
    assert all(frame["annotations"] == [] for frame in manifest["frames"])
    assert {f["group_key"] for f in manifest["frames"]} == {"game:823407", "game:849845"}
    assert str(prepared[0]) not in json.dumps(summary)
    assert "opaque_" not in json.dumps(summary)


def test_status_pose_visibility_and_nulls_remain_separate(prepared):
    path = response(prepared)
    original = path.read_bytes()
    summary = review_point_data.prepare(*prepared, responses=[path])
    rows = [frame["annotations"][0] for frame in load(prepared[-1] / "manifest.json")["frames"]]
    assert summary["annotation_status_counts"] == dict(
        marked=2, unavailable=1, unknown=1, unreviewed=2
    )
    assert summary["marked_visibility_counts"] == dict(full=1, partial=1)
    assert rows[0]["pose"] == "resting" and rows[0]["candidate_point_mask"]
    assert rows[1]["visibility"] == "partial" and rows[1]["candidate_point_mask"]
    assert all(row["mitt"] is None and not row["candidate_point_mask"] for row in rows[2:])
    assert all(row["glove_presence_target"] is None for row in rows)
    assert summary["training_examples_selected"] == 0 and not summary["ready_for_training"]
    assert path.read_bytes() == original
    assert "Reviewer-Synthetic-A" not in json.dumps(summary)


def test_reviewers_do_not_multiply_unique_frames_or_create_consensus(prepared):
    a = response(prepared)
    b = response(prepared, "b.json", "Other", offset=2)
    summary = review_point_data.prepare(*prepared, responses=[a, b])
    rows = load(prepared[-1] / "manifest.json")["frames"]
    assert summary["point_annotations"] == 4
    assert summary["unique_frames_with_points"] == 2
    assert summary["source_frames"] == 6 and summary["annotation_rows"] == 12
    assert [r["mitt"] for r in rows[0]["annotations"]] == [[5, 6], [7, 6]]
    assert all(len(row["annotations"]) == 2 for row in rows)


def test_response_order_does_not_change_image_point_joins(prepared):
    path = response(prepared)
    document = load(path)
    document["rows"].reverse()
    write(path, document)
    review_point_data.prepare(*prepared, responses=[path])
    frames = load(prepared[-1] / "manifest.json")["frames"]
    assert frames[0]["observation_id"] == "opaque_0"
    assert frames[0]["annotations"][0]["mitt"] == [5, 6]
    assert frames[-1]["annotations"][0]["status"] == "unreviewed"


def test_cli_prints_only_public_summary(prepared, capsys):
    arguments = []
    for flag, path in zip(
        ("--repo-root", "--package", "--dataset-manifest", "--dataset-audit", "--out"),
        prepared,
        strict=True,
    ):
        arguments.extend([flag, str(path)])
    review_point_data.main(arguments)
    output = capsys.readouterr().out
    assert json.loads(output) == load(prepared[-1] / "summary.json")
    assert str(prepared[0]) not in output and "opaque_" not in output


@pytest.mark.parametrize("field", ["pitch_id", "source_path", "frame_seconds", "image_sha256"])
def test_tampered_private_join_is_rejected(prepared, field):
    path = prepared[1] / "private_selection.json"
    doc = load(path)
    doc["mapping"][0][field] = doc["mapping"][1][field]
    write(path, doc)
    with pytest.raises(ValueError):
        review_point_data.prepare(*prepared)
    assert not prepared[-1].exists()


@pytest.mark.parametrize("target", ["private", "source", "reviewer"])
def test_duplicate_join_rows_are_rejected_even_with_rebound_hash(prepared, target):
    if target == "private":
        path = prepared[1] / "private_selection.json"
        doc = load(path)
        doc["mapping"].append(deepcopy(doc["mapping"][0]))
        write(path, doc)
    elif target == "source":
        doc = load(prepared[2])
        doc["frames"].append(deepcopy(doc["frames"][0]))
        write(prepared[2], doc)
        audit = load(prepared[3])
        audit["manifest_sha256"] = _sha(prepared[2].read_bytes())
        write(prepared[3], audit)
    else:
        path = prepared[1] / "reviewer/manifest.json"
        doc = load(path)
        doc["frames"][1]["image_sha256"] = doc["frames"][0]["image_sha256"]
        write(path, doc)
    with pytest.raises(ValueError):
        review_point_data.prepare(*prepared)
    assert not prepared[-1].exists()


@pytest.mark.parametrize("kind", ["ai", "legacy", "blank", "duplicate_reviewer", "image", "audit"])
def test_incompatible_or_changed_inputs_are_rejected(prepared, kind):
    path = response(prepared)
    responses = [path]
    if kind in {"ai", "legacy"}:
        doc = load(path)
        doc["schema"] = "intent_visual_observation_v1" if kind == "ai" else "intent_human_labels_v0"
        write(path, doc)
    elif kind == "blank":
        responses = [prepared[1] / "reviewer/response_template.json"]
    elif kind == "duplicate_reviewer":
        responses.append(response(prepared, "b.json", " REVIEWER-SYNTHETIC-A ", 1))
    elif kind == "image":
        (prepared[0] / "outputs/frames/823407/1.jpg").write_bytes(b"changed")
    else:
        doc = load(prepared[3])
        doc["manifest_sha256"] = "0" * 64
        write(prepared[3], doc)
    with pytest.raises(ValueError):
        review_point_data.prepare(*prepared, responses=responses)
    assert not prepared[-1].exists()


def test_input_changed_after_aggregation_aborts_before_output(prepared, monkeypatch):
    path = response(prepared)
    original = review_point_data.public_summary

    def mutate(document):
        result = original(document)
        path.write_bytes(path.read_bytes() + b" ")
        return result

    monkeypatch.setattr(review_point_data, "public_summary", mutate)
    with pytest.raises(ValueError, match="SHA256"):
        review_point_data.prepare(*prepared, responses=[path])
    assert not prepared[-1].exists()


def test_existing_output_and_path_escape_are_rejected(prepared):
    review_point_data.prepare(*prepared)
    original = (prepared[-1] / "manifest.json").read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        review_point_data.prepare(*prepared)
    assert (prepared[-1] / "manifest.json").read_bytes() == original
    escaped = (*prepared[:-1], prepared[0] / "outputs/../escaped")
    with pytest.raises(ValueError, match="inside repo outputs"):
        review_point_data.prepare(*escaped)
