"""Sanity check: verify OtrembaMLP can learn on a small subset."""

import sys
from pathlib import Path

import torch
import torch.nn as nn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.otremba_mlp import OtrembaMLP
from src.utils.device import get_device


def main():
    # === 데이터 로드 (1000 샘플) ===
    data = torch.load("data/processed/model_b_train.pt", weights_only=False)
    vectors = torch.from_numpy(data["vectors"][:1000]).float()
    labels = torch.from_numpy(data["labels"][:1000]).long()

    print(f"Data: {vectors.shape}, Labels: {labels.shape}")
    print(f"Label distribution: {dict(zip(*torch.unique(labels, return_counts=True)))}")

    # === 디바이스 설정 ===
    device = get_device()
    print(f"Device: {device}")

    # === 모델 + 옵티마이저 ===
    model = OtrembaMLP(input_dim=77, hidden_dim=128, n_classes=4).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    total_params = sum(p.numel() for p in model.parameters())
    print(f"Parameters: {total_params:,}")

    vectors = vectors.to(device)
    labels = labels.to(device)

    # === 학습 (10 epochs) ===
    print("\nEpoch  Loss     Accuracy")
    print("-" * 30)
    losses = []
    for epoch in range(10):
        model.train()
        optimizer.zero_grad()
        logits = model(vectors)
        loss = criterion(logits, labels)
        loss.backward()
        optimizer.step()

        # 정확도
        with torch.no_grad():
            preds = logits.argmax(dim=-1)
            acc = (preds == labels).float().mean().item()
        losses.append(loss.item())
        print(f"  {epoch+1:2d}    {loss.item():.4f}   {acc:.1%}")

    # === 검증 ===
    print()
    if losses[-1] < losses[0]:
        print("Loss 감소 확인 — sanity check PASSED")
    else:
        print("WARNING: Loss가 감소하지 않음!")

    # Softmax 합 검증
    model.eval()
    with torch.no_grad():
        proba = model.predict_proba(vectors[:5])
        sums = proba.sum(dim=-1)
        print(f"Softmax sums (should be 1.0): {sums.cpu().tolist()}")
        print(f"Sample probabilities:\n{proba.cpu()}")


if __name__ == "__main__":
    main()
