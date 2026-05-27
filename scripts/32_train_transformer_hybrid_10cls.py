"""Phase 10.4 - Transformer hybrid (10-class, sequence 400×87 + static 58-dim)

CUDA 최적화:
  - torch.set_float32_matmul_precision("high") : TF32
  - torch.compile(model)                       : ~20-30% 속도
  - torch.cuda.amp.autocast + GradScaler       : FP16 Tensor Core
  - pin_memory=True, batch_size=64 (Transformer 12-layer AMP)

Usage:
  python scripts/32_train_transformer_hybrid_10cls.py --drop-missing true
  python scripts/32_train_transformer_hybrid_10cls.py --drop-missing false
"""

import argparse
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch._dynamo
import torch.nn.functional as F
from torch.amp import GradScaler, autocast
from torch.utils.data import DataLoader

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.dataset import PitchSequenceDatasetHybrid
from src.data.features import PitchResult10
from src.evaluation.metrics import cross_entropy, per_class_metrics, top_k_accuracy
from src.models.transformer import PitchTransformer
from src.utils.device import get_device

DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
CKPT_DIR = OUTPUT_DIR / "checkpoints"
CKPT_DIR.mkdir(parents=True, exist_ok=True)

CLASS_NAMES = [PitchResult10.NAMES[i] for i in range(PitchResult10.NUM_CLASSES)]

BATCH_SIZE = 64
EPOCHS = 30
PATIENCE = 7      # 큰 모델 수렴 느림 → 77d Transformer보다 1.4x 여유
LR = 1e-4
WEIGHT_DECAY = 1e-5


def load_sequence_dataset(split: str, drop_missing: bool) -> PitchSequenceDatasetHybrid:
    vecs = np.load(DATA_DIR / f"vectors_c_{split}.npy", mmap_mode="r")
    static = np.load(DATA_DIR / f"static_58_{split}.npy")
    static_valid = np.load(DATA_DIR / f"static_58_valid_{split}.npy")
    labels = np.load(DATA_DIR / f"labels_10_{split}.npy")
    hlocs = np.load(DATA_DIR / f"hit_locs_{split}.npy")
    with open(DATA_DIR / f"indices_{split}.pkl", "rb") as f:
        indices = pickle.load(f)
    return PitchSequenceDatasetHybrid(
        vecs, static, static_valid, labels, hlocs, indices,
        seq_length=400, drop_missing_static=drop_missing,
    )


def train_epoch(model, loader, optimizer, scaler, device, pr_w=0.7, hl_w=0.7):
    model.train()
    total_loss, total_pr_correct, total_valid = 0.0, 0, 0
    for batch in loader:
        x = batch["sequence"].to(device, non_blocking=True)
        s = batch["static"].to(device, non_blocking=True)
        target_pr = batch["pitch_result"].to(device, non_blocking=True)
        target_hl = batch["hit_location"].to(device, non_blocking=True)

        valid_pr = target_pr >= 0
        if not valid_pr.any():
            continue

        optimizer.zero_grad(set_to_none=True)
        with autocast(str(device.type)):
            output = model(x, s)               # (B, 24)
            pr_logits = output[:, :10]
            hl_logits = output[:, 10:19]

            loss_pr = F.cross_entropy(pr_logits[valid_pr], target_pr[valid_pr])
            valid_hl = target_hl >= 0
            loss_hl = (
                F.cross_entropy(hl_logits[valid_hl], target_hl[valid_hl])
                if valid_hl.any()
                else torch.tensor(0.0, device=device)
            )
            loss = pr_w * loss_pr + hl_w * loss_hl

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()

        total_loss += loss.item() * valid_pr.sum().item()
        total_pr_correct += (pr_logits.argmax(1)[valid_pr] == target_pr[valid_pr]).sum().item()
        total_valid += valid_pr.sum().item()

    return total_loss / max(total_valid, 1), total_pr_correct / max(total_valid, 1)


def eval_epoch(model, loader, device, pr_w=0.7, hl_w=0.7):
    model.eval()
    total_loss, total_pr_correct, total_valid = 0.0, 0, 0
    with torch.no_grad():
        for batch in loader:
            x = batch["sequence"].to(device, non_blocking=True)
            s = batch["static"].to(device, non_blocking=True)
            target_pr = batch["pitch_result"].to(device, non_blocking=True)
            target_hl = batch["hit_location"].to(device, non_blocking=True)
            valid_pr = target_pr >= 0
            if not valid_pr.any():
                continue
            with autocast(str(device.type)):
                output = model(x, s)
                pr_logits = output[:, :10]
                hl_logits = output[:, 10:19]
                loss_pr = F.cross_entropy(pr_logits[valid_pr], target_pr[valid_pr])
                valid_hl = target_hl >= 0
                loss_hl = (
                    F.cross_entropy(hl_logits[valid_hl], target_hl[valid_hl])
                    if valid_hl.any()
                    else torch.tensor(0.0, device=device)
                )
                loss = pr_w * loss_pr + hl_w * loss_hl
            total_loss += loss.item() * valid_pr.sum().item()
            total_pr_correct += (pr_logits.argmax(1)[valid_pr] == target_pr[valid_pr]).sum().item()
            total_valid += valid_pr.sum().item()
    return total_loss / max(total_valid, 1), total_pr_correct / max(total_valid, 1)


def collect_test_probs(model, loader, device):
    model.eval()
    all_probs, all_targets = [], []
    with torch.no_grad():
        for batch in loader:
            x = batch["sequence"].to(device, non_blocking=True)
            s = batch["static"].to(device, non_blocking=True)
            y = batch["pitch_result"]
            with autocast(str(device.type)):
                output = model(x, s)
            pr_probs = F.softmax(output[:, :10].float(), dim=-1).cpu().numpy()
            all_probs.append(pr_probs)
            all_targets.append(y.numpy())
    return np.concatenate(all_probs), np.concatenate(all_targets)


def main(drop_missing: bool):
    suffix = "drop" if drop_missing else "fullN"
    ckpt_name = f"transformer_hybrid_{suffix}_10cls"
    npz_name = f"evaluation_transformer_hybrid_{suffix}_10cls"

    print("=" * 60)
    print(f"Phase 10.4 - Transformer Hybrid (10-class, drop_missing={drop_missing})")

    device = get_device()
    use_cuda = device.type == "cuda"
    print(f"Device: {device}")

    if use_cuda:
        torch.set_float32_matmul_precision("high")
        print("TF32 matmul precision 활성화")

    print("\nLoading sequence data...")
    train_ds = load_sequence_dataset("train", drop_missing)
    val_ds = load_sequence_dataset("val", drop_missing)
    test_ds = load_sequence_dataset("test", drop_missing)
    print(f"  Train: {len(train_ds):,}  Val: {len(val_ds):,}  Test: {len(test_ds):,}")

    num_workers = 0
    pin = use_cuda
    train_loader = DataLoader(
        train_ds, batch_size=BATCH_SIZE, shuffle=True,
        num_workers=num_workers, pin_memory=pin,
    )
    val_loader = DataLoader(
        val_ds, batch_size=BATCH_SIZE, shuffle=False,
        num_workers=num_workers, pin_memory=pin,
    )
    test_loader = DataLoader(
        test_ds, batch_size=BATCH_SIZE, shuffle=False,
        num_workers=num_workers,
    )

    model = PitchTransformer(
        input_dim=87, d_model=256, nhead=8, num_layers=12,
        dim_feedforward=1024, dropout=0.1, max_seq_len=400,
        n_pitch_classes=10, n_hit_classes=9, n_continuous=5,
        static_dim=58,
    ).to(device)

    n_params = sum(p.numel() for p in model.parameters())
    print(f"\nModel: PitchTransformer(static_dim=58)  params={n_params:,}")

    if use_cuda:
        torch._dynamo.config.suppress_errors = True
        try:
            model = torch.compile(model, mode="reduce-overhead")
            print("torch.compile 적용 (reduce-overhead)")
        except Exception as e:
            print(f"[WARN] torch.compile 실패: {e} (일반 모드로 진행)")

    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    scaler = GradScaler("cuda", enabled=use_cuda)

    best_val_loss = float("inf")
    patience_counter = 0
    best_epoch = 0
    t_train_start = time.time()

    print(f"\nTraining (batch={BATCH_SIZE}, AMP={'ON' if use_cuda else 'OFF'}, patience={PATIENCE})...")
    print("-" * 60)

    for epoch in range(EPOCHS):
        t0 = time.time()
        train_loss, train_acc = train_epoch(model, train_loader, optimizer, scaler, device)
        val_loss, val_acc = eval_epoch(model, val_loader, device)
        elapsed = time.time() - t0

        print(
            f"Epoch {epoch + 1:2d}/{EPOCHS}  ({elapsed:.0f}s) "
            f"train_loss={train_loss:.4f} train_pr_acc={train_acc * 100:.1f}%  "
            f"val_loss={val_loss:.4f} val_pr_acc={val_acc * 100:.1f}%",
            flush=True,
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch + 1
            patience_counter = 0
            torch.save(
                {"epoch": epoch, "model_state": model.state_dict(), "val_loss": val_loss},
                CKPT_DIR / f"{ckpt_name}_best.pt",
            )
            print(f"  → Best saved (val_loss={best_val_loss:.4f})")
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                print(f"\nEarly stopping at epoch {epoch + 1}")
                break

    total_train_time = time.time() - t_train_start
    print(f"\nTraining complete. Best val_loss={best_val_loss:.4f} at epoch {best_epoch}")
    print(f"Total: {total_train_time / 3600:.1f}h")

    print("\nEvaluating best checkpoint...")
    ckpt = torch.load(CKPT_DIR / f"{ckpt_name}_best.pt", weights_only=False, map_location="cpu")
    best_model = PitchTransformer(
        input_dim=87, d_model=256, nhead=8, num_layers=12,
        dim_feedforward=1024, dropout=0.1, max_seq_len=400,
        n_pitch_classes=10, n_hit_classes=9, n_continuous=5,
        static_dim=58,
    )
    state = ckpt["model_state"]
    state = {k.replace("_orig_mod.", ""): v for k, v in state.items()}
    best_model.load_state_dict(state)
    best_model = best_model.to(device)

    proba, y_test = collect_test_probs(best_model, test_loader, device)
    valid = y_test >= 0
    proba, y_test = proba[valid], y_test[valid]

    top1 = top_k_accuracy(proba, y_test, k=1)
    top3 = top_k_accuracy(proba, y_test, k=3)
    ce = cross_entropy(proba, y_test)
    pcm = per_class_metrics(proba, y_test, PitchResult10.NUM_CLASSES)

    print(f"\n  Top-1: {top1 * 100:.1f}%  (baseline Transformer 77d: 67.2%)")
    print(f"  Top-3: {top3 * 100:.1f}%")
    print(f"  CE:    {ce:.4f}")
    print("\n  Per-class accuracy:")
    for name, acc in zip(CLASS_NAMES, pcm["per_class_accuracy"]):
        print(f"    {name:<12}: {acc * 100:.1f}%")

    np.savez(
        OUTPUT_DIR / f"{npz_name}.npz",
        probs=proba,
        targets=y_test,
        top1=np.float32(top1),
        top3=np.float32(top3),
        ce=np.float32(ce),
        per_class_accuracy=pcm["per_class_accuracy"],
        confusion_matrix=pcm["confusion_matrix"],
        best_val_loss=np.float32(best_val_loss),
        train_time=np.float32(total_train_time),
        model_name=np.array(f"Transformer_hybrid_{suffix}"),
        class_names=np.array(CLASS_NAMES),
    )
    print(f"\n[OK] {OUTPUT_DIR / f'{npz_name}.npz'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--drop-missing", type=lambda x: x.lower() in ("true", "1", "yes"),
        default=True,
    )
    args = parser.parse_args()
    main(drop_missing=args.drop_missing)
