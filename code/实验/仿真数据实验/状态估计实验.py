"""
状态估计实验：读取固定的《合成数据集.json》，只验证 BAE 的动态融合能力。

注意：本实验直接使用 observed_question_level 作为输入，不测试大模型的问题等级识别能力。
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
RESULT_CSV = EXPERIMENT_DIR / "状态估计实验结果.csv"
USER_RESULT_CSV = EXPERIMENT_DIR / "状态估计实验_用户明细.csv"
SLIDING_WINDOW = 5
CONVERGENCE_TOLERANCE = 0.5
CONVERGENCE_STREAK = 5
METHODS = [
    "raw",
    "cumulative_mean",
    "sliding_mean",
    "bae_plain",
    "bae_smoothing",
    "weighted_bae_noise_flag",
    "weighted_bae_noise_type",
]


def level_to_distribution(level: float, sigma: float = 0.8) -> List[float]:
    """把观测等级转换为 L1-L5 概率分布。"""
    raw_probs = []
    for x in range(1, 6):
        density = math.exp(-((x - level) ** 2) / (2 * sigma ** 2))
        raw_probs.append(density)

    total = sum(raw_probs)
    return [p / total for p in raw_probs]


class AblationBayesianLevelEstimator(BayesianLevelEstimator):
    """用于实验消融的 BAE 变体，不影响主系统中的 BAE。"""

    def __init__(self, use_smoothing: bool, use_adaptive: bool):
        smooth_window = 5 if use_smoothing else 1
        super().__init__(
            smooth_window=smooth_window,
            use_adaptive_prior=use_adaptive,
            adaptive_threshold=5,
        )
        self.use_smoothing = use_smoothing
        self.use_adaptive = use_adaptive

    def _smooth_distribution(self, new_distribution: List[float]) -> List[float]:
        if self.use_smoothing:
            return super()._smooth_distribution(new_distribution)

        self.observation_window = [new_distribution]
        return new_distribution


def mean_absolute_error(values: List[float], target: float) -> float:
    return sum(abs(v - target) for v in values) / len(values)


def volatility(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.stdev(values)


def convergence_turn(values: List[float], target: float) -> int:
    """返回首次连续多轮进入真实等级允许误差范围的轮次；未收敛返回 -1。"""
    streak = 0
    for index, value in enumerate(values, start=1):
        if abs(value - target) <= CONVERGENCE_TOLERANCE:
            streak += 1
            if streak >= CONVERGENCE_STREAK:
                return index - CONVERGENCE_STREAK + 1
        else:
            streak = 0
    return -1


def load_dataset(path: str) -> List[dict]:
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


def noise_flag_weight(row: dict) -> float:
    """只根据是否显式噪声降权。"""
    return 0.35 if row["is_noise"] else 1.0


def noise_type_weight(row: dict) -> float:
    """根据噪声类型设置更细的可靠性权重。"""
    weights = {
        "normal": 1.0,
        "high_noise": 0.25,
        "low_noise": 0.45,
        "cross_domain": 0.2,
    }
    return weights.get(row["noise_type"], 1.0)


def run_methods(user_rows: List[dict]) -> Dict[str, List[float]]:
    estimators = {
        "bae_plain": AblationBayesianLevelEstimator(
            use_smoothing=False,
            use_adaptive=False,
        ),
        "bae_smoothing": AblationBayesianLevelEstimator(
            use_smoothing=True,
            use_adaptive=False,
        ),
        "weighted_bae_noise_flag": AblationBayesianLevelEstimator(
            use_smoothing=True,
            use_adaptive=False,
        ),
        "weighted_bae_noise_type": AblationBayesianLevelEstimator(
            use_smoothing=True,
            use_adaptive=False,
        ),
    }

    raw = []
    cumulative_mean = []
    sliding_mean = []
    bae_outputs = {method: [] for method in estimators}

    for row in user_rows:
        level = row["observed_question_level"]
        raw.append(float(level))
        cumulative_mean.append(sum(raw) / len(raw))
        recent_levels = raw[-SLIDING_WINDOW:]
        sliding_mean.append(sum(recent_levels) / len(recent_levels))

        distribution = level_to_distribution(level)
        for method, estimator in estimators.items():
            observation_weight = 1.0
            if method == "weighted_bae_noise_flag":
                observation_weight = noise_flag_weight(row)
            elif method == "weighted_bae_noise_type":
                observation_weight = noise_type_weight(row)

            result = estimator.update(
                distribution,
                observation_weight=observation_weight,
            )
            bae_outputs[method].append(result["fine_level"])

    outputs = {
        "raw": raw,
        "cumulative_mean": cumulative_mean,
        "sliding_mean": sliding_mean,
    }
    outputs.update(bae_outputs)
    return outputs


def evaluate_user(user_rows: List[dict]) -> List[dict]:
    first = user_rows[0]
    true_level = first["true_user_level"]
    method_outputs = run_methods(user_rows)

    results = []
    for method, values in method_outputs.items():
        convergence = convergence_turn(values, true_level)
        results.append({
            "user_id": first["user_id"],
            "method": method,
            "true_user_level": true_level,
            "primary_domain": first["primary_domain"],
            "scenario": first["scenario"],
            "num_questions": len(user_rows),
            "noise_count": sum(1 for row in user_rows if row["is_noise"]),
            "noise_ratio": sum(1 for row in user_rows if row["is_noise"]) / len(user_rows),
            "final_prediction": values[-1],
            "final_error": abs(values[-1] - true_level),
            "mae_all": mean_absolute_error(values, true_level),
            "mae_after_10": mean_absolute_error(values[9:], true_level),
            "volatility": volatility(values),
            "convergence_turn": convergence,
            "is_converged": convergence != -1,
        })

    return results


def aggregate(rows: List[dict]) -> Dict[str, float]:
    converged_turns = [row["convergence_turn"] for row in rows if row["is_converged"]]
    return {
        "user_count": len(rows),
        "final_error": statistics.mean(row["final_error"] for row in rows),
        "mae_all": statistics.mean(row["mae_all"] for row in rows),
        "mae_after_10": statistics.mean(row["mae_after_10"] for row in rows),
        "volatility": statistics.mean(row["volatility"] for row in rows),
        "convergence_rate": len(converged_turns) / len(rows),
        "avg_convergence_turn": statistics.mean(converged_turns) if converged_turns else -1,
    }


def add_summary_rows(summary_rows: List[dict], group_type: str, group_value: str, rows: List[dict]):
    rows_by_method = defaultdict(list)
    for row in rows:
        rows_by_method[row["method"]].append(row)

    for method in METHODS:
        metrics = aggregate(rows_by_method[method])
        summary_rows.append({
            "group_type": group_type,
            "group_value": group_value,
            "method": method,
            **metrics,
        })


def build_summary(user_results: List[dict]) -> List[dict]:
    summary_rows = []
    add_summary_rows(summary_rows, "overall", "all", user_results)

    group_specs = [
        ("true_user_level", "true_user_level"),
        ("primary_domain", "primary_domain"),
        ("scenario", "scenario"),
    ]
    for field, group_type in group_specs:
        values = sorted({row[field] for row in user_results})
        for value in values:
            group_rows = [row for row in user_results if row[field] == value]
            add_summary_rows(summary_rows, group_type, str(value), group_rows)

    return summary_rows


def write_csv(path: str, rows: List[dict], fieldnames: List[str]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def print_overall(summary_rows: List[dict]):
    rows = [
        row for row in summary_rows
        if row["group_type"] == "overall" and row["group_value"] == "all"
    ]
    print("\n总体结果")
    print("-" * 105)
    print(
        f"{'method':<18} {'users':>7} {'final_err':>10} {'mae_all':>10} "
        f"{'mae_after10':>12} {'volatility':>12} {'conv_rate':>10} {'conv_turn':>10}"
    )
    print("-" * 105)
    for row in rows:
        print(
            f"{row['method']:<18} "
            f"{row['user_count']:>7} "
            f"{row['final_error']:>10.3f} "
            f"{row['mae_all']:>10.3f} "
            f"{row['mae_after_10']:>12.3f} "
            f"{row['volatility']:>12.3f} "
            f"{row['convergence_rate']:>10.2%} "
            f"{row['avg_convergence_turn']:>10.2f}"
        )


def run_experiment():
    dataset = load_dataset(DATASET_PATH)
    users = group_by_user(dataset)

    user_results = []
    for user_rows in users.values():
        user_results.extend(evaluate_user(user_rows))

    summary_rows = build_summary(user_results)

    summary_fields = [
        "group_type",
        "group_value",
        "method",
        "user_count",
        "final_error",
        "mae_all",
        "mae_after_10",
        "volatility",
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
        "noise_count",
        "noise_ratio",
        "final_prediction",
        "final_error",
        "mae_all",
        "mae_after_10",
        "volatility",
        "convergence_turn",
        "is_converged",
    ]

    write_csv(RESULT_CSV, summary_rows, summary_fields)
    write_csv(USER_RESULT_CSV, user_results, user_fields)

    print(f"读取数据集: {DATASET_PATH}")
    print(f"用户数: {len(users)}")
    print(f"样本数: {len(dataset)}")
    print_overall(summary_rows)
    print(f"\n汇总结果已保存到 {RESULT_CSV}")
    print(f"用户明细已保存到 {USER_RESULT_CSV}")


if __name__ == "__main__":
    run_experiment()
