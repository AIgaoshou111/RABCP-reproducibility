"""State-switch and forgetting-factor evaluation for short-term support states."""

import csv
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path


EXPERIMENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EXPERIMENT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(EXPERIMENT_DIR))

from BAE import BayesianLevelEstimator
from 状态估计实验 import level_to_distribution
from model_misspecification_experiment import ewma, kalman, hmm


SEEDS = list(range(20260901, 20260951))
USERS_PER_CONDITION = 420
TURNS = 40
SWITCH_TURN = 21
FORGETTING_RATES = [0.02, 0.05, 0.10]
METHODS = ["ewma", "kalman", "hmm", "weighted_bae_original"] + [f"weighted_bae_forget_{rate:.2f}" for rate in FORGETTING_RATES]
CONDITIONS = ["abrupt_up", "abrupt_down", "gradual_up", "transient_up", "stationary_noisy"]
SEED_CSV = EXPERIMENT_DIR / "state_switch_forgetting_seed_results.csv"
SUMMARY_CSV = EXPERIMENT_DIR / "state_switch_forgetting_summary.csv"
REPORT = EXPERIMENT_DIR / "state_switch_forgetting_report.md"


class ForgettingBayesianEstimator(BayesianLevelEstimator):
    """Mix the previous posterior with a uniform transition prior each turn."""

    def __init__(self, forgetting_rate):
        super().__init__(smooth_window=5, use_adaptive_prior=False)
        self.forgetting_rate = forgetting_rate

    def update(self, observation_distribution, observation_weight=1.0):
        rate = self.forgetting_rate
        self.p_levels = [(1 - rate) * value + rate * 0.2 for value in self.p_levels]
        return super().update(observation_distribution, observation_weight)


def true_path(condition):
    if condition == "abrupt_up":
        return [2.0] * 20 + [4.0] * 20
    if condition == "abrupt_down":
        return [4.0] * 20 + [2.0] * 20
    if condition == "gradual_up":
        return [2.0] * 15 + [2.0 + 2.0 * index / 14 for index in range(15)] + [4.0] * 10
    if condition == "transient_up":
        return [2.0] * 20 + [4.0] * 6 + [2.0] * 14
    if condition == "stationary_noisy":
        return [3.0] * 40
    raise ValueError(condition)


def observations(path, rng):
    values, risks = [], []
    for target in path:
        risk = rng.random() < 0.15
        if risk:
            value = rng.choice([1.0, 5.0])
        else:
            value = min(5.0, max(1.0, round(target + rng.choice([-1, 0, 0, 0, 0, 1]))))
        values.append(value)
        risks.append(risk)
    flags = [rng.random() < (0.8 if risk else 0.1) for risk in risks]
    return values, flags


def bae(values, flags, forgetting_rate=None):
    estimator = (ForgettingBayesianEstimator(forgetting_rate)
                 if forgetting_rate is not None else
                 BayesianLevelEstimator(smooth_window=5, use_adaptive_prior=False))
    outputs = []
    for value, flag in zip(values, flags):
        result = estimator.update(level_to_distribution(value), 0.35 if flag else 1.0)
        outputs.append(result["fine_level"])
    return outputs


def method_outputs(values, flags):
    outputs = {
        "ewma": ewma(values),
        "kalman": kalman(values),
        "hmm": hmm(values),
        "weighted_bae_original": bae(values, flags),
    }
    for rate in FORGETTING_RATES:
        outputs[f"weighted_bae_forget_{rate:.2f}"] = bae(values, flags, rate)
    return outputs


def first_recovery(estimates, targets, start, tolerance=0.5, streak=3):
    for index in range(start, len(estimates) - streak + 1):
        if all(abs(estimates[j] - targets[j]) <= tolerance for j in range(index, index + streak)):
            return index - start + 1
    # The sentinel belongs to the original penalized timing metric.
    # conditional_recovery.py excludes this sentinel when computing Table 7 delays.
    return len(estimates) - start + 1


def metrics(condition, estimates, targets):
    if condition in ("abrupt_up", "abrupt_down"):
        start = 20
    elif condition == "gradual_up":
        start = 15
    elif condition == "transient_up":
        start = 20
    else:
        start = 9
    post = [abs(estimates[index] - targets[index]) for index in range(start, TURNS)]
    return {
        "post_change_mae": statistics.mean(post),
        "recovery_turns": first_recovery(estimates, targets, start),
        "final_error": abs(estimates[-1] - targets[-1]),
    }


def quantile(values, p):
    ordered = sorted(values)
    position = (len(ordered) - 1) * p
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    fraction = position - low
    return ordered[low] * (1 - fraction) + ordered[high] * fraction


def main():
    seed_rows = []
    for seed in SEEDS:
        rng = random.Random(seed)
        grouped = defaultdict(list)
        for condition in CONDITIONS:
            targets = true_path(condition)
            for _ in range(USERS_PER_CONDITION):
                values, flags = observations(targets, rng)
                for method, estimates in method_outputs(values, flags).items():
                    result = metrics(condition, estimates, targets)
                    for metric, value in result.items():
                        grouped[(condition, method, metric)].append(value)
        for (condition, method, metric), values in grouped.items():
            seed_rows.append({
                "seed": seed,
                "condition": condition,
                "method": method,
                "metric": metric,
                "value": statistics.mean(values),
            })

    with open(SEED_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(seed_rows[0]))
        writer.writeheader()
        writer.writerows(seed_rows)

    grouped = defaultdict(list)
    for row in seed_rows:
        grouped[(row["condition"], row["method"], row["metric"])].append(row["value"])
    summary = []
    for (condition, method, metric), values in sorted(grouped.items()):
        summary.append({
            "condition": condition,
            "method": method,
            "metric": metric,
            "n_seeds": len(values),
            "mean": statistics.mean(values),
            "sd": statistics.stdev(values),
            "ci_low": quantile(values, 0.025),
            "ci_high": quantile(values, 0.975),
        })
    with open(SUMMARY_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    lookup = {(row["condition"], row["method"], row["metric"]): row for row in summary}
    display_methods = ["ewma", "kalman", "hmm", "weighted_bae_original", "weighted_bae_forget_0.05"]
    lines = [
        "# State-switch and forgetting experiment", "",
        "Fifty seeds, 420 users per condition, 40 turns. Observations include 15% outliers and imperfect flags (TPR 0.8/FPR 0.1).", "",
        "## Post-change MAE", "",
        "| Condition | EWMA | Kalman | HMM | Original weighted BAE | Forgetting BAE (0.05) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for condition in CONDITIONS:
        values = [lookup[(condition, method, "post_change_mae")]["mean"] for method in display_methods]
        lines.append(f"| {condition} | " + " | ".join(f"{value:.3f}" for value in values) + " |")
    lines += ["", "## Recovery turns after abrupt switches", "",
              "| Condition | Original weighted BAE | Forgetting BAE (0.02) | Forgetting BAE (0.05) | Forgetting BAE (0.10) |",
              "|---|---:|---:|---:|---:|"]
    for condition in ("abrupt_up", "abrupt_down"):
        methods = ["weighted_bae_original", "weighted_bae_forget_0.02", "weighted_bae_forget_0.05", "weighted_bae_forget_0.10"]
        values = [lookup[(condition, method, "recovery_turns")]["mean"] for method in methods]
        lines.append(f"| {condition} | " + " | ".join(f"{value:.1f}" for value in values) + " |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
