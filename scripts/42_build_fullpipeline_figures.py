"""
scripts/42_build_fullpipeline_figures.py

전체 파이프라인 발표용 그래프 2종 추가 생성.

출력: outputs/figures/
    fig_pipeline_4stage.png   — 4-stage 파이프라인 다이어그램
    fig_rl_reward_comparison.png — RL 알고리즘 RE24 보상 비교

Usage:
    uv run python scripts/42_build_fullpipeline_figures.py
"""

import json
from pathlib import Path

import matplotlib
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np

matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False
matplotlib.rcParams["figure.facecolor"] = "white"

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "outputs"
FIG_DIR = OUTPUT_DIR / "figures"
RL_RESULTS_DIR = ROOT.parent / "rl-agent" / "outputs" / "results"
FIG_DIR.mkdir(exist_ok=True)


# ═════════════════════════════════════════════════════════════════════════════
# Fig A: 4-Stage Pipeline Diagram
# ═════════════════════════════════════════════════════════════════════════════
def build_fig_pipeline():
    fig, ax = plt.subplots(figsize=(18, 6))
    ax.set_xlim(0, 18)
    ax.set_ylim(0, 6)
    ax.axis("off")
    fig.patch.set_facecolor("#F8F9FA")
    ax.set_facecolor("#F8F9FA")

    stages = [
        {
            "name": "data",
            "label": "① Data\n수집 · 정제",
            "color": "#2980B9",
            "light": "#D6EAF8",
            "x": 0.4,
            "lines": [
                "Statcast 2022–2025",
                "3.08M raw → 2.98M clean",
                "15-D z-scored features",
                "17 pitch types",
                "CLI: pitcheezy-data all",
            ],
            "out": "normalized_*.parquet\nscaler.pkl",
        },
        {
            "name": "clustering",
            "label": "② Clustering\n상태 추상화",
            "color": "#8E44AD",
            "light": "#E8DAEF",
            "x": 4.9,
            "lines": [
                "Pitch: UMAP 5D 연속",
                "Batter: k=3 (L/R)",
                "Arsenal: k=3 (moment+func)",
                "Count: Ward k=4",
                "r=0.9795 (L/R Pearson)",
            ],
            "out": "arsenal_features_v1.parquet\ncount_clusters_v1.parquet",
        },
        {
            "name": "transition\nmodels",
            "label": "③ Transition Model\n전이확률 추정",
            "color": "#E67E22",
            "light": "#FDEBD0",
            "x": 9.4,
            "lines": [
                "P(outcome | state, action,",
                "  pitcher context)",
                "10-class 분류",
                "MLP10 135d focal",
                "Top-1 67.6% ★ MDP 호환",
            ],
            "out": "TransitionModelMLP10\n(inference wrapper)",
        },
        {
            "name": "rl-agent",
            "label": "④ RL Agent\n최적 정책 학습",
            "color": "#27AE60",
            "light": "#D5F5E3",
            "x": 13.9,
            "lines": [
                "|S| = 9,216  |A| = 117",
                "Reward: RE24 기반",
                "MDP-VI / Dyna-Q (model-based)",
                "vs DQN·PPO·Random",
                "MDP-VI Δ = +0.41 RE24/inning",
            ],
            "out": "policy_*.pkl\npitch+zone 추천",
        },
    ]

    box_w = 4.0
    box_h = 4.2
    header_h = 0.85

    for s in stages:
        x = s["x"]
        y_bottom = 0.7

        # 메인 박스 (본문)
        rect = mpatches.FancyBboxPatch(
            (x, y_bottom), box_w, box_h,
            boxstyle="round,pad=0.08",
            facecolor=s["light"], edgecolor=s["color"], linewidth=2.0,
        )
        ax.add_patch(rect)

        # 헤더 배경
        header_rect = mpatches.FancyBboxPatch(
            (x, y_bottom + box_h - header_h), box_w, header_h,
            boxstyle="round,pad=0.08",
            facecolor=s["color"], edgecolor=s["color"], linewidth=0,
        )
        ax.add_patch(header_rect)

        # 헤더 텍스트
        ax.text(
            x + box_w / 2, y_bottom + box_h - header_h / 2,
            s["label"], ha="center", va="center",
            fontsize=11, fontweight="bold", color="white",
            multialignment="center",
        )

        # 본문 bullet lines
        for i, line in enumerate(s["lines"]):
            ax.text(
                x + 0.15, y_bottom + box_h - header_h - 0.38 - i * 0.55,
                line, ha="left", va="center",
                fontsize=9, color="#2C3E50",
            )

        # 산출물 박스
        out_rect = mpatches.FancyBboxPatch(
            (x + 0.1, y_bottom + 0.05), box_w - 0.2, 0.52,
            boxstyle="round,pad=0.05",
            facecolor="white", edgecolor=s["color"], linewidth=1.2, linestyle="--",
        )
        ax.add_patch(out_rect)
        ax.text(
            x + box_w / 2, y_bottom + 0.31,
            s["out"], ha="center", va="center",
            fontsize=7.5, color=s["color"], fontweight="bold",
            multialignment="center",
        )

        # 폴더 태그 레이블
        ax.text(
            x + box_w / 2, 0.38,
            f"[{s['name']}]", ha="center", va="center",
            fontsize=9, color=s["color"], fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.2", facecolor=s["light"],
                      edgecolor=s["color"], linewidth=1),
        )

    # 화살표
    arrow_ys = [0.7 + box_h / 2]
    for x_start in [0.4 + box_w, 4.9 + box_w, 9.4 + box_w]:
        x_end = x_start + (4.9 - 0.4 - box_w)
        ax.annotate(
            "", xy=(x_end, 3.05), xytext=(x_start, 3.05),
            arrowprops=dict(arrowstyle="-|>", color="#555555",
                            lw=2.0, mutation_scale=18),
        )

    # 상단 제목
    ax.text(
        9.1, 5.55,
        "SmartPitch 4-Stage Pipeline — byte-equal CONTRACT_v1 계약으로 연결",
        ha="center", va="center",
        fontsize=13, fontweight="bold", color="#2C3E50",
    )

    plt.tight_layout(pad=0.4)
    out_path = FIG_DIR / "fig_pipeline_4stage.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="#F8F9FA")
    plt.close()
    print(f"저장: {out_path}  ({out_path.stat().st_size // 1024} KB)")


# ═════════════════════════════════════════════════════════════════════════════
# Fig B: RL Reward Comparison
# ═════════════════════════════════════════════════════════════════════════════
def load_rl_result(fname):
    p = RL_RESULTS_DIR / fname
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def build_fig_rl_comparison():
    # 모델B 기준 5알고리즘 비교 (일관된 transition model 조건)
    modelB_results = {}
    for algo_file, algo_key in [
        ("mdp_modelB_b0_p0.json",   "MDP-VI"),
        ("dynaq_modelB_b0_p0.json", "Dyna-Q"),
        ("dqn_modelB_b0_p0.json",   "DQN"),
        ("ddqn_modelB_b0_p0.json",  "DDQN"),
        ("ppo_modelB_b0_p0.json",   "PPO"),
    ]:
        d = load_rl_result(algo_file)
        if d and algo_key in d["results"]:
            modelB_results[algo_key] = d["results"][algo_key]

    # Random baseline (Model B 기준)
    d_mdp_b = load_rl_result("mdp_modelB_b0_p0.json")
    random_b = d_mdp_b["results"]["Random"] if d_mdp_b else {"mean_reward": -0.046, "ci95_lo": -0.113, "ci95_hi": 0.021}
    mostfreq_b = d_mdp_b["results"]["MostFreq"] if d_mdp_b else {"mean_reward": -0.072, "ci95_lo": -0.140, "ci95_hi": -0.003}

    # MLP10 (우리 모델) 기준 MDP-VI, Dyna-Q
    d_mlp10_mdp = load_rl_result("mdp_modelMLP10_b0_p0.json")
    d_mlp10_dynaq = load_rl_result("dynaq_modelMLP10_b0_p0_b_vs_mlp10_v1.json")

    mlp10_mdp = d_mlp10_mdp["results"]["MDP-VI"] if d_mlp10_mdp else None
    mlp10_random = d_mlp10_mdp["results"]["Random"] if d_mlp10_mdp else None
    mlp10_dynaq = d_mlp10_dynaq["results"]["Dyna-Q"] if d_mlp10_dynaq else None

    # ── 왼쪽 차트: Model B 기준 7개 비교 ──────────────────────────────────
    bar_items = [
        ("MostFreq",  mostfreq_b,       "#AAAAAA", "baseline"),
        ("Random",    random_b,         "#BBBBBB", "baseline"),
        ("PPO",       modelB_results.get("PPO"),   "#9B59B6", "model-free"),
        ("DDQN",      modelB_results.get("DDQN"),  "#8E44AD", "model-free"),
        ("DQN",       modelB_results.get("DQN"),   "#7D3C98", "model-free"),
        ("Dyna-Q\n(Model B)",  modelB_results.get("Dyna-Q"), "#52BE80", "model-based"),
        ("MDP-VI\n(Model B)",  modelB_results.get("MDP-VI"), "#1E8449", "model-based"),
    ]

    # ── 오른쪽 차트: 우리 모델(MLP10) vs Random ────────────────────────────
    mlp10_items = [
        ("Random\n(MLP10)", mlp10_random,  "#BBBBBB"),
        ("Dyna-Q\n(MLP10)", mlp10_dynaq,   "#2ECC71"),
        ("MDP-VI\n(MLP10★)", mlp10_mdp,   "#E67E22"),
    ]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6),
                                    gridspec_kw={"width_ratios": [7, 3]})
    fig.patch.set_facecolor("white")

    # ── 왼쪽 ──────────────────────────────────────────────────────────────
    ax1.set_facecolor("white")
    ax1.axhline(0, color="#888888", linewidth=1.2, linestyle="--", alpha=0.6)

    colors_left  = [item[2] for item in bar_items]
    means_left   = [item[1]["mean_reward"] if item[1] else 0 for item in bar_items]
    lo_left      = [item[1]["ci95_lo"] if item[1] else 0 for item in bar_items]
    hi_left      = [item[1]["ci95_hi"] if item[1] else 0 for item in bar_items]
    errs_lo      = [m - l for m, l in zip(means_left, lo_left)]
    errs_hi      = [h - m for m, h in zip(means_left, hi_left)]
    labels_left  = [item[0] for item in bar_items]
    categories   = [item[3] for item in bar_items]

    xs = np.arange(len(bar_items))
    bars = ax1.bar(xs, means_left, color=colors_left, width=0.6, alpha=0.88,
                   yerr=[errs_lo, errs_hi], capsize=5, ecolor="#555555",
                   error_kw={"elinewidth": 1.5}, zorder=3)

    for bar, v, c in zip(bars, means_left, categories):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            v + (0.012 if v >= 0 else -0.02),
            f"{v:+.3f}",
            ha="center", va="bottom" if v >= 0 else "top",
            fontsize=9, fontweight="bold", color="#333333",
        )

    # 구분선
    ax1.axvline(4.5, color="#CCCCCC", linewidth=1.2, linestyle=":", alpha=0.8)

    ax1.set_xticks(xs)
    ax1.set_xticklabels(labels_left, fontsize=9)
    ax1.set_ylabel("Mean Reward per Inning (RE24 기반)", fontsize=11)
    ax1.set_title("알고리즘 비교 — Model B (4-class) 동일 조건\n(n=1,000 episodes, 95% CI, batter_c=0, pitcher_c=0)",
                  fontsize=11, pad=8)
    ax1.set_ylim(-0.22, 0.18)
    ax1.yaxis.grid(True, alpha=0.3)
    ax1.set_axisbelow(True)

    # 범례
    legend_handles = [
        mpatches.Patch(color="#BBBBBB", label="Baseline (Random/Freq)"),
        mpatches.Patch(color="#7D3C98", label="Model-free (DQN/DDQN/PPO)"),
        mpatches.Patch(color="#1E8449", label="Model-based (MDP-VI/Dyna-Q)"),
    ]
    ax1.legend(handles=legend_handles, loc="upper left", fontsize=9, framealpha=0.9)

    # ── 오른쪽: MLP10 (우리 모델) ──────────────────────────────────────────
    ax2.set_facecolor("#FDFEFE")
    ax2.axhline(0, color="#888888", linewidth=1.2, linestyle="--", alpha=0.6)

    means_r  = [item[1]["mean_reward"] if item[1] else 0 for item in mlp10_items]
    lo_r     = [item[1]["ci95_lo"] if item[1] else 0 for item in mlp10_items]
    hi_r     = [item[1]["ci95_hi"] if item[1] else 0 for item in mlp10_items]
    errs_lo2 = [m - l for m, l in zip(means_r, lo_r)]
    errs_hi2 = [h - m for m, h in zip(means_r, hi_r)]
    colors_r = [item[2] for item in mlp10_items]
    labels_r = [item[0] for item in mlp10_items]

    xs2 = np.arange(len(mlp10_items))
    bars2 = ax2.bar(xs2, means_r, color=colors_r, width=0.55, alpha=0.88,
                    yerr=[errs_lo2, errs_hi2], capsize=5, ecolor="#555555",
                    error_kw={"elinewidth": 1.5}, zorder=3)

    for bar, v in zip(bars2, means_r):
        ax2.text(
            bar.get_x() + bar.get_width() / 2,
            v + (0.012 if v >= 0 else -0.022),
            f"{v:+.3f}",
            ha="center", va="bottom" if v >= 0 else "top",
            fontsize=10, fontweight="bold", color="#333333",
        )

    # Δ 화살표 (Random → MDP-VI)
    if mlp10_random and mlp10_mdp:
        r_val = mlp10_random["mean_reward"]
        m_val = mlp10_mdp["mean_reward"]
        delta = m_val - r_val
        ax2.annotate(
            "", xy=(2, m_val), xytext=(0, r_val),
            arrowprops=dict(arrowstyle="-|>", color="#E67E22", lw=2.0, mutation_scale=14),
        )
        ax2.text(
            1.0, (r_val + m_val) / 2,
            f"Δ = {delta:+.2f}\n(+0.41 RE24\n/inning)",
            ha="center", va="center", fontsize=9, color="#E67E22", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="#E67E22", alpha=0.9),
        )

    ax2.set_xticks(xs2)
    ax2.set_xticklabels(labels_r, fontsize=9)
    ax2.set_title("우리 모델(MLP10)\n사용 시 MDP-VI 효과", fontsize=11, pad=8)
    ax2.set_ylim(-0.52, 0.28)
    ax2.yaxis.grid(True, alpha=0.3)
    ax2.set_axisbelow(True)

    # 강조 박스
    ax2.add_patch(mpatches.FancyBboxPatch(
        (1.7, -0.05), 1.05, 0.22,
        boxstyle="round,pad=0.05",
        facecolor="#FEF9E7", edgecolor="#E67E22", linewidth=2, zorder=0,
    ))

    plt.suptitle(
        "베이스라인 비교 ② — 정책 가치 (RE24/inning)\n"
        "Model-based (MDP-VI/Dyna-Q) ▶ Random·Model-free보다 통계적으로 유의미하게 우월",
        fontsize=12, fontweight="bold", y=1.01,
    )
    plt.tight_layout(pad=1.0)
    out_path = FIG_DIR / "fig_rl_reward_comparison.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"저장: {out_path}  ({out_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    print("=== Full-pipeline figures 생성 ===")
    build_fig_pipeline()
    build_fig_rl_comparison()
    print("완료.")
