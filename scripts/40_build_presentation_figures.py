"""
scripts/40_build_presentation_figures.py

발표용 그래프 7종 생성 (Phase 10 최종 + 베이스라인 비교 포함).

출력: outputs/figures/
    fig1_core_finding_context.png     — 핵심 발견: context 추가 효과 (7-bar)
    fig2_paper_positioning.png        — 3-way 논문 포지셔닝 표
    fig3_phase10_12model.png          — Phase 10 전체 12-model 비교
    fig4_sota_comparison.png          — 외부 참고 + 내부 베이스라인 비교
    fig5_context_effect_detail.png    — G3 vs G4 context 효과 세부
    fig6_per_class_heatmap.png        — Per-class accuracy 히트맵 (6-model)
    fig7_4class_mdp.png               — 4-class MDP 그룹 비교

Usage:
    uv run python scripts/40_build_presentation_figures.py
"""

import json
from pathlib import Path

import matplotlib
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False
matplotlib.rcParams["figure.facecolor"] = "white"

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "outputs"
FIG_DIR = OUTPUT_DIR / "figures"
FIG_DIR.mkdir(exist_ok=True)

# ── 데이터 로드 ───────────────────────────────────────────────────────────────
with open(OUTPUT_DIR / "all_models_comparison_10cls.json", encoding="utf-8") as f:
    comp10 = json.load(f)
with open(OUTPUT_DIR / "all_models_comparison_4cls.json", encoding="utf-8") as f:
    comp4 = json.load(f)
with open(OUTPUT_DIR / "top4_precision_comparison.json", encoding="utf-8") as f:
    top4_data = json.load(f)

print("데이터 로드 완료")
print(f"  10-class 모델 수: {len(comp10)}")
print(f"  4-class  모델 수: {len(comp4)}")


# ═════════════════════════════════════════════════════════════════════════════
# Fig 1: 핵심 발견 — Pitcher Arsenal이 Sequence 모델을 대체
# ═════════════════════════════════════════════════════════════════════════════
def build_fig1():
    MODELS = [
        ("Random\n(10 classes)", 0.10),
        ("LR\n(77d)", 0.411),
        ("LightGBM\n(77d)", 0.130),
        ("MLP\n(77d)", 0.411),
        ("MLP 135d★\n(+context 58d)", 0.676),
        ("RNN\n(400-pitch seq)", 0.669),
        ("Transformer\n(400-pitch seq)", 0.672),
    ]
    COLORS = ["#aaaaaa", "#888888", "#888888", "#888888", "#e67e22", "#27ae60", "#27ae60"]
    HATCHES = ["", "///", "///", "///", "", r"\\\\", r"\\\\"]

    names = [m[0] for m in MODELS]
    vals = [m[1] for m in MODELS]

    fig, ax = plt.subplots(figsize=(16, 6))

    bars = ax.bar(names, vals, color=COLORS, alpha=0.88, width=0.6, zorder=3)
    for bar, hatch in zip(bars, HATCHES):
        bar.set_hatch(hatch)
        bar.set_edgecolor("white")

    for bar, v in zip(bars, vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            v + 0.012,
            f"{v*100:.1f}%",
            ha="center", va="bottom", fontsize=12, fontweight="bold", color="#333333",
        )

    ax.axhline(0.411, color="#cc3333", linestyle="--", linewidth=1.8, alpha=0.7,
               zorder=2, label="i.i.d. 77d collapse 수준 (41.1%)")

    # MLP 77d → 135d 화살표
    ax.annotate(
        "",
        xy=(4 - 0.05, 0.676 + 0.01),
        xytext=(3 + 0.05, 0.411 + 0.01),
        arrowprops=dict(arrowstyle="->", color="#e67e22", lw=2.5,
                        connectionstyle="arc3,rad=-0.3"),
        zorder=10,
    )
    ax.text(3.5, 0.570, "+26.5pp\n+context 58d", ha="center", va="center",
            fontsize=11, fontweight="bold", color="#e67e22",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#fff8f0",
                      edgecolor="#e67e22", alpha=0.9))

    ax.text(4, 0.61, "MDP OK", ha="center", va="center", fontsize=9.5,
            color="white", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#e67e22", alpha=0.95))
    for xi in [5, 6]:
        ax.text(xi, 0.04, "MDP X", ha="center", va="center", fontsize=8.5,
                color="white",
                bbox=dict(boxstyle="round,pad=0.25", facecolor="#666666", alpha=0.85))

    ax.axvspan(-0.5, 3.5, alpha=0.04, color="#888888", zorder=0)
    ax.axvspan(3.5, 4.5, alpha=0.07, color="#e67e22", zorder=0)
    ax.axvspan(4.5, 6.5, alpha=0.04, color="#27ae60", zorder=0)

    ax.text(1.5, 0.85, "i.i.d. (77d) — collapse", ha="center", fontsize=10,
            color="#777777", style="italic")
    ax.text(4.0, 0.85, "본인 기여\n(i.i.d. + context 58d)", ha="center", fontsize=10,
            color="#e67e22", fontweight="bold")
    ax.text(5.5, 0.85, "Sequence 모델\n(MDP 비호환)", ha="center", fontsize=10,
            color="#27ae60", style="italic")

    ax.set_ylim(0, 0.95)
    ax.set_ylabel("Top-1 Accuracy (10-class)", fontsize=12)
    ax.set_title("핵심 발견: Pitcher Arsenal이 Sequence 모델을 대체할 수 있다",
                 fontsize=14, fontweight="bold", pad=14)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax.tick_params(axis="x", labelsize=10.5)
    ax.grid(axis="y", alpha=0.3, linestyle=":")
    ax.set_axisbelow(True)
    ax.legend(fontsize=9.5, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    fig.savefig(FIG_DIR / "fig1_core_finding_context.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("[OK] fig1_core_finding_context.png")


# ═════════════════════════════════════════════════════════════════════════════
# Fig 2: 3-way 논문 포지셔닝
# ═════════════════════════════════════════════════════════════════════════════
def build_fig2():
    fig, ax = plt.subplots(figsize=(14, 6.5))
    ax.set_xlim(0, 3)
    ax.set_ylim(0, 1)
    ax.axis("off")

    COL_X = [0.5, 1.5, 2.5]
    COL_W = 0.88
    HEADER_Y = 0.91
    ROW_Y = [0.72, 0.55, 0.38, 0.20]
    ROW_H = 0.14

    HEADERS = ["Otremba 2022\n(SmartPitch MDP)", "MIT Sloan 2025\n(Transformer)", "본인 SmartPitch\n(이번 발표)"]
    ROWS = ["Sequence 활용", "MDP/RL 통합", "Pitcher 맥락", "Outcome class"]

    HEADER_BG = ["#dddddd", "#dddddd", "#2980b9"]
    HEADER_FG = ["#333333", "#333333", "white"]

    CELLS = [
        [("없음 (단일 투구)", "neu"), ("있음 (400 pitch)", "pos"), ("없음 (i.i.d. + context)", "pos")],
        [("있음 (Value Iteration)", "pos"), ("없음 (1-step pred.)", "neg"), ("MDP-VI/Dyna-Q 직접\nDQN/PPO 환경 간접", "pos")],
        [("없음 (77d 기본)", "neg"), ("없음", "neg"), ("있음 (arsenal 58d)", "pos")],
        [("4-class\n(Ball/Strike/Foul/InPlay)", "neu"), ("10-class\n(세분화)", "pos"), ("4+10 이중\n(MDP 호환 유지)", "pos")],
    ]

    COLOR_MAP = {"pos": "#d5f5e3", "neg": "#fde8e8", "neu": "#fef9e7"}
    TEXT_MAP = {"pos": "#1a7a3e", "neg": "#a93226", "neu": "#7d6608"}

    # 성능 행 추가 (하단)
    PERF_Y = 0.06
    PERF_DATA = [
        ("Top-1: 60.9%\n(4-class)", "neu"),
        ("Top-1: 67.2%\n(10-class, 내부 재현)", "pos"),
        ("Top-1: 67.6%\n(10-class, MDP ✅)", "pos"),
    ]

    for ry, label in zip(ROW_Y, ROWS):
        ax.text(-0.02, ry, label, ha="right", va="center", fontsize=10,
                fontweight="bold", color="#444444")
    ax.text(-0.02, PERF_Y, "Top-1 성능", ha="right", va="center", fontsize=10,
            fontweight="bold", color="#444444")

    for ci, (cx, txt, bg, fg) in enumerate(zip(COL_X, HEADERS, HEADER_BG, HEADER_FG)):
        rect = plt.Rectangle((cx - COL_W / 2, HEADER_Y - 0.10), COL_W, 0.17,
                              facecolor=bg, edgecolor="white", linewidth=1.5, zorder=3)
        ax.add_patch(rect)
        ax.text(cx, HEADER_Y - 0.015, txt, ha="center", va="center",
                fontsize=10.5, fontweight="bold", color=fg, zorder=4)

    for ri, (ry, row) in enumerate(zip(ROW_Y, CELLS)):
        for ci, (cx, (txt, hint)) in enumerate(zip(COL_X, row)):
            ec, ew = ("#2980b9", 1.8) if ci == 2 else ("#cccccc", 0.8)
            rect = plt.Rectangle((cx - COL_W / 2, ry - ROW_H / 2), COL_W, ROW_H,
                                  facecolor=COLOR_MAP[hint], edgecolor=ec, linewidth=ew, zorder=3)
            ax.add_patch(rect)
            ax.text(cx, ry, txt, ha="center", va="center", fontsize=9.5,
                    color=TEXT_MAP[hint], fontweight="bold", zorder=4)

    for ci, (cx, (txt, hint)) in enumerate(zip(COL_X, PERF_DATA)):
        ec, ew = ("#2980b9", 1.8) if ci == 2 else ("#cccccc", 0.8)
        rect = plt.Rectangle((cx - COL_W / 2, PERF_Y - ROW_H / 2), COL_W, ROW_H,
                              facecolor=COLOR_MAP[hint], edgecolor=ec, linewidth=ew, zorder=3)
        ax.add_patch(rect)
        fw = "bold" if ci == 2 else "normal"
        ax.text(cx, PERF_Y, txt, ha="center", va="center", fontsize=9.5,
                color=TEXT_MAP[hint], fontweight=fw, zorder=4)

    ax.set_title("논문 비교: Otremba 2022 vs MIT Sloan 2025 vs 본인",
                 fontsize=13, fontweight="bold", pad=12)
    fig.text(0.5, 0.00,
             "Otremba MDP/RL 통합  +  MIT Sloan-style 10-class 세분화  +  본인 Arsenal Context 58d  =  차별점",
             ha="center", fontsize=9.5, style="italic", color="#555555")

    plt.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(FIG_DIR / "fig2_paper_positioning.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("[OK] fig2_paper_positioning.png")


# ═════════════════════════════════════════════════════════════════════════════
# Fig 3: Phase 10 전체 12-model 비교
# ═════════════════════════════════════════════════════════════════════════════
def build_fig3():
    names = list(comp10.keys())
    top1 = [comp10[n]["top1"] for n in names]
    macro_f1 = [comp10[n].get("macro_f1", 0.0) for n in names]

    color_map = {
        "Logistic Regression": "#E74C3C",
        "LightGBM": "#E74C3C",
        "MLP (10-class)": "#E74C3C",
        "RNN (LSTM)": "#9B59B6",
        "Transformer (Model C)": "#9B59B6",
        "LR 135d": "#3498DB",
        "LightGBM 135d": "#3498DB",
        "MLP 135d (focal)": "#27AE60",
        "RNN Hybrid (drop)": "#E67E22",
        "RNN Hybrid (fullN)": "#E67E22",
        "Transformer Hybrid (drop)": "#E67E22",
        "Transformer Hybrid (fullN)": "#E67E22",
    }
    colors = [color_map.get(n, "#BDC3C7") for n in names]
    xlabels = [
        "LR\n(77d)", "LGB\n(77d)", "MLP\n(77d)",
        "RNN\n(87d)", "Trans\n(87d)",
        "LR\n(135d)", "LGB\n(135d)", "MLP★\n(135d)",
        "RNN-H\ndrop", "RNN-H\nfullN",
        "TH\ndrop", "TH\nfullN",
    ]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 6.5),
                                    gridspec_kw={"width_ratios": [3, 2]})

    bars = ax1.bar(xlabels[: len(names)], top1, color=colors, alpha=0.85, width=0.65)
    for bar, v, n in zip(bars, top1, names):
        fw = "bold" if "focal" in n else "normal"
        ax1.text(bar.get_x() + bar.get_width() / 2, v + 0.008, f"{v:.1%}",
                 ha="center", fontsize=9, fontweight=fw)

    ax1.axhline(0.411, color="#E74C3C", ls="--", alpha=0.4, lw=1.5, label="iid 77d collapse (41.1%)")
    ax1.axhline(0.672, color="#9B59B6", ls=":", alpha=0.4, lw=1.5, label="Seq 87d Transformer (67.2%)")
    ax1.set_ylim(0, 0.85)
    ax1.set_ylabel("Test Top-1 Accuracy", fontsize=11)
    ax1.set_title("Phase 10 최종: 12-model 10-class 비교", fontsize=12, fontweight="bold")
    ax1.grid(True, axis="y", alpha=0.25)
    ax1.set_axisbelow(True)
    for x in [2.5, 4.5, 7.5, 9.5]:
        ax1.axvline(x, color="gray", alpha=0.2)

    legend_patches = [
        mpatches.Patch(color="#E74C3C", label="G3: iid 77d (collapse)"),
        mpatches.Patch(color="#3498DB", label="G4: iid 135d"),
        mpatches.Patch(color="#27AE60", label="G4: MLP 135d focal ⭐"),
        mpatches.Patch(color="#9B59B6", label="G5: seq 87d"),
        mpatches.Patch(color="#E67E22", label="G6/G6': hybrid"),
    ]
    ax1.legend(handles=legend_patches, fontsize=8, loc="lower right")
    ax1.spines[["top", "right"]].set_visible(False)

    groups = ["LR", "LightGBM", "MLP"]
    v77 = [comp10["Logistic Regression"]["top1"], comp10["LightGBM"]["top1"], comp10["MLP (10-class)"]["top1"]]
    v135 = [comp10["LR 135d"]["top1"], comp10["LightGBM 135d"]["top1"], comp10["MLP 135d (focal)"]["top1"]]

    x2 = np.arange(len(groups))
    w2 = 0.35
    ax2.bar(x2 - w2 / 2, v77, w2, label="77d (collapse)", color="#E74C3C", alpha=0.75)
    b135 = ax2.bar(x2 + w2 / 2, v135, w2, label="135d (+arsenal)", color="#3498DB", alpha=0.85)
    ax2.bar([2 + w2 / 2], [comp10["MLP 135d (focal)"]["top1"]], w2,
            color="#27AE60", alpha=0.9, label="MLP 135d focal ⭐")

    for i, (a, b) in enumerate(zip(v77, v135)):
        ax2.annotate(
            f"+{(b - a) * 100:.1f}pp",
            xy=(i + w2 / 2, b),
            xytext=(i + w2 / 2, b + 0.032),
            ha="center", fontsize=9.5, color="#1A5E20", fontweight="bold",
            arrowprops=dict(arrowstyle="->", color="#1A5E20", lw=1.2),
        )

    ax2.set_xticks(x2)
    ax2.set_xticklabels(groups)
    ax2.set_ylim(0, 0.90)
    ax2.set_ylabel("Top-1 Accuracy")
    ax2.set_title("Context 효과 (G3→G4)\n같은 architecture, context만 추가", fontsize=11, fontweight="bold")
    ax2.legend(fontsize=8)
    ax2.grid(True, axis="y", alpha=0.25)
    ax2.spines[["top", "right"]].set_visible(False)

    plt.suptitle("Phase 10 최종: Context = Architecture-agnostic (iid 모델 기준)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    fig.savefig(FIG_DIR / "fig3_phase10_12model.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("[OK] fig3_phase10_12model.png")


# ═════════════════════════════════════════════════════════════════════════════
# Fig 4: 외부 참고 + 내부 베이스라인 비교
# ═════════════════════════════════════════════════════════════════════════════
def build_fig4():
    """
    비교표 시각화.
    출처:
      - XGBoost 2-tier Tier1 (Ball/Strike/BIP 3-class): 72.4% [Schilamkur et al.]
      - MIT Sloan-style Transformer internal reproduction (10-class): 67.2%
      - LLM Neural Sabermetrics (next-pitch 10-class): 64% [Ahn et al. 2025]
      - Random Forest Ball/Strike (2-class): 91.1% [Northwestern EECS 349]
      - 본인 MLP 135d focal: 67.6% (10-class)
    주의: 외부 문헌은 task가 다르므로 직접 순위 비교 불가 — task complexity 명시
    """
    # (이름, accuracy, task_desc, 비교가능성, 색상)
    COMP_MODELS = [
        ("Random Forest\n(Ball/Strike 2-class)\n[Northwestern]", 0.911, "2-class", "외부 참고", "#cccccc"),
        ("XGBoost Tier-1\n(Ball/Strike/BIP 3-class)\n[Schilamkur]", 0.724, "3-class", "외부 참고", "#aaaaaa"),
        ("LLM\nNeural Sabermetrics\n[Ahn et al.]", 0.640, "10-class\n(next pitch)", "외부 참고", "#9B59B6"),
        ("Internal Transformer\n(MIT Sloan-style)", 0.672, "10-class\n(sequence)", "내부 baseline", "#3498DB"),
        ("MLP10\n135d focal\n(ours)", 0.676, "10-class\n(MDP-ready)", "본인 모델", "#e67e22"),
    ]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7),
                                    gridspec_kw={"width_ratios": [3, 2]})

    names = [m[0] for m in COMP_MODELS]
    vals = [m[1] for m in COMP_MODELS]
    tasks = [m[2] for m in COMP_MODELS]
    comp_level = [m[3] for m in COMP_MODELS]
    colors = [m[4] for m in COMP_MODELS]

    bars = ax1.bar(range(len(names)), vals, color=colors, alpha=0.85, width=0.6)
    ax1.set_xticks(range(len(names)))
    ax1.set_xticklabels(names, fontsize=9)

    for bar, v, task, cl in zip(bars, vals, tasks, comp_level):
        ax1.text(bar.get_x() + bar.get_width() / 2, v + 0.012,
                 f"{v:.1%}", ha="center", fontsize=11, fontweight="bold")
        ax1.text(bar.get_x() + bar.get_width() / 2, 0.02,
                 task, ha="center", fontsize=7.5, color="#555555", style="italic")

    # 본인 모델 강조 박스
    ax1.add_patch(plt.Rectangle((3.7, 0), 0.6, vals[-1] + 0.04,
                                 fill=False, edgecolor="#e67e22", linewidth=3, zorder=5))

    ax1.set_ylim(0, 1.08)
    ax1.set_ylabel("Top-1 Accuracy", fontsize=11)
    ax1.set_title("외부 참고 + 내부 베이스라인 비교\n※ 외부 문헌은 task 정의가 달라 직접 순위 비교 금지",
                  fontsize=12, fontweight="bold")
    ax1.grid(axis="y", alpha=0.3, linestyle=":")
    ax1.set_axisbelow(True)
    ax1.spines[["top", "right"]].set_visible(False)

    legend_patches = [
        mpatches.Patch(color="#cccccc", label="외부 참고 (2-class)"),
        mpatches.Patch(color="#aaaaaa", label="외부 참고 (3-class)"),
        mpatches.Patch(color="#9B59B6", label="외부 참고 (10-class, 다른 정의)"),
        mpatches.Patch(color="#3498DB", label="내부 sequence baseline"),
        mpatches.Patch(color="#e67e22", label="본인 MLP10 (MDP-ready)"),
    ]
    ax1.legend(handles=legend_patches, fontsize=9, loc="upper left")

    # 오른쪽: Task 복잡도 vs 정확도 scatter
    task_complexity = [1, 2, 4, 4, 4]  # 1=2class, 2=3class, 4=10class
    accs = vals
    scatter_colors = colors
    scatter_labels = ["RF\n(2-cls)", "XGB\n(3-cls)", "LLM\n(10-cls)", "Trans\nbaseline", "★MLP10"]

    label_offsets = [
        (0.05, 0.01),
        (0.05, 0.02),
        (0.08, -0.015),
        (-0.45, 0.035),
        (0.08, 0.005),
    ]
    for i, (x, y, c, lbl) in enumerate(zip(task_complexity, accs, scatter_colors, scatter_labels)):
        ax2.scatter(x, y, color=c, s=180, zorder=5, edgecolors="white", linewidths=1.5)
        offset = label_offsets[i]
        ax2.annotate(lbl, (x, y), (x + offset[0], y + offset[1]), fontsize=8.5)

    ax2.set_xlim(0.5, 5)
    ax2.set_ylim(0.5, 1.05)
    ax2.set_xticks([1, 2, 4])
    ax2.set_xticklabels(["2-class", "3-class", "10-class"], fontsize=9)
    ax2.set_xlabel("출력 클래스 수 (task 복잡도 ↑)", fontsize=10)
    ax2.set_ylabel("Top-1 Accuracy", fontsize=10)
    ax2.set_title("Task 복잡도 vs 정확도\n(클래스 수↑ = 더 어려운 과제)", fontsize=11, fontweight="bold")
    ax2.grid(alpha=0.3, linestyle=":")
    ax2.spines[["top", "right"]].set_visible(False)

    fig.text(0.5, 0.00,
             "직접 주장 가능한 비교: 내부 Transformer baseline 67.2% vs MLP10 67.6%; 외부 문헌은 task 정의가 달라 참고용",
             ha="center", fontsize=9.5, color="#333333", style="italic")

    plt.suptitle("베이스라인 비교: 성능보다 비교 조건을 먼저 분리", fontsize=13, fontweight="bold")
    plt.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(FIG_DIR / "fig4_sota_comparison.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("[OK] fig4_sota_comparison.png")


# ═════════════════════════════════════════════════════════════════════════════
# Fig 5: Context 효과 세부 (G3 vs G4, Macro-F1 포함)
# ═════════════════════════════════════════════════════════════════════════════
def build_fig5():
    groups = ["LR", "LightGBM", "MLP"]
    v77_t1 = [comp10["Logistic Regression"]["top1"], comp10["LightGBM"]["top1"], comp10["MLP (10-class)"]["top1"]]
    v135_t1 = [comp10["LR 135d"]["top1"], comp10["LightGBM 135d"]["top1"], comp10["MLP 135d (focal)"]["top1"]]
    v77_f1 = [comp10["Logistic Regression"]["macro_f1"], comp10["LightGBM"]["macro_f1"], comp10["MLP (10-class)"]["macro_f1"]]
    v135_f1 = [comp10["LR 135d"]["macro_f1"], comp10["LightGBM 135d"]["macro_f1"], comp10["MLP 135d (focal)"]["macro_f1"]]

    x = np.arange(len(groups))
    w = 0.32

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

    for ax, v77, v135, ylabel, title, ylim in [
        (ax1, v77_t1, v135_t1, "Top-1 Accuracy", "Top-1 Accuracy: G3(77d) vs G4(135d)", 0.90),
        (ax2, v77_f1, v135_f1, "Macro-F1", "Macro-F1: G3(77d) vs G4(135d)", 0.45),
    ]:
        b1 = ax.bar(x - w / 2, v77, w, label="77d (G3, collapse)", color="#E74C3C", alpha=0.75)
        b2 = ax.bar(x + w / 2, v135, w, label="135d (G4, +context)", color="#3498DB", alpha=0.85)
        ax.bar([2 + w / 2], [v135[2]], w, color="#27AE60", alpha=0.9, label="MLP 135d focal ⭐")

        for bar, v in zip(b1, v77):
            ax.text(bar.get_x() + bar.get_width() / 2, v + ylim * 0.01,
                    f"{v:.1%}", ha="center", fontsize=9)
        for i, (bar, v) in enumerate(zip(b2, v135)):
            c = "#1A5E20" if i == 2 else "#1a4a8a"
            ax.text(bar.get_x() + bar.get_width() / 2, v + ylim * 0.01,
                    f"{v:.1%}", ha="center", fontsize=9, color=c, fontweight="bold")

        for i, (a, b) in enumerate(zip(v77, v135)):
            ax.annotate(
                f"+{(b - a) * 100:.1f}pp",
                xy=(i + w / 2, b),
                xytext=(i + w / 2, b + ylim * 0.07),
                ha="center", fontsize=9, color="#1A5E20", fontweight="bold",
                arrowprops=dict(arrowstyle="->", color="#1A5E20", lw=1),
            )

        ax.set_xticks(x)
        ax.set_xticklabels(groups)
        ax.set_ylim(0, ylim)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.legend(fontsize=9)
        ax.grid(axis="y", alpha=0.3, linestyle=":")
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)

    # 핵심 메시지
    fig.text(0.5, 0.00,
             "같은 아키텍처, 같은 N (353,667~353,776) — context 58d 추가만으로 collapse 완전 해소",
             ha="center", fontsize=10, style="italic", color="#555555")

    plt.suptitle("Context 효과: G3(77d) → G4(135d), Architecture-Agnostic", fontsize=13, fontweight="bold")
    plt.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(FIG_DIR / "fig5_context_effect_detail.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("[OK] fig5_context_effect_detail.png")


# ═════════════════════════════════════════════════════════════════════════════
# Fig 6: Per-class Accuracy 히트맵 (6 core models)
# ═════════════════════════════════════════════════════════════════════════════
def build_fig6():
    import seaborn as sns

    CLASSES = ["Ball", "Strike", "Single", "Double", "Triple", "HomeRun",
               "FieldOut", "Strikeout", "Walk", "HBP"]
    CLASS_FREQ = {
        "Ball": 33.3, "Strike": 27.7, "Single": 3.6, "Double": 1.1,
        "Triple": 0.09, "HomeRun": 0.81, "FieldOut": 11.8,
        "Strikeout": 5.9, "Walk": 2.0, "HBP": 0.28,
    }
    MODEL_KEYS = [
        "Logistic Regression", "LightGBM", "MLP (10-class)",
        "MLP 135d (focal)", "RNN (LSTM)", "Transformer (Model C)"
    ]
    MODEL_LABELS = [
        "LR (77d)\nG3", "LGB (77d)\nG3", "MLP (77d)\nG3",
        "MLP 135d★\nG4", "RNN (87d)\nG5", "Transformer\nG5"
    ]
    PCA_KEY_MAP = {
        "Ball": "Ball", "Strike": "Strike", "Single": "Single",
        "Double": "Double", "Triple": "Triple", "HomeRun": "HomeRun",
        "FieldOut": "FieldOut", "Strikeout": "Strikeout", "Walk": "Walk",
        "HBP": "HitByPitch",
    }

    mat = np.full((len(CLASSES), len(MODEL_KEYS)), np.nan)
    for mi, mk in enumerate(MODEL_KEYS):
        pca = comp10[mk].get("per_class_accuracy", {})
        for ci, cls in enumerate(CLASSES):
            key = PCA_KEY_MAP[cls]
            val = pca.get(key)
            if val is not None:
                mat[ci, mi] = val

    fig, ax = plt.subplots(figsize=(14, 8))
    im = ax.imshow(mat, cmap=plt.cm.RdYlGn, vmin=0, vmax=1, aspect="auto")

    for ci in range(len(CLASSES)):
        for mi in range(len(MODEL_KEYS)):
            v = mat[ci, mi]
            if np.isnan(v):
                txt, col = "-", "#888888"
            else:
                txt = f"{v:.0%}"
                col = "white" if v < 0.15 else ("black" if v < 0.80 else "black")
            fw = "bold" if mi == 3 else "normal"
            ax.text(mi, ci, txt, ha="center", va="center", fontsize=10, color=col, fontweight=fw)

    ax.set_yticks(range(len(CLASSES)))
    y_labels = [f"{c} ({CLASS_FREQ.get(c, 0):.2g}%)" for c in CLASSES]
    ax.set_yticklabels(y_labels, fontsize=10)
    ax.set_xticks(range(len(MODEL_KEYS)))
    ax.set_xticklabels(MODEL_LABELS, fontsize=10)

    # MDP 구분선 (MLP135d와 RNN 사이)
    ax.axvline(3.5, color="#1f4e8c", linewidth=3, linestyle="--", alpha=0.85, zorder=5)
    ax.text(3.5, -0.7, "← MDP 호환  |  MDP 비호환 →",
            ha="center", va="bottom", fontsize=10, color="#1f4e8c", fontweight="bold")

    # MLP 135d 열 강조
    ax.add_patch(plt.Rectangle((2.5, -0.5), 1, len(CLASSES),
                                fill=False, edgecolor="#e67e22", linewidth=3.5, zorder=10))

    cbar = plt.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
    cbar.set_label("Per-class Accuracy", fontsize=10)

    ax.set_title("Per-class Accuracy 히트맵 (6-model 비교)\n* 클래스 빈도(%) 표시 — 희소 클래스일수록 예측 어려움",
                 fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel("모델 (그룹)", fontsize=11)
    ax.set_ylabel("클래스 (테스트셋 비율)", fontsize=11)

    fig.text(0.5, 0.01,
             "77d 모델: Ball/Strike만 예측 (collapse)  →  135d MLP: Walk 86%, Strikeout 19%, 나머지도 정상 예측  →  Single~HR은 타자 맥락 부재로 여전히 0%",
             ha="center", fontsize=9, color="#333333")

    plt.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(FIG_DIR / "fig6_per_class_heatmap.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("[OK] fig6_per_class_heatmap.png")


# ═════════════════════════════════════════════════════════════════════════════
# Fig 7: 4-class MDP 그룹 비교
# ═════════════════════════════════════════════════════════════════════════════
def build_fig7():
    # 4class json 키 확인
    key_map = {
        "Logistic Regression": "LR (77d)",
        "LightGBM": "LightGBM (77d)",
        "MLP Model B": "MLP Model B (77d)",
    }
    # 실제 키 체크
    k_lr = "LR (77d)" if "LR (77d)" in comp4 else "Logistic Regression"
    k_lgb = "LightGBM (77d)" if "LightGBM (77d)" in comp4 else "LightGBM"
    k_mlp = "MLP Model B (77d)" if "MLP Model B (77d)" in comp4 else "MLP (Model B)"

    names4 = [k_lr, k_lgb, k_mlp]
    labels4 = ["Logistic\nRegression", "LightGBM", "MLP (Model B)\n★ MDP 권장"]
    top1_4 = [comp4[n]["top1"] for n in names4]
    mf1_4 = [comp4[n]["macro_f1"] for n in names4]
    ce_4 = [comp4[n]["ce"] for n in names4]
    colors4 = ["#5dade2", "#e67e22", "#2ecc71"]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5.5))

    for ax, vals, ylabel, title, ylim in [
        (axes[0], top1_4, "Top-1 Accuracy", "Top-1 Accuracy\n(4-class, MDP 호환)", 0.85),
        (axes[1], mf1_4, "Macro-F1", "Macro-F1\n(4-class)", 0.75),
        (axes[2], ce_4, "Cross-Entropy (↓)", "Cross-Entropy\n(캘리브레이션)", 1.4),
    ]:
        bars = ax.bar(labels4, vals, color=colors4, alpha=0.85, width=0.5, zorder=3)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, v + ylim * 0.01,
                    f"{v:.3f}" if ylabel.startswith("Cross") else f"{v:.1%}",
                    ha="center", fontsize=11, fontweight="bold")

        ax.set_ylim(0, ylim)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(title, fontsize=11, fontweight="bold")
        if not ylabel.startswith("Cross"):
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
        ax.grid(axis="y", alpha=0.3, linestyle=":")
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)

    # empirical baseline 수평선
    axes[0].axhline(0.356, color="gray", ls="--", alpha=0.6, label="Empirical baseline (35.6%)")
    axes[0].legend(fontsize=9)

    fig.suptitle("4-class MDP/DQN 호환 그룹 — LR → LightGBM → MLP (Model B) 단계적 성능 향상",
                 fontsize=12, fontweight="bold")
    fig.text(0.5, 0.00,
             "N=353,776 (2024 H2 test set)  |  MDP 호환: 단일 pitch 77d input, 추론 <1ms  |  Model B 최종 권장",
             ha="center", fontsize=9.5, color="#555555")

    plt.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(FIG_DIR / "fig7_4class_mdp.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("[OK] fig7_4class_mdp.png")


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("발표용 그래프 생성 (Phase 10 최종 + 베이스라인 비교)")
    print("=" * 60)

    build_fig1()
    build_fig2()
    build_fig3()
    build_fig4()
    build_fig5()
    build_fig6()
    build_fig7()

    print()
    print("=" * 60)
    print("저장 확인:")
    for fname in [
        "fig1_core_finding_context.png",
        "fig2_paper_positioning.png",
        "fig3_phase10_12model.png",
        "fig4_sota_comparison.png",
        "fig5_context_effect_detail.png",
        "fig6_per_class_heatmap.png",
        "fig7_4class_mdp.png",
    ]:
        p = FIG_DIR / fname
        if p.exists():
            print(f"  [OK] {fname}  ({p.stat().st_size / 1024:.0f} KB)")
        else:
            print(f"  [MISSING] {fname}")
