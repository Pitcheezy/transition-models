"""Model B: Otremba 2022 SmartPitch 4-class MLP.

Architecture (from paper):
    Input:  77-dim feature vector
    Hidden: 2 fully-connected layers, 128 units each, ReLU activation
    Output: 4-class softmax (Ball / Strike / Foul / InPlay)

Reference: Otremba (2022), "SmartPitch: Leveraging Statcast Data for
           Pitch Outcome Prediction with Machine Learning"
"""

import torch
import torch.nn as nn

from src.models.base import TransitionModel


class OtrembaMLP(TransitionModel):
    """Otremba 2022 two-layer MLP for 4-class pitch outcome prediction."""

    def __init__(
        self,
        input_dim: int = 77,
        hidden_dim: int = 128,
        n_classes: int = 4,
        dropout: float = 0.0,
    ):
        super().__init__()
        self.input_dim = input_dim
        self._n_classes = n_classes
        self._name = "OtrembaMLP"

        layers = [
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
        ]
        if dropout > 0:
            layers.append(nn.Dropout(dropout))
        layers.extend([
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        ])
        if dropout > 0:
            layers.append(nn.Dropout(dropout))
        layers.append(nn.Linear(hidden_dim, n_classes))

        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Return raw logits of shape (batch, 4)."""
        return self.net(x)

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Return softmax probabilities of shape (batch, 4)."""
        return torch.softmax(self.forward(x), dim=-1)

    def num_classes(self) -> int:
        return self._n_classes

    def model_name(self) -> str:
        return self._name
