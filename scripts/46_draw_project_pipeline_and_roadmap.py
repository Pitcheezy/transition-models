"""Draw project-level pipeline and future-work roadmap figures.

Outputs:
    outputs/figures/project_full_pipeline.png
    outputs/figures/project_full_pipeline.svg
    outputs/figures/future_work_roadmap_slide.png
    outputs/figures/future_work_roadmap_slide.svg
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

INK = "#1A1A1A"
SUB = "#666666"
GREEN = "#2C5F2D"
GREEN_D = "#1F4A25"
GREEN_L = "#EAF0E8"
BLUE = "#2E5E7E"
BLUE_L = "#E8F1F7"
GOLD = "#C49A3A"
GOLD_L = "#FFF7E0"
RED = "#B33A3A"
RED_L = "#FBEAEA"
GRAY_L = "#F7FAF8"
LINE = "#DDE6DF"


def set_korean_font() -> None:
    preferred = ["Malgun Gothic", "NanumGothic", "Noto Sans CJK KR", "Arial Unicode MS"]
    installed = {f.name for f in fm.fontManager.ttflist}
    for name in preferred:
        if name in installed:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


def box(ax, x, y, w, h, *, fc="#FFFFFF", ec=GREEN, lw=1.4, r=0.014, ls="-", z=2):
    p = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.010,rounding_size={r}",
        linewidth=lw,
        edgecolor=ec,
        facecolor=fc,
        linestyle=ls,
        zorder=z,
    )
    ax.add_patch(p)
    return p


def txt(ax, x, y, s, *, size=10, color=INK, weight="normal", ha="center", va="center",
        ls=1.2, style="normal", z=6):
    ax.text(
        x,
        y,
        s,
        fontsize=size,
        color=color,
        fontweight=weight,
        ha=ha,
        va=va,
        linespacing=ls,
        fontstyle=style,
        zorder=z,
    )


def arrow(ax, p0, p1, *, color=GREEN, lw=2.0, scale=16, rad=0.0, ls="-"):
    ax.add_patch(
        FancyArrowPatch(
            p0,
            p1,
            arrowstyle="-|>",
            mutation_scale=scale,
            linewidth=lw,
            color=color,
            linestyle=ls,
            connectionstyle=f"arc3,rad={rad}",
            zorder=10,
            shrinkA=4,
            shrinkB=4,
        )
    )


def title(ax, main, sub):
    txt(ax, 0.04, 0.96, main, size=23, weight="bold", ha="left", va="top")
    txt(ax, 0.04, 0.915, sub, size=11.5, color=SUB, ha="left", va="top")
    ax.plot([0.04, 0.96], [0.885, 0.885], color=LINE, lw=1.3)


def stage_header(ax, x, y, w, label, color=GREEN):
    box(ax, x, y, w, 0.048, fc=color, ec=color, lw=0, r=0.011)
    txt(ax, x + w / 2, y + 0.024, label, size=10.8, color="#FFFFFF", weight="bold")


def pipeline_box(ax, x, y, w, h, head, body, *, fc=GRAY_L, ec=GREEN, head_color=GREEN):
    box(ax, x, y, w, h, fc=fc, ec=ec, lw=1.5, r=0.016)
    txt(ax, x + w / 2, y + h - 0.030, head, size=10.2, color=head_color, weight="bold")
    txt(ax, x + w / 2, y + h / 2 - 0.010, body, size=8.5, color=INK, weight="bold", ls=1.25)


def draw_full_pipeline() -> tuple[Path, Path]:
    fig, ax = plt.subplots(figsize=(17.2, 9.6), dpi=180)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("#FFFFFF")

    title(
        ax,
        "Pitcheezy 전체 파이프라인",
        "Statcast 원천 데이터에서 전이확률 모델과 RE24 기반 RL 정책을 거쳐 최종 구종×존 추천까지",
    )

    # Four large columns. This avoids crossing arrows and makes the direction explicit.
    cols = [
        (0.055, "1. Data / Context", GREEN, GREEN_L),
        (0.295, "2. Transition Model", BLUE, BLUE_L),
        (0.535, "3. PitchEnv / Reward", GOLD, GOLD_L),
        (0.775, "4. Policy / Output", GREEN, GREEN_L),
    ]
    y_col, w_col, h_col = 0.265, 0.175, 0.525

    for x, label, color, light in cols:
        box(ax, x, y_col, w_col, h_col, fc=light, ec=color, lw=1.8, r=0.018)
        box(ax, x + 0.014, y_col + h_col - 0.060, w_col - 0.028, 0.042, fc=color, ec=color, lw=0, r=0.010)
        txt(ax, x + w_col / 2, y_col + h_col - 0.039, label, size=10.0, color="#FFFFFF", weight="bold")

    # Column 1: data/context
    x = cols[0][0]
    txt(ax, x + w_col / 2, y_col + 0.405, "MLB Statcast\n2022–2024", size=10.0, color=GREEN, weight="bold", ls=1.0)
    ax.plot([x + 0.025, x + w_col - 0.025], [y_col + 0.345, y_col + 0.345], color="#CBD8CD", lw=1.0)
    txt(ax, x + w_col / 2, y_col + 0.292, "전처리\nclean · split · label mapping\n77d base feature", size=8.6, weight="bold", ls=1.2)
    ax.plot([x + 0.025, x + w_col - 0.025], [y_col + 0.215, y_col + 0.215], color="#CBD8CD", lw=1.0)
    txt(ax, x + w_col / 2, y_col + 0.145, "Clustering repo\npitcher arsenal 58d\nbatter cluster/context", size=8.6, weight="bold", color=SUB, ls=1.2)

    # Column 2: transition model
    x = cols[1][0]
    txt(ax, x + w_col / 2, y_col + 0.405, "MLP10 / MLP135CE", size=10.0, color=BLUE, weight="bold")
    txt(ax, x + w_col / 2, y_col + 0.352, "135d → 10-class\nP(outcome | state, action)", size=8.7, weight="bold", ls=1.15)
    ax.plot([x + 0.025, x + w_col - 0.025], [y_col + 0.285, y_col + 0.285], color="#C8D7E0", lw=1.0)
    txt(ax, x + w_col / 2, y_col + 0.235, "평가 지표\nTop-1 / CE / Brier\nMacro-F1", size=8.4, color=SUB, weight="bold", ls=1.15)
    box(ax, x + 0.022, y_col + 0.090, w_col - 0.044, 0.075, fc=RED_L, ec=RED, lw=1.2, r=0.010, ls="--")
    txt(ax, x + w_col / 2, y_col + 0.128, "Next\n193d = 135d + batter58d", size=8.2, color=RED, weight="bold", ls=1.0)

    # Column 3: environment/reward
    x = cols[2][0]
    txt(ax, x + w_col / 2, y_col + 0.405, "PitchEnv", size=10.0, color="#6B4A00", weight="bold")
    txt(ax, x + w_col / 2, y_col + 0.352, "state + action\n→ transition sample\n→ next state", size=8.7, weight="bold", ls=1.15)
    ax.plot([x + 0.025, x + w_col - 0.025], [y_col + 0.285, y_col + 0.285], color="#E1D6B5", lw=1.0)
    txt(ax, x + w_col / 2, y_col + 0.225, "Reward\nRE24 delta\n+ count shaping", size=8.8, color="#6B4A00", weight="bold", ls=1.15)
    txt(ax, x + w_col / 2, y_col + 0.110, "전이모델이 곧\nRL 환경의 세계 모델", size=8.2, color=SUB, weight="bold", ls=1.15)

    # Column 4: policy/output
    x = cols[3][0]
    txt(ax, x + w_col / 2, y_col + 0.405, "RL / MDP Policy", size=10.0, color=GREEN, weight="bold")
    txt(ax, x + w_col / 2, y_col + 0.350, "MDP-VI · Dyna-Q\nDQN · PPO\nQ(s,a), π(a|s)", size=8.7, weight="bold", ls=1.15)
    ax.plot([x + 0.025, x + w_col - 0.025], [y_col + 0.275, y_col + 0.275], color="#CBD8CD", lw=1.0)
    txt(ax, x + w_col / 2, y_col + 0.220, "Policy Evaluation\nmean reward\nΔRandom / heatmap", size=8.4, color=SUB, weight="bold", ls=1.15)
    box(ax, x + 0.023, y_col + 0.070, w_col - 0.046, 0.080, fc="#FFFFFF", ec=GREEN, lw=1.2, r=0.010)
    txt(ax, x + w_col / 2, y_col + 0.110, "최종 추천\n구종 × 존", size=9.0, color=GREEN, weight="bold", ls=1.0)

    # Main direction arrows
    for (x0, _, c0, _), (x1, _, _, _) in zip(cols[:-1], cols[1:]):
        arrow(ax, (x0 + w_col + 0.005, y_col + h_col / 2), (x1 - 0.005, y_col + h_col / 2),
              color=c0 if c0 != GOLD else GOLD, lw=2.2, scale=17)

    # Small feedback loop inside the online side
    arrow(ax, (cols[3][0] + 0.035, y_col + 0.010), (cols[2][0] + 0.040, y_col + 0.010),
          color=GOLD, lw=1.5, scale=12, rad=0.10, ls="--")
    txt(ax, 0.735, y_col - 0.020, "agent action loop", size=7.8, color="#6B4A00", weight="bold")

    # Bottom emphasis
    box(ax, 0.06, 0.105, 0.880, 0.095, fc="#FFFDF7", ec=GOLD, lw=1.2, r=0.012)
    txt(
        ax,
        0.50,
        0.152,
        "핵심 논리: 전이모델은 RL 환경의 ‘세계 모델’이다. 따라서 추천 성능 개선은 먼저 P(outcome | state, action)의 현실성,\n그 다음 RL state 표현력과 planning 효율을 높이는 순서로 진행해야 한다.",
        size=9.7,
        color="#4A3A14",
        weight="bold",
        ls=1.35,
    )

    txt(ax, 0.04, 0.045, "Current code path: clustering → transition-models → rl-agent/PitchEnv → MDP-VI·Dyna-Q → pitch recommendation",
        size=8.0, color=SUB, ha="left")

    png = OUT_DIR / "project_full_pipeline.png"
    svg = OUT_DIR / "project_full_pipeline.svg"
    fig.savefig(png, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(svg, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return png, svg


def focus_card(ax, x, y, w, h, *, color, light, title, why, direction, effect, tag):
    box(ax, x, y, w, h, fc=light, ec=color, lw=1.7, r=0.018)
    box(ax, x + 0.016, y + h - 0.060, 0.070, 0.037, fc=color, ec=color, lw=0, r=0.010)
    txt(ax, x + 0.051, y + h - 0.041, tag, size=9.6, color="#FFFFFF", weight="bold")
    txt(ax, x + 0.098, y + h - 0.042, title, size=11.7, color=color, weight="bold", ha="left")

    def section(yy, label, body):
        txt(ax, x + 0.028, yy, label, size=8.6, color=color, weight="bold", ha="left", va="top")
        txt(ax, x + 0.028, yy - 0.027, body, size=7.75, color=INK, weight="bold", ha="left", va="top", ls=1.25)

    section(y + h - 0.100, "필요성", why)
    section(y + h - 0.205, "개선 방향", direction)
    section(y + h - 0.310, "기대효과", effect)


def draw_future_slide() -> tuple[Path, Path]:
    fig, ax = plt.subplots(figsize=(16, 9), dpi=190)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("#FFFFFF")

    title(
        ax,
        "향후계획: 성능 개선은 전이모델의 현실성을 먼저 뚫는다",
        "핵심 성과가 Feature(Context) 추가라면, 다음 단계는 그 feature가 reward로 연결되도록 환경과 정책 입력을 정상화하는 것이다.",
    )

    # Top thesis band
    box(ax, 0.055, 0.775, 0.890, 0.085, fc=GREEN_L, ec=GREEN, lw=1.2, r=0.014)
    txt(
        ax,
        0.500,
        0.818,
        "추천 시스템의 병목은 RL 알고리즘 자체보다, 전이모델이 만들어주는 환경 P(outcome | s,a)의 품질이다.",
        size=12.0,
        color=GREEN_D,
        weight="bold",
    )

    # Focus cards
    card_y, card_h = 0.305, 0.415
    focus_card(
        ax,
        0.045,
        card_y,
        0.300,
        card_h,
        color=RED,
        light=RED_L,
        tag="P0",
        title="안타 확률 복원",
        why="현재 135d 모델은 타자 피처가 없어\nSingle/HR 등 안타류를 거의 0%로 예측.\n환경이 징벌을 못 주면 RL도 회피를 못 배움.",
        direction="타자 58d context를 추가한\n193d 전이모델 구축\n(135d + batter 58d) 및 rare outcome calibration.",
        effect="홈런·장타 위험을 반영한 현실적 환경.\n한가운데 투구를 피하고 유인구/존 선택이\n보상으로 학습되는 기반 확보.",
    )
    focus_card(
        ax,
        0.365,
        card_y,
        0.300,
        card_h,
        color=GOLD,
        light=GOLD_L,
        tag="P1",
        title="RL State에 Feature 직접 주입",
        why="현재 PPO/DQN은 batter_cluster=3처럼\nID 중심 상태를 받음.\n연속 feature의 세부 차이를 정책망이 직접 못 봄.",
        direction="군집 ID를 유지하되,\n투수 58d + 타자 58d feature를\nobservation에 직접 concat.",
        effect="강타자/뜬공형/컨택형 같은 matchup 차이를\n정책망이 직접 인지.\n상황·상대별 추천 설명력과 일반화 향상.",
    )
    focus_card(
        ax,
        0.685,
        card_y,
        0.270,
        card_h,
        color=GREEN,
        light=GREEN_L,
        tag="P2",
        title="Dyna-Q Planning 효율화",
        why="193d 전이모델은 빠른 확률 예측이 가능.\nModel-free PPO/DQN은 많은 실제 rollout이 필요.",
        direction="전이모델을 내부 simulator로 사용.\nDyna-Q planning 횟수(n_sweeps)와\nprioritized planning 튜닝.",
        effect="적은 episode로 높은 reward 정책 학습.\n전이모델의 확률 품질을 planning에 100% 활용.",
    )

    # Roadmap arrow
    y0 = 0.235
    box(ax, 0.075, y0, 0.235, 0.058, fc=RED_L, ec=RED, lw=1.2, r=0.012)
    box(ax, 0.385, y0, 0.235, 0.058, fc=GOLD_L, ec=GOLD, lw=1.2, r=0.012)
    box(ax, 0.695, y0, 0.235, 0.058, fc=GREEN_L, ec=GREEN, lw=1.2, r=0.012)
    txt(ax, 0.192, y0 + 0.029, "1) 환경 정상화\n193d transition model", size=8.8, color=RED, weight="bold", ls=1.0)
    txt(ax, 0.502, y0 + 0.029, "2) 정책 입력 확장\nfeature-aware RL state", size=8.8, color="#6B4A00", weight="bold", ls=1.0)
    txt(ax, 0.812, y0 + 0.029, "3) planning 극대화\nDyna-Q sweep tuning", size=8.8, color=GREEN_D, weight="bold", ls=1.0)
    arrow(ax, (0.310, y0 + 0.029), (0.385, y0 + 0.029), color=SUB, lw=1.6, scale=12)
    arrow(ax, (0.620, y0 + 0.029), (0.695, y0 + 0.029), color=SUB, lw=1.6, scale=12)

    # Validation strip
    box(ax, 0.055, 0.105, 0.890, 0.085, fc="#FFFFFF", ec=LINE, lw=1.2, r=0.012)
    txt(ax, 0.500, 0.148,
        "검증 지표: 전이확률 단계는 CE/Brier/rare-class recall, 최종 추천 단계는 MDP Reward·ΔRandom·상황별 pitch-zone heatmap으로 평가",
        size=9.8, color=INK, weight="bold")

    txt(ax, 0.055, 0.055, "Future-work slide generated from current project diagnosis: hit-probability restoration → feature-aware policy → model-based planning",
        size=7.7, color=SUB, ha="left")

    png = OUT_DIR / "future_work_roadmap_slide.png"
    svg = OUT_DIR / "future_work_roadmap_slide.svg"
    fig.savefig(png, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(svg, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return png, svg


def main() -> None:
    set_korean_font()
    outputs = [*draw_full_pipeline(), *draw_future_slide()]
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
