"""Verify complete-grid output and build Chinese review tables, without refitting."""
from pathlib import Path
import csv
import json
import hashlib
import sys
import numpy as np

import run_grid as g


def load_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    root = Path(__file__).resolve().parent
    output = root / (sys.argv[1] if len(sys.argv) > 1 else "results_verified")
    config = json.loads((root / "protocol.json").read_text())
    completion = json.loads((output / "completed.json").read_text())
    assert all(g.digest(output / name) == value for name, value in completion["output_hashes"].items())
    summary = load_csv(output / "test_summary.csv")
    detail = load_csv(output / "test_seed_condition.csv")
    selected = json.loads((output / "selected_before_test.json").read_text())
    verified_count = 0
    for choice in selected:
        s, r, m = choice["suite"], choice["regime"], choice["method"]
        records = json.loads((output / f"search_{s}_{r}_{m}.json").read_text())
        assert [x["params"] for x in records] == g.parameters(config, m, r)
        assert choice["candidate_id"] == min(records, key=lambda x:(x["development_MAE"],x["candidate_id"]))["candidate_id"]
        verified_count += len(records)
        one = next(x for x in summary if (x["suite"],x["regime"],x["method"]) == (s,r,m))
        vals = [float(x["MAE"]) for x in detail if (x["suite"],x["regime"],x["method"]) == (s,r,m)]
        assert abs(np.mean(vals) - float(one["test_MAE"])) < 1e-12
    assert verified_count == completion["n_development_candidates"]
    verification = dict(completed=True, evaluated_candidates=verified_count,
                        parameter_panels=len(selected), all_grid_combinations_present=True,
                        selected_configurations_are_development_minima=True,
                        test_summary_matches_seed_condition_rows=True,
                        recorded_file_hashes_match=True)
    # Replay each selected configuration on saved test observations once.
    # This checks serialization/replay, not a second parameter selection.
    largest = 0.
    for suite in config["suites"]:
        saved = np.load(output / f"test_{suite}.npz")
        data = {key:saved[key] for key in saved.files}
        dev = np.load(output / f"development_{suite}.npz")
        assert set(data["seed"]).isdisjoint(set(dev["seed"]))
        evaluator = g.Evaluator(data)
        for choice in [x for x in selected if x["suite"] == suite]:
            err = evaluator.errors(choice["method"], choice["params"], choice["regime"])
            row = next(x for x in summary if (x["suite"],x["regime"],x["method"]) == (suite,choice["regime"],choice["method"]))
            delta = abs(float(err.mean())-float(row["test_MAE"]))
            largest = max(largest,delta)
            assert delta < 1e-12
        dev.close(); saved.close()
    verification["maximum_replay_MAE_difference"] = largest
    g.write_json(output / "verification_after_run.json", verification)
    names = {"raw":"原始观测", "cumulative_mean":"累积均值", "sliding_mean":"滑动均值",
             "ewma":"EWMA", "kalman":"Kalman", "hmm":"HMM", "power_update":"单步幂更新",
             "rabcp_no_forgetting":"RABCP（无遗忘）", "rabcp":"RABCP（调节遗忘）"}
    suites = {"stable":"稳定能力与观测噪声", "change":"能力变化及稳定对照"}
    lines = ["# 原论文条件下的完整网格调参：核验结果", "",
             f"本轮共评估 **{verified_count:,}** 个方法／实验组／标记条件／参数组合，形成 **{len(selected)}** 组开发集选参结果。所有声明网格组合均已计算。", "",
             "开发集共1,800条序列，测试集共10,800条序列，均为40轮；测试序列在每个方法间复用。两个实验组各用10个开发种子和30个全新测试种子。", "",
             "以下MAE按原论文对应评分窗口计算。两个实验组分别选参、分别报告。置信区间对30个测试种子成组重抽样5,000次。", ""]
    for suite in config["suites"]:
        lines += [f"## {suites[suite]}", "", "| 方法 | 无标记MAE | 相同不完美标记MAE |", "|---|---:|---:|"]
        for method in config["methods"]:
            vals = [float(next(x for x in summary if (x["suite"],x["regime"],x["method"]) == (suite,r,method))["test_MAE"]) for r in config["regimes"]]
            lines.append(f"| {names[method]} | {vals[0]:.5f} | {vals[1]:.5f} |")
        lines += ["", "所选RABCP参数：", ""]
        for r in config["regimes"]:
            row = next(x for x in summary if (x["suite"],x["regime"],x["method"]) == (suite,r,"rabcp"))
            lines.append(f"- {r}：`{row['params']}`；MAE 95%区间 [{float(row['seed_bootstrap_low']):.5f}, {float(row['seed_bootstrap_high']):.5f}]。")
        lines.append("")
    sensitivity = load_csv(output / "rabcp_development_sensitivity.csv")
    lines += ["## 参数敏感性与边界", "", "| 实验组 | 标记条件 | 参数 | 选择值 | 单因素扫描MAE范围 | 选择值在网格端点 |", "|---|---|---|---:|---|---|"]
    for suite in config["suites"]:
        for regime in config["regimes"]:
            sub = [x for x in sensitivity if x["suite"] == suite and x["regime"] == regime]
            for parameter in dict.fromkeys(x["parameter"] for x in sub):
                entries = [x for x in sub if x["parameter"] == parameter]
                vals = [float(x["local_development_MAE"]) for x in entries]
                e = entries[0]
                lines.append(f"| {suite} | {regime} | {parameter} | {e['selected_value']} | {min(vals):.5f}–{max(vals):.5f} | {e['selected_at_grid_boundary']} |")
    lines += ["", "单因素范围表示固定其余已选开发参数、遍历该参数全部候选的误差跨度；不是统计置信区间。完整逐点及剖面结果见CSV。端点选择按预先规则报告，不利用测试成绩改动网格。", "",
              "## 全部材料", "", "- `protocol.json`：参数空间、种子、选择规则和原生成器来源哈希。",
              "- `results_verified/search_*.json`及两张搜索CSV：全部候选开发误差。",
              "- `selected_before_test.json`：测试数据生成前保存的全部配置。",
              "- `test_summary.csv`、`test_seed_condition.csv`：完整及逐情景测试结果。",
              "- `paired_seed_intervals.csv`：RABCP与每个对照的按种子配对差值。",
              "- `rabcp_development_sensitivity.csv`：局部单因素与参数剖面。",
              "- `original_default_reference.csv`：原稳定与原动态配置的分别复算。",
              "- `verification_after_run.json`：完整性、选择规则、文件哈希与数值重放核验。", "",
              "旧results目录是数值库警告后中止的开发运行，正式分析只使用results_verified。未改变算法、候选范围或测试规则；改动仅为把五项矩阵乘法换成直接求和。", ""]
    (root / "完整网格结果_供审核.md").write_text("\n".join(lines))
    print(json.dumps(verification,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
