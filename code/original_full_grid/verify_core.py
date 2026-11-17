"""Low-cost independent scalar checks for the vectorized tuning implementation."""
import json
import math
from pathlib import Path
import numpy as np
import run_grid as g


def scalar_rabcp(values, flags, window, sigma, gamma, low_weight):
    p = [.2] * 5
    history, trace = [], []
    for value, flag in zip(values, flags):
        q = [math.exp(-.5 * ((k-value)/sigma)**2) for k in range(1,6)]
        q = [x/sum(q) for x in q]
        history.append(q)
        history = history[-window:]
        h = len(history)
        avg = [sum((i+1)*v[k] for i,v in enumerate(history))/(h*(h+1)/2) for k in range(5)]
        weight = low_weight if flag else 1.
        raw = [((1-gamma)*p[k]+gamma/5) * avg[k]**weight for k in range(5)]
        p = [x/sum(raw) for x in raw]
        trace.append(sum((k+1)*p[k] for k in range(5)))
    return trace


def main():
    np.seterr(divide="raise", over="raise", invalid="raise", under="ignore")
    config = json.loads((Path(__file__).parent / "protocol.json").read_text())
    small = dict(config, development_seeds=[171101], development_per_condition_seed=5)
    data = g.generate(small, "stable", "development")
    evaluator = g.Evaluator(data)
    delta = 0.
    for h in [1,5,40]:
        for sigma in [.4,.8,1.6]:
            for gamma in [0.,.05,1.]:
                for regime in config["regimes"]:
                    p = dict(window=h,sigma=sigma,gamma=gamma,low_weight=.35)
                    actual = evaluator.predictions("rabcp",p,regime)
                    flags = data["flag"] if regime != "no_flags" else np.zeros_like(data["flag"])
                    expected = np.asarray([scalar_rabcp(v,f,**p) for v,f in zip(data["observed"],flags)])
                    delta = max(delta,float(np.max(np.abs(actual-expected))))
                    assert np.allclose(actual,expected,atol=1e-12,rtol=0)
    p = dict(window=5,sigma=.8,gamma=.05,low_weight=.35)
    expected = evaluator.predictions("rabcp",p,"matched_imperfect_flags")
    changed = {k:v.copy() for k,v in data.items()}
    changed["observed"][:,30:] = 5
    actual = g.Evaluator(changed).predictions("rabcp",p,"matched_imperfect_flags")
    assert np.array_equal(actual[:,:30],expected[:,:30])
    for method in config["methods"]:
        for regime in config["regimes"]:
            candidates = g.parameters(config,method,regime)
            assert len(candidates) == len({json.dumps(x,sort_keys=True) for x in candidates})
    print(json.dumps(dict(scalar_reference_configurations=54, maximum_prediction_difference=delta,
                          causal_update=True, unique_grid_combinations=True),indent=2))


if __name__ == "__main__":
    main()
