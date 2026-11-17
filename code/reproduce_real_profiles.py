"""从冻结的逐题观测重算每位用户的十题后验；不调用网络。"""

import csv
import json
from collections import defaultdict
from pathlib import Path

from BAE import BayesianLevelEstimator


ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / "data/question_observations_870.jsonl"
    observations = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    users = defaultdict(list)
    for row in observations:
        users[row["user_code"]].append(row)
    assert len(observations) == 870 and len(users) == 87

    result = []
    for user_code, history in sorted(users.items()):
        assert len(history) == 10
        history.sort(key=lambda row: (row["creation_date"], row["question_id"]))
        estimator = BayesianLevelEstimator(smooth_window=5)
        for row in history:
            estimator.update(row["distribution"], observation_weight=float(row["observation_weight"]))
        posterior = estimator.get_distribution()
        result.append({
            "user_code": user_code,
            "questions": len(history),
            "posterior_mean": f"{sum((i + 1) * probability for i, probability in enumerate(posterior)):.6f}",
            **{f"p{i + 1}": f"{probability:.6f}" for i, probability in enumerate(posterior)},
        })

    output = ROOT / "results/real_profiles_recomputed.csv"
    with output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(result[0]))
        writer.writeheader()
        writer.writerows(result)
    print(f"Recomputed {len(result)} profiles from {len(observations)} archived observations: {output.name}")


if __name__ == "__main__":
    main()
