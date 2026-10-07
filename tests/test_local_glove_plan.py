"""Fresh plan construction with synthetic bytes only; no runtime is started."""

import builtins
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from test_intent_clip_frames import inputs as inputs

from intent import local_glove_plan as builder


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def fixture(inputs, tmp_path, monkeypatch):
    capture_args, capture_receipt, media = inputs
    weights = tmp_path / "weights with spaces.pth"
    weights.write_bytes(b"synthetic checkpoint; no deserialization")
    sha = builder.observer._sha(weights.read_bytes())
    model = "ssdlite320_mobilenet_v3_large"
    monkeypatch.setattr(
        builder.observer,
        "SPECS",
        {model: replace(builder.observer.SPECS[model], sha256_prefix=sha[:8])},
    )
    config = tmp_path / "strict config.json"
    write(
        config,
        {
            "schema": builder.observer.CONFIG_SCHEMA,
            "model_id": model,
            "weights": str(weights),
            "weights_sha256": sha,
            "device": "cpu",
            "threads": 4,
            "threshold": 0.5,
            "input_view": "full_frame",
            "crop_xyxy": None,
        },
    )
    ffmpeg = tmp_path / "ffmpeg synthetic.exe"
    ffmpeg.write_bytes(b"not an executable; only file presence is checked")
    args = {
        "capture_dir": capture_args["capture_dir"],
        "config": config,
        "ffmpeg": str(ffmpeg),
        "out_directory": tmp_path / "fresh bundle",
        "observer_timeout_seconds": 10,
        "extract_timeout_seconds": 20,
        "cutoffs": ["1.0", "11/10", "1.30"],
    }

    def prohibited(*args, **kwargs):
        pytest.fail("Plan generation must not start models, subprocesses or extraction")

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"torch", "torchvision"}:
            pytest.fail("Plan generation must not import torch or torchvision")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(subprocess, "run", prohibited)
    monkeypatch.setattr(subprocess, "Popen", prohibited)
    monkeypatch.setattr(builder.observer, "LocalGloveDetector", prohibited)
    monkeypatch.setattr(builder.local_glove_worker.detector, "LocalGloveDetector", prohibited)
    monkeypatch.setattr(builder.observation_loop.clip_frames, "extract_frame", prohibited)
    monkeypatch.setattr(builder.local_glove_worker, "PersistentGloveRunner", prohibited)
    return args, weights, capture_receipt, media


def test_new_bundle_preserves_config_launcher_and_all_required_bindings(fixture):
    args, _, _, _ = fixture
    original = args["config"].read_bytes()
    receipt = builder.build_plan(**args)
    bundle = args["out_directory"]
    assert receipt == read(bundle / builder.RECEIPT_NAME)
    assert receipt["status"] == "validated" and receipt["error"] is None
    assert args["config"].read_bytes() == original
    assert {path.name for path in bundle.iterdir()} == {"plan.json", builder.RECEIPT_NAME}
    assert not (bundle / "run").exists() and not (bundle / "run.startup").exists()
    plan = read(bundle / "plan.json")
    assert set(plan) == builder.observation_loop._FIELDS
    assert plan["observer_argv"][0] == sys.executable
    assert plan["observer_argv"][1:3] == ["-m", "intent.local_glove_observer"]
    assert plan["observer_argv"][8] == str(args["config"])
    assert plan["cutoffs"] == args["cutoffs"]
    assert plan["ffmpeg"] == args["ffmpeg"]
    expected = {
        "local_glove_observer.py",
        "local_glove_detector.py",
        "local_glove_observer_report.py",
        "local_glove_worker.py",
        "local_glove_ready.py",
        "local_glove_plan.py",
        args["config"].name,
    }
    assert {Path(path).name for path in plan["observer_code_files"]} == expected
    bound = receipt["input_code_bindings"]
    configs = [row for row in bound if row["path"] == str(args["config"])]
    assert len(configs) == 1 and configs[0]["sha256"] == builder.observer._sha(original)
    assert receipt["config_sha256"] == configs[0]["sha256"]
    assert receipt["observer_launcher_binding"]["launcher"] == str(Path(sys.executable).absolute())
    assert receipt["model_calls"] == receipt["decoder_calls"] == receipt["subprocess_calls"] == 0
    assert not any(
        receipt[key]
        for key in (
            "device_operation_verified",
            "decoder_operation_verified",
            "model_operation_verified",
            "config_copied_or_modified",
        )
    )


def test_json_cutoffs_and_path_lookup_are_bound_without_running_binary(fixture, monkeypatch):
    args, _, _, _ = fixture
    source = args["out_directory"].parent / "cutoffs.json"
    source.write_bytes(b'[1, "1.1", "13/10"]\n')
    args.pop("cutoffs")
    args["cutoffs_json"] = source
    decoder = args["ffmpeg"]
    args["ffmpeg"] = "ffmpeg"
    original_which = builder.shutil.which
    monkeypatch.setattr(
        builder.shutil,
        "which",
        lambda value: decoder if value == "ffmpeg" else original_which(value),
    )
    result = builder.build_plan(**args)
    assert result["cutoffs_input"] == {
        "path": str(source),
        "sha256": builder.observer._sha(source.read_bytes()),
    }
    assert read(args["out_directory"] / "plan.json")["cutoffs"] == [1, "1.1", "13/10"]
    assert result["ffmpeg_path"] == decoder


@pytest.mark.parametrize(
    "values", [[], [True], [1.1], ["NaN"], ["1/0"], ["-1"], [1, 1], [2, 1], list(range(51))]
)
def test_invalid_exact_cutoffs_preserve_failed_receipt(fixture, values):
    args, _, _, _ = fixture
    args["cutoffs"] = values
    with pytest.raises(ValueError):
        builder.build_plan(**args)
    assert read(args["out_directory"] / builder.RECEIPT_NAME)["status"] == "failed"
    assert not (args["out_directory"] / "run").exists()


@pytest.mark.parametrize("value", ["0.99", "1.2", "1.4"])
def test_future_gap_and_outside_capture_preflight_fail(fixture, value):
    args, _, _, _ = fixture
    args["cutoffs"] = [value]
    with pytest.raises(ValueError):
        builder.build_plan(**args)
    result = read(args["out_directory"] / builder.RECEIPT_NAME)
    assert result["status"] == "failed" and result["error"]["type"] == "ValueError"
    assert (args["out_directory"] / "plan.json").exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("weights", "relative.pth"),
        ("device", "mps"),
        ("threshold", 2),
        ("weights_sha256", "0" * 64),
        ("threads", True),
        ("unexpected", 1),
    ],
)
def test_strict_config_is_not_rewritten_to_fix_it(fixture, field, value):
    args, _, _, _ = fixture
    config = read(args["config"])
    config[field] = value
    write(args["config"], config)
    original = args["config"].read_bytes()
    with pytest.raises(ValueError):
        builder.build_plan(**args)
    assert args["config"].read_bytes() == original
    assert read(args["out_directory"] / builder.RECEIPT_NAME)["status"] == "failed"


@pytest.mark.parametrize("kind", ["weights", "media", "source_table", "receipt"])
def test_tampered_inputs_are_rejected(fixture, kind):
    args, weights, capture_receipt, media = fixture
    if kind == "weights":
        weights.write_bytes(b"changed checkpoint")
    elif kind == "media":
        media.write_bytes(b"changed source media")
    elif kind == "source_table":
        (args["capture_dir"] / "source.framemd5").write_bytes(b"changed table")
    else:
        capture_receipt["status"] = "failed"
        write(args["capture_dir"] / "receipt.json", capture_receipt)
    with pytest.raises(ValueError):
        builder.build_plan(**args)
    assert read(args["out_directory"] / builder.RECEIPT_NAME)["status"] == "failed"


def test_existing_and_overlapping_bundles_are_not_changed(fixture):
    args, _, _, _ = fixture
    bundle = args["out_directory"]
    bundle.mkdir()
    sentinel = bundle / "prior-result.json"
    sentinel.write_bytes(b"original result")
    with pytest.raises(FileExistsError):
        builder.build_plan(**args)
    assert sentinel.read_bytes() == b"original result" and len(list(bundle.iterdir())) == 1
    args["out_directory"] = args["capture_dir"] / "nested bundle"
    with pytest.raises(ValueError, match="overlap"):
        builder.build_plan(**args)
    assert not args["out_directory"].exists()


@pytest.mark.parametrize("role", ["capture", "config", "weights", "cutoffs", "output_parent"])
def test_symlink_paths_refused_even_when_target_bytes_are_valid(fixture, monkeypatch, role):
    args, weights, _, _ = fixture
    # Simulated leaf links also exercise this guard on Windows without symlink privileges.
    paths = {
        "capture": args["capture_dir"],
        "config": args["config"],
        "weights": weights,
        "ffmpeg": Path(args["ffmpeg"]),
        "output_parent": args["out_directory"].parent,
    }
    if role == "cutoffs":
        path = args["out_directory"].parent / "cutoffs.json"
        write(path, args.pop("cutoffs"))
        args["cutoffs_json"] = path
        paths[role] = path
    target = paths[role]
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == target or original(path))
    with pytest.raises(ValueError, match="[Ss]ymlink"):
        builder.build_plan(**args)
    if role in {"capture", "config", "cutoffs", "output_parent"}:
        assert not args["out_directory"].exists()
    else:
        assert read(args["out_directory"] / builder.RECEIPT_NAME)["status"] == "failed"


def test_original_preflight_exception_and_failed_receipt_are_preserved(fixture, monkeypatch):
    args, _, _, _ = fixture
    failure = RuntimeError("synthetic exact preflight failure")

    def fail(*args):
        raise failure

    monkeypatch.setattr(builder.observation_loop, "_prepare", fail)
    with pytest.raises(RuntimeError) as caught:
        builder.build_plan(**args)
    assert caught.value is failure
    result = read(args["out_directory"] / builder.RECEIPT_NAME)
    assert result["status"] == "failed"
    assert result["error"] == {"type": "RuntimeError", "message": str(failure)}
    assert not (args["out_directory"] / "run").exists()


def test_receipt_failure_does_not_mask_original_error(fixture, monkeypatch):
    args, _, _, _ = fixture
    failure = ValueError("original config failure")

    def fail(*args):
        raise failure

    def receipt_fail(*args):
        raise OSError("receipt disk failure")

    monkeypatch.setattr(builder.observer, "_config", fail)
    monkeypatch.setattr(builder, "_receipt", receipt_fail)
    with pytest.raises(ValueError) as caught:
        builder.build_plan(**args)
    assert caught.value is failure
    assert "receipt disk failure" in caught.value.__notes__[0]
    assert not (args["out_directory"] / builder.RECEIPT_NAME).exists()


@pytest.mark.parametrize("phase", ["plan", "success_receipt"])
def test_post_creation_write_failure_never_publishes_success(fixture, monkeypatch, phase):
    args, _, _, _ = fixture
    original = builder._write
    failure = OSError("synthetic interrupted output write")

    def fail(path, value):
        if (phase == "plan" and path.name == "plan.json") or (
            phase == "success_receipt" and value.get("status") == "validated"
        ):
            path.write_bytes(b"partial")
            raise failure
        return original(path, value)

    monkeypatch.setattr(builder, "_write", fail)
    with pytest.raises(OSError) as caught:
        builder.build_plan(**args)
    assert caught.value is failure
    result = read(args["out_directory"] / builder.RECEIPT_NAME)
    assert result["status"] == "failed" and result["error"]["type"] == "OSError"


@pytest.mark.parametrize("kind", ["config", "cutoffs", "weights"])
def test_changed_input_during_prepare_is_not_reaccepted(fixture, monkeypatch, kind):
    args, weights, _, _ = fixture
    target = weights if kind == "weights" else args["config"]
    if kind == "cutoffs":
        target = args["out_directory"].parent / "cutoffs.json"
        write(target, args.pop("cutoffs"))
        args["cutoffs_json"] = target
    original = builder.observation_loop._prepare

    def changed(*values):
        result = original(*values)
        target.write_bytes(target.read_bytes() + b" ")
        return result

    monkeypatch.setattr(builder.observation_loop, "_prepare", changed)
    with pytest.raises(ValueError, match="changed"):
        builder.build_plan(**args)
    assert read(args["out_directory"] / builder.RECEIPT_NAME)["status"] == "failed"


@pytest.mark.parametrize(
    "field,value",
    [
        ("ffmpeg", "missing-ffmpeg-unavailable"),
        ("observer_timeout_seconds", 0),
        ("extract_timeout_seconds", 3601),
        ("extract_timeout_seconds", float("nan")),
    ],
)
def test_missing_decoder_or_invalid_timeouts_do_not_validate(fixture, field, value):
    args, _, _, _ = fixture
    args[field] = value
    with pytest.raises((ValueError, FileNotFoundError)):
        builder.build_plan(**args)
    assert read(args["out_directory"] / builder.RECEIPT_NAME)["status"] == "failed"


def test_cli_passes_explicit_repeated_cutoffs_and_prints_scope(fixture, capsys):
    args, _, _, _ = fixture
    argv = []
    for key, value in args.items():
        if key == "cutoffs":
            for cutoff in value:
                argv += ["--cutoff", cutoff]
        else:
            argv += ["--" + key.replace("_", "-"), str(value)]
    assert builder.main(argv) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "validated" and not result["model_operation_verified"]


def test_receipt_publication_race_preserves_foreign_receipt(fixture, monkeypatch):
    args, _, _, _ = fixture
    original = builder.os.link
    foreign = b'{"status":"foreign-existing-result"}\n'

    def race(source, destination):
        if not destination.exists():
            destination.write_bytes(foreign)
        return original(source, destination)

    monkeypatch.setattr(builder.os, "link", race)
    with pytest.raises(FileExistsError) as caught:
        builder.build_plan(**args)
    assert (args["out_directory"] / builder.RECEIPT_NAME).read_bytes() == foreign
    assert "Could not preserve validation receipt" in caught.value.__notes__[0]
    assert not (args["out_directory"] / "run").exists()


def test_ffmpeg_lookup_link_is_resolved_to_explicit_file_without_execution(fixture, monkeypatch):
    args, _, _, _ = fixture
    target = Path(args["ffmpeg"])
    alias = target.with_name("homebrew-ffmpeg-link")
    original_which, original_resolve = builder.shutil.which, Path.resolve
    args["ffmpeg"] = "ffmpeg"
    monkeypatch.setattr(
        builder.shutil,
        "which",
        lambda value: str(alias) if value == "ffmpeg" else original_which(value),
    )

    def resolve(path, strict=False):
        if path == alias:
            assert strict is True
            return target
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve)
    result = builder.build_plan(**args)
    assert result["ffmpeg_requested"] == "ffmpeg"
    assert result["ffmpeg_lookup_path"] == str(alias)
    assert result["ffmpeg_path"] == str(target)
    assert result["ffmpeg_resolution"] == "resolved_existing_file_without_execution"
    assert read(args["out_directory"] / "plan.json")["ffmpeg"] == str(target)
    assert not result["decoder_operation_verified"]
    weights = result["weights_binding"]
    assert weights["sha256"] == result["weights_sha256"]
    assert weights["bytes"] == Path(weights["path"]).stat().st_size


def test_generated_plan_change_before_prepare_is_not_adopted(fixture, monkeypatch):
    args, _, _, _ = fixture
    original = builder.observation_loop._prepare

    def changed(plan_path, run_output):
        value = read(plan_path)
        value["cutoffs"] = ["1.0"]
        write(plan_path, value)
        return original(plan_path, run_output)

    monkeypatch.setattr(builder.observation_loop, "_prepare", changed)
    with pytest.raises(ValueError, match="Generated plan changed"):
        builder.build_plan(**args)
    assert read(args["out_directory"] / builder.RECEIPT_NAME)["status"] == "failed"
