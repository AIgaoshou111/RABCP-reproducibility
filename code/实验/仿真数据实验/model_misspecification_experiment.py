"""Stress-test RABCP under observation processes not matched to its generator.

The latent support state is fixed in this experiment.  Four observation
processes introduce symmetric noise, directional bias, bursty heavy-tail
outliers, or persistent late domain bias.  Risk flags are imperfect
(TPR=0.8, FPR=0.1), so Weighted BAE does not receive oracle labels.
"""

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


SEEDS = list(range(20260801, 20260851))
LEVELS = range(1, 6)
USERS_PER_LEVEL = 84
TURNS = 40
CONDITIONS = ["symmetric_mixed", "asymmetric_high", "heavy_tail_bursts", "persistent_late_bias"]
METHODS = ["cumulative_mean", "ewma", "kalman", "hmm", "bae_smoothing", "weighted_bae_imperfect_flag"]
SEED_CSV = EXPERIMENT_DIR / "model_misspecification_seed_results.csv"
SUMMARY_CSV = EXPERIMENT_DIR / "model_misspecification_summary.csv"
REPORT = EXPERIMENT_DIR / "model_misspecification_report.md"


def clip(value):
    return min(5.0, max(1.0, value))


def generate_sequence(level, condition, rng):
    observations, risks = [], []
    burst_start = rng.choice([8, 14, 20, 26])
    for turn in range(TURNS):
        risk = False
        value = float(level)
        if condition == "symmetric_mixed" and rng.random() < 0.4:
            risk = True
            value = clip(level + rng.choice([-2, -1, 1, 2]))
        elif condition == "asymmetric_high" and rng.random() < 0.4:
            risk = True
            value = clip(level + rng.choice([1, 1, 2]))
        elif condition == "heavy_tail_bursts":
            if burst_start <= turn < burst_start + 5 or rng.random() < 0.08:
                risk = True
                value = float(rng.choice([1, 5]))
            elif rng.random() < 0.15:
                value = clip(level + rng.choice([-1, 1]))
        elif condition == "persistent_late_bias":
            if turn >= 25:
                risk = True
                value = clip(level + 1)
            elif rng.random() < 0.15:
                value = clip(level + rng.choice([-1, 1]))
        observations.append(value)
        risks.append(risk)
    return observations, risks


def imperfect_flags(risks, rng):
    return [rng.random() < (0.8 if risk else 0.1) for risk in risks]


def cumulative(values):
    out, total = [], 0.0
    for index, value in enumerate(values, 1):
        total += value
        out.append(total / index)
    return out


def ewma(values, alpha=0.2):
    state, out = 3.0, []
    for value in values:
        state = alpha * value + (1 - alpha) * state
        out.append(state)
    return out


def kalman(values, process_variance=0.03, observation_variance=0.64):
    state, variance, out = 3.0, 1.0, []
    for value in values:
        variance += process_variance
        gain = variance / (variance + observation_variance)
        state = state + gain * (value - state)
        variance = (1 - gain) * variance
        out.append(clip(state))
    return out


def hmm(values, stay_probability=0.9, sigma=0.8):
    posterior = [0.2] * 5
    out = []
    off_diagonal = (1 - stay_probability) / 4
    for value in values:
        predicted = [
            sum(posterior[i] * (stay_probability if i == j else off_diagonal) for i in range(5))
            for j in range(5)
        ]
        likelihood = [math.exp(-((j + 1 - value) ** 2) / (2 * sigma ** 2)) for j in range(5)]
        posterior = [p * l for p, l in zip(predicted, likelihood)]
        total = sum(posterior)
        posterior = [p / total for p in posterior]
        out.append(sum((j + 1) * p for j, p in enumerate(posterior)))
    return out


def bae(values, flags=None):
    estimator = BayesianLevelEstimator(smooth_window=5, use_adaptive_prior=False)
    out = []
    for index, value in enumerate(values):
        weight = 0.35 if flags is not None and flags[index] else 1.0
        out.append(estimator.update(level_to_distribution(value), observation_weight=weight)["fine_level"])
    return out


def evaluate(values, flags):
    return {
        "cumulative_mean": cumulative(values),
        "ewma": ewma(values),
        "kalman": kalman(values),
        "hmm": hmm(values),
        "bae_smoothing": bae(values),
        "weighted_bae_imperfect_flag": bae(values, flags),
    }


def quantile(values, p):
    ordered = sorted(values)
    pos = (len(ordered) - 1) * p
    lo, hi = int(pos), min(int(pos) + 1, len(ordered) - 1)
    return ordered[lo] * (hi - pos) + ordered[hi] * (pos - lo)


def main():
    seed_rows = []
    for seed in SEEDS:
        rng = random.Random(seed)
        accumulator = defaultdict(list)
        for condition in CONDITIONS:
            for level in LEVELS:
                for _ in range(USERS_PER_LEVEL):
                    values, risks = generate_sequence(level, condition, rng)
                    flags = imperfect_flags(risks, rng)
                    for method, estimates in evaluate(values, flags).items():
                        accumulator[(condition, method)].append(
                            sum(abs(value - level) for value in estimates[9:]) / len(estimates[9:])
                        )
        for (condition, method), errors in accumulator.items():
            seed_rows.append({
                "seed": seed,
                "condition": condition,
                "method": method,
                "mae_after_10": statistics.mean(errors),
            })

    with open(SEED_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(seed_rows[0]))
        writer.writeheader()
        writer.writerows(seed_rows)

    grouped = defaultdict(list)
    for row in seed_rows:
        grouped[(row["condition"], row["method"])].append(row["mae_after_10"])
    summary = []
    for (condition, method), values in sorted(grouped.items()):
        summary.append({
            "condition": condition,
            "method": method,
            "n_seeds": len(values),
            "mean_mae_after_10": statistics.mean(values),
            "sd": statistics.stdev(values),
            "ci_low": quantile(values, 0.025),
            "ci_high": quantile(values, 0.975),
        })
    with open(SUMMARY_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    lines = [
        "# Model-misspecification stress test", "",
        "Fifty independently generated cohorts; 420 users and 40 turns per condition and seed. Weighted BAE uses imperfect flags (TPR 0.8, FPR 0.1), not oracle labels.", "",
        "| Condition | Cumulative | EWMA | Kalman | HMM | BAE smoothing | Weighted BAE | Best |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for condition in CONDITIONS:
        rows = {row["method"]: row for row in summary if row["condition"] == condition}
        best = min(rows, key=lambda method: rows[method]["mean_mae_after_10"])
        lines.append("| " + " | ".join([
            condition,
            f"{rows['cumulative_mean']['mean_mae_after_10']:.3f}",
            f"{rows['ewma']['mean_mae_after_10']:.3f}",
            f"{rows['kalman']['mean_mae_after_10']:.3f}",
            f"{rows['hmm']['mean_mae_after_10']:.3f}",
            f"{rows['bae_smoothing']['mean_mae_after_10']:.3f}",
            f"{rows['weighted_bae_imperfect_flag']['mean_mae_after_10']:.3f}",
            best,
        ]) + " |")
    lines += ["", "Lower is better. Full seed intervals are stored in the summary CSV."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
