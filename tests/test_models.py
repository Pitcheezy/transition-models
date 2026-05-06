"""Unit tests for model base interface and OtrembaMLP."""

import torch
import pytest

from src.models.base import TransitionModel
from src.models.otremba_mlp import OtrembaMLP


# =============================================================================
# Base interface
# =============================================================================


class TestBaseInterface:
    def test_cannot_instantiate_abstract(self):
        """TransitionModel is abstract — direct instantiation must fail."""
        with pytest.raises(TypeError):
            TransitionModel()

    def test_otremba_is_transition_model(self):
        model = OtrembaMLP()
        assert isinstance(model, TransitionModel)


# =============================================================================
# OtrembaMLP
# =============================================================================


class TestOtrembaMLP:
    def test_forward_shape(self):
        model = OtrembaMLP(input_dim=77, n_classes=4)
        x = torch.randn(32, 77)
        out = model(x)
        assert out.shape == (32, 4)

    def test_predict_proba_sums_to_one(self):
        model = OtrembaMLP()
        x = torch.randn(16, 77)
        proba = model.predict_proba(x)
        assert proba.shape == (16, 4)
        sums = proba.sum(dim=-1)
        assert torch.allclose(sums, torch.ones(16), atol=1e-5)

    def test_predict_proba_non_negative(self):
        model = OtrembaMLP()
        proba = model.predict_proba(torch.randn(8, 77))
        assert (proba >= 0).all()

    def test_num_classes(self):
        assert OtrembaMLP(n_classes=4).num_classes() == 4

    def test_model_name(self):
        assert OtrembaMLP().model_name() == "OtrembaMLP"

    def test_parameter_count(self):
        model = OtrembaMLP(input_dim=77, hidden_dim=128, n_classes=4)
        total = sum(p.numel() for p in model.parameters())
        # 77*128 + 128 + 128*128 + 128 + 128*4 + 4 = 9856 + 128 + 16384 + 128 + 512 + 4 = 27012
        expected = 77 * 128 + 128 + 128 * 128 + 128 + 128 * 4 + 4
        assert total == expected, f"Expected {expected}, got {total}"

    def test_dropout_variant(self):
        model = OtrembaMLP(dropout=0.3)
        x = torch.randn(8, 77)
        out = model(x)
        assert out.shape == (8, 4)

    def test_single_sample(self):
        model = OtrembaMLP()
        x = torch.randn(1, 77)
        out = model(x)
        assert out.shape == (1, 4)

    def test_mps_compatible(self):
        """Model can be moved to MPS if available."""
        if not torch.backends.mps.is_available():
            pytest.skip("MPS not available")
        model = OtrembaMLP().to("mps")
        x = torch.randn(4, 77, device="mps")
        out = model(x)
        assert out.device.type == "mps"
        assert out.shape == (4, 4)

    def test_gradient_flows(self):
        model = OtrembaMLP()
        x = torch.randn(8, 77)
        out = model(x)
        loss = out.sum()
        loss.backward()
        for p in model.parameters():
            assert p.grad is not None
