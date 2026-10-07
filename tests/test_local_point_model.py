"""Synthetic-only checks of the frozen CV15 point model and artifact contract."""

# Import the model first so its src/Arrow guard runs before any torch import.
# isort: off
from intent import local_point_model as point
# isort: on

import copy
import hashlib
import inspect
import math

import numpy as np
import pytest
import torch
from PIL import Image


@pytest.fixture(scope="module")
def synthetic_training():
    images = np.zeros((2, 3, 128, 192), dtype=np.float32)
    images[0, :, 40:56, 40:56] = 1.0
    images[1, :, 40:56, 136:152] = 1.0
    targets = np.array([[0.25, 0.375], [0.75, 0.375]], dtype=np.float32)
    model, checkpoint = point.train_point_model(images, targets, seed=42, device="cpu")
    return images, targets, model, checkpoint


def test_architecture_matches_frozen_spec():
    model = point.TinyPointHeatmap()
    convolutions = [layer for layer in model.layers if isinstance(layer, torch.nn.Conv2d)]
    assert [(layer.in_channels, layer.out_channels) for layer in convolutions] == [
        (3, 16),
        (16, 32),
        (32, 32),
        (32, 1),
    ]
    assert [layer.stride for layer in convolutions] == [(2, 2), (2, 2), (1, 1), (1, 1)]
    assert [layer.kernel_size for layer in convolutions] == [(3, 3), (3, 3), (3, 3), (1, 1)]
    assert sum(parameter.numel() for parameter in model.parameters()) == 14369
    with torch.inference_mode():
        result = model(torch.zeros(2, 3, 128, 192))
    assert result.shape == (2, 1, 32, 48)
    assert torch.isfinite(result).all()


def test_rgb_preprocessing_matches_runner_contract():
    source = Image.new("RGBA", (17, 11), (41, 88, 203, 19))
    actual = point.prepare_rgb_image(source)
    expected = np.asarray(
        source.convert("RGB").resize((192, 128), Image.Resampling.BILINEAR),
        dtype=np.float32,
    ).transpose(2, 0, 1) / np.float32(255.0)
    np.testing.assert_array_equal(actual.numpy(), expected)
    assert actual.shape == (3, 128, 192)
    assert actual.is_contiguous()
    assert actual.device.type == "cpu"
    assert actual.dtype == torch.float32


def test_gaussian_peak_sigma_and_finite_grid_normalization():
    points = torch.tensor([[(10.5) / 48, (7.5) / 32], [0.0, 1.0]], dtype=torch.float32)
    target = point.gaussian_targets(points)
    assert target.shape == (2, 1, 32, 48)
    torch.testing.assert_close(target.flatten(1).sum(1), torch.ones(2))
    assert target[0].argmax().item() == 7 * 48 + 10
    adjacent_ratio = target[0, 0, 7, 11] / target[0, 0, 7, 10]
    assert adjacent_ratio.item() == pytest.approx(math.exp(-1 / (2 * 1.5**2)), rel=1e-6)
    assert torch.isfinite(target).all()
    assert target[1].argmax().item() == 31 * 48


def test_softargmax_uses_cell_centers_and_uv_order():
    uniform = torch.zeros(1, 1, 32, 48)
    torch.testing.assert_close(point.softargmax_points(uniform), torch.tensor([[0.5, 0.5]]))
    logits = torch.full((2, 1, 32, 48), -100.0)
    logits[0, 0, 5, 37] = 100.0
    logits[1, 0, 31, 0] = 100.0
    expected = torch.tensor([[37.5 / 48, 5.5 / 32], [0.5 / 48, 31.5 / 32]])
    torch.testing.assert_close(point.softargmax_points(logits), expected)


def test_cross_entropy_matches_uniform_distribution_and_has_gradient():
    logits = torch.zeros(2, 1, 32, 48, requires_grad=True)
    targets = torch.tensor([[0.3, 0.7], [0.6, 0.2]])
    loss = point.point_loss(logits, targets)
    assert loss.item() == pytest.approx(math.log(32 * 48), rel=1e-6)
    loss.backward()
    assert logits.grad is not None
    assert torch.isfinite(logits.grad).all()
    assert torch.count_nonzero(logits.grad) > 0
    matching_logits = point.gaussian_targets(targets).clamp_min(1e-30).log()
    assert point.point_loss(matching_logits, targets) < loss


@pytest.mark.parametrize(
    "bad",
    [
        torch.tensor([[float("nan"), 0.5]]),
        torch.tensor([[0.5, float("inf")]]),
        torch.tensor([[-0.001, 0.5]]),
        torch.tensor([[0.5, 1.001]]),
        torch.ones(1, 3),
        torch.ones(2),
        torch.empty(0, 2),
        torch.ones(1, 2, dtype=torch.float64),
        torch.ones(1, 2, dtype=torch.bool),
        [[0.5, 0.5]],
    ],
)
def test_invalid_targets_rejected_without_clipping(bad):
    with pytest.raises(point.PointModelError):
        point.gaussian_targets(bad)


@pytest.mark.parametrize(
    "bad",
    [
        torch.full((1, 1, 32, 48), float("nan")),
        torch.full((1, 1, 32, 48), float("inf")),
        torch.zeros(1, 32, 48),
        torch.zeros(1, 1, 48, 32),
        torch.empty(0, 1, 32, 48),
        torch.zeros(1, 1, 32, 48, dtype=torch.float64),
    ],
)
def test_invalid_heatmaps_rejected(bad):
    with pytest.raises(point.PointModelError):
        point.softargmax_points(bad)


@pytest.mark.parametrize(
    "bad",
    [
        np.full((1, 3, 128, 192), np.nan, dtype=np.float32),
        np.full((1, 3, 128, 192), -0.01, dtype=np.float32),
        np.full((1, 3, 128, 192), 1.01, dtype=np.float32),
        np.zeros((1, 3, 192, 128), dtype=np.float32),
        np.zeros((0, 3, 128, 192), dtype=np.float32),
        np.zeros((1, 3, 128, 192), dtype=np.float64),
        np.zeros((1, 3, 128, 192), dtype=np.uint8),
        np.zeros((1, 3, 128, 192), dtype=bool),
    ],
)
def test_invalid_training_images_rejected_before_training(bad):
    with pytest.raises(point.PointModelError):
        point.train_point_model(bad, np.array([[0.5, 0.5]], np.float32), seed=42, device="cpu")


@pytest.mark.parametrize("seed", [True, 0, 41, 45, 42.0, "42", None])
def test_only_fixed_seeds_are_allowed(seed):
    with pytest.raises(point.PointModelError, match="seed"):
        point.train_point_model(None, None, seed=seed, device="cpu")


@pytest.mark.parametrize("device", ["mps", "cuda:0", "auto", None])
def test_device_must_be_explicit_cpu_or_cuda(device):
    with pytest.raises(point.PointModelError, match="device"):
        point.train_point_model(None, None, seed=42, device=device)


def test_unavailable_cuda_is_not_replaced_with_cpu(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(point.PointModelError, match="no fallback"):
        point.train_point_model(None, None, seed=42, device="cuda")


def test_training_api_has_no_evaluation_or_tuning_inputs():
    signature = inspect.signature(point.train_point_model)
    assert list(signature.parameters) == ["train_images", "normalized_points", "seed", "device"]
    assert signature.parameters["seed"].kind == inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["device"].kind == inspect.Parameter.KEYWORD_ONLY


def test_training_lengths_must_match():
    with pytest.raises(point.PointModelError, match="equal lengths"):
        point.train_point_model(
            np.zeros((2, 3, 128, 192), np.float32),
            np.array([[0.5, 0.5]], np.float32),
            seed=42,
            device="cpu",
        )


def test_loss_batch_sizes_must_match():
    with pytest.raises(point.PointModelError, match="equal batch"):
        point.point_loss(torch.zeros(2, 1, 32, 48), torch.zeros(1, 2))


def test_fixed_training_records_final_state_without_mutating_inputs(synthetic_training):
    images, targets, model, checkpoint = synthetic_training
    metadata = checkpoint["metadata"]
    assert checkpoint["schema"] == point.SCHEMA
    assert metadata["config"] == point.fixed_config()
    assert metadata["seed"] == 42
    assert metadata["train_count"] == 2
    assert metadata["epochs_completed"] == 20
    assert metadata["optimizer_steps"] == 20
    assert len(metadata["train_losses"]) == 20
    assert all(math.isfinite(loss) for loss in metadata["train_losses"])
    assert metadata["runtime"]["threads"] == 4
    assert metadata["runtime"]["device"] == "cpu"
    assert metadata["runtime"]["deterministic_algorithms"] is True
    assert metadata["runtime"]["cudnn_benchmark"] is False
    assert all(not module.training for module in model.modules())
    assert all(value.device.type == "cpu" for value in checkpoint["state_dict"].values())
    for name, value in model.state_dict().items():
        torch.testing.assert_close(value, checkpoint["state_dict"][name], rtol=0, atol=0)
        assert value.data_ptr() != checkpoint["state_dict"][name].data_ptr()
    assert images[0, 0, 40, 40] == 1.0
    assert images[0, 0, 0, 0] == 0.0
    np.testing.assert_array_equal(targets, np.array([[0.25, 0.375], [0.75, 0.375]], np.float32))


def test_same_cpu_seed_repeats_synthetic_training(synthetic_training):
    images, targets, _, first = synthetic_training
    _, second = point.train_point_model(images, targets, seed=42, device="cpu")
    assert first["metadata"]["train_losses"] == second["metadata"]["train_losses"]
    for name, value in first["state_dict"].items():
        torch.testing.assert_close(value, second["state_dict"][name], rtol=0, atol=0)


def test_partial_final_batch_is_included(monkeypatch):
    calls = []

    class SyntheticScalarModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.scalar = torch.nn.Parameter(torch.tensor(0.0))

        def forward(self, images):
            calls.append(len(images))
            return self.scalar.expand(len(images), 1, 32, 48)

    monkeypatch.setattr(point, "TinyPointHeatmap", SyntheticScalarModel)
    _, checkpoint = point.train_point_model(
        np.zeros((9, 3, 128, 192), np.float32),
        np.full((9, 2), 0.5, np.float32),
        seed=43,
        device="cpu",
    )
    assert calls == [8, 1] * 20
    assert checkpoint["metadata"]["optimizer_steps"] == 40


def test_checkpoint_round_trip_is_sha_bound_and_weights_only(
    synthetic_training, tmp_path, monkeypatch
):
    images, _, model, checkpoint = synthetic_training
    path = tmp_path / "synthetic.pt"
    torch.save(checkpoint, path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    calls = []
    original_load = torch.load

    def spy_load(*args, **kwargs):
        calls.append(kwargs)
        return original_load(*args, **kwargs)

    monkeypatch.setattr(torch, "load", spy_load)
    loaded, metadata = point.load_point_model(path, device="cpu", expected_sha256=digest)
    assert calls == [{"map_location": "cpu", "weights_only": True}]
    assert metadata == checkpoint["metadata"]
    assert all(not module.training for module in loaded.modules())
    expected = point.predict_points(model, images, device="cpu")
    actual = point.predict_points(loaded, images, device="cpu")
    torch.testing.assert_close(actual, expected, rtol=0, atol=0)
    assert actual.shape == (2, 2)
    assert actual.device.type == "cpu"
    assert torch.all((actual > 0) & (actual < 1))


def test_hash_mismatch_rejected_before_deserialization(tmp_path, monkeypatch):
    path = tmp_path / "not-a-checkpoint.pt"
    path.write_bytes(b"synthetic")
    monkeypatch.setattr(torch, "load", lambda *a, **kw: pytest.fail("must not deserialize"))
    with pytest.raises(point.PointModelError, match="SHA-256"):
        point.load_point_model(path, device="cpu", expected_sha256="0" * 64)


@pytest.mark.parametrize("bad_hash", ["", "abc", "A" * 64, False, None])
def test_full_sha_is_required_before_opening_file(bad_hash):
    with pytest.raises(point.PointModelError, match="SHA-256"):
        point.load_point_model("unused.pt", device="cpu", expected_sha256=bad_hash)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("seed", 123),
        ("train_count", 0),
        ("train_count", True),
        ("epochs_completed", 19),
        ("optimizer_steps", 19),
        ("train_losses", [float("nan")] * 20),
        ("runtime", None),
        ("config", {}),
    ],
)
def test_incompatible_checkpoint_metadata_rejected(synthetic_training, tmp_path, key, value):
    checkpoint = copy.deepcopy(synthetic_training[3])
    checkpoint["metadata"][key] = value
    path = tmp_path / "incompatible.pt"
    torch.save(checkpoint, path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(point.PointModelError):
        point.load_point_model(path, device="cpu", expected_sha256=digest)


def test_wrong_state_shape_is_not_silently_accepted(synthetic_training, tmp_path):
    checkpoint = copy.deepcopy(synthetic_training[3])
    checkpoint["state_dict"]["layers.0.weight"] = torch.zeros(1)
    path = tmp_path / "wrong-state.pt"
    torch.save(checkpoint, path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(point.PointModelError, match="invalid CV15 checkpoint"):
        point.load_point_model(path, device="cpu", expected_sha256=digest)


def test_prediction_preserves_all_rows_in_fixed_batches():
    model = point.TinyPointHeatmap().eval()
    calls = []
    hook = model.register_forward_pre_hook(lambda module, inputs: calls.append(len(inputs[0])))
    try:
        result = point.predict_points(model, np.zeros((11, 3, 128, 192), np.float32), device="cpu")
    finally:
        hook.remove()
    assert result.shape == (11, 2)
    assert calls == [8, 3]
    assert result.requires_grad is False


def test_config_result_cannot_mutate_later_config():
    first = point.fixed_config()
    first["architecture"][0]["out"] = 999
    assert point.fixed_config()["architecture"][0]["out"] == 16
