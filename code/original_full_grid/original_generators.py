"""原投稿模拟生成函数的逐字摘录；只移除与数据生成无关的导入和主程序。"""

import random

TURNS = 40

def clip(value):
    return min(5.0, max(1.0, value))

def generate_sequence(level, condition, rng):
    observations, risks = [], []
    burst_start = rng.choice([8, 14, 20, 26])
    for turn in range(TURNS):
        risk = False
        value = float(level)
        if condition == "symmetric_mixed" and rng.random() < 0.4:
            risk = True
            value = clip(level + rng.choice([-2, -1, 1, 2]))
        elif condition == "asymmetric_high" and rng.random() < 0.4:
            risk = True
            value = clip(level + rng.choice([1, 1, 2]))
        elif condition == "heavy_tail_bursts":
            if burst_start <= turn < burst_start + 5 or rng.random() < 0.08:
                risk = True
                value = float(rng.choice([1, 5]))
            elif rng.random() < 0.15:
                value = clip(level + rng.choice([-1, 1]))
        elif condition == "persistent_late_bias":
            if turn >= 25:
                risk = True
                value = clip(level + 1)
            elif rng.random() < 0.15:
                value = clip(level + rng.choice([-1, 1]))
        observations.append(value)
        risks.append(risk)
    return observations, risks

def imperfect_flags(risks, rng):
    return [rng.random() < (0.8 if risk else 0.1) for risk in risks]

def true_path(condition):
    if condition == "abrupt_up":
        return [2.0] * 20 + [4.0] * 20
    if condition == "abrupt_down":
        return [4.0] * 20 + [2.0] * 20
    if condition == "gradual_up":
        return [2.0] * 15 + [2.0 + 2.0 * index / 14 for index in range(15)] + [4.0] * 10
    if condition == "transient_up":
        return [2.0] * 20 + [4.0] * 6 + [2.0] * 14
    if condition == "stationary_noisy":
        return [3.0] * 40
    raise ValueError(condition)

def observations(path, rng):
    values, risks = [], []
    for target in path:
        risk = rng.random() < 0.15
        if risk:
            value = rng.choice([1.0, 5.0])
        else:
            value = min(5.0, max(1.0, round(target + rng.choice([-1, 0, 0, 0, 0, 1]))))
        values.append(value)
        risks.append(risk)
    flags = [rng.random() < (0.8 if risk else 0.1) for risk in risks]
    return values, flags
