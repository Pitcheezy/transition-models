"""Phase 9: 5개 모델 종합 평가 — 10-class 통일 비교

각 모델의 evaluation_*_10cls.npz 파일을 로드해 비교 표를 출력하고
all_models_comparison_10cls.json으로 저장한다.

모델별 npz가 없으면 graceful skip.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_DIR = PROJECT_ROOT / "outputs"

CLASS_NAMES = ["Ball", "Strike", "Single", "Double", "Triple",
               "HomeRun", "FieldOut", "Strikeout", "Walk", "HitByPitch"]


def load_npz_safe(path: Path) -> dict | None:
    if not path.exists():
        return None
    data = np.load(path, allow_pickle=True)
    return {k: data[k] for k in data.files}


def scalar(v) -> float:
    """Safely extract scalar from numpy scalar or 0-d array."""
    if hasattr(v, "item"):
        return float(v.item())
    return float(v)


def macro_f1_from_npz(data: dict, probs_key: str = "probs", targets_key: str = "targets") -> float | None:
    probs = data.get(probs_key)
    targets = data.get(targets_key)
    if probs is None or targets is None:
        return None
    y_pred = np.argmax(np.array(probs), axis=1)
    y_true = np.array(targets).flatten().astype(int)
    return float(f1_score(y_true, y_pred, average="macro",
                          labels=list(range(len(CLASS_NAMES))), zero_division=0))


def build_result(data: dict, input_desc: str, arch: str, params: str,
                 probs_key: str = "probs", targets_key: str = "targets") -> dict:
    r = {
        "top1": scalar(data["top1"]),
        "top3": scalar(data["top3"]),
        "ce": scalar(data["ce"]),
        "input": input_desc,
        "arch": arch,
        "params": params,
    }
    mf1 = macro_f1_from_npz(data, probs_key, targets_key)
    if mf1 is not None:
        r["macro_f1"] = mf1
    if "train_time" in data:
        r["train_time_min"] = scalar(data["train_time"]) / 60
    per = data.get("per_class_accuracy")
    if per is not None:
        per_arr = np.array(per).flatten()
        r["per_class_accuracy"] = {CLASS_NAMES[i]: float(per_arr[i]) for i in range(len(per_arr))}
    return r


def main():
    parser = argparse.ArgumentParser(description="Historical, identity-unverified comparison only")
    parser.add_argument("--allow-legacy", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.allow_legacy:
        parser.error("77d historical labels were misaligned. Use scripts/49_compare_aligned_runs.py. "
                     "Historical inspection requires --allow-legacy and a fresh --output.")
    if args.output.exists():
        raise FileExistsError(args.output)
    print("WARNING: Historical results only; 77d targets are misaligned and cohorts lack pitch IDs.")
    print("=" * 70)
    print("Phase 10: Multi-Model Comparison (10-class unified)")
    print("=" * 70)

    results: dict[str, dict] = {}

    # 1. Logistic Regression
    data = load_npz_safe(OUTPUT_DIR / "evaluation_lr_10cls.npz")
    if data:
        results["Logistic Regression"] = build_result(
            data, "Single pitch (77d)", "Linear", "~770"
        )
    else:
        print("[SKIP] evaluation_lr_10cls.npz not found")

    # 2. LightGBM
    data = load_npz_safe(OUTPUT_DIR / "evaluation_lgb_10cls.npz")
    if data:
        results["LightGBM"] = build_result(
            data, "Single pitch (77d)", "Tree (boosting)", "~50K leaves"
        )
    else:
        print("[SKIP] evaluation_lgb_10cls.npz not found")

    # 3. MLP 10-class
    data = load_npz_safe(OUTPUT_DIR / "evaluation_mlp_10cls.npz")
    if data:
        results["MLP (10-class)"] = build_result(
            data, "Single pitch (77d)", "MLP [128,128]", "~27K"
        )
    else:
        print("[SKIP] evaluation_mlp_10cls.npz not found")

    # 4. RNN
    data = load_npz_safe(OUTPUT_DIR / "evaluation_rnn_10cls.npz")
    if data:
        results["RNN (LSTM)"] = build_result(
            data, "Sequence 400×87", "LSTM 2-layer", "~590K"
        )
    else:
        print("[SKIP] evaluation_rnn_10cls.npz not found")

    # 5. Transformer — 기존 3시즌 결과 사용
    data = load_npz_safe(OUTPUT_DIR / "evaluation_c_3season.npz")
    if data:
        # evaluation_c_3season.npz has different keys (top_1_pr, top_3_pr, ce_pr)
        transformer_result = {
            "top1": scalar(data["top_1_pr"]),
            "top3": scalar(data["top_3_pr"]),
            "ce": scalar(data["ce_pr"]),
            "input": "Sequence 400x87",
            "arch": "Transformer (12-layer)",
            "params": "9.7M",
        }
        mf1 = macro_f1_from_npz(data, probs_key="pr_probs", targets_key="pr_targets")
        if mf1 is not None:
            transformer_result["macro_f1"] = mf1
        per = data.get("per_class_accuracy_pr")
        if per is not None:
            per_arr = np.array(per).flatten()
            transformer_result["per_class_accuracy"] = {
                CLASS_NAMES[i]: float(per_arr[i]) for i in range(len(per_arr))
            }
        results["Transformer (Model C)"] = transformer_result
    else:
        print("[SKIP] evaluation_c_3season.npz not found")

    # --- Phase 10: 135-dim iid models ---

    # 6. LR 135d (10-class)
    data = load_npz_safe(OUTPUT_DIR / "evaluation_lr_135d_10cls.npz")
    if data:
        results["LR 135d"] = build_result(
            data, "Single pitch (135d)", "Linear", "~1350"
        )
    else:
        print("[SKIP] evaluation_lr_135d_10cls.npz not found")

    # 7. LightGBM 135d (10-class)
    data = load_npz_safe(OUTPUT_DIR / "evaluation_lgb_135d_10cls.npz")
    if data:
        results["LightGBM 135d"] = build_result(
            data, "Single pitch (135d)", "Tree (boosting)", "~50K leaves"
        )
    else:
        print("[SKIP] evaluation_lgb_135d_10cls.npz not found")

    # 8. MLP 135d focal (10-class)
    data = load_npz_safe(OUTPUT_DIR / "evaluation_mlp_135dim_10cls_focal.npz")
    if data:
        results["MLP 135d (focal)"] = build_result(
            data, "Single pitch (135d)", "MLP [128,128]", "~27K"
        )
    else:
        print("[SKIP] evaluation_mlp_135dim_10cls_focal.npz not found")

    # 9. RNN hybrid (drop=True)
    data = load_npz_safe(OUTPUT_DIR / "evaluation_rnn_hybrid_drop_10cls.npz")
    if data:
        results["RNN Hybrid (drop)"] = build_result(
            data, "Seq 400x87 + static 58d", "LSTM 2-layer + static", "~590K"
        )
    else:
        print("[SKIP] evaluation_rnn_hybrid_drop_10cls.npz not found")

    # 10. RNN hybrid (drop=False, fair compare)
    data = load_npz_safe(OUTPUT_DIR / "evaluation_rnn_hybrid_fullN_10cls.npz")
    if data:
        results["RNN Hybrid (fullN)"] = build_result(
            data, "Seq 400x87 + static 58d", "LSTM 2-layer + static", "~590K"
        )
    else:
        print("[SKIP] evaluation_rnn_hybrid_fullN_10cls.npz not found")

    # 11. Transformer hybrid (drop=True)
    data = load_npz_safe(OUTPUT_DIR / "evaluation_transformer_hybrid_drop_10cls.npz")
    if data:
        results["Transformer Hybrid (drop)"] = build_result(
            data, "Seq 400x87 + static 58d", "Transformer 12-layer + static", "9.7M+"
        )
    else:
        print("[SKIP] evaluation_transformer_hybrid_drop_10cls.npz not found")

    # 12. Transformer hybrid (drop=False, fair compare)
    data = load_npz_safe(OUTPUT_DIR / "evaluation_transformer_hybrid_fullN_10cls.npz")
    if data:
        results["Transformer Hybrid (fullN)"] = build_result(
            data, "Seq 400x87 + static 58d", "Transformer 12-layer + static", "9.7M+"
        )
    else:
        print("[SKIP] evaluation_transformer_hybrid_fullN_10cls.npz not found")

    if not results:
        print("\nNo evaluation files found. Run training scripts first.")
        return

    # --- Summary table ---
    print(f"\n{'Model':<25} {'Top-1':>8} {'Top-3':>8} {'CE':>8} {'Macro-F1':>10}  Input")
    print("-" * 85)
    for name, r in results.items():
        mf1_str = f"{r['macro_f1'] * 100:>8.1f}%" if "macro_f1" in r else "       ---"
        print(
            f"{name:<25} {r['top1'] * 100:>7.1f}%  {r['top3'] * 100:>7.1f}%  "
            f"{r['ce']:>7.4f}  {mf1_str}  {r['input']}"
        )
    print("-" * 85)

    # --- Per-class table ---
    print(f"\n{'Model':<25}", end="")
    for cls in CLASS_NAMES:
        print(f"  {cls[:7]:>7}", end="")
    print()
    print("-" * (25 + 9 * len(CLASS_NAMES)))
    for name, r in results.items():
        pca = r.get("per_class_accuracy", {})
        print(f"{name:<25}", end="")
        for cls in CLASS_NAMES:
            acc = pca.get(cls)
            print(f"  {acc * 100:>6.1f}%" if acc is not None else "     ---", end="")
        print()

    # --- Save JSON ---
    out_path = args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Saved: {out_path}")


if __name__ == "__main__":
    main()
