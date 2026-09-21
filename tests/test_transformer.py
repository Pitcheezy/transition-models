"""Unit tests for PitchTransformer (Model C)."""

import torch
import pytest

from src.models.base import TransitionModel
from src.models.transformer import PitchTransformer, SinusoidalPositionalEncoding


class TestPositionalEncoding:
    def test_shape_preservation(self):
        pe = SinusoidalPositionalEncoding(d_model=256, max_len=400)
        x = torch.randn(2, 400, 256)
        assert pe(x).shape == x.shape

    def test_different_positions(self):
        pe = SinusoidalPositionalEncoding(256, 400)
        x = torch.zeros(1, 400, 256)
        out = pe(x)
        assert not torch.allclose(out[0, 0], out[0, 1])
        assert not torch.allclose(out[0, 0], out[0, 100])

    def test_shorter_sequence(self):
        pe = SinusoidalPositionalEncoding(256, 400)
        x = torch.randn(1, 200, 256)
        assert pe(x).shape == (1, 200, 256)


class TestPitchTransformer:
    @pytest.fixture
    def model(self):
        return PitchTransformer()

    def test_inheritance(self, model):
        assert isinstance(model, TransitionModel)

    def test_forward_shape(self, model):
        x = torch.randn(4, 400, 87)
        out = model(x)
        assert out.shape == (4, 24)

    def test_predict_proba_dict(self, model):
        x = torch.randn(2, 400, 87)
        proba = model.predict_proba(x)
        assert proba["pitch_result"].shape == (2, 10)
        assert proba["hit_location"].shape == (2, 9)
        assert proba["continuous"].shape == (2, 5)

    def test_softmax_sum_to_one(self, model):
        x = torch.randn(2, 400, 87)
        proba = model.predict_proba(x)
        assert torch.allclose(proba["pitch_result"].sum(-1), torch.ones(2), atol=1e-5)
        assert torch.allclose(proba["hit_location"].sum(-1), torch.ones(2), atol=1e-5)

    def test_parameter_count(self, model):
        n = sum(p.numel() for p in model.parameters())
        # 12-layer transformer (d=256, ff=1024, 8 heads) ≈ 9.7M params
        assert 5_000_000 < n < 15_000_000, f"Unexpected param count: {n:,}"

    def test_model_name(self, model):
        assert model.model_name() == "PitchTransformer"

    def test_num_classes(self, model):
        assert model.num_classes() == 10

    def test_gradient_flow(self, model):
        x = torch.randn(2, 400, 87)
        loss = model(x).sum()
        loss.backward()
        for name, p in model.named_parameters():
            assert p.grad is not None, f"No gradient: {name}"

    def test_last_pitch_residual(self, model):
        """Changing only the last pitch should change the output."""
        x1 = torch.randn(1, 400, 87)
        x2 = x1.clone()
        x2[:, -1, :] = torch.randn(1, 87)
        with torch.no_grad():
            out1 = model(x1)
            out2 = model(x2)
        assert not torch.allclose(out1, out2, atol=1e-4)

    @pytest.mark.mps
    def test_mps_compatible(self, model):
        if not torch.backends.mps.is_available():
            pytest.skip("MPS not available")
        model = model.to("mps")
        x = torch.randn(2, 400, 87, device="mps")
        out = model(x)
        assert out.device.type == "mps"
        assert out.shape == (2, 24)

    def test_single_sample(self, model):
        x = torch.randn(1, 400, 87)
        assert model(x).shape == (1, 24)


class TestPitchTransformerHybrid:
    """Tests for PitchTransformer with static_dim > 0 (Phase 10.4 hybrid mode)."""

    @pytest.fixture
    def hybrid_model(self):
        return PitchTransformer(static_dim=58)

    def test_forward_hybrid_shape(self, hybrid_model):
        x = torch.randn(4, 400, 87)
        static = torch.randn(4, 58)
        out = hybrid_model(x, static)
        assert out.shape == (4, 24)

    def test_hybrid_requires_static(self, hybrid_model):
        x = torch.randn(2, 400, 87)
        with pytest.raises(AssertionError):
            hybrid_model(x)  # static=None should fail when static_dim > 0

    def test_baseline_backward_compat(self):
        model = PitchTransformer(static_dim=0)
        x = torch.randn(2, 400, 87)
        assert model(x).shape == (2, 24)

    def test_hybrid_gradient_flow(self, hybrid_model):
        x = torch.randn(2, 400, 87)
        static = torch.randn(2, 58)
        loss = hybrid_model(x, static).sum()
        loss.backward()
        for name, p in hybrid_model.named_parameters():
            assert p.grad is not None, f"No gradient: {name}"
