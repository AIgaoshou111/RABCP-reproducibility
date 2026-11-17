#!/usr/bin/env python3
"""Sensitivity of reliability weighting to imperfect binary risk flags."""

from __future__ import annotations

import csv
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from BAE import BayesianLevelEstimator

HERE = Path(__file__).resolve().parent
DATA = ROOT / "data" / "合成数据集.json"
CSV_OUT = HERE / "risk_flag_error_sensitivity_results.csv"
REPORT = HERE / "risk_flag_error_sensitivity_report.md"
DETECTOR_SEEDS = list(range(20260714, 20260764))
SETTINGS = [
    ("perfect", 1.0, 0.0),
    ("high_quality", 0.9, 0.05),
    ("moderate", 0.8, 0.10),
    ("low_recall", 0.6, 0.10),
    ("noisy_detector", 0.6, 0.20),
    ("weak_detector", 0.4, 0.20),
    ("no_flags", 0.0, 0.0),
]


def distribution(level, sigma=0.8):
    values = [math.exp(-((x - level) ** 2) / (2 * sigma ** 2)) for x in range(1, 6)]
    total = sum(values)
    return [value / total for value in values]


def grouped_users():
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    users = defaultdict(list)
    for row in rows:
        users[row["user_id"]].append(row)
    return {key: sorted(value, key=lambda item: item["turn_id"]) for key, value in users.items()}


def evaluate(user_rows, tpr, fpr, seed):
    rng = random.Random(f"{seed}:{user_rows[0]['user_id']}")
    estimator = BayesianLevelEstimator(smooth_window=5, use_adaptive_prior=False)
    predictions = []
    tp = fp = positives = negatives = 0
    for row in user_rows:
        actual = bool(row["is_noise"])
        if actual:
            positives += 1
            flagged = rng.random() < tpr
            tp += int(flagged)
        else:
            negatives += 1
            flagged = rng.random() < fpr
            fp += int(flagged)
        result = estimator.update(distribution(row["observed_question_level"]), observation_weight=0.35 if flagged else 1.0)
        predictions.append(result["fine_level"])
    target = float(user_rows[0]["true_user_level"])
    return {
        "mae_after_10": statistics.mean(abs(value - target) for value in predictions[9:]),
        "final_error": abs(predictions[-1] - target),
        "observed_tpr": tp / positives if positives else 0.0,
        "observed_fpr": fp / negatives if negatives else 0.0,
    }


def main():
    users = grouped_users()
    rows = []
    for name, tpr, fpr in SETTINGS:
        seeds = [DETECTOR_SEEDS[0]] if name in {"perfect", "no_flags"} else DETECTOR_SEEDS
        for seed in seeds:
            for group in ("all", "mixed_noisy"):
                selected = [items for items in users.values() if group == "all" or items[0]["scenario"] == group]
                metrics = [evaluate(items, tpr, fpr, seed) for items in selected]
                rows.append({
                    "setting": name, "target_tpr": tpr, "target_fpr": fpr, "seed": seed,
                    "group": group, "users": len(metrics),
                    "mae_after_10": statistics.mean(item["mae_after_10"] for item in metrics),
                    "final_error": statistics.mean(item["final_error"] for item in metrics),
                    "observed_tpr": statistics.mean(item["observed_tpr"] for item in metrics),
                    "observed_fpr": statistics.mean(item["observed_fpr"] for item in metrics),
                })
    with CSV_OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)

    summarized = []
    for name, tpr, fpr in SETTINGS:
        for group in ("all", "mixed_noisy"):
            subset = [row for row in rows if row["setting"] == name and row["group"] == group]
            values = [row["mae_after_10"] for row in subset]
            summarized.append((name, tpr, fpr, group, statistics.mean(values), statistics.stdev(values) if len(values) > 1 else 0.0))
    lines = [
        "# Risk-flag error sensitivity", "",
        f"Detector seeds: {len(DETECTOR_SEEDS)} (20260714--20260763); risk-flag weight: 0.35.", "",
        "| Setting | Target TPR | Target FPR | Group | MAE after turn 10 (mean) | Across-detector-seed SD |",
        "|---|---:|---:|---|---:|---:|",
    ]
    for name, tpr, fpr, group, mean, sd in summarized:
        lines.append(f"| {name} | {tpr:.2f} | {fpr:.2f} | {group} | {mean:.4f} | {sd:.4f} |")
    baseline = next(item[4] for item in summarized if item[0] == "no_flags" and item[3] == "mixed_noisy")
    lines += ["", f"The no-flag smoothed-BAE reference on mixed-noisy users is {baseline:.4f}. Settings below this value improve MAE under the simulated detector error; settings at or above it do not."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
