"""
噪声鲁棒性实验。

目的：
- 系统改变噪声比例，观察各状态估计方法的稳定性。
- 不调用大模型，只使用合成数据中的 true_user_level / observed_question_level。
- 该实验回答：当问题序列中异常观测变多时，WeightedBAE 是否比普通 BAE 更稳。
"""

import csv
import random
import sys
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from 状态估计实验 import (
    METHODS,
    aggregate,
    evaluate_user,
    group_by_user,
    load_dataset,
)


EXPERIMENT_DIR = Path(__file__).resolve().parent
DATASET_PATH = PROJECT_ROOT / "data" / "合成数据集.json"
RESULT_CSV = EXPERIMENT_DIR / "噪声鲁棒性实验结果.csv"
RANDOM_SEED = 20260528
NOISE_RATIOS = [0.0, 0.1, 0.2, 0.4, 0.6]
NOISE_MODES = ["high_noise", "low_noise", "mixed_noise"]


def inject_noise(user_rows: List[dict], noise_ratio: float, noise_mode: str, rng: random.Random) -> List[dict]:
    """在干净用户序列中按比例注入观测噪声，不改变 true_user_level。

    注意：鲁棒性实验从 true_user_level 构造干净观测，再注入指定比例的
    人工噪声。这样不同 noise_ratio 之间只有注入比例不同，避免原始合成
    数据中已有的自然波动影响趋势解释。
    """
    rows = [row.copy() for row in user_rows]
    count = int(round(len(rows) * noise_ratio))
    if count <= 0:
        for row in rows:
            row["observed_question_level"] = row["true_user_level"]
            row["is_noise"] = False
            row["noise_type"] = "normal"
            row["question_domain"] = row["primary_domain"]
        return rows

    noise_indexes = set(rng.sample(range(len(rows)), count))
    for index, row in enumerate(rows):
        true_level = row["true_user_level"]

        if index not in noise_indexes:
            row["observed_question_level"] = true_level
            row["is_noise"] = False
            row["noise_type"] = "normal"
            row["question_domain"] = row["primary_domain"]
            continue

        if noise_mode == "high_noise":
            noise_type = "high_noise"
        elif noise_mode == "low_noise":
            noise_type = "low_noise"
        else:
            noise_type = rng.choice(["high_noise", "low_noise", "cross_domain"])

        row["is_noise"] = True
        row["noise_type"] = noise_type

        if noise_type == "high_noise":
            row["observed_question_level"] = min(5, true_level + rng.choice([1, 2]))
            row["question_domain"] = row["primary_domain"]
        elif noise_type == "low_noise":
            row["observed_question_level"] = max(1, true_level - rng.choice([1, 2]))
            row["question_domain"] = row["primary_domain"]
        else:
            row["observed_question_level"] = rng.randint(1, 5)
            row["question_domain"] = "__cross_domain__"

    return rows


def run_experiment():
    dataset = load_dataset(DATASET_PATH)
    users = group_by_user(dataset)
    rows = []

    for noise_mode in NOISE_MODES:
        for noise_ratio in NOISE_RATIOS:
            rng = random.Random(f"{RANDOM_SEED}-{noise_mode}-{noise_ratio}")
            user_results = []
            for user_rows in users.values():
                noisy_rows = inject_noise(
                    user_rows=user_rows,
                    noise_ratio=noise_ratio,
                    noise_mode=noise_mode,
                    rng=rng,
                )
                user_results.extend(evaluate_user(noisy_rows))

            by_method: Dict[str, List[dict]] = {method: [] for method in METHODS}
            for result in user_results:
                by_method[result["method"]].append(result)

            for method in METHODS:
                metrics = aggregate(by_method[method])
                rows.append({
                    "noise_mode": noise_mode,
                    "noise_ratio": noise_ratio,
                    "method": method,
                    **metrics,
                })

    fieldnames = [
        "noise_mode",
        "noise_ratio",
        "method",
        "user_count",
        "final_error",
        "mae_all",
        "mae_after_10",
        "volatility",
        "convergence_rate",
        "avg_convergence_turn",
    ]
    with open(RESULT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"读取数据集: {DATASET_PATH}")
    print(f"输出结果: {RESULT_CSV}")
    print("\n关键结果：mixed_noise")
    print("-" * 82)
    print(f"{'ratio':>6} {'method':<26} {'final_err':>10} {'mae_after10':>12} {'conv_rate':>10}")
    print("-" * 82)
    for row in rows:
        if row["noise_mode"] == "mixed_noise" and row["method"] in [
            "bae_smoothing",
            "weighted_bae_noise_flag",
            "weighted_bae_noise_type",
        ]:
            print(
                f"{row['noise_ratio']:>6.1f} "
                f"{row['method']:<26} "
                f"{row['final_error']:>10.3f} "
                f"{row['mae_after_10']:>12.3f} "
                f"{row['convergence_rate']:>10.2%}"
            )


if __name__ == "__main__":
    run_experiment()
