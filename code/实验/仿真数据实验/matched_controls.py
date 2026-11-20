"""Table 6 controls on the original 50 stationary and 50 change cohorts."""

from collections import defaultdict
from pathlib import Path
import csv
import json
import math
import random
import statistics
import numpy as np
import model_misspecification_experiment as stress
import state_switch_forgetting_experiment as switch

R = Path(__file__).resolve().parent


def kernel(v):
    q = [math.exp(-((k - v) ** 2) / (2 * 0.8**2)) for k in range(1, 6)]
    return [x / sum(q) for x in q]


def outputs(values, flags, gamma):
    p = [0.2] * 5
    total = mass = 0.0
    means = []
    filters = []
    for v, f in zip(values, flags):
        w = 0.35 if f else 1.0
        total += w * v
        mass += w
        means.append(total / mass)
        q = kernel(v)
        u = [((1 - gamma) * a + gamma / 5) * b**w for a, b in zip(p, q)]
        p = [a / sum(u) for a in u]
        filters.append(sum(k * a for k, a in enumerate(p, 1)))
    return {"weighted_mean": means, "weighted_filter_window1": filters}


def save(name, rows):
    with (R / name).open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def controls():
    rows = []
    for seed in stress.SEEDS:
        rng = random.Random(seed)
        for c in stress.CONDITIONS:
            acc = defaultdict(list)
            for level in stress.LEVELS:
                for _ in range(stress.USERS_PER_LEVEL):
                    v, r = stress.generate_sequence(level, c, rng)
                    f = stress.imperfect_flags(r, rng)
                    for m, est in outputs(v, f, 0).items():
                        acc[m].append(statistics.mean(abs(x - level) for x in est[9:]))
            for m, x in acc.items():
                rows.append(
                    dict(
                        seed=seed,
                        condition=c,
                        method=m,
                        gamma=0,
                        MAE=statistics.mean(x),
                    )
                )
    for seed in switch.SEEDS:
        rng = random.Random(seed)
        for c in switch.CONDITIONS:
            target = switch.true_path(c)
            acc = defaultdict(list)
            for _ in range(switch.USERS_PER_CONDITION):
                v, f = switch.observations(target, rng)
                if c not in ("abrupt_up", "abrupt_down"):
                    continue
                for m, est in outputs(v, f, 0.05).items():
                    acc[m].append(
                        statistics.mean(
                            abs(x - y) for x, y in zip(est[20:], target[20:])
                        )
                    )
            for m, x in acc.items():
                rows.append(
                    dict(
                        seed=seed,
                        condition=c,
                        method=m,
                        gamma=0.05,
                        MAE=statistics.mean(x),
                    )
                )
    save("component_control_seed_results.csv", rows)
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["condition"], r["method"], r["gamma"])].append(r["MAE"])
    summary = [
        dict(
            condition=c,
            method=m,
            gamma=g,
            MAE=statistics.mean(v),
            seed_low=float(np.quantile(v, 0.025)),
            seed_high=float(np.quantile(v, 0.975)),
        )
        for (c, m, g), v in grouped.items()
    ]
    save("component_control_summary.csv", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    controls()
