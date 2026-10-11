"""Compare saved local replay publication delays without invoking models."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="append", type=Path, required=True)
    parser.add_argument("--label", action="append", required=True)
    parser.add_argument("--note", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if len(args.report) != len(args.label):
        raise ValueError("Every report needs one explicit label")
    reports = [json.loads(path.read_bytes()) for path in args.report]
    expected = [row["cutoff_seconds_exact"] for row in reports[0]["observations"]]
    if len(expected) != 10:
        raise ValueError("Expected the registered ten-cutoff study")
    figure, axes = plt.subplots(1, 2, figsize=(13, 5.8))
    colors = ("#8b6266", "#407c9c", "#228673")
    for report, label, color in zip(reports, args.label, colors, strict=True):
        rows = report["observations"]
        if [row["cutoff_seconds_exact"] for row in rows] != expected:
            raise ValueError("Cannot compare different input schedules")
        if report["counts"]["accepted"] != 10:
            raise ValueError("This plot expects complete runs; do not silently drop failures")
        delays = [row["publication_seconds"] for row in rows]
        for axis in axes:
            axis.plot(range(1, 11), delays, marker="o", color=color, label=label)
            axis.set_xticks(range(1, 11))
            axis.set_xlabel("Fixed observation index")
    for axis in axes:
        axis.axhline(5, color="#ad7532", linestyle="--", linewidth=1.4, label="5-second target")
        axis.set_ylabel("Scheduled input to validated publication (seconds)")
        axis.grid(alpha=0.17)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].set_title("All recorded delays")
    axes[0].set_ylim(bottom=0)
    axes[1].set_title("0–35 seconds detail (higher delays clipped)")
    axes[1].set_ylim(0, 35)
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.93), ncol=2)
    figure.suptitle("Same ten known frames: engineering latency comparison", fontsize=15, y=0.995)
    figure.text(0.5, 0.065, args.note, ha="center", fontsize=10)
    figure.text(
        0.5,
        0.025,
        "One sequential run per mode; not independent mitt accuracy or live-broadcast validation.",
        ha="center",
        fontsize=9,
        color="#555555",
    )
    figure.tight_layout(rect=(0, 0.11, 1, 0.80))
    if args.out.exists():
        raise FileExistsError(args.out)
    figure.savefig(args.out, dpi=150, facecolor="white")
    plt.close(figure)


if __name__ == "__main__":
    main()
