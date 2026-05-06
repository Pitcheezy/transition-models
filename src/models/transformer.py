"""Model C: MIT Sloan 2025 Transformer for pitch outcome prediction.

Architecture:
    Input:  (batch, 400, 87) pitch sequence with sub-token masking
    Embed:  Linear 87 → 256 + sinusoidal positional encoding
    Encoder: 12-layer Transformer Encoder (d_model=256, 8 heads, ff=1024)
    Head:   Last-token + last-pitch residual → FC → 24-dim output

Output decomposition (24-dim):
    [0:10]  pitch_result logits (10-class)
    [10:19] hit_location logits (9-class)
    [19:24] continuous regression (5-dim)

Multi-task loss: 0.7 × (CE_pitch_result + CE_hit_location) + 0.3 × MSE_continuous

Reference: MIT Sloan Sports Analytics Conference 2025
"""

import math

import torch
import torch.nn as nn
import torch.nn.functional as F

from src.models.base import TransitionModel


class SinusoidalPositionalEncoding(nn.Module):
    """Fixed sinusoidal positional encoding (Vaswani et al. 2017)."""

    def __init__(self, d_model: int = 256, max_len: int = 400):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len).unsqueeze(1).float()
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * -(math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))  # (1, max_len, d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Add positional encoding to input embeddings.

        Args:
            x: (batch, seq_len, d_model)

        Returns:
            (batch, seq_len, d_model) with positional encoding added.
        """
        return x + self.pe[:, : x.size(1), :]


class PitchTransformer(TransitionModel):
    """MIT Sloan 2025 Transformer for multi-task pitch outcome prediction."""

    def __init__(
        self,
        input_dim: int = 87,
        d_model: int = 256,
        nhead: int = 8,
        num_layers: int = 12,
        dim_feedforward: int = 1024,
        dropout: float = 0.1,
        max_seq_len: int = 400,
        n_pitch_classes: int = 10,
        n_hit_classes: int = 9,
        n_continuous: int = 5,
    ):
        super().__init__()

        self.input_dim = input_dim
        self.d_model = d_model
        self.n_pitch_classes = n_pitch_classes
        self.n_hit_classes = n_hit_classes
        self.n_continuous = n_continuous
        self._output_dim = n_pitch_classes + n_hit_classes + n_continuous  # 24

        # 1. Linear embedding: 87 → d_model
        self.embedding = nn.Linear(input_dim, d_model)

        # 2. Positional encoding
        self.pos_encoding = SinusoidalPositionalEncoding(d_model, max_seq_len)

        # 3. Transformer Encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            activation="relu",
            batch_first=True,
            norm_first=False,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # 4. Last-pitch residual projection: 87 → d_model
        self.last_pitch_proj = nn.Linear(input_dim, d_model)

        # 5. FC head: concat(d_model, d_model) → d_model → output_dim
        self.fc1 = nn.Linear(d_model * 2, d_model)
        self.fc2 = nn.Linear(d_model, self._output_dim)
        self.head_dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass returning raw 24-dim output.

        Args:
            x: (batch, seq_len, 87) pitch sequence.

        Returns:
            (batch, 24) — [0:10] pr logits, [10:19] hl logits, [19:24] continuous.
        """
        # Embed + positional encoding
        embedded = self.pos_encoding(self.embedding(x))  # (B, S, d_model)

        # Transformer encoder
        encoded = self.transformer(embedded)  # (B, S, d_model)

        # Last token from encoder
        last_encoded = encoded[:, -1, :]  # (B, d_model)

        # Last-pitch residual connection
        last_raw = x[:, -1, :]  # (B, 87)
        last_proj = self.last_pitch_proj(last_raw)  # (B, d_model)

        # Concat + FC head
        combined = torch.cat([last_encoded, last_proj], dim=-1)  # (B, 2*d_model)
        h = F.relu(self.fc1(combined))
        h = self.head_dropout(h)
        return self.fc2(h)  # (B, 24)

    def predict_proba(self, x: torch.Tensor) -> dict:
        """Return per-task probabilities.

        Args:
            x: (batch, seq_len, 87)

        Returns:
            Dict with keys "pitch_result" (B, 10), "hit_location" (B, 9),
            "continuous" (B, 5).
        """
        logits = self.forward(x)
        pr_end = self.n_pitch_classes
        hl_end = pr_end + self.n_hit_classes
        return {
            "pitch_result": F.softmax(logits[:, :pr_end], dim=-1),
            "hit_location": F.softmax(logits[:, pr_end:hl_end], dim=-1),
            "continuous": logits[:, hl_end:],
        }

    def num_classes(self) -> int:
        return self.n_pitch_classes

    def model_name(self) -> str:
        return "PitchTransformer"
