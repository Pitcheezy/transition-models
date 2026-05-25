"""Top-4 Precision 계산 (MIT Sloan 2025 평가 기준).

Top-4 precision: 각 샘플에서 상위 4개 예측 클래스 안에 정답이 포함될 비율.
전체(overall) + 클래스별(per-class) 모두 계산.

MIT Sloan 2025 보고값: Top-3 = 94.7%, Top-1 = 67.2%
본인 목표: Top-4 precision 비교 + per-class breakdown
"""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

CLASSES = ["Ball", "Strike", "Single", "Double", "Triple",
           "HomeRun", "FieldOut", "Strikeout", "Walk", "HitByPitch"]
N_CLASSES = len(CLASSES)

EVAL_FILES = {
    "LR":             ("outputs/evaluation_lr_10cls.npz",                  "probs",    "targets"),
    "LightGBM":       ("outputs/evaluation_lgb_10cls.npz",                 "probs",    "targets"),
    "MLP (77d)":      ("outputs/evaluation_mlp_10cls.npz",                 "probs",    "targets"),
    "MLP (135d)":     ("outputs/evaluation_mlp_135dim_10cls_focal.npz",    "probs",    "targets"),
    "RNN":            ("outputs/evaluation_rnn_10cls.npz",                 "probs",    "targets"),
    "Transformer":    ("outputs/evaluation_c_3season.npz",                 "pr_probs", "pr_targets"),
}


def topk_precision(probs: np.ndarray, targets: np.ndarray, k: int = 4) -> dict:
    """전체 + 클래스별 Top-k precision 계산."""
    top_k_preds = np.argsort(probs, axis=1)[:, -k:]  # (N, k), 오름차순 → 끝이 top
    # 정답이 top-k 안에 있는지
    in_topk = np.any(top_k_preds == targets[:, None], axis=1)  # (N,)
    overall = float(in_topk.mean())

    per_class: dict[str, float] = {}
    for c, cname in enumerate(CLASSES):
        mask = targets == c
        if mask.sum() == 0:
            per_class[cname] = float("nan")
        else:
            per_class[cname] = float(in_topk[mask].mean())

    return {"overall": overall, "per_class": per_class, "n_samples": int(len(targets))}


def random_baseline(targets: np.ndarray, k: int = 4, seed: int = 42) -> dict:
    """Uniform random 예측의 Top-k precision."""
    rng = np.random.default_rng(seed)
    probs = rng.dirichlet(np.ones(N_CLASSES), size=len(targets)).astype(np.float32)
    return topk_precision(probs, targets, k=k)


def main() -> None:
    results: dict[str, dict] = {}
    all_targets_point: np.ndarray | None = None

    for model_name, (rel_path, prob_key, tgt_key) in EVAL_FILES.items():
        fpath = REPO / rel_path
        if not fpath.exists():
            print(f"[SKIP] {fpath.name} not found")
            continue
        data = np.load(fpath)
        probs   = data[prob_key].astype(np.float64)
        targets = data[tgt_key].astype(np.int64)
        # normalise (수치 안정)
        row_sums = probs.sum(axis=1, keepdims=True)
        probs = np.where(row_sums > 0, probs / row_sums, 1.0 / N_CLASSES)

        res = topk_precision(probs, targets, k=4)
        results[model_name] = res
        print(f"[{model_name:20s}] overall Top-4={res['overall']:.4f}  n={res['n_samples']:,}")
        for cname in CLASSES:
            v = res["per_class"][cname]
            print(f"    {cname:<12s}: {v:.4f}" if not np.isnan(v) else f"    {cname:<12s}: -")

        # point 모델 targets 보존 (random baseline용)
        if model_name == "MLP (77d)":
            all_targets_point = targets

    # Random baseline (point 모델과 동일한 테스트셋 크기 기준)
    if all_targets_point is not None:
        rnd = random_baseline(all_targets_point, k=4)
        results["Random"] = rnd
        print(f"[{'Random':20s}] overall Top-4={rnd['overall']:.4f}  n={rnd['n_samples']:,} (theoretical~0.400)")

    # MIT Sloan 2025 공개 수치 추가 (비교용)
    results["MIT Sloan 2025 (reported)"] = {
        "overall": None,
        "top1": 0.672,
        "top3": 0.947,
        "top4": None,
        "note": "Top-4 미공개; Top-3=94.7% 공개값",
        "n_samples": None,
        "per_class": {},
    }

    out_path = REPO / "outputs" / "top4_precision_comparison.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
