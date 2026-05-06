"""Common interface for all transition probability models."""

from abc import ABC, abstractmethod

import torch
import torch.nn as nn


class TransitionModel(ABC, nn.Module):
    """Base class for transition probability prediction models.

    All models (OtrembaMLP, MIT Transformer, SmartPitch wrapper) inherit
    from this class to ensure a consistent interface for training and evaluation.
    """

    @abstractmethod
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass returning raw logits.

        Args:
            x: Input tensor (shape depends on subclass).

        Returns:
            Logits tensor of shape (batch, num_classes).
        """
        ...

    @abstractmethod
    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Return class probabilities (softmax applied).

        Args:
            x: Input tensor.

        Returns:
            Probability tensor of shape (batch, num_classes), rows sum to 1.
        """
        ...

    @abstractmethod
    def num_classes(self) -> int:
        """Return the number of output classes."""
        ...

    @abstractmethod
    def model_name(self) -> str:
        """Return a human-readable model identifier."""
        ...
