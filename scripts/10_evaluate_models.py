"""Phase 6.1: Test set evaluation for Model B, Model C, and baselines."""

import pickle
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.dataset import PitchPointDataset, PitchSequenceDataset
from src.evaluation.evaluate import (
    baseline_empirical,
    baseline_majority,
    evaluate_model_b,
    evaluate_model_c,
)
from src.evaluation.metrics import (
    brier_score,
    cross_entropy,
    per_class_metrics,
    top_k_accuracy,
)
from src.models.otremba_mlp import OtrembaMLP
from src.models.transformer import PitchTransformer

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


def _print_header(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def evaluate_b():
    _print_header("Model B Test Evaluation (4-class)")

    test_data = torch.load("data/processed/model_b_test.pt", weights_only=False)
    test_ds = PitchPointDataset(test_data["vectors"], test_data["labels"])
    test_loader = DataLoader(test_ds, batch_size=256, num_workers=2, pin_memory=True)

    ckpt = torch.load(
        "outputs/checkpoints/model_b_full_v1_best.pt",
        weights_only=False,
        map_location="cpu",
    )
    model = OtrembaMLP()
    model.load_state_dict(ckpt["model_state"])

    print(f"Checkpoint epoch: {ckpt['epoch'] + 1}")
    print(f"Val metrics (saved): {ckpt['val_metrics']}")
    print(f"Test samples: {len(test_ds):,}")

    # --- Trained Model B ---
    print("\n[Model B (Trained)]")
    res = evaluate_model_b(model, test_loader)
    ce = cross_entropy(res["probs"], res["targets"])
    brier = brier_score(res["probs"], res["targets"], 4)
    top1 = top_k_accuracy(res["probs"], res["targets"], k=1)
    top2 = top_k_accuracy(res["probs"], res["targets"], k=2)
    top3 = top_k_accuracy(res["probs"], res["targets"], k=3)
    pcm = per_class_metrics(res["probs"], res["targets"], 4)

    print(f"  Cross-entropy : {ce:.4f}")
    print(f"  Brier score   : {brier:.4f}")
    print(f"  Top-1 accuracy: {top1:.4f} ({top1*100:.1f}%)")
    print(f"  Top-2 accuracy: {top2:.4f} ({top2*100:.1f}%)")
    print(f"  Top-3 accuracy: {top3:.4f} ({top3*100:.1f}%)")
    print("  Per-class accuracy:")
    for cls, acc in zip(["Ball", "Strike", "Foul", "InPlay"], pcm["per_class_accuracy"]):
        print(f"    {cls:<8}: {acc:.4f} ({acc*100:.1f}%)")

    # --- Baseline 1: Majority ---
    print("\n[Baseline: Majority class]")
    base_maj = baseline_majority(res["targets"], 4)
    bm_top1 = top_k_accuracy(base_maj, res["targets"], k=1)
    bm_ce = cross_entropy(base_maj, res["targets"])
    bm_brier = brier_score(base_maj, res["targets"], 4)
    print(f"  Top-1 accuracy: {bm_top1:.4f} ({bm_top1*100:.1f}%)")
    print(f"  Cross-entropy : {bm_ce:.4f}")
    print(f"  Brier score   : {bm_brier:.4f}")

    # --- Baseline 2: Empirical ---
    print("\n[Baseline: Empirical distribution]")
    base_emp = baseline_empirical(res["targets"], 4)
    be_top1 = top_k_accuracy(base_emp, res["targets"], k=1)
    be_ce = cross_entropy(base_emp, res["targets"])
    be_brier = brier_score(base_emp, res["targets"], 4)
    print(f"  Top-1 accuracy: {be_top1:.4f} ({be_top1*100:.1f}%)")
    print(f"  Cross-entropy : {be_ce:.4f}")
    print(f"  Brier score   : {be_brier:.4f}")

    np.savez(
        OUTPUT_DIR / "evaluation_b.npz",
        probs=res["probs"],
        targets=res["targets"],
        ce=ce,
        brier=brier,
        top_1=top1,
        top_2=top2,
        top_3=top3,
        confusion_matrix=pcm["confusion_matrix"],
        per_class_accuracy=pcm["per_class_accuracy"],
        baseline_majority_probs=base_maj,
        baseline_majority_top_1=bm_top1,
        baseline_majority_ce=bm_ce,
        baseline_majority_brier=bm_brier,
        baseline_empirical_probs=base_emp,
        baseline_empirical_top_1=be_top1,
        baseline_empirical_ce=be_ce,
        baseline_empirical_brier=be_brier,
        epoch=ckpt["epoch"],
    )
    print(f"\n→ Saved: {OUTPUT_DIR / 'evaluation_b.npz'}")


def evaluate_c():
    ckpt_path = OUTPUT_DIR / "checkpoints" / "model_c_full_v2_best.pt"
    if not ckpt_path.exists():
        print(f"\n[SKIP] {ckpt_path} not found. Run after Model C training completes.")
        return

    _print_header("Model C Test Evaluation (10-class PR + 9-class HL)")

    vecs = np.load("data/processed/vectors_c_test.npy")
    labels = np.load("data/processed/labels_10_test.npy")
    hlocs = np.load("data/processed/hit_locs_test.npy")
    with open("data/processed/indices_test.pkl", "rb") as f:
        indices = pickle.load(f)

    test_ds = PitchSequenceDataset(vecs, labels, hlocs, indices, 400)
    test_loader = DataLoader(test_ds, batch_size=32, num_workers=2, pin_memory=True)

    ckpt = torch.load(ckpt_path, weights_only=False, map_location="cpu")
    model = PitchTransformer()
    model.load_state_dict(ckpt["model_state"])

    print(f"Checkpoint epoch: {ckpt['epoch'] + 1}")
    print(f"Val metrics (saved): {ckpt['val_metrics']}")
    print(f"Test sequences: {len(test_ds):,}")

    res = evaluate_model_c(model, test_loader)

    # --- Pitch Result (10-class) ---
    print("\n[Pitch Result] (10-class)")
    ce_pr = cross_entropy(res["pr_probs"], res["pr_targets"])
    brier_pr = brier_score(res["pr_probs"], res["pr_targets"], 10)
    top1_pr = top_k_accuracy(res["pr_probs"], res["pr_targets"], k=1)
    top3_pr = top_k_accuracy(res["pr_probs"], res["pr_targets"], k=3)
    pcm_pr = per_class_metrics(res["pr_probs"], res["pr_targets"], 10)

    print(f"  Cross-entropy : {ce_pr:.4f}")
    print(f"  Brier score   : {brier_pr:.4f}")
    print(f"  Top-1 accuracy: {top1_pr:.4f} ({top1_pr*100:.1f}%)")
    print(f"  Top-3 accuracy: {top3_pr:.4f} ({top3_pr*100:.1f}%)")
    pr_classes = ["Ball", "Strike", "Single", "Double", "Triple",
                  "HomeRun", "FieldOut", "Strikeout", "Walk", "HitByPitch"]
    print("  Per-class accuracy:")
    for cls, acc in zip(pr_classes, pcm_pr["per_class_accuracy"]):
        print(f"    {cls:<12}: {acc:.4f} ({acc*100:.1f}%)")

    # --- Hit Location (9-class, InPlay 한정) ---
    print("\n[Hit Location] (9-class, InPlay 한정)")
    n_valid_hl = int((res["hl_targets"] >= 0).sum())
    print(f"  Valid samples: {n_valid_hl:,} / {len(res['hl_targets']):,}")
    hl_results = {}
    if n_valid_hl > 0:
        ce_hl = cross_entropy(res["hl_probs"], res["hl_targets"])
        brier_hl = brier_score(res["hl_probs"], res["hl_targets"], 9)
        top1_hl = top_k_accuracy(res["hl_probs"], res["hl_targets"], k=1)
        top3_hl = top_k_accuracy(res["hl_probs"], res["hl_targets"], k=3)
        print(f"  Cross-entropy : {ce_hl:.4f}")
        print(f"  Brier score   : {brier_hl:.4f}")
        print(f"  Top-1 accuracy: {top1_hl:.4f} ({top1_hl*100:.1f}%)")
        print(f"  Top-3 accuracy: {top3_hl:.4f} ({top3_hl*100:.1f}%)")
        hl_results = dict(ce_hl=ce_hl, brier_hl=brier_hl, top_1_hl=top1_hl, top_3_hl=top3_hl)

    # --- Baseline (10-class) ---
    print("\n[Baseline: Empirical (10-class)]")
    base_emp_c = baseline_empirical(res["pr_targets"], 10)
    bec_top1 = top_k_accuracy(base_emp_c, res["pr_targets"], k=1)
    bec_ce = cross_entropy(base_emp_c, res["pr_targets"])
    bec_brier = brier_score(base_emp_c, res["pr_targets"], 10)
    print(f"  Top-1 accuracy: {bec_top1:.4f} ({bec_top1*100:.1f}%)")
    print(f"  Cross-entropy : {bec_ce:.4f}")
    print(f"  Brier score   : {bec_brier:.4f}")

    save_kwargs = dict(
        pr_probs=res["pr_probs"],
        pr_targets=res["pr_targets"],
        ce_pr=ce_pr,
        brier_pr=brier_pr,
        top_1_pr=top1_pr,
        top_3_pr=top3_pr,
        confusion_matrix_pr=pcm_pr["confusion_matrix"],
        per_class_accuracy_pr=pcm_pr["per_class_accuracy"],
        hl_probs=res["hl_probs"],
        hl_targets=res["hl_targets"],
        baseline_empirical_top_1=bec_top1,
        baseline_empirical_ce=bec_ce,
        baseline_empirical_brier=bec_brier,
        epoch=ckpt["epoch"],
    )
    save_kwargs.update(hl_results)
    np.savez(OUTPUT_DIR / "evaluation_c.npz", **save_kwargs)
    print(f"\n→ Saved: {OUTPUT_DIR / 'evaluation_c.npz'}")


def main():
    _print_header("Phase 6.1: Test Set Evaluation")
    evaluate_b()
    evaluate_c()
    _print_header("Done!")


if __name__ == "__main__":
    main()
