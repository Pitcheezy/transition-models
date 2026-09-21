"""Draw a clean paper-style diagram for the MLP10 transition model.

Outputs:
    outputs/figures/mlp10_transition_model_architecture.png
    outputs/figures/mlp10_transition_model_architecture.svg
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle


matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

GREEN = "#2C5F2D"
DARK = "#1A1A1A"
MID = "#666666"
LIGHT = "#F7FAF8"
PALE = "#EAF0E8"
GOLD = "#C49A3A"
LINE = "#DDE6DF"


def set_korean_font() -> None:
    preferred = ["Malgun Gothic", "NanumGothic", "Noto Sans CJK KR", "Arial Unicode MS"]
    installed = {f.name for f in fm.fontManager.ttflist}
    for name in preferred:
        if name in installed:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


def rounded_box(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fc: str = "#FFFFFF",
    ec: str = GREEN,
    lw: float = 1.5,
    radius: float = 0.018,
    zorder: int = 2,
):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.012,rounding_size={radius}",
        linewidth=lw,
        edgecolor=ec,
        facecolor=fc,
        zorder=zorder,
    )
    ax.add_patch(patch)
    return patch


def add_text(
    ax,
    x: float,
    y: float,
    text: str,
    *,
    size: float = 10,
    color: str = DARK,
    weight: str = "normal",
    ha: str = "center",
    va: str = "center",
    linespacing: float = 1.22,
    zorder: int = 5,
):
    ax.text(
        x,
        y,
        text,
        fontsize=size,
        color=color,
        fontweight=weight,
        ha=ha,
        va=va,
        linespacing=linespacing,
        zorder=zorder,
    )


def arrow(ax, start: tuple[float, float], end: tuple[float, float]) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=18,
            linewidth=2.2,
            color=GREEN,
            zorder=10,
            shrinkA=4,
            shrinkB=4,
        )
    )


def stage(ax, n: int, title: str, x: float, y: float, w: float, h: float) -> None:
    rounded_box(ax, x, y, w, h, fc=LIGHT, ec=GREEN, lw=1.7)
    add_text(ax, x + w / 2, y + h - 0.045, f"{n}. {title}", size=12, color=GREEN, weight="bold")


def feature_bar(ax, x: float, y: float, w: float, h: float) -> None:
    parts = [
        ("77", 77, GREEN),
        ("5", 5, "#9BBB59"),
        ("1", 1, "#4BACC6"),
        ("32", 32, "#81B29A"),
        ("20", 20, "#C7DCA7"),
    ]
    total = sum(v for _, v, _ in parts)
    cursor = x
    for label, size, color in parts:
        pw = w * size / total
        ax.add_patch(Rectangle((cursor, y), pw, h, facecolor=color, edgecolor="#FFFFFF", linewidth=0.8, zorder=4))
        if size >= 20:
            add_text(ax, cursor + pw / 2, y + h / 2, label, size=8, color="#FFFFFF", weight="bold")
        cursor += pw
    ax.add_patch(Rectangle((x, y), w, h, fill=False, edgecolor="#1F3B2D", linewidth=1.1, zorder=5))


def draw_mlp(ax, x: float, y: float, w: float, h: float) -> None:
    labels = ["Input\n135", "Hidden\n128", "Hidden\n128", "Logits\n10"]
    xs = [x + w * r for r in [0.17, 0.39, 0.61, 0.83]]
    node_ys = [y + h * r for r in [0.28, 0.38, 0.48, 0.58, 0.68, 0.78]]

    for lx, label in zip(xs, labels):
        add_text(ax, lx, y + h * 0.86, label, size=7.8, color=GREEN, weight="bold", linespacing=0.9)

    # Fully connected layer-to-layer edges. Draw these above the stage box
    # but below the nodes so the MLP structure is visible without dominating.
    for i in range(len(xs) - 1):
        for yy1 in node_ys:
            for yy2 in node_ys:
                ax.plot(
                    [xs[i] + 0.010, xs[i + 1] - 0.010],
                    [yy1, yy2],
                    color="#7EA184",
                    linewidth=0.45,
                    alpha=0.38,
                    zorder=4,
                )

    for lx in xs:
        for yy in node_ys:
            ax.add_patch(Circle((lx, yy), 0.0105, facecolor=PALE, edgecolor=GREEN, linewidth=1.0, zorder=6))

    # Ellipses indicate omitted units from the high-dimensional layers.
    for lx in xs:
        add_text(ax, lx, y + h * 0.225, "...", size=11, color=GREEN, weight="bold")

    add_text(
        ax,
        x + w / 2,
        y + h * 0.11,
        "Dense + ReLU + Dropout(.2)\n135 -> 128 -> 128 -> 10",
        size=7.8,
        color=DARK,
        weight="bold",
        linespacing=1.1,
    )


def main() -> None:
    set_korean_font()
    fig, ax = plt.subplots(figsize=(17, 9.5), dpi=180)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("#FFFFFF")

    # Header
    add_text(ax, 0.04, 0.95, "MLP10 Transition Probability Model", size=24, weight="bold", ha="left", va="top")
    add_text(
        ax,
        0.04,
        0.905,
        "RL-agent에서 쓰는 135-dim, 10-class focal-loss MLP:  P(outcome | state, action)",
        size=12,
        color=MID,
        ha="left",
        va="top",
    )
    ax.plot([0.04, 0.96], [0.875, 0.875], color=LINE, linewidth=1.3)

    y, h, w = 0.30, 0.49, 0.16
    xs = [0.04, 0.235, 0.43, 0.625, 0.82]

    # Stage 1
    stage(ax, 1, "Inputs", xs[0], y, w, h)
    add_text(
        ax,
        xs[0] + w / 2,
        y + 0.345,
        "Game state s\nballs / strikes / outs\nrunners / inning / hands",
        size=9.1,
        weight="bold",
    )
    ax.plot([xs[0] + 0.025, xs[0] + w - 0.025], [y + 0.285, y + 0.285], color=LINE, linewidth=1)
    add_text(
        ax,
        xs[0] + w / 2,
        y + 0.225,
        "Candidate action a\npitch type x zone\n예: FF-Z5, SL-Z14",
        size=9.1,
        weight="bold",
    )
    ax.plot([xs[0] + 0.025, xs[0] + w - 0.025], [y + 0.165, y + 0.165], color=LINE, linewidth=1)
    add_text(
        ax,
        xs[0] + w / 2,
        y + 0.105,
        "Pitcher context\ncluster, arsenal profile\npitch physics defaults",
        size=8.8,
        color=MID,
        weight="bold",
    )

    # Stage 2
    stage(ax, 2, "Feature Builder", xs[1], y, w, h)
    add_text(
        ax,
        xs[1] + w / 2,
        y + 0.335,
        "single pitch vector\nfor one (s, a) query",
        size=9.2,
        weight="bold",
    )
    feature_bar(ax, xs[1] + 0.015, y + 0.255, w - 0.03, 0.055)
    add_text(ax, xs[1] + w / 2, y + 0.225, "135-dim feature vector", size=8.7, color=GREEN, weight="bold")
    add_text(
        ax,
        xs[1] + w / 2,
        y + 0.145,
        "[0:77] Otremba base\nphysics15 + pitch17 + zone14\ncount/state/hands/inning",
        size=7.7,
        color=MID,
        weight="bold",
    )
    add_text(
        ax,
        xs[1] + w / 2,
        y + 0.055,
        "[77:135] cluster/arsenal\nUMAP5(0) + count1\nfunc32 + moment20",
        size=7.7,
        color=MID,
        weight="bold",
    )

    # Stage 3
    stage(ax, 3, "MLP10", xs[2], y, w, h)
    draw_mlp(ax, xs[2] + 0.005, y + 0.03, w - 0.01, h - 0.09)

    # Stage 4
    stage(ax, 4, "Outcome Prob.", xs[3], y, w, h)
    rounded_box(ax, xs[3] + 0.025, y + 0.315, w - 0.05, 0.09, fc=PALE, ec=GREEN, lw=1.2, radius=0.014)
    add_text(ax, xs[3] + w / 2, y + 0.36, "Softmax\nsum p_i = 1", size=10.2, weight="bold", linespacing=1.05)
    add_text(
        ax,
        xs[3] + w / 2,
        y + 0.195,
        "10-class probability\n\nBall, Strike,\nSingle, Double, Triple,\nHomeRun, FieldOut,\nStrikeout, Walk, HBP",
        size=8.4,
        weight="bold",
        linespacing=1.13,
    )

    # Stage 5
    stage(ax, 5, "MDP Policy", xs[4], y, w, h)
    add_text(
        ax,
        xs[4] + w / 2,
        y + 0.335,
        "Transition expansion\np(o | s,a) -> s', r, done",
        size=8.8,
        weight="bold",
    )
    ax.plot([xs[4] + 0.025, xs[4] + w - 0.025], [y + 0.27, y + 0.27], color=LINE, linewidth=1)
    add_text(
        ax,
        xs[4] + w / 2,
        y + 0.205,
        "Value Iteration\nQ(s,a)=sum p(r + gamma V)",
        size=8.5,
        weight="bold",
    )
    ax.plot([xs[4] + 0.025, xs[4] + w - 0.025], [y + 0.145, y + 0.145], color=LINE, linewidth=1)
    rounded_box(ax, xs[4] + 0.025, y + 0.045, w - 0.05, 0.075, fc="#FFFDF7", ec=GOLD, lw=1.2, radius=0.014)
    add_text(ax, xs[4] + w / 2, y + 0.082, "recommended\npitch type + zone", size=8.4, color="#4A3A14", weight="bold", linespacing=1.05)

    # Direction arrows
    center_y = y + h / 2
    for i in range(4):
        arrow(ax, (xs[i] + w + 0.006, center_y), (xs[i + 1] - 0.006, center_y))

    # Bottom explanation band
    rounded_box(ax, 0.04, 0.145, 0.92, 0.09, fc="#FFFDF7", ec=GOLD, lw=1.2, radius=0.014)
    add_text(
        ax,
        0.50,
        0.19,
        "MLP10의 핵심: history sequence 없이 현재 state-action만으로 확률분포를 만들기 때문에, 모든 (s,a)에 대해 batch inference 후 MDP Value Iteration에 바로 넣을 수 있다.",
        size=10.0,
        color="#4A3A14",
        weight="bold",
    )

    add_text(
        ax,
        0.04,
        0.055,
        "Implementation basis: transition-models/src/inference/transition_model.py, rl-agent/src/envs/feature_builder.py, rl-agent/src/agents/mdp_vi.py",
        size=8,
        color="#777777",
        ha="left",
    )

    png_path = OUT_DIR / "mlp10_transition_model_architecture.png"
    svg_path = OUT_DIR / "mlp10_transition_model_architecture.svg"
    fig.savefig(png_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(svg_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(png_path)
    print(svg_path)


if __name__ == "__main__":
    main()
