"""Table 7: recovery fraction and delay conditional on a three-turn recovery."""

from pathlib import Path
import csv
import json
import random
import statistics
import state_switch_forgetting_experiment as switch
from model_misspecification_experiment import hmm

ROOT = Path(__file__).resolve().parent


def save_csv(name, rows):
    with (ROOT / name).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def recovery():
    rows = []
    for seed in switch.SEEDS:
        rng = random.Random(seed)
        for condition in switch.CONDITIONS:
            target = switch.true_path(condition)
            acc = {}
            for _ in range(switch.USERS_PER_CONDITION):
                values, flags = switch.observations(target, rng)
                if condition not in ("abrupt_up", "abrupt_down"):
                    continue
                outputs = switch.method_outputs(values, flags)
                outputs["hmm_matched_stay096"] = hmm(values, stay_probability=0.96)
                for method, est in outputs.items():
                    d = switch.first_recovery(est, target, 20)
                    a = acc.setdefault(
                        method, {"recovered": 0, "delay_sum": 0, "mae_sum": 0.0}
                    )
                    a["recovered"] += d <= 20
                    a["delay_sum"] += d if d <= 20 else 0
                    a["mae_sum"] += statistics.mean(
                        abs(x - y) for x, y in zip(est[20:], target[20:])
                    )
            for method, a in acc.items():
                rows.append(
                    {
                        "seed": seed,
                        "condition": condition,
                        "method": method,
                        "sequences": 420,
                        "recovered": a["recovered"],
                        "delay_sum_recovered": a["delay_sum"],
                        "post_change_MAE": a["mae_sum"] / 420,
                    }
                )
    save_csv("recovery_corrected_seed_results.csv", rows)
    summary = []
    for condition in ("abrupt_up", "abrupt_down"):
        for method in list(dict.fromkeys(r["method"] for r in rows)):
            vals = [
                r for r in rows if r["condition"] == condition and r["method"] == method
            ]
            n = sum(r["sequences"] for r in vals)
            k = sum(r["recovered"] for r in vals)
            summary.append(
                {
                    "condition": condition,
                    "method": method,
                    "sequences": n,
                    "recovered": k,
                    "recovered_fraction": k / n,
                    "conditional_recovery_delay": sum(
                        r["delay_sum_recovered"] for r in vals
                    )
                    / k
                    if k
                    else "",
                    "post_change_MAE": statistics.mean(
                        r["post_change_MAE"] for r in vals
                    ),
                }
            )
    save_csv("recovery_corrected_summary.csv", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    recovery()
