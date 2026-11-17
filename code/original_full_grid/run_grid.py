"""Complete finite-grid tuning using the submitted paper's simulation generators.

Run: python3 run_grid.py
Only NumPy is required. No network/model calls; one process, single BLAS thread.
Development results select configurations. Fresh test seeds are evaluated only
after all configurations have been saved. Existing outputs are never overwritten.
"""
from __future__ import annotations

import os
for _key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_key] = "1"

import argparse
import csv
import hashlib
import itertools
import json
import random
import time
from pathlib import Path

import numpy as np
import original_generators as gen

HERE = Path(__file__).resolve().parent
LEVELS = np.arange(1., 6.)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_csv(path, rows):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parameters(config, method, regime):
    space = dict(config["spaces"][method])
    if regime != "no_flags" and method != "raw":
        space["low_weight"] = config["low_weights"]
    return [dict(zip(space, values)) for values in itertools.product(*space.values())]


def generate(config, suite, split):
    """Use original functions; new independent RNG streams for each seed/condition.

    Stable cohorts are balanced across all five original levels. Seeds differ
    from the submitted experiments and the previous exploratory supplement.
    """
    per = config[f"{split}_per_condition_seed"]
    seeds = config[f"{split}_seeds"]
    obs, truth, flags, seed_ids, conditions, starts = [], [], [], [], [], []
    for seed in seeds:
        for ci, condition in enumerate(config["suites"][suite]):
            rng = random.Random(seed * 100 + ci + (0 if suite == "stable" else 50))
            for i in range(per):
                if suite == "stable":
                    level = i % 5 + 1
                    values, risks = gen.generate_sequence(level, condition, rng)
                    detected = gen.imperfect_flags(risks, rng)
                    target = [float(level)] * config["turns"]
                else:
                    target = gen.true_path(condition)
                    values, detected = gen.observations(target, rng)
                obs.append(values)
                truth.append(target)
                flags.append(detected)
                seed_ids.append(seed)
                conditions.append(condition)
                starts.append(config["scoring_start_zero_based"][condition])
    data = dict(observed=np.asarray(obs, dtype=float), truth=np.asarray(truth, dtype=float),
                flag=np.asarray(flags, dtype=bool), seed=np.asarray(seed_ids),
                condition=np.asarray(conditions), start=np.asarray(starts))
    data["mask"] = np.arange(config["turns"])[None, :] >= data["start"][:, None]
    return data


class Evaluator:
    """Vectorize over independent sequences while keeping the original updates."""
    def __init__(self, data):
        self.data = data
        self.q_cache = {}
        self.smooth_cache = {}
        self.error_cache = {}

    def likelihood(self, sigma):
        if sigma not in self.q_cache:
            logq = -.5 * ((self.data["observed"].T[:, :, None] - LEVELS) / sigma) ** 2
            logq -= logq.max(axis=2, keepdims=True)
            q = np.exp(logq)
            self.q_cache[sigma] = q / q.sum(axis=2, keepdims=True)
        return self.q_cache[sigma]

    def smooth(self, sigma, window):
        key = (sigma, window)
        if key not in self.smooth_cache:
            q = self.likelihood(sigma)
            smooth = np.empty_like(q)
            for t in range(len(q)):
                h = min(t + 1, window)
                w = np.arange(1., h + 1.)
                smooth[t] = np.sum(q[t + 1 - h:t + 1] * w[:, None, None], axis=0) / w.sum()
            self.smooth_cache[key] = np.log(smooth)
        return self.smooth_cache[key]

    def predictions(self, method, params, regime):
        v = self.data["observed"]
        n, turns = v.shape
        flag = self.data["flag"] if regime != "no_flags" else np.zeros_like(self.data["flag"])
        weights = np.where(flag, params.get("low_weight", 1.), 1.)
        out = np.empty_like(v)
        if method == "raw":
            return v.copy()
        if method in ("cumulative_mean", "sliding_mean"):
            h = turns if method == "cumulative_mean" else params["window"]
            for t in range(turns):
                a = max(0, t + 1 - h)
                w = weights[:, a:t + 1]
                out[:, t] = (v[:, a:t + 1] * w).sum(axis=1) / w.sum(axis=1)
        elif method == "ewma":
            state = np.full(n, 3.)
            for t in range(turns):
                state += params["alpha"] * weights[:, t] * (v[:, t] - state)
                out[:, t] = state
        elif method == "kalman":
            state = np.full(n, 3.)
            variance = np.full(n, params["initial_variance"])
            for t in range(turns):
                variance += params["process_variance"]
                gain = variance / (variance + params["observation_variance"] / weights[:, t])
                state += gain * (v[:, t] - state)
                variance *= 1 - gain
                out[:, t] = state
        elif method == "hmm":
            state = np.full((n, 5), .2)
            stay = params["stay_probability"]
            off = (1 - stay) / 4
            q = self.likelihood(params["sigma"])
            for t in range(turns):
                state = (state * (stay - off) + off) * q[t] ** weights[:, t, None]
                state /= state.sum(axis=1, keepdims=True)
                out[:, t] = np.sum(state * LEVELS, axis=1)
        elif method in ("rabcp", "power_update", "rabcp_no_forgetting"):
            logstate = np.full((n, 5), -np.log(5.))
            logq = self.smooth(params["sigma"], params["window"])
            gamma = params["gamma"]
            for t in range(turns):
                if gamma:
                    logstate = np.log((1 - gamma) * np.exp(logstate) + gamma / 5)
                logstate += logq[t] * weights[:, t, None]
                logstate -= logstate.max(axis=1, keepdims=True)
                logstate -= np.log(np.exp(logstate).sum(axis=1, keepdims=True))
                out[:, t] = np.sum(np.exp(logstate) * LEVELS, axis=1)
        else:
            raise ValueError(method)
        assert np.isfinite(out).all()
        return out

    def errors(self, method, params, regime):
        # Reuse identical algorithm/configuration evaluations across ablations.
        engine = "rabcp" if method in ("power_update", "rabcp_no_forgetting") else method
        key = (engine, json.dumps(params, sort_keys=True), regime)
        if key not in self.error_cache:
            pred = self.predictions(method, params, regime)
            mask = self.data["mask"]
            err = np.abs(pred - self.data["truth"])
            self.error_cache[key] = (err * mask).sum(axis=1) / mask.sum(axis=1)
        return self.error_cache[key]


def sensitivity(config, records, selected):
    rows = []
    for regime in config["regimes"]:
        entries = [r for r in records if r["regime"] == regime and r["method"] == "rabcp"]
        best = next(s for s in selected if s["regime"] == regime and s["method"] == "rabcp")
        bestp = best["params"]
        for field in bestp:
            vals = sorted({r["params"][field] for r in entries})
            for value in vals:
                matches = [r for r in entries if r["params"][field] == value]
                local = [r for r in matches if all(r["params"][k] == v for k, v in bestp.items() if k != field)]
                assert len(local) == 1
                rows.append(dict(suite=best["suite"], regime=regime, parameter=field, value=value,
                                 selected_value=bestp[field], selected_at_grid_boundary=bestp[field] in (vals[0], vals[-1]),
                                 local_development_MAE=local[0]["development_MAE"],
                                 profiled_development_MAE=min(r["development_MAE"] for r in matches)))
    return rows


def cluster_interval(values, rng, draws):
    indices = rng.integers(0, len(values), size=(draws, len(values)))
    lo, hi = np.quantile(values[indices].mean(axis=1), [.025, .975])
    return float(lo), float(hi)


def main():
    np.seterr(divide="raise", over="raise", invalid="raise", under="ignore")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="results")
    args = parser.parse_args()
    config = json.loads((HERE / "protocol.json").read_text())
    output = HERE / args.output
    output.mkdir(exist_ok=True)
    hashes = {f: digest(HERE / f) for f in ("protocol.json", "run_grid.py", "original_generators.py")}
    manifest = dict(hashes=hashes, numpy=np.__version__, python=__import__("sys").version,
                    start_utc=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                    threads=1, external_calls=0)
    manifest_file = output / "run_manifest.json"
    if manifest_file.exists():
        old = json.loads(manifest_file.read_text())
        if old["hashes"] != hashes:
            raise RuntimeError("Frozen code/configuration changed. Use a new output directory.")
        if (output / "completed.json").exists():
            raise RuntimeError("Run already completed; refusing to overwrite.")
    else:
        write_json(manifest_file, manifest)
    assert set(config["development_seeds"]).isdisjoint(config["test_seeds"])
    all_selected, all_sensitivity = [], []
    started = time.monotonic()
    for suite in config["suites"]:
        dev = generate(config, suite, "development")
        np.savez_compressed(output / f"development_{suite}.npz", **dev)
        evaluator = Evaluator(dev)
        suite_records, suite_selected = [], []
        for regime in config["regimes"]:
            for method in config["methods"]:
                checkpoint = output / f"search_{suite}_{regime}_{method}.json"
                candidates = parameters(config, method, regime)
                if checkpoint.exists():
                    records = json.loads(checkpoint.read_text())
                    assert [r["params"] for r in records] == candidates
                else:
                    records = []
                    for cid, params in enumerate(candidates):
                        error = evaluator.errors(method, params, regime)
                        records.append(dict(suite=suite, regime=regime, method=method, candidate_id=cid,
                                            params=params, development_MAE=float(error.mean())))
                        if (cid + 1) % 100 == 0:
                            print(f"{suite}/{regime}/{method} {cid+1}/{len(candidates)} elapsed={time.monotonic()-started:.0f}s", flush=True)
                        time.sleep(config["sleep_between_candidates_seconds"])
                    write_json(checkpoint, records)
                best = min(records, key=lambda r: (r["development_MAE"], r["candidate_id"]))
                suite_selected.append(dict(best, candidates=len(candidates)))
                suite_records.extend(records)
                print(f"DONE DEV {suite}/{regime}/{method} {len(candidates)} best={best['development_MAE']:.6f}", flush=True)
        all_selected.extend(suite_selected)
        all_sensitivity.extend(sensitivity(config, suite_records, suite_selected))
        write_csv(output / f"search_{suite}.csv", [dict(r, params=json.dumps(r["params"], sort_keys=True)) for r in suite_records])
        del evaluator, dev
    # Freeze every choice before generating any test observation.
    write_json(output / "selected_before_test.json", all_selected)
    selection_hash = digest(output / "selected_before_test.json")
    write_csv(output / "rabcp_development_sensitivity.csv", all_sensitivity)
    rows, detail, pairs, defaults = [], [], [], []
    rng = np.random.default_rng(config["bootstrap_seed"])
    for suite in config["suites"]:
        data = generate(config, suite, "test")
        np.savez_compressed(output / f"test_{suite}.npz", **data)
        evaluator = Evaluator(data)
        cache = {}
        for selection in [s for s in all_selected if s["suite"] == suite]:
            regime, method = selection["regime"], selection["method"]
            error = evaluator.errors(method, selection["params"], regime)
            per_seed = np.array([error[data["seed"] == seed].mean() for seed in config["test_seeds"]])
            cache[(regime, method)] = per_seed
            low, high = cluster_interval(per_seed, rng, config["bootstrap_resamples"])
            rows.append(dict(selection, params=json.dumps(selection["params"], sort_keys=True),
                             test_MAE=float(per_seed.mean()), seed_bootstrap_low=low, seed_bootstrap_high=high,
                             test_sequences=len(error)))
            for seed in config["test_seeds"]:
                for condition in config["suites"][suite]:
                    mask = (data["seed"] == seed) & (data["condition"] == condition)
                    detail.append(dict(suite=suite, regime=regime, method=method, seed=seed, condition=condition,
                                       MAE=float(error[mask].mean())))
            print(f"TEST {suite}/{regime}/{method}: {per_seed.mean():.6f}", flush=True)
        for regime in config["regimes"]:
            for method in config["methods"]:
                if method == "rabcp":
                    continue
                difference = cache[(regime, "rabcp")] - cache[(regime, method)]
                lo, hi = cluster_interval(difference, rng, config["bootstrap_resamples"])
                pairs.append(dict(suite=suite, regime=regime, comparison=f"rabcp minus {method}",
                                  delta_MAE=float(difference.mean()), seed_bootstrap_low=lo, seed_bootstrap_high=hi))
            # Correctly retain original stationary/dynamic configurations separately.
            for gamma in ([0.] if suite == "stable" else [0., .02, .05, .1]):
                p = dict(window=5, sigma=.8, gamma=gamma)
                if regime != "no_flags":
                    p["low_weight"] = .35
                err = evaluator.errors("rabcp", p, regime)
                for condition in config["suites"][suite]:
                    defaults.append(dict(suite=suite, regime=regime, condition=condition, params=json.dumps(p, sort_keys=True),
                                         test_MAE=float(err[data["condition"] == condition].mean())))
        del evaluator, data
    write_csv(output / "test_summary.csv", rows)
    write_csv(output / "test_seed_condition.csv", detail)
    write_csv(output / "paired_seed_intervals.csv", pairs)
    write_csv(output / "original_default_reference.csv", defaults)
    assert selection_hash == digest(output / "selected_before_test.json")
    write_json(output / "completed.json", dict(seconds=time.monotonic()-started,
               n_development_candidates=sum(r["candidates"] for r in rows), selected_hash=selection_hash,
               output_hashes={p.name:digest(p) for p in output.iterdir() if p.is_file()}))
    print("COMPLETED", output, flush=True)


if __name__ == "__main__":
    main()
