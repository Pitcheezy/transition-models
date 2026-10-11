"""Lightweight batched PyTorch probability inference shared by training and deployment."""

import numpy as np
import torch


def predict_mlp(model, features, device, batch_size=8192):
    """Predict in bounded batches without retaining the autograd graph."""
    model.eval()
    with torch.inference_mode():
        return np.concatenate(
            [
                torch.softmax(
                    model(torch.as_tensor(features[i : i + batch_size], device=device)), dim=1
                )
                .cpu()
                .numpy()
                for i in range(0, len(features), batch_size)
            ]
        )
