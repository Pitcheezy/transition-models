"""Phase 9: 4-class 모델 종합 평가 — MDP/DQN 호환 그룹

각 모델의 evaluation_*_4cls.npz + evaluation_b_3season.npz 로드해 비교 표 출력.
all_models_comparison_4cls.json으로 저장.

모델별 파일이 없으면 graceful skip.
"""

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_DIR = PROJECT_ROOT / "outputs"

CLASS_NAMES = ["Ball", "Strike", "Foul", "InPlay"]


def load_npz_safe(path: Path) -> dict | None:
    if not path.exists():
        return None
    data = np.load(path, allow_pickle=True)
    return {k: data[k] for k in data.files}


def scalar(v) -> float:
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


def build_result(data: dict, top1_key: str, top3_key: str, input_desc: str, arch: str, params: str,
                 probs_key: str = "probs", targets_key: str = "targets") -> dict:
    r = {
        "top1": scalar(data[top1_key]),
        "top3": scalar(data[top3_key]),
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
    print("=" * 70)
    print("Phase 10: 4-class MDP/DQN Compatible Model Comparison")
    print("=" * 70)

    results: dict[str, dict] = {}

    # 1. Logistic Regression (4-class, 77d)
    data = load_npz_safe(OUTPUT_DIR / "evaluation_lr_4cls.npz")
    if data:
        results["LR (77d)"] = build_result(
            data, "top1", "top3", "Single pitch (77d)", "Linear", "~308"
        )
    else:
        print("[SKIP] evaluation_lr_4cls.npz not found")

    # 2. LightGBM (4-class, 77d)
    data = load_npz_safe(OUTPUT_DIR / "evaluation_lgb_4cls.npz")
    if data:
        results["LightGBM (77d)"] = build_result(
            data, "top1", "top3", "Single pitch (77d)", "Tree (boosting)", "~50K leaves"
        )
    else:
        print("[SKIP] evaluation_lgb_4cls.npz not found")

    # 3. MLP Model B (4-class, 77d) — 기존 3시즌 결과 재사용 (top_1/top_3 키)
    data = load_npz_safe(OUTPUT_DIR / "evaluation_b_3season.npz")
    if data:
        results["MLP Model B (77d)"] = build_result(
            data, "top_1", "top_3", "Single pitch (77d)", "MLP [128,128]", "~27K"
        )
    else:
        print("[SKIP] evaluation_b_3season.npz not found")

    # --- Phase 10: 135-dim iid models ---

    # 4. LR 135d (4-class)
    data = load_npz_safe(OUTPUT_DIR / "evaluation_lr_135d_4cls.npz")
    if data:
        results["LR (135d)"] = build_result(
            data, "top1", "top3", "Single pitch (135d)", "Linear", "~540"
        )
    else:
        print("[SKIP] evaluation_lr_135d_4cls.npz not found")

    # 5. LightGBM 135d (4-class)
    data = load_npz_safe(OUTPUT_DIR / "evaluation_lgb_135d_4cls.npz")
    if data:
        results["LightGBM (135d)"] = build_result(
            data, "top1", "top3", "Single pitch (135d)", "Tree (boosting)", "~50K leaves"
        )
    else:
        print("[SKIP] evaluation_lgb_135d_4cls.npz not found")

    if not results:
        print("\nNo evaluation files found. Run training scripts first.")
        return

    # --- Summary table ---
    print(f"\n{'Model':<22} {'Top-1':>8} {'Top-3':>8} {'CE':>8} {'Macro-F1':>10}  Input")
    print("-" * 78)
    for name, r in results.items():
        mf1_str = f"{r['macro_f1'] * 100:>8.1f}%" if "macro_f1" in r else "       ---"
        print(
            f"{name:<22} {r['top1'] * 100:>7.1f}%  {r['top3'] * 100:>7.1f}%  "
            f"{r['ce']:>7.4f}  {mf1_str}  {r['input']}"
        )
    print("-" * 78)

    # --- Per-class table ---
    print(f"\n{'Model':<22}", end="")
    for cls in CLASS_NAMES:
        print(f"  {cls[:7]:>7}", end="")
    print()
    print("-" * (22 + 9 * len(CLASS_NAMES)))
    for name, r in results.items():
        pca = r.get("per_class_accuracy", {})
        print(f"{name:<22}", end="")
        for cls in CLASS_NAMES:
            acc = pca.get(cls)
            print(f"  {acc * 100:>6.1f}%" if acc is not None else "     ---", end="")
        print()

    # --- Save JSON ---
    out_path = OUTPUT_DIR / "all_models_comparison_4cls.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Saved: {out_path}")


if __name__ == "__main__":
    main()
