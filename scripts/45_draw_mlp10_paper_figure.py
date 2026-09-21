"""Paper-style figure for the MLP10 transition probability model.

Emphasises the MLP's defining characteristics: a fully-connected (dense)
feed-forward network that maps one (state, action) feature vector to a
softmax distribution over 10 pitch outcomes, with no temporal/sequence
input. Layout follows a left-to-right "data -> processing -> output" flow
typical of ML method figures.

Outputs:
    outputs/figures/mlp10_paper_figure.png
    outputs/figures/mlp10_paper_figure.svg
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# --- palette (muted, print-friendly) -------------------------------------
INK = "#1A1A1A"
SUB = "#5B5B5B"
GREEN = "#2C5F2D"
GREEN_L = "#7EA184"
BLUE = "#3E6B89"
GOLD = "#C49A3A"
LINE = "#D9E1DB"
PANEL = "#F7FAF8"
PALE = "#EAF0E8"

# segment colours for the 135-dim input composition
SEG = [
    ("Otremba base", 77, "#2C5F2D"),
    ("UMAP 5d (=0)", 5, "#9BBB59"),
    ("count", 1, "#4BACC6"),
    ("arsenal_func", 32, "#81B29A"),
    ("arsenal_moment", 20, "#C7DCA7"),
]


def set_korean_font() -> None:
    preferred = ["Malgun Gothic", "NanumGothic", "Noto Sans CJK KR", "Arial Unicode MS"]
    installed = {f.name for f in fm.fontManager.ttflist}
    for name in preferred:
        if name in installed:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


def rbox(ax, x, y, w, h, *, fc="#FFFFFF", ec=GREEN, lw=1.4, r=0.016, z=2, ls="-"):
    p = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.010,rounding_size={r}",
        linewidth=lw, edgecolor=ec, facecolor=fc, zorder=z, linestyle=ls,
    )
    ax.add_patch(p)
    return p


def txt(ax, x, y, s, *, size=10, color=INK, weight="normal", ha="center",
        va="center", ls=1.2, z=5, style="normal", rot=0):
    ax.text(x, y, s, fontsize=size, color=color, fontweight=weight, ha=ha,
            va=va, linespacing=ls, zorder=z, fontstyle=style, rotation=rot)


def arrow(ax, p0, p1, *, color=GREEN, lw=2.2, scale=16):
    ax.add_patch(FancyArrowPatch(
        p0, p1, arrowstyle="-|>", mutation_scale=scale, linewidth=lw,
        color=color, zorder=10, shrinkA=3, shrinkB=3))


def draw_input_panel(ax, x, y, w, h):
    """Stage 1: one (state, action) query -> 135-dim feature vector."""
    txt(ax, x + w / 2, y + h + 0.034, "① 입력  (single state–action query)",
        size=12.5, color=GREEN, weight="bold")
    rbox(ax, x, y, w, h, fc=PANEL, ec=GREEN, lw=1.6)

    rows = [
        ("Game state  s", "balls·strikes·outs / runners\ninning / batter·pitcher hands"),
        ("Action  a", "pitch type × zone\n(예: FF-Z5, SL-Z14)"),
        ("Pitcher context", "cluster id · arsenal profile\n(투수 레퍼토리 통계)"),
    ]
    ry = y + h - 0.060
    for title, body in rows:
        txt(ax, x + 0.014, ry, title, size=9.6, weight="bold", ha="left")
        txt(ax, x + 0.014, ry - 0.040, body, size=8.4, color=SUB, ha="left", ls=1.15)
        ry -= 0.120
        if title != rows[-1][0]:
            ax.plot([x + 0.014, x + w - 0.014], [ry + 0.038, ry + 0.038],
                    color=LINE, lw=1)

    # composition bar of the 135-dim vector
    bx, by, bw, bh = x + 0.014, y + 0.042, w - 0.028, 0.052
    txt(ax, x + w / 2, by + bh + 0.028, "→  135-dim feature vector  x",
        size=9.2, color=GREEN, weight="bold")
    total = sum(v for _, v, _ in SEG)
    cur = bx
    for label, v, c in SEG:
        pw = bw * v / total
        ax.add_patch(Rectangle((cur, by), pw, bh, facecolor=c,
                               edgecolor="#FFFFFF", lw=0.8, zorder=4))
        if v >= 5:
            txt(ax, cur + pw / 2, by + bh / 2, str(v), size=7.6,
                color="#FFFFFF", weight="bold")
        cur += pw
    ax.add_patch(Rectangle((bx, by), bw, bh, fill=False,
                           edgecolor="#1F3B2D", lw=1.1, zorder=5))


def draw_mlp_panel(ax, x, y, w, h):
    """Stage 2: the fully-connected MLP itself (the focus of the figure)."""
    txt(ax, x + w / 2, y + h + 0.034,
        "② MLP10  —  fully-connected feed-forward network",
        size=12.5, color=GREEN, weight="bold")
    rbox(ax, x, y, w, h, fc="#FFFFFF", ec=GREEN, lw=1.6)

    # four layers: input(135) - hidden(128) - hidden(128) - logits(10)
    layer_labels = ["Input\n135", "Hidden 1\n128", "Hidden 2\n128", "Logits\n10"]
    layer_sub = ["x", "ReLU", "ReLU", "z"]
    xs = [x + w * r for r in (0.13, 0.40, 0.66, 0.90)]
    # vertical node positions (a visual sample of each layer's units)
    n_show = 7
    cy = y + h * 0.50
    spread = h * 0.30
    node_ys = [cy - spread + 2 * spread * i / (n_show - 1) for i in range(n_show)]
    logit_ys = [cy - spread * 0.62 + 2 * spread * 0.62 * i / 4 for i in range(5)]

    layer_nodes = [node_ys, node_ys, node_ys, logit_ys]

    # dense edges between consecutive layers -> the "fully-connected" look
    for i in range(3):
        for ya in layer_nodes[i]:
            for yb in layer_nodes[i + 1]:
                ax.plot([xs[i] + 0.012, xs[i + 1] - 0.012], [ya, yb],
                        color=GREEN_L, lw=0.4, alpha=0.32, zorder=3)

    # nodes
    for li, lx in enumerate(xs):
        fc = PALE if li < 3 else "#FBF3DD"
        ec = GREEN if li < 3 else GOLD
        for yy in layer_nodes[li]:
            ax.add_patch(Circle((lx, yy), 0.0098, facecolor=fc, edgecolor=ec,
                                lw=1.1, zorder=6))
        # ellipsis to signal omitted units in the wide layers
        if li < 3:
            txt(ax, lx, cy - spread - 0.030, r"$\vdots$", size=13, color=GREEN, weight="bold")
        txt(ax, lx, cy + spread + 0.052, layer_labels[li], size=8.2,
            color=GREEN if li < 3 else GOLD, weight="bold", ls=0.95)
        txt(ax, lx, cy + spread + 0.012, layer_sub[li], size=7.4,
            color=SUB, style="italic")

    # operation annotations beneath each gap (kept to 2 lines to avoid crowding)
    ops = [
        ((xs[0] + xs[1]) / 2, "Linear 135→128\nReLU · Dropout .2"),
        ((xs[1] + xs[2]) / 2, "Linear 128→128\nReLU · Dropout .2"),
        ((xs[2] + xs[3]) / 2, "Linear\n128→10"),
    ]
    for ox, label in ops:
        txt(ax, ox, cy - spread - 0.055, label, size=7.0, color=INK,
            weight="bold", ls=1.1)

    # footer: defining property of an MLP (no sequence / i.i.d.)
    txt(ax, x + w / 2, y + 0.016,
        "i.i.d. 한 투구만 입력 · history sequence 없음 · ~28K params",
        size=8.0, color=SUB, style="italic")


def draw_output_panel(ax, x, y, w, h):
    """Stage 3: softmax -> 10-class probability distribution (a bar plot)."""
    txt(ax, x + w / 2, y + h + 0.034, "③ 출력  P(outcome | s, a)",
        size=12.5, color=GREEN, weight="bold")
    rbox(ax, x, y, w, h, fc=PANEL, ec=GREEN, lw=1.6)

    # softmax tag
    rbox(ax, x + 0.018, y + h - 0.066, w - 0.036, 0.044, fc=PALE, ec=GREEN,
         lw=1.1, r=0.012)
    txt(ax, x + w / 2, y + h - 0.044, r"softmax(z) :  $\sum_i p_i = 1$",
        size=9.4, weight="bold")

    classes = ["Ball", "Strike", "Single", "Double", "Triple",
               "HomeRun", "FieldOut", "Strikeout", "Walk", "HBP"]
    # illustrative probabilities (shape only — not exact model output)
    probs = [0.34, 0.27, 0.05, 0.015, 0.004, 0.012, 0.10, 0.11, 0.085, 0.014]

    # bars are distributed to fill the panel height below the softmax tag
    bx = x + 0.112
    bw_max = w - 0.112 - 0.024
    top = y + h - 0.094
    bottom = y + 0.030
    n = len(classes)
    per = (top - bottom) / n
    bh = per * 0.66
    pmax = max(probs)
    for i, (cname, p) in enumerate(zip(classes, probs)):
        yy = top - (i + 1) * per + (per - bh) / 2
        # highlight the two dominant outcomes
        col = GREEN if p >= 0.25 else (BLUE if p >= 0.09 else GREEN_L)
        txt(ax, bx - 0.010, yy + bh / 2, cname, size=7.8, ha="right",
            color=INK, weight="bold" if p >= 0.09 else "normal")
        ax.add_patch(Rectangle((bx, yy), bw_max * p / pmax, bh, facecolor=col,
                               edgecolor="none", zorder=4))
        ax.add_patch(Rectangle((bx, yy), bw_max, bh, fill=False,
                               edgecolor=LINE, lw=0.7, zorder=3))
        txt(ax, bx + bw_max * p / pmax + 0.006, yy + bh / 2, f"{p:.2f}",
            size=7.0, ha="left", color=SUB)


def main() -> None:
    set_korean_font()
    fig, ax = plt.subplots(figsize=(16.5, 8.4), dpi=190)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("#FFFFFF")

    # header
    txt(ax, 0.035, 0.965, "MLP10 Transition Probability Model",
        size=23, weight="bold", ha="left", va="top")
    txt(ax, 0.035, 0.915,
        "한 (state, action) 쌍을 10-class 투구 결과 확률분포로 사상하는 "
        "fully-connected MLP  ·  OtrembaMLP(135→128→128→10), focal loss",
        size=11, color=SUB, ha="left", va="top")
    ax.plot([0.035, 0.965], [0.888, 0.888], color=LINE, lw=1.3)

    # three panels — widths balanced so each is sized to its content
    y, h = 0.255, 0.515
    p1x, p1w = 0.035, 0.278
    p2x, p2w = 0.353, 0.352
    p3x, p3w = 0.740, 0.225

    draw_input_panel(ax, p1x, y, p1w, h)
    draw_mlp_panel(ax, p2x, y, p2w, h)
    draw_output_panel(ax, p3x, y, p3w, h)

    # flow arrows between panels
    cy = y + h * 0.5
    arrow(ax, (p1x + p1w + 0.004, cy), (p2x - 0.004, cy))
    arrow(ax, (p2x + p2w + 0.004, cy), (p3x - 0.004, cy))

    # downstream note (two lines so it fits inside the box)
    rbox(ax, 0.035, 0.105, 0.930, 0.098, fc="#FFFDF7", ec=GOLD, lw=1.2, r=0.012)
    txt(ax, 0.500, 0.154,
        "MLP의 특성 — 순서(history)를 보지 않고 현재 (s, a)만으로 확률을 내므로 모든 행동에 대해 batch inference가 가능하다.\n"
        "그 확률을 그대로 MDP Value Iteration의 전이확률 p(o | s, a)로 사용한다.",
        size=10.0, color="#4A3A14", weight="bold", ls=1.45)

    txt(ax, 0.035, 0.045,
        "Source: transition-models/src/models/otremba_mlp.py · "
        "src/inference/transition_model.py (TransitionModelMLP10)",
        size=8, color="#888888", ha="left")

    png = OUT_DIR / "mlp10_paper_figure.png"
    svg = OUT_DIR / "mlp10_paper_figure.svg"
    fig.savefig(png, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(svg, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(png)
    print(svg)


if __name__ == "__main__":
    main()
