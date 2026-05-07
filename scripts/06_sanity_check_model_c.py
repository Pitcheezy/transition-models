"""Sanity check: verify PitchTransformer can learn on a small subset."""

import pickle
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.dataset import PitchSequenceDataset
from src.models.transformer import PitchTransformer
from src.utils.device import get_device


def main():
    device = get_device()
    print(f"Device: {device}")

    # === 작은 subset 로드 ===
    vecs = np.load("data/processed/vectors_c_train.npy")
    labels = np.load("data/processed/labels_10_train.npy")
    hlocs = np.load("data/processed/hit_locs_train.npy")
    with open("data/processed/indices_train.pkl", "rb") as f:
        indices = pickle.load(f)

    # 첫 64개 시퀀스만
    indices_small = indices[:64]
    ds = PitchSequenceDataset(vecs, labels, hlocs, indices_small, seq_length=400)
    loader = DataLoader(ds, batch_size=8, shuffle=True, num_workers=0)
    print(f"Dataset: {len(ds)} sequences, batch_size=8")

    # === 모델 ===
    model = PitchTransformer().to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"Parameters: {n_params:,}")

    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)

    # === 학습 (5 epochs) ===
    print("\nEpoch  Loss     PR_Acc")
    print("-" * 30)
    t0 = time.time()

    for epoch in range(5):
        epoch_loss = 0.0
        correct = 0
        total = 0

        for batch in loader:
            seq = batch["sequence"].to(device)
            target_pr = batch["pitch_result"].to(device)
            target_hl = batch["hit_location"].to(device)

            optimizer.zero_grad()
            output = model(seq)

            pr_logits = output[:, :10]
            hl_logits = output[:, 10:19]

            # Pitch result loss
            valid_pr = target_pr >= 0
            loss_pr = (
                F.cross_entropy(pr_logits[valid_pr], target_pr[valid_pr])
                if valid_pr.any()
                else torch.tensor(0.0, device=device)
            )

            # Hit location loss
            valid_hl = target_hl >= 0
            loss_hl = (
                F.cross_entropy(hl_logits[valid_hl], target_hl[valid_hl])
                if valid_hl.any()
                else torch.tensor(0.0, device=device)
            )

            loss = 0.7 * (loss_pr + loss_hl)
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()
            correct += (pr_logits.argmax(-1)[valid_pr] == target_pr[valid_pr]).sum().item()
            total += valid_pr.sum().item()

        acc = correct / total if total > 0 else 0.0
        print(f"  {epoch + 1:2d}    {epoch_loss:.4f}   {acc:.1%}")

    elapsed = time.time() - t0
    print(f"\nTotal: {elapsed:.1f}s, Per epoch: {elapsed / 5:.1f}s")

    # === Predict proba 검증 ===
    model.eval()
    with torch.no_grad():
        batch = next(iter(loader))
        proba = model.predict_proba(batch["sequence"].to(device))
        pr_sums = proba["pitch_result"].sum(-1).cpu()
        print(f"\nSoftmax sums (pitch_result): {pr_sums[:4].tolist()}")
        print(f"Sample probs: {proba['pitch_result'][0].cpu().tolist()}")

    print("\nSanity check complete!")


if __name__ == "__main__":
    main()
