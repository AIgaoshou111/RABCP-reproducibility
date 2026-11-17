"""One-factor-at-a-time sensitivity for core RABCP state parameters."""

import csv
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
from state_switch_forgetting_experiment import ForgettingBayesianEstimator


SEEDS = range(20261001, 20261031)
USERS = 420
TURNS = 40
SWEEP = {
    "sigma": [0.6, 0.8, 1.0, 1.2],
    "smooth_window": [1, 3, 5, 7],
    "flag_weight": [0.20, 0.35, 0.50, 0.70],
    "gamma": [0.00, 0.02, 0.05, 0.10],
}
DEFAULTS = {"sigma": 0.8, "smooth_window": 5, "flag_weight": 0.35, "gamma": 0.05}
SEED_CSV = EXPERIMENT_DIR / "hyperparameter_sensitivity_seed_results.csv"
SUMMARY_CSV = EXPERIMENT_DIR / "hyperparameter_sensitivity_summary.csv"
REPORT = EXPERIMENT_DIR / "hyperparameter_sensitivity_report.md"


def make_data(targets, rng, noise_ratio):
    observations, flags = [], []
    for target in targets:
        risk = rng.random() < noise_ratio
        if risk:
            observed = rng.choice([1, 5])
        else:
            observed = min(5, max(1, round(target + rng.choice([-1, 0, 0, 0, 0, 1]))))
        flag = rng.random() < (0.8 if risk else 0.1)
        observations.append(observed)
        flags.append(flag)
    return observations, flags


def run_estimator(observations, flags, params):
    estimator = (ForgettingBayesianEstimator(params["gamma"])
                 if params["gamma"] > 0 else
                 BayesianLevelEstimator(smooth_window=params["smooth_window"], use_adaptive_prior=False))
    estimator.smooth_window = params["smooth_window"]
    values = []
    for observed, flag in zip(observations, flags):
        distribution = level_to_distribution(observed, sigma=params["sigma"])
        weight = params["flag_weight"] if flag else 1.0
        values.append(estimator.update(distribution, weight)["fine_level"])
    return values


def main():
    rows = []
    for seed in SEEDS:
        rng = random.Random(seed)
        cached = {"stationary": [], "abrupt_switch": []}
        for _ in range(USERS):
            cached["stationary"].append(make_data([3.0] * TURNS, rng, 0.35))
            cached["abrupt_switch"].append(make_data([2.0] * 20 + [4.0] * 20, rng, 0.15))
        for parameter, values in SWEEP.items():
            for setting in values:
                params = dict(DEFAULTS)
                params[parameter] = setting
                for condition, datasets in cached.items():
                    errors = []
                    targets = [3.0] * TURNS if condition == "stationary" else [2.0] * 20 + [4.0] * 20
                    start = 9 if condition == "stationary" else 20
                    for observations, flags in datasets:
                        estimates = run_estimator(observations, flags, params)
                        errors.append(statistics.mean(abs(estimates[i] - targets[i]) for i in range(start, TURNS)))
                    rows.append({"seed": seed, "parameter": parameter, "setting": setting,
                                 "condition": condition, "mae": statistics.mean(errors)})

    with open(SEED_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["parameter"], row["setting"], row["condition"])].append(row["mae"])
    summary = []
    for (parameter, setting, condition), values in sorted(grouped.items()):
        summary.append({"parameter": parameter, "setting": setting, "condition": condition,
                        "n_seeds": len(values), "mean_mae": statistics.mean(values),
                        "sd": statistics.stdev(values), "min": min(values), "max": max(values)})
    with open(SUMMARY_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader(); writer.writerows(summary)

    lookup = {(r["parameter"], float(r["setting"]), r["condition"]): r["mean_mae"] for r in summary}
    lines = ["# Hyperparameter sensitivity", "", "Thirty independently generated cohorts; one factor varied at a time.", "",
             "| Parameter | Setting | Stationary noisy MAE | Abrupt-switch MAE |", "|---|---:|---:|---:|"]
    for parameter, settings in SWEEP.items():
        for setting in settings:
            key = float(setting)
            lines.append(f"| {parameter} | {setting:.2f} | {lookup[(parameter,key,'stationary')]:.3f} | {lookup[(parameter,key,'abrupt_switch')]:.3f} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
