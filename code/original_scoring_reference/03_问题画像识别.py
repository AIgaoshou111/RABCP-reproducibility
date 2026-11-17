"""
03_问题画像识别.py

目的：
对每条 Stack Overflow Docker 问题运行 QuestionProfiler，
输出 L/C/G 评分、Dreyfus 观测等级和 L1-L5 概率分布。

输入：
实验结果/预处理数据.json

输出：
实验结果/问题画像结果.jsonl
实验结果/问题画像统计报告.md
实验结果/问题画像进度.json

注意：
本脚本输出的是“问题观测等级”，不是用户真实能力。
单题问题只是一次行为观测，后续需要按用户序列聚合。
"""

import json
import argparse
from pathlib import Path
from tqdm import tqdm
from datetime import datetime
from collections import defaultdict
import sys


BASE_DIR = Path(__file__).resolve().parent
RESULT_DIR = BASE_DIR / "实验结果"

INPUT_DATA = RESULT_DIR / "预处理数据.json"
OUTPUT_JSONL = RESULT_DIR / "问题画像结果.jsonl"
OUTPUT_REPORT = RESULT_DIR / "问题画像统计报告.md"
PROGRESS_FILE = RESULT_DIR / "问题画像进度.json"

BATCH_SIZE = 20


def import_profiler_agent():
    """
    尝试导入项目中的 profiler_agent。
    请确保当前脚本所在目录能够访问 profiler_agent.py。
    """
    candidate_paths = [
        BASE_DIR,
        BASE_DIR.parent,
        BASE_DIR.parent.parent,
        BASE_DIR.parent.parent.parent,
    ]
    for p in candidate_paths:
        sys.path.insert(0, str(p))

    try:
        from profiler_agent import (
            ProfilerExtractor,
            ProfilerAuditor,
            ProfilerMapper,
            get_client,
            get_model_name,
        )
        return ProfilerExtractor, ProfilerAuditor, ProfilerMapper, get_client, get_model_name
    except Exception as e:
        raise ImportError(
            "无法导入 profiler_agent。请确认 profiler_agent.py 位于项目路径中，"
            "且其中包含 ProfilerExtractor、ProfilerAuditor、ProfilerMapper、get_client、get_model_name。"
            f"\n原始错误：{e}"
        )


def compute_weight(confidence: float, risk_flags: list, is_real_data: bool = True) -> float:
    """
    对真实 Stack Overflow 技术问答数据，默认使用固定置信度权重。
    这里不强行触发 risk_flags，避免把真实提问误判为大模型交互噪声。
    """
    if is_real_data:
        return max(0.10, min(1.00, confidence))

    weight = confidence
    if "low_context" in risk_flags:
        weight *= 0.70
    if "copy_paste_risk" in risk_flags:
        weight *= 0.50
    if "cross_domain" in risk_flags:
        weight *= 0.80
    if "simple_confirmation" in risk_flags:
        weight *= 0.85
    if "ambiguous_context" in risk_flags:
        weight *= 0.75
    return max(0.10, min(1.00, weight))


def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"processed_ids": [], "last_update": None}


def save_progress(progress):
    progress["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def load_existing_results():
    results = []
    if OUTPUT_JSONL.exists():
        with open(OUTPUT_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))
    return results


def save_results(results):
    with open(OUTPUT_JSONL, "a", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def process_question(q, extractor, auditor, mapper):
    input_text = f"""Title:
{q.get('title', '')}

Tags:
{q.get('tags', '')}

Body:
{q.get('body', '')}
"""

    try:
        extracted = extractor.extract_information(input_text)
        deconstruction = extracted.get("deconstruction", {})
        audited = auditor.audit_features(deconstruction)

        L = audited.get("linguistic_score", 1)
        C = audited.get("contextual_score", 1)
        G = audited.get("cognitive_score", 1)

        mapped = mapper.map_features_to_dreyfus([L, C, G])

        display_str = mapped.get("display_level", "L3_Competent")
        try:
            display_level = int(display_str.split("_")[0].replace("L", ""))
        except Exception:
            display_level = 3

        confidence = 0.75
        risk_flags = []
        weight = compute_weight(confidence, risk_flags, is_real_data=True)

        distribution = mapped.get("distribution", [0.1, 0.2, 0.4, 0.2, 0.1])
        if not isinstance(distribution, list) or len(distribution) != 5:
            distribution = [0.1, 0.2, 0.4, 0.2, 0.1]

        s = sum(distribution)
        if s > 0:
            distribution = [v / s for v in distribution]

        return {
            "question_id": q["question_id"],
            "user_id": q["user_id"],
            "creation_date": q["creation_date"],
            "title": q.get("title", ""),
            "tags": q.get("tags", ""),
            "domain": "docker",
            "observed_level": mapped.get("fine_level", 3.0),
            "display_level": display_level,
            "distribution": distribution,
            "linguistic_score": L,
            "contextual_score": C,
            "cognitive_score": G,
            "confidence": confidence,
            "risk_flags": risk_flags,
            "observation_weight": weight,

            "body_length": q.get("body_length", 0),
            "has_code": q.get("has_code", False),
            "has_error": q.get("has_error", False),
            "code_block_count": q.get("code_block_count", 0),

            "question_score": q.get("question_score", 0),
            "answer_count": q.get("answer_count", 0),
            "accepted": q.get("accepted", False),
            "closed": q.get("closed", False),
            "view_count": q.get("view_count", 0),
            "comment_count": q.get("comment_count", 0),

            "reputation": q.get("reputation", 0),
            "user_question_count": q.get("user_question_count", 0),
            "user_answer_count": q.get("user_answer_count", 0),
            "answer_question_ratio": q.get("answer_question_ratio", 0),
        }

    except Exception as e:
        print(f"处理问题 {q.get('question_id')} 出错，使用默认画像：{e}")
        return {
            "question_id": q["question_id"],
            "user_id": q["user_id"],
            "creation_date": q["creation_date"],
            "title": q.get("title", ""),
            "tags": q.get("tags", ""),
            "domain": "docker",
            "observed_level": 3.0,
            "display_level": 3,
            "distribution": [0.1, 0.2, 0.4, 0.2, 0.1],
            "linguistic_score": 1,
            "contextual_score": 1,
            "cognitive_score": 1,
            "confidence": 0.75,
            "risk_flags": [],
            "observation_weight": 0.75,

            "body_length": q.get("body_length", 0),
            "has_code": q.get("has_code", False),
            "has_error": q.get("has_error", False),
            "code_block_count": q.get("code_block_count", 0),

            "question_score": q.get("question_score", 0),
            "answer_count": q.get("answer_count", 0),
            "accepted": q.get("accepted", False),
            "closed": q.get("closed", False),
            "view_count": q.get("view_count", 0),
            "comment_count": q.get("comment_count", 0),

            "reputation": q.get("reputation", 0),
            "user_question_count": q.get("user_question_count", 0),
            "user_answer_count": q.get("user_answer_count", 0),
            "answer_question_ratio": q.get("answer_question_ratio", 0),
        }


def run_profiling(batch_size=BATCH_SIZE):
    if not INPUT_DATA.exists():
        raise FileNotFoundError(f"预处理数据不存在：{INPUT_DATA}")

    with open(INPUT_DATA, "r", encoding="utf-8") as f:
        data = json.load(f)

    progress = load_progress()
    processed_ids = set(progress.get("processed_ids", []))
    existing = load_existing_results()

    pending = [q for q in data if q["question_id"] not in processed_ids]
    print(f"总问题数：{len(data)}")
    print(f"已处理：{len(processed_ids)}")
    print(f"剩余：{len(pending)}")

    if not pending:
        print("全部问题已处理。")
        generate_report(existing)
        return

    batch = pending[:batch_size]
    print(f"本批次处理：{len(batch)} 条")

    ProfilerExtractor, ProfilerAuditor, ProfilerMapper, get_client, get_model_name = import_profiler_agent()
    client = get_client()
    model = get_model_name()
    extractor = ProfilerExtractor(client, model)
    auditor = ProfilerAuditor(client, model)
    mapper = ProfilerMapper()

    batch_results = []
    for q in tqdm(batch, desc="问题画像识别"):
        result = process_question(q, extractor, auditor, mapper)
        batch_results.append(result)
        processed_ids.add(q["question_id"])

    save_results(batch_results)
    progress["processed_ids"] = list(processed_ids)
    save_progress(progress)

    print(f"本批次完成：{len(batch_results)}")
    print(f"累计完成：{len(processed_ids)} / {len(data)}")

    all_results = load_existing_results()
    if len(processed_ids) >= len(data):
        generate_report(all_results)


def generate_report(results):
    if not results:
        return

    levels = [float(r["observed_level"]) for r in results]
    displays = defaultdict(int)
    for r in results:
        displays[int(r["display_level"])] += 1

    weights = [float(r["observation_weight"]) for r in results]

    l_dist = defaultdict(int)
    c_dist = defaultdict(int)
    g_dist = defaultdict(int)
    for r in results:
        l_dist[r["linguistic_score"]] += 1
        c_dist[r["contextual_score"]] += 1
        g_dist[r["cognitive_score"]] += 1

    mean_level = sum(levels) / len(levels)
    std_level = (sum((x - mean_level) ** 2 for x in levels) / len(levels)) ** 0.5

    report = []
    report.append("# 问题画像统计报告\n\n")
    report.append(f"> 处理问题数：{len(results)}\n")
    report.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    report.append("## 1. 观测等级统计\n\n")
    report.append("| 指标 | 数值 |\n")
    report.append("|---|---:|\n")
    report.append(f"| 最小值 | {min(levels):.2f} |\n")
    report.append(f"| 最大值 | {max(levels):.2f} |\n")
    report.append(f"| 均值 | {mean_level:.2f} |\n")
    report.append(f"| 标准差 | {std_level:.2f} |\n\n")

    report.append("## 2. 显示等级分布\n\n")
    report.append("| 等级 | 数量 | 占比 |\n")
    report.append("|---|---:|---:|\n")
    for level in sorted(displays):
        report.append(f"| L{level} | {displays[level]} | {displays[level] / len(results):.2%} |\n")

    report.append("\n## 3. 权重统计\n\n")
    report.append("| 指标 | 数值 |\n")
    report.append("|---|---:|\n")
    report.append(f"| 平均 observation_weight | {sum(weights) / len(weights):.2f} |\n")
    report.append(f"| 最小值 | {min(weights):.2f} |\n")
    report.append(f"| 最大值 | {max(weights):.2f} |\n\n")

    report.append("## 4. L/C/G 分布\n\n")
    report.append("### Linguistic Score\n\n")
    for k in sorted(l_dist):
        report.append(f"- L={k}: {l_dist[k]} ({l_dist[k] / len(results):.2%})\n")
    report.append("\n### Contextual Score\n\n")
    for k in sorted(c_dist):
        report.append(f"- C={k}: {c_dist[k]} ({c_dist[k] / len(results):.2%})\n")
    report.append("\n### Cognitive Score\n\n")
    for k in sorted(g_dist):
        report.append(f"- G={k}: {g_dist[k]} ({g_dist[k] / len(results):.2%})\n")

    report.append("\n## 5. 说明\n\n")
    report.append(
        "以上结果描述的是单个问题的观测等级。"
        "单个问题不能代表用户真实能力，后续需要按用户 10 条问题序列进行聚合。\n"
    )

    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write("".join(report))

    print(f"画像统计报告已保存：{OUTPUT_REPORT}")


def reset_progress():
    PROGRESS_FILE.unlink(missing_ok=True)
    OUTPUT_JSONL.unlink(missing_ok=True)
    OUTPUT_REPORT.unlink(missing_ok=True)
    print("已重置问题画像进度和结果。")


def show_status():
    progress = load_progress()
    count = len(progress.get("processed_ids", []))
    print(f"已处理：{count}")
    print(f"最后更新：{progress.get('last_update')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["run", "status", "reset", "report"], default="run")
    parser.add_argument("--batch", type=int, default=BATCH_SIZE)
    args = parser.parse_args()

    if args.mode == "run":
        run_profiling(args.batch)
    elif args.mode == "status":
        show_status()
    elif args.mode == "reset":
        reset_progress()
    elif args.mode == "report":
        generate_report(load_existing_results())
