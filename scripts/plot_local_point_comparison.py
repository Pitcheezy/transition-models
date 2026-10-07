"""Plot saved cross-game conditional point discrepancies; never invoke a model."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_bytes())
    if report.get("status") != "completed" or report.get("results_usable") is not True:
        raise ValueError("A complete, usable saved report is required")
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    colors = ("#1b8578", "#8b939f", "#cb7936")
    labels = ("TinyCNN final epoch", "Fixed crop center", "Training-game mean")
    for column, train in enumerate((823407, 849845)):
        arms = sorted(
            (arm for arm in report["arms"] if arm["train_game"] == train),
            key=lambda arm: arm["seed"],
        )
        if len(arms) != 3 or any(
            arm["prediction_states"] != {"completed": arm["planned_marked"]} for arm in arms
        ):
            raise ValueError("Expected three complete seed arms in each direction")
        for row, metric in enumerate(("median", "p90")):
            axis = axes[row, column]
            values = [
                [arm["model_errors"]["distance_pixels"][metric] for arm in arms],
                *[
                    [
                        arm["baselines_all_marked"][baseline]["errors"]["distance_pixels"][metric]
                        for arm in arms
                    ]
                    for baseline in ("crop_center", "training_game_mean")
                ],
            ]
            for index, (series, color, label) in enumerate(
                zip(values, colors, labels, strict=True)
            ):
                bars = axis.bar(
                    np.arange(3) + (index - 1) * 0.25, series, 0.24, color=color, label=label
                )
                axis.bar_label(bars, fmt="%.1f", fontsize=9, padding=3)
            axis.set_ylim(0, max(max(series) for series in values) * 1.22)
            axis.set_ylabel(f"{metric} distance (original pixels)")
            axis.set_xticks(np.arange(3), [f"Seed {arm['seed']}" for arm in arms])
            axis.grid(axis="y", alpha=0.18)
            axis.set_axisbelow(True)
            axis.spines[["top", "right"]].set_visible(False)
            if row == 0:
                axis.set_title(
                    f"Train {train} / evaluate {arms[0]['test_game']}\n"
                    f"{arms[0]['planned_marked']} marked frames per seed"
                )
    fig.suptitle(
        "Conditional point regression on two previously reviewed games", fontsize=16, y=0.98
    )
    handles, legend_labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc="upper center", bbox_to_anchor=(0.5, 0.925), ncol=3)
    fig.text(
        0.5,
        0.025,
        "Known marked frames + manually fixed crops; 84 unique frames, not 252 independent samples.\n"
        "Distance to legacy single-labeler points; not detection, independent accuracy, or pitcher intent.",
        ha="center",
        fontsize=10,
        color="#454b53",
    )
    fig.tight_layout(rect=(0, 0.09, 1, 0.875), h_pad=2.0)
    if args.out.exists():
        raise FileExistsError(args.out)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=150, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
