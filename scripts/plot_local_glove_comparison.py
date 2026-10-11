"""Plot a saved development comparison; no images, weights, or inference required."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError("Use a new plot path")
    data = json.loads(args.input.read_text(encoding="utf-8"))
    if data.get("schema") != "local_glove_development_comparison_v1":
        raise ValueError("Expected a saved local development comparison")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = {
        "ssdlite_full_cuda": "SSDLite / full / GPU",
        "ssdlite_crop_cuda": "SSDLite / crop / GPU",
        "fasterrcnn_full_cuda": "Faster R-CNN / full / GPU",
        "fasterrcnn_crop_cuda": "Faster R-CNN / crop / GPU",
        "fasterrcnn_crop_cpu": "Faster R-CNN / crop / CPU",
    }
    arms = data["arms"]
    labels = [names[arm["arm"]] for arm in arms]
    colors = ["#f59e0b", "#f59e0b", "#14b8a6", "#14b8a6", "#60a5fa"]
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 10}):
        fig, axes = plt.subplots(1, 3, figsize=(15, 5.6), gridspec_kw={"wspace": 0.58})
        fig.patch.set_facecolor("#f7fafc")
        for ax in axes:
            ax.set_facecolor("#f7fafc")
            ax.spines[["top", "right", "left"]].set_visible(False)
            ax.grid(axis="x", alpha=0.15)
            ax.set_axisbelow(True)
            ax.set_yticks(range(len(arms)))
            ax.set_ylim(len(arms) - 0.4, -0.6)
        axes[0].set_yticklabels(labels)
        for ax in axes[1:]:
            ax.set_yticklabels([])
        coverage = [arm["first_pass_summary"]["counts"]["candidate"] for arm in arms]
        axes[0].barh(range(len(arms)), coverage, color=colors, height=0.54)
        for i, (value, arm) in enumerate(zip(coverage, arms, strict=True)):
            axes[0].text(value + 1, i, f"{value}/{arm['planned_frames']}", va="center")
        axes[0].set_xlim(0, max(arm["planned_frames"] for arm in arms) * 1.18)
        axes[0].set_title("Candidate output\n(first pass, not accuracy)", pad=18, loc="left")
        axes[0].set_xlabel("Frames with exactly one score >= 0.5")

        distances = [
            arm["first_pass_summary"]["conditional_point_discrepancy"]["distance_pixels"]
            for arm in arms
        ]
        max_distance = max((row["median"] or 0 for row in distances), default=1) or 1
        for i, row in enumerate(distances):
            if row["median"] is None:
                axes[1].text(0, i, "No paired points", va="center", color="#64748b")
            else:
                axes[1].barh(i, row["median"], color=colors[i], height=0.54)
                axes[1].text(
                    row["median"] + max_distance * 0.025,
                    i,
                    f"{row['median']:.1f}px (n={row['n']})",
                    va="center",
                )
        axes[1].set_xlim(0, max_distance * 1.75)
        axes[1].set_title("Difference from legacy points\n(conditional median)", pad=18, loc="left")
        axes[1].set_xlabel("Original 1280 x 720 image pixels")

        times = [arm["service_seconds_all_passes"] for arm in arms]
        max_time = max(row["p95"] for row in times) * 1000
        for i, row in enumerate(times):
            value = row["median"] * 1000
            axes[2].barh(i, value, color=colors[i], height=0.54)
            axes[2].plot([value, row["p95"] * 1000], [i, i], color="#334155", linewidth=1.4)
            axes[2].text(row["p95"] * 1000 + max_time * 0.025, i, f"{value:.0f}ms", va="center")
        axes[2].set_xlim(0, max_time * 1.5)
        axes[2].set_title(
            "Local frame service time\n(median; line extends to p95)", pad=18, loc="left"
        )
        axes[2].set_xlabel("Milliseconds, model already loaded")
        fig.suptitle(
            "Pitcheezy | Local glove detector development comparison",
            x=0.06,
            ha="left",
            fontsize=18,
            fontweight="bold",
        )
        fig.text(
            0.06,
            0.06,
            "Previously reviewed 86 frames; 84 legacy points. Manual fixed crop; generic glove box center.\nGPU: 258 timing attempts/arm; CPU: 86. No verified catcher role, physical accuracy, or live/pre-pitch claim.",
            color="#475569",
            fontsize=10,
        )
        fig.subplots_adjust(left=0.2, right=0.98, top=0.76, bottom=0.23)
        fig.savefig(args.out, dpi=170, facecolor=fig.get_facecolor())
        plt.close(fig)


if __name__ == "__main__":
    main()
