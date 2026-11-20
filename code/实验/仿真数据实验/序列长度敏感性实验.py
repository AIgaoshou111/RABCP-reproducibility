"""
序列长度敏感性实验。

目的：
- 检验不同历史问题轮数下，各状态估计方法的稳定性。
- 回答 RABCP 需要多少轮连续提问才能形成相对稳定的阶段性画像。
- 不调用大模型，只使用合成数据中的 observed_question_level / true_user_level。
"""

import csv
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from 状态估计实验 import (
    convergence_turn,
    group_by_user,
    load_dataset,
    run_methods,
    volatility,
)


EXPERIMENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EXPERIMENT_DIR.parent.parent
DATASET_PATH = PROJECT_ROOT / "data" / "合成数据集.json"
RESULT_CSV = EXPERIMENT_DIR / "序列长度敏感性实验结果.csv"
USER_RESULT_CSV = EXPERIMENT_DIR / "序列长度敏感性实验_用户明细.csv"

PREFIX_LENGTHS = [5, 10, 20, 30, 40]
CORE_METHODS = [
    "raw",
    "cumulative_mean",
    "sliding_mean",
    "bae_plain",
    "bae_smoothing",
    "weighted_bae_noise_flag",
    "weighted_bae_noise_type",
]


def mean_absolute_error(values: List[float], target: float) -> float:
    return sum(abs(value - target) for value in values) / len(values)


def evaluate_prefix(user_rows: List[dict], prefix_length: int) -> List[dict]:
    prefix_rows = user_rows[:prefix_length]
    first = prefix_rows[0]
    true_level = first["true_user_level"]
    outputs = run_methods(prefix_rows)

    results = []
    for method in CORE_METHODS:
        values = outputs[method]
        convergence = convergence_turn(values, true_level)
        results.append({
            "user_id": first["user_id"],
            "prefix_length": prefix_length,
            "method": method,
            "true_user_level": true_level,
            "primary_domain": first["primary_domain"],
            "scenario": first["scenario"],
            "noise_ratio": sum(1 for row in prefix_rows if row["is_noise"]) / len(prefix_rows),
            "final_prediction": values[-1],
            "final_error": abs(values[-1] - true_level),
            "mae_all": mean_absolute_error(values, true_level),
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
        "volatility": statistics.mean(row["volatility"] for row in rows),
        "convergence_rate": len(converged_turns) / len(rows),
        "avg_convergence_turn": statistics.mean(converged_turns) if converged_turns else -1,
    }


def build_summary(user_results: List[dict]) -> List[dict]:
    summary_rows = []
    grouped: Dict[tuple, List[dict]] = defaultdict(list)
    for row in user_results:
        grouped[(row["prefix_length"], row["method"])].append(row)

    for prefix_length in PREFIX_LENGTHS:
        for method in CORE_METHODS:
            metrics = aggregate(grouped[(prefix_length, method)])
            summary_rows.append({
                "prefix_length": prefix_length,
                "method": method,
                **metrics,
            })
    return summary_rows


def write_csv(path: Path, rows: List[dict], fieldnames: List[str]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_experiment():
    dataset = load_dataset(DATASET_PATH)
    users = group_by_user(dataset)

    user_results = []
    for user_rows in users.values():
        for prefix_length in PREFIX_LENGTHS:
            user_results.extend(evaluate_prefix(user_rows, prefix_length))

    summary_rows = build_summary(user_results)

    summary_fields = [
        "prefix_length",
        "method",
        "user_count",
        "final_error",
        "mae_all",
        "volatility",
        "convergence_rate",
        "avg_convergence_turn",
    ]
    user_fields = [
        "user_id",
        "prefix_length",
        "method",
        "true_user_level",
        "primary_domain",
        "scenario",
        "noise_ratio",
        "final_prediction",
        "final_error",
        "mae_all",
        "volatility",
        "convergence_turn",
        "is_converged",
    ]

    write_csv(RESULT_CSV, summary_rows, summary_fields)
    write_csv(USER_RESULT_CSV, user_results, user_fields)

    print(f"读取数据集: {DATASET_PATH}")
    print(f"汇总结果: {RESULT_CSV}")
    print(f"用户明细: {USER_RESULT_CSV}")
    print("\n关键结果：序列长度敏感性")
    print("-" * 92)
    print(f"{'turns':>6} {'method':<28} {'final_err':>10} {'mae_all':>10} {'conv_rate':>10}")
    print("-" * 92)
    for row in summary_rows:
        if row["method"] in ["cumulative_mean", "bae_smoothing", "weighted_bae_noise_flag"]:
            print(
                f"{row['prefix_length']:>6} "
                f"{row['method']:<28} "
                f"{row['final_error']:>10.3f} "
                f"{row['mae_all']:>10.3f} "
                f"{row['convergence_rate']:>10.2%}"
            )


if __name__ == "__main__":
    run_experiment()
