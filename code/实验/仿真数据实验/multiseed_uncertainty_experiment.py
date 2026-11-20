"""Multi-seed uncertainty analysis for the main synthetic claims.

Each replicate regenerates the complete balanced synthetic cohort (420 users,
40 turns) with an independent seed.  Results are summarized across seeds so
that the intervals reflect variation in the synthetic generation process.
"""

import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path


EXPERIMENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EXPERIMENT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(EXPERIMENT_DIR))

from generate_dataset import build_full_dataset
from 状态估计实验 import METHODS, aggregate as state_aggregate, evaluate_user, group_by_user
from 序列长度敏感性实验 import CORE_METHODS, PREFIX_LENGTHS, aggregate as prefix_aggregate, evaluate_prefix
from 噪声鲁棒性实验 import inject_noise


SEEDS = list(range(20260714, 20260764))
SELECTED_PREFIX_METHODS = [
    "cumulative_mean",
    "bae_smoothing",
    "weighted_bae_noise_flag",
]
SELECTED_NOISE_METHODS = [
    "cumulative_mean",
    "bae_plain",
    "bae_smoothing",
    "weighted_bae_noise_flag",
]
SELECTED_NOISE_RATIOS = [0.4, 0.6]

SEED_RESULTS = EXPERIMENT_DIR / "multiseed_uncertainty_seed_results.csv"
SUMMARY_RESULTS = EXPERIMENT_DIR / "multiseed_uncertainty_summary.csv"
REPORT = EXPERIMENT_DIR / "multiseed_uncertainty_report.md"


def quantile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def summarize(values):
    return {
        "mean": statistics.mean(values),
        "sd": statistics.stdev(values),
        "ci_low": quantile(values, 0.025),
        "ci_high": quantile(values, 0.975),
    }


def run_seed(seed):
    dataset = build_full_dataset(users_per_group=3, questions_per_user=40, seed=seed)
    users = group_by_user(dataset)
    rows = []

    prefix_results = []
    for user_rows in users.values():
        for prefix_length in PREFIX_LENGTHS:
            prefix_results.extend(evaluate_prefix(user_rows, prefix_length))
    prefix_groups = defaultdict(list)
    for result in prefix_results:
        prefix_groups[(result["prefix_length"], result["method"])].append(result)
    for prefix_length in PREFIX_LENGTHS:
        for method in SELECTED_PREFIX_METHODS:
            metrics = prefix_aggregate(prefix_groups[(prefix_length, method)])
            for metric in ("final_error", "mae_all", "volatility"):
                rows.append({
                    "seed": seed,
                    "experiment": "sequence_length",
                    "condition": str(prefix_length),
                    "method": method,
                    "metric": metric,
                    "value": metrics[metric],
                })

    for noise_ratio in SELECTED_NOISE_RATIOS:
        noisy_user_results = []
        import random
        rng = random.Random(f"{seed}-mixed_noise-{noise_ratio}")
        for user_rows in users.values():
            noisy_user_results.extend(evaluate_user(inject_noise(
                user_rows, noise_ratio, "mixed_noise", rng
            )))
        noise_groups = defaultdict(list)
        for result in noisy_user_results:
            noise_groups[result["method"]].append(result)
        for method in SELECTED_NOISE_METHODS:
            metrics = state_aggregate(noise_groups[method])
            for metric in ("final_error", "mae_after_10", "volatility"):
                rows.append({
                    "seed": seed,
                    "experiment": "mixed_noise",
                    "condition": str(noise_ratio),
                    "method": method,
                    "metric": metric,
                    "value": metrics[metric],
                })
    return rows


def main():
    seed_rows = []
    for seed in SEEDS:
        seed_rows.extend(run_seed(seed))

    with open(SEED_RESULTS, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(seed_rows[0]))
        writer.writeheader()
        writer.writerows(seed_rows)

    grouped = defaultdict(list)
    for row in seed_rows:
        key = (row["experiment"], row["condition"], row["method"], row["metric"])
        grouped[key].append(row["value"])

    summary_rows = []
    for key, values in sorted(grouped.items()):
        summary_rows.append({
            "experiment": key[0],
            "condition": key[1],
            "method": key[2],
            "metric": key[3],
            "n_seeds": len(values),
            **summarize(values),
        })

    # Paired seed-level effect for the paper's main high-noise comparison.
    lookup = {
        (row["seed"], row["experiment"], row["condition"], row["method"], row["metric"]): row["value"]
        for row in seed_rows
    }
    baseline = [lookup[(s, "mixed_noise", "0.6", "bae_smoothing", "mae_after_10")] for s in SEEDS]
    weighted = [lookup[(s, "mixed_noise", "0.6", "weighted_bae_noise_flag", "mae_after_10")] for s in SEEDS]
    differences = [b - w for b, w in zip(baseline, weighted)]
    relative = [(b - w) / b for b, w in zip(baseline, weighted)]
    for metric, values in (("paired_absolute_reduction", differences), ("paired_relative_reduction", relative)):
        summary_rows.append({
            "experiment": "mixed_noise_effect",
            "condition": "0.6",
            "method": "weighted_vs_bae_smoothing",
            "metric": metric,
            "n_seeds": len(values),
            **summarize(values),
        })

    with open(SUMMARY_RESULTS, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)

    def get(experiment, condition, method, metric):
        return next(row for row in summary_rows if (
            row["experiment"], row["condition"], row["method"], row["metric"]
        ) == (experiment, condition, method, metric))

    b = get("mixed_noise", "0.6", "bae_smoothing", "mae_after_10")
    w = get("mixed_noise", "0.6", "weighted_bae_noise_flag", "mae_after_10")
    d = get("mixed_noise_effect", "0.6", "weighted_vs_bae_smoothing", "paired_absolute_reduction")
    rel = get("mixed_noise_effect", "0.6", "weighted_vs_bae_smoothing", "paired_relative_reduction")
    report = f"""# Multi-seed synthetic uncertainty analysis

- Replicates: {len(SEEDS)} independently regenerated balanced datasets.
- Seeds: {SEEDS[0]}--{SEEDS[-1]}.
- Per replicate: 420 users, 40 turns, 16,800 observations.
- Intervals: empirical 2.5th and 97.5th percentiles across seed-level aggregate results.

## Main mixed-noise result (noise ratio 0.6)

| Method | Mean MAE after turn 10 | 95% seed interval |
|---|---:|---:|
| BAE + smoothing | {b['mean']:.4f} | [{b['ci_low']:.4f}, {b['ci_high']:.4f}] |
| Weighted BAE (flag) | {w['mean']:.4f} | [{w['ci_low']:.4f}, {w['ci_high']:.4f}] |

The paired absolute reduction is {d['mean']:.4f} [{d['ci_low']:.4f}, {d['ci_high']:.4f}], and the paired relative reduction is {100*rel['mean']:.1f}% [{100*rel['ci_low']:.1f}%, {100*rel['ci_high']:.1f}%]. The interval is across independently generated datasets, not individual observations.

Full sequence-length and mixed-noise summaries are in `{SUMMARY_RESULTS.name}`; seed-level results are in `{SEED_RESULTS.name}`.
"""
    REPORT.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
