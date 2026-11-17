"""同一合成序列上的公平调参与独立种子检验。

运行：python3 公平搜索运行器.py
输入：同目录 搜索配置.json。只使用 NumPy；不调用网络或大模型。
开发集只选参数，测试种子只在每方法选定一组参数后计算。
"""

from __future__ import annotations

import csv
import itertools
import json
import math
import random
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
CONFIG = json.loads((HERE / "搜索配置.json").read_text(encoding="utf-8"))
METHODS = ("raw", "cumulative_mean", "sliding_mean", "ewma", "kalman", "hmm", "power_update", "rabcp")
LEVELS = np.arange(1, 6, dtype=float)
LOW_WEIGHTS = CONFIG["spaces"]["rabcp"]["low_weight"]


def generate(seeds: list[int], per_cell: int) -> dict[str, np.ndarray]:
    """Each seed × condition has equal sequence count; anomalies are not true changes."""
    observed, truth, anomalies, imperfect, seed_ids, condition_ids = [], [], [], [], [], []
    turns = CONFIG["turns"]
    timeline = np.arange(turns)
    for seed in seeds:
        for ci, condition in enumerate(CONFIG["conditions"]):
            rng = np.random.default_rng(seed * 17 + ci)
            n = per_cell
            base = rng.uniform(2.0, 4.0, size=(n, 1))
            latent = np.repeat(base, turns, axis=1)
            if condition == "abrupt_up":
                latent[:, 20:] = np.minimum(5.0, base + 1.3)
            elif condition == "abrupt_down":
                latent[:, 20:] = np.maximum(1.0, base - 1.3)
            elif condition == "gradual_up":
                latent += np.minimum(1.3, np.maximum(0.0, (timeline - 10) * 1.3 / 20))[None, :]
                latent = np.clip(latent, 1, 5)
            elif condition == "transient_up":
                latent[:, 15:26] = np.minimum(5.0, base + 1.3)
            noise = rng.normal(0, 0.5, size=(n, turns))
            anomaly = np.zeros((n, turns), dtype=bool)
            contamination = np.zeros((n, turns), dtype=float)
            if condition == "symmetric_mixed":
                anomaly = rng.random((n, turns)) < 0.2
                contamination = anomaly * rng.choice((-1.5, 1.5), size=(n, turns))
            elif condition == "asymmetric_high":
                anomaly = rng.random((n, turns)) < 0.25
                contamination = anomaly * 1.5
            elif condition == "heavy_tail_bursts":
                for i in range(n):
                    for start in rng.integers(0, turns - 3, size=2):
                        anomaly[i, start:start + 3] = True
                contamination = anomaly * rng.standard_t(df=2.5, size=(n, turns)) * 1.4
            elif condition == "persistent_late_bias":
                anomaly[:, 28:] = True
                contamination[:, 28:] = 1.1
            score = np.clip(latent + noise + contamination, 1.0, 5.0)
            detected = rng.random((n, turns)) < np.where(
                anomaly,
                CONFIG["flag_reference"]["recall"],
                CONFIG["flag_reference"]["false_positive_rate"],
            )
            observed.append(score)
            truth.append(latent)
            anomalies.append(anomaly)
            imperfect.append(detected)
            seed_ids.extend([seed] * n)
            condition_ids.extend([condition] * n)
    result = {
        "observed": np.concatenate(observed),
        "truth": np.concatenate(truth),
        "anomaly": np.concatenate(anomalies),
        "flag": np.concatenate(imperfect),
        "seed": np.array(seed_ids),
        "condition": np.array(condition_ids),
    }
    assert result["observed"].shape == result["truth"].shape == result["flag"].shape
    return result


def candidate_configs(method: str, regime: str) -> list[dict]:
    if method == "raw":
        return [{}]
    fields = list(CONFIG["spaces"].get(method, {}))
    if regime == "no_flags":
        fields = [key for key in fields if key != "low_weight"]
    elif "low_weight" not in fields:
        fields.append("low_weight")
    values = [CONFIG["spaces"][method][field] if field in CONFIG["spaces"].get(method, {}) else LOW_WEIGHTS for field in fields]
    configs = [dict(zip(fields, item)) for item in itertools.product(*values)]
    max_configs = CONFIG["max_unique_configs_per_method"]
    if len(configs) > max_configs:
        rng = random.Random(20261115 + METHODS.index(method) * 13 + (regime == "matched_imperfect_flags"))
        configs = [configs[i] for i in sorted(rng.sample(range(len(configs)), max_configs))]
    assert len(configs) <= max_configs and len({json.dumps(c, sort_keys=True) for c in configs}) == len(configs)
    return configs


def gaussian_observation(values: np.ndarray, sigma: float) -> np.ndarray:
    density = np.exp(-0.5 * ((values[:, None] - LEVELS[None, :]) / sigma) ** 2)
    return density / density.sum(axis=1, keepdims=True)


def evaluate(method: str, params: dict, data: dict, regime: str) -> np.ndarray:
    values = data["observed"]
    truth = data["truth"]
    n, turns = values.shape
    low_weight = params.get("low_weight", 1.0)
    flags = data["flag"] if regime == "matched_imperfect_flags" else np.zeros_like(data["flag"])
    weights = np.where(flags, low_weight, 1.0)
    predictions = np.empty_like(values)
    if method == "raw":
        predictions[:] = values
    elif method in ("cumulative_mean", "sliding_mean"):
        window = turns if method == "cumulative_mean" else params["window"]
        for t in range(turns):
            start = max(0, t + 1 - window)
            w = weights[:, start:t + 1]
            predictions[:, t] = (values[:, start:t + 1] * w).sum(axis=1) / w.sum(axis=1)
    elif method == "ewma":
        state = np.full(n, 3.0)
        for t in range(turns):
            alpha = params["alpha"] * weights[:, t]
            state += alpha * (values[:, t] - state)
            predictions[:, t] = state
    elif method == "kalman":
        state = np.full(n, 3.0)
        variance = np.ones(n)
        for t in range(turns):
            variance += params["process_variance"]
            measurement = params["observation_variance"] / weights[:, t]
            gain = variance / (variance + measurement)
            state += gain * (values[:, t] - state)
            variance *= 1 - gain
            predictions[:, t] = state
    elif method == "hmm":
        state = np.full((n, 5), 0.2)
        stay = params["stay_probability"]
        off_diagonal = (1 - stay) / 4
        for t in range(turns):
            likelihood = gaussian_observation(values[:, t], params["sigma"])
            prior = state * (stay - off_diagonal) + off_diagonal
            state = prior * likelihood ** weights[:, t, None]
            state /= state.sum(axis=1, keepdims=True)
            predictions[:, t] = np.sum(state * LEVELS[None, :], axis=1)
    elif method in ("power_update", "rabcp"):
        state = np.full((n, 5), 0.2)
        history: list[np.ndarray] = []
        window = params["window"]
        for t in range(turns):
            likelihood = gaussian_observation(values[:, t], params["sigma"])
            history.append(likelihood)
            history = history[-window:]
            den = len(history) * (len(history) + 1) / 2
            smoothed = sum((i + 1) * item for i, item in enumerate(history)) / den
            gamma = params["gamma"]
            state = ((1 - gamma) * state + gamma / 5) * smoothed ** weights[:, t, None]
            state /= state.sum(axis=1, keepdims=True)
            predictions[:, t] = np.sum(state * LEVELS[None, :], axis=1)
    else:
        raise ValueError(method)
    return np.mean(np.abs(predictions - truth), axis=1)


def save_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    dev = generate(CONFIG["development_seeds"], CONFIG["development_sequences_per_condition_per_seed"])
    test = generate(CONFIG["test_seeds"], CONFIG["test_sequences_per_condition_per_seed"])
    assert set(dev["seed"]).isdisjoint(set(test["seed"]))
    assert len(dev["seed"]) == 10 * 8 * 20 and len(test["seed"]) == 30 * 8 * 40
    search_rows, test_rows, per_seed_rows = [], [], []
    for regime in CONFIG["regimes"]:
        for method in METHODS:
            candidates = candidate_configs(method, regime)
            scored = []
            for cid, params in enumerate(candidates, start=1):
                value = float(evaluate(method, params, dev, regime).mean())
                scored.append((value, cid, params))
                search_rows.append({"regime": regime, "method": method, "candidate_id": cid,
                                    "params_json": json.dumps(params, sort_keys=True), "development_MAE": f"{value:.6f}"})
            best, cid, params = min(scored, key=lambda entry: (entry[0], entry[1]))
            error = evaluate(method, params, test, regime)
            per_seed = [float(error[test["seed"] == seed].mean()) for seed in CONFIG["test_seeds"]]
            test_rows.append({"regime": regime, "method": method, "n_candidates": len(candidates),
                              "best_candidate_id": cid, "params_json": json.dumps(params, sort_keys=True),
                              "development_MAE": f"{best:.6f}", "test_MAE": f"{np.mean(per_seed):.6f}",
                              "test_seed_SD": f"{np.std(per_seed, ddof=1):.6f}"})
            per_seed_rows.extend({"regime": regime, "method": method, "seed": seed, "MAE": f"{value:.6f}"}
                                 for seed, value in zip(CONFIG["test_seeds"], per_seed))
            print(regime, method, len(candidates), f"dev={best:.4f}", f"test={np.mean(per_seed):.4f}", flush=True)
    save_csv(HERE / "开发搜索/参数搜索_实测.csv", search_rows)
    save_csv(HERE / "留出测试/方法汇总_实测.csv", test_rows)
    save_csv(HERE / "留出测试/每种子误差_实测.csv", per_seed_rows)


if __name__ == "__main__":
    main()
