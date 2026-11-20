"""
权重消融实验。

目的：
- 比较不同 observation_weight 来源对 BAE 的影响。
- 不调用大模型，使用合成数据中的 confidence/risk 的可模拟版本。
- 该实验回答：权重机制中 confidence、risk_flags、oracle noise label 各自贡献多少。
"""

import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from BAE import BayesianLevelEstimator


EXPERIMENT_DIR = Path(__file__).resolve().parent
DATASET_PATH = PROJECT_ROOT / "data" / "合成数据集.json"
RESULT_CSV = EXPERIMENT_DIR / "权重消融实验结果.csv"
USER_RESULT_CSV = EXPERIMENT_DIR / "权重消融实验_用户明细.csv"
CONVERGENCE_TOLERANCE = 0.5
CONVERGENCE_STREAK = 5
METHODS = [
    "no_weight",
    "confidence_only",
    "risk_only",
    "confidence_plus_risk",
    "oracle_noise_label",
]


def level_to_distribution(level: float, sigma: float = 0.8) -> List[float]:
    raw_probs = []
    for x in range(1, 6):
        raw_probs.append(math.exp(-((x - level) ** 2) / (2 * sigma ** 2)))
    total = sum(raw_probs)
    return [p / total for p in raw_probs]


def load_dataset(path: Path) -> List[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def group_by_user(rows: List[dict]) -> Dict[str, List[dict]]:
    users = defaultdict(list)
    for row in rows:
        users[row["user_id"]].append(row)
    return {
        user_id: sorted(items, key=lambda item: item["turn_id"])
        for user_id, items in users.items()
    }


def simulated_confidence(row: dict) -> float:
    """模拟模型置信度：正常高、低上下文或跨域略低。"""
    if row["noise_type"] == "normal":
        return 0.9
    if row["noise_type"] == "cross_domain":
        return 0.65
    if row["noise_type"] == "high_noise":
        return 0.7
    if row["noise_type"] == "low_noise":
        return 0.75
    return 0.7


def simulated_risk_penalty(row: dict) -> float:
    penalties = {
        "normal": 0.0,
        "high_noise": 0.35,
        "low_noise": 0.4,
        "cross_domain": 0.45,
    }
    return penalties.get(row["noise_type"], 0.0)


def clamp_weight(value: float) -> float:
    return max(0.05, min(1.0, value))


def observation_weight(row: dict, method: str) -> float:
    confidence = simulated_confidence(row)
    risk = simulated_risk_penalty(row)

    if method == "no_weight":
        return 1.0
    if method == "confidence_only":
        return clamp_weight(0.35 + 0.65 * confidence)
    if method == "risk_only":
        return clamp_weight(1.0 - risk)
    if method == "confidence_plus_risk":
        return clamp_weight(0.35 + 0.65 * confidence - risk)
    if method == "oracle_noise_label":
        return 0.35 if row["is_noise"] else 1.0
    raise ValueError(f"未知方法: {method}")


def mean_absolute_error(values: List[float], target: float) -> float:
    return sum(abs(v - target) for v in values) / len(values)


def volatility(values: List[float]) -> float:
    return statistics.stdev(values) if len(values) >= 2 else 0.0


def convergence_turn(values: List[float], target: float) -> int:
    streak = 0
    for index, value in enumerate(values, start=1):
        if abs(value - target) <= CONVERGENCE_TOLERANCE:
            streak += 1
            if streak >= CONVERGENCE_STREAK:
                return index - CONVERGENCE_STREAK + 1
        else:
            streak = 0
    return -1


def evaluate_user(user_rows: List[dict]) -> List[dict]:
    first = user_rows[0]
    true_level = first["true_user_level"]
    results = []

    for method in METHODS:
        estimator = BayesianLevelEstimator(smooth_window=5, use_adaptive_prior=False)
        values = []
        weights = []
        for row in user_rows:
            distribution = level_to_distribution(row["observed_question_level"])
            weight = observation_weight(row, method)
            weights.append(weight)
            result = estimator.update(distribution, observation_weight=weight)
            values.append(result["fine_level"])

        convergence = convergence_turn(values, true_level)
        results.append({
            "user_id": first["user_id"],
            "method": method,
            "true_user_level": true_level,
            "primary_domain": first["primary_domain"],
            "scenario": first["scenario"],
            "num_questions": len(user_rows),
            "noise_ratio": sum(1 for row in user_rows if row["is_noise"]) / len(user_rows),
            "avg_weight": sum(weights) / len(weights),
            "final_prediction": values[-1],
            "final_error": abs(values[-1] - true_level),
            "mae_all": mean_absolute_error(values, true_level),
            "mae_after_10": mean_absolute_error(values[9:], true_level),
            "volatility": volatility(values),
            "convergence_turn": convergence,
            "is_converged": convergence != -1,
        })
    return results


def aggregate(rows: List[dict]) -> dict:
    converged_turns = [row["convergence_turn"] for row in rows if row["is_converged"]]
    return {
        "user_count": len(rows),
        "final_error": statistics.mean(row["final_error"] for row in rows),
        "mae_all": statistics.mean(row["mae_all"] for row in rows),
        "mae_after_10": statistics.mean(row["mae_after_10"] for row in rows),
        "volatility": statistics.mean(row["volatility"] for row in rows),
        "avg_weight": statistics.mean(row["avg_weight"] for row in rows),
        "convergence_rate": len(converged_turns) / len(rows),
        "avg_convergence_turn": statistics.mean(converged_turns) if converged_turns else -1,
    }


def run_experiment():
    dataset = load_dataset(DATASET_PATH)
    users = group_by_user(dataset)

    user_results = []
    for user_rows in users.values():
        user_results.extend(evaluate_user(user_rows))

    summary_rows = []
    groups = [("overall", "all", user_results)]
    for scenario in sorted({row["scenario"] for row in user_results}):
        groups.append((
            "scenario",
            scenario,
            [row for row in user_results if row["scenario"] == scenario],
        ))

    for group_type, group_value, group_rows in groups:
        by_method = defaultdict(list)
        for row in group_rows:
            by_method[row["method"]].append(row)
        for method in METHODS:
            summary_rows.append({
                "group_type": group_type,
                "group_value": group_value,
                "method": method,
                **aggregate(by_method[method]),
            })

    summary_fields = [
        "group_type",
        "group_value",
        "method",
        "user_count",
        "final_error",
        "mae_all",
        "mae_after_10",
        "volatility",
        "avg_weight",
        "convergence_rate",
        "avg_convergence_turn",
    ]
    user_fields = [
        "user_id",
        "method",
        "true_user_level",
        "primary_domain",
        "scenario",
        "num_questions",
        "noise_ratio",
        "avg_weight",
        "final_prediction",
        "final_error",
        "mae_all",
        "mae_after_10",
        "volatility",
        "convergence_turn",
        "is_converged",
    ]

    with open(RESULT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(summary_rows)

    with open(USER_RESULT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=user_fields)
        writer.writeheader()
        writer.writerows(user_results)

    print(f"读取数据集: {DATASET_PATH}")
    print(f"汇总结果: {RESULT_CSV}")
    print(f"用户明细: {USER_RESULT_CSV}")
    print("\n总体结果")
    print("-" * 92)
    print(f"{'method':<24} {'final_err':>10} {'mae_after10':>12} {'avg_w':>8} {'conv_rate':>10}")
    print("-" * 92)
    for row in summary_rows:
        if row["group_type"] == "overall":
            print(
                f"{row['method']:<24} "
                f"{row['final_error']:>10.3f} "
                f"{row['mae_after_10']:>12.3f} "
                f"{row['avg_weight']:>8.3f} "
                f"{row['convergence_rate']:>10.2%}"
            )


if __name__ == "__main__":
    run_experiment()
