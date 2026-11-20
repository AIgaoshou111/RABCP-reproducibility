"""Plot the fixed-cohort prefix and mixed-noise panels of Figure 2."""

import argparse
import csv
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "results/manuscript_tables",
        help="directory containing the two fixed-cohort CSVs",
    )
    parser.add_argument("--output", type=Path, default=Path("figure2.pdf"))
    args = parser.parse_args()
    prefix = rows(args.source / "序列长度敏感性实验结果.csv")
    noise = rows(args.source / "噪声鲁棒性实验结果.csv")
    methods = [
        ("cumulative_mean", "Mean", "#25394a"),
        ("bae_smoothing", "Smoothed", "#a94c38"),
        ("weighted_bae_noise_flag", "Rel.-weighted", "#00776c"),
    ]
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.5, 2.7), layout="constrained")
    for (m, label, c), marker, line in zip(methods, ["o", "s", "D"], ["--", "-", "-"]):
        subset = sorted(
            (r for r in prefix if r["method"] == m),
            key=lambda r: int(r["prefix_length"]),
        )
        x = [int(r["prefix_length"]) for r in subset]
        y = [float(r["mae_all"]) for r in subset]
        assert x == [5, 10, 20, 30, 40]
        a.plot(x, y, marker=marker, linestyle=line, color=c, label=label)
    a.set(
        xticks=x,
        xlabel="Questions observed",
        ylabel="MAE over sequence",
        title="(a) Sequence length sensitivity",
    )
    a.legend(frameon=False, fontsize=8)
    cohort = {
        r["method"]: float(r["mae_after_10"])
        for r in noise
        if r["noise_mode"] == "mixed_noise" and float(r["noise_ratio"]) == 0.6
    }
    methods = [("raw", "Raw", "#74685e"), *methods]
    values = [cohort[m] for m, _, _ in methods]
    bars = b.bar(range(4), values, color=[c for _, _, c in methods])
    b.bar_label(bars, fmt="%.3f", fontsize=8)
    b.set(
        xticks=range(4),
        xticklabels=[label for _, label, _ in methods],
        ylabel="MAE@10",
        ylim=(0, 0.83),
        title="(b) Mixed-noise robustness",
    )
    for ax in (a, b):
        ax.spines[["right", "top"]].set_visible(False)
    fig.savefig(args.output)
    print("Fixed-cohort bars:", ", ".join(f"{v:.3f}" for v in values))


if __name__ == "__main__":
    main()
