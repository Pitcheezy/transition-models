"""RNN hybrid model: LSTM(87-dim sequence) + static 58-dim context.

Architecture:
    LSTM(87, hidden=256, layers=2) → last hidden (256,)
    concat([last_hidden, static_58]) → (314,)
    Linear(314, 128) → ReLU → Dropout → Linear(128, 10)
"""

import torch
import torch.nn as nn


class PitchRNNHybrid(nn.Module):
    """2-layer LSTM + static 58-dim context injected at head.

    Input:
        x_seq:    (batch, 400, 87) pitch sequence
        x_static: (batch, 58)  static context (arsenal + count + umap)
    Output:
        (batch, num_classes) logits
    """

    def __init__(
        self,
        seq_dim: int = 87,
        static_dim: int = 58,
        hidden_dim: int = 256,
        num_layers: int = 2,
        num_classes: int = 10,
        dropout: float = 0.2,
        head_hidden: int = 128,
    ):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=seq_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout,
        )
        combined_dim = hidden_dim + static_dim  # 256 + 58 = 314
        self.head = nn.Sequential(
            nn.Linear(combined_dim, head_hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(head_hidden, num_classes),
        )

    def forward(self, x_seq: torch.Tensor, x_static: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x_seq)              # (B, 400, 256)
        last = out[:, -1, :]                   # (B, 256)
        combined = torch.cat([last, x_static], dim=-1)  # (B, 314)
        return self.head(combined)             # (B, num_classes)
