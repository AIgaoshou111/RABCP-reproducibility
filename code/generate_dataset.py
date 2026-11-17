"""
生成新版严谨合成数据集。

目标：
1. 每个样本都有上帝视角用户等级 true_user_level。
2. 每个问题都有观测等级 observed_question_level，用来模拟提问中暴露出的认知水平。
3. 显式记录噪声类型，区分正常问题、复制粘贴型高估、偶发简单问题、跨领域漂移。
4. 等级、领域、用户画像场景尽量均衡，便于后续做收敛实验和消融实验。
"""

import argparse
import json
import random
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List


RANDOM_SEED = 20260526
DEFAULT_OUTPUT = "data/合成数据集.json"
DEFAULT_META_OUTPUT = "data/合成数据集_元信息.json"

DOMAINS = {
    "backend": {
        "entities": ["Flask", "FastAPI", "Django", "Redis", "MySQL", "Kafka", "JWT", "Celery"],
        "concepts": ["连接池", "事务隔离", "缓存一致性", "消息幂等", "认证鉴权", "异步任务"],
        "errors": ["Connection refused", "Deadlock found", "Token expired", "Timeout", "Duplicate key"],
    },
    "frontend": {
        "entities": ["React", "Vue", "CSS", "WebSocket", "Webpack", "DOM", "Vite", "Next.js"],
        "concepts": ["组件生命周期", "状态管理", "虚拟 DOM", "hydration", "事件冒泡", "响应式布局"],
        "errors": ["Hydration failed", "CORS error", "Cannot read properties of undefined", "Chunk load failed"],
    },
    "devops": {
        "entities": ["Docker", "Nginx", "Kubernetes", "Jenkins", "Terraform", "Linux", "Prometheus"],
        "concepts": ["滚动发布", "服务发现", "资源限制", "反向代理", "健康检查", "CI/CD"],
        "errors": ["ImagePullBackOff", "CrashLoopBackOff", "502 Bad Gateway", "Permission denied"],
    },
    "data": {
        "entities": ["SQL", "Pandas", "Spark", "ClickHouse", "Elasticsearch", "Hive", "Airflow"],
        "concepts": ["索引优化", "数据倾斜", "分区裁剪", "窗口函数", "ETL", "查询计划"],
        "errors": ["Out of memory", "Slow query", "Shuffle spill", "Schema mismatch"],
    },
    "ml": {
        "entities": ["PyTorch", "TensorFlow", "CUDA", "LLM", "向量数据库", "NumPy", "LoRA"],
        "concepts": ["反向传播", "梯度累积", "显存优化", "向量检索", "模型蒸馏", "推理延迟"],
        "errors": ["CUDA out of memory", "nan loss", "shape mismatch", "kernel timeout"],
    },
    "security": {
        "entities": ["JWT", "OAuth", "SSL", "XSS", "SQL注入", "Bcrypt", "RSA", "WAF"],
        "concepts": ["令牌刷新", "权限边界", "输入校验", "加密签名", "会话固定", "最小权限"],
        "errors": ["Invalid signature", "CSRF token missing", "certificate verify failed", "403 Forbidden"],
    },
    "system": {
        "entities": ["Linux", "TCP", "GIL", "线程", "进程", "文件系统", "编译器", "内存管理"],
        "concepts": ["上下文切换", "锁竞争", "系统调用", "内存分页", "TCP 拥塞控制", "调度策略"],
        "errors": ["segmentation fault", "too many open files", "connection reset", "race condition"],
    },
}

LEVEL_SCORE_VECTOR = {
    1: [0, 0, 0],
    2: [2, 2, 0],
    3: [1, 1, 1],
    4: [0, 0, 2],
    5: [2, 2, 2],
}

USER_SCENARIOS = {
    "stable": {
        "description": "大部分问题围绕真实水平，少量轻微波动",
        "noise_ratio": 0.10,
        "high_noise_weight": 0.35,
        "low_noise_weight": 0.45,
        "cross_domain_weight": 0.20,
    },
    "copy_paste_high": {
        "description": "经常出现复制粘贴式高等级问题，容易高估能力",
        "noise_ratio": 0.25,
        "high_noise_weight": 0.75,
        "low_noise_weight": 0.10,
        "cross_domain_weight": 0.15,
    },
    "simple_burst_low": {
        "description": "经常问低等级操作性问题，容易低估能力",
        "noise_ratio": 0.25,
        "high_noise_weight": 0.10,
        "low_noise_weight": 0.75,
        "cross_domain_weight": 0.15,
    },
    "mixed_noisy": {
        "description": "高低噪声和跨领域问题混合出现",
        "noise_ratio": 0.35,
        "high_noise_weight": 0.40,
        "low_noise_weight": 0.40,
        "cross_domain_weight": 0.20,
    },
}


TEMPLATES = {
    1: [
        "{entity} 是什么？",
        "怎么安装 {entity}？",
        "{entity} 的基本用法是什么？",
        "怎么启动一个最简单的 {entity} 示例？",
        "{concept} 是什么意思？",
    ],
    2: [
        "我用 {entity} 遇到 {error}，应该先检查什么？",
        "{entity} 里怎么配置 {concept}？",
        "用 {entity} 实现一个简单的 {concept} 应该怎么写？",
        "{entity} 和 {entity2} 在日常使用上有什么区别？",
        "{entity} 出现 {error} 时，有哪些常见解决办法？",
    ],
    3: [
        "{entity} 的 {concept} 工作流程是什么？",
        "{entity} 在高并发场景下怎么优化 {concept}？",
        "为什么 {entity} 会出现 {error}，排查路径应该怎么设计？",
        "设计一个基于 {entity} 的 {concept} 模块，需要注意哪些边界？",
        "{entity} 和 {entity2} 在 {concept} 上的实现思路有什么差异？",
    ],
    4: [
        "在生产环境中，{entity} 出现 {error}。日志显示请求集中在峰值窗口，资源监控也有异常。如何分析 {concept} 层面的根因？",
        "{entity} 的 {concept} 底层机制是怎样的，它在极端负载下会暴露哪些瓶颈？",
        "如果要优化 {entity} 的 {concept}，应该如何权衡吞吐、延迟和一致性？",
        "从源码或运行时机制看，{entity} 处理 {error} 的关键路径在哪里？",
        "{entity} 与 {entity2} 在 {concept} 设计上有哪些架构取舍？",
    ],
    5: [
        "如果重新设计 {entity} 的 {concept} 架构，你会如何定义模块边界、失败语义和可观测性？",
        "从理论模型看，{entity} 的 {concept} 是否存在无法突破的边界？",
        "在跨区域、多租户、强一致约束下，{entity} 的 {concept} 应该如何重新抽象？",
        "{entity} 和 {entity2} 在 {concept} 的理论假设上有什么本质差异？",
        "如何构造一个实验来验证 {entity} 在 {concept} 极限场景下的退化行为？",
    ],
}


def choose_domain(rng: random.Random, primary_domain: str, noise_type: str) -> str:
    if noise_type != "cross_domain":
        return primary_domain

    candidates = [domain for domain in DOMAINS if domain != primary_domain]
    return rng.choice(candidates)


def choose_observed_level(rng: random.Random, true_level: int, scenario: dict) -> tuple:
    if rng.random() >= scenario["noise_ratio"]:
        nearby = [true_level]
        if true_level > 1:
            nearby.append(true_level - 1)
        if true_level < 5:
            nearby.append(true_level + 1)
        weights = [0.80] + [0.10] * (len(nearby) - 1)
        return rng.choices(nearby, weights=weights, k=1)[0], "normal"

    noise_types = ["high_noise", "low_noise", "cross_domain"]
    weights = [
        scenario["high_noise_weight"],
        scenario["low_noise_weight"],
        scenario["cross_domain_weight"],
    ]
    noise_type = rng.choices(noise_types, weights=weights, k=1)[0]

    if noise_type == "high_noise":
        return min(5, true_level + rng.choice([1, 2])), noise_type
    if noise_type == "low_noise":
        return max(1, true_level - rng.choice([1, 2])), noise_type

    drift = rng.choice([-1, 1])
    return min(5, max(1, true_level + drift)), noise_type


def render_question(rng: random.Random, level: int, domain: str, noise_type: str) -> str:
    domain_data = DOMAINS[domain]
    entity = rng.choice(domain_data["entities"])
    entity2 = rng.choice([item for item in domain_data["entities"] if item != entity])
    concept = rng.choice(domain_data["concepts"])
    error = rng.choice(domain_data["errors"])
    question = rng.choice(TEMPLATES[level]).format(
        entity=entity,
        entity2=entity2,
        concept=concept,
        error=error,
    )

    if noise_type == "high_noise":
        return "我看到一段资料但没完全理解：" + question
    if noise_type == "low_noise":
        return "临时确认一下：" + question
    if noise_type == "cross_domain":
        return "虽然我平时不做这个方向，但想问：" + question
    return question


def generate_user_sequence(
    rng: random.Random,
    user_index: int,
    true_level: int,
    primary_domain: str,
    scenario_name: str,
    num_questions: int,
) -> List[dict]:
    scenario = USER_SCENARIOS[scenario_name]
    user_id = (
        f"user_synthetic_{user_index:04d}_"
        f"l{true_level}_{primary_domain}_{scenario_name}"
    )
    rows = []

    for turn_id in range(1, num_questions + 1):
        observed_level, noise_type = choose_observed_level(rng, true_level, scenario)
        domain = choose_domain(rng, primary_domain, noise_type)
        question = render_question(rng, observed_level, domain, noise_type)

        rows.append({
            "sample_id": f"{user_id}_q{turn_id:03d}",
            "user_id": user_id,
            "turn_id": turn_id,
            "primary_domain": primary_domain,
            "question_domain": domain,
            "scenario": scenario_name,
            "true_user_level": true_level,
            "observed_question_level": observed_level,
            "noise_type": noise_type,
            "is_noise": noise_type != "normal",
            "expected_score_vector": LEVEL_SCORE_VECTOR[observed_level],
            "question": question,
        })

    return rows


def generate_dataset(
    num_questions: int = 50,
    true_level: int = 2,
    noise_ratio: float = 0.2,
    seed: int = RANDOM_SEED,
) -> List[dict]:
    """
    兼容旧实验脚本的轻量生成函数。
    返回字段包含 observed_level，供 simulation_experiment.py 使用。
    """
    rng = random.Random(seed)
    domain = rng.choice(list(DOMAINS))
    scenario = {
        "noise_ratio": noise_ratio,
        "high_noise_weight": 0.4,
        "low_noise_weight": 0.4,
        "cross_domain_weight": 0.2,
    }
    rows = []

    for turn_id in range(1, num_questions + 1):
        observed_level, noise_type = choose_observed_level(rng, true_level, scenario)
        question_domain = choose_domain(rng, domain, noise_type)
        rows.append({
            "id": turn_id,
            "question": render_question(rng, observed_level, question_domain, noise_type),
            "domain": question_domain,
            "true_level": true_level,
            "observed_level": observed_level,
            "is_noise": noise_type != "normal",
            "noise_type": noise_type,
        })

    return rows


def build_full_dataset(
    users_per_group: int,
    questions_per_user: int,
    seed: int,
) -> List[dict]:
    rng = random.Random(seed)
    rows = []
    user_index = 1

    for true_level in range(1, 6):
        for primary_domain in DOMAINS:
            for scenario_name in USER_SCENARIOS:
                for _ in range(users_per_group):
                    rows.extend(generate_user_sequence(
                        rng=rng,
                        user_index=user_index,
                        true_level=true_level,
                        primary_domain=primary_domain,
                        scenario_name=scenario_name,
                        num_questions=questions_per_user,
                    ))
                    user_index += 1

    return rows


def summarize(rows: List[dict]) -> dict:
    users = sorted({row["user_id"] for row in rows})
    return {
        "num_samples": len(rows),
        "num_users": len(users),
        "level_distribution": dict(Counter(row["true_user_level"] for row in rows)),
        "observed_level_distribution": dict(Counter(row["observed_question_level"] for row in rows)),
        "primary_domain_distribution": dict(Counter(row["primary_domain"] for row in rows)),
        "question_domain_distribution": dict(Counter(row["question_domain"] for row in rows)),
        "scenario_distribution": dict(Counter(row["scenario"] for row in rows)),
        "noise_type_distribution": dict(Counter(row["noise_type"] for row in rows)),
    }


def write_json(path: str, data):
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--meta-output", default=DEFAULT_META_OUTPUT)
    parser.add_argument("--users-per-group", type=int, default=3)
    parser.add_argument("--questions-per-user", type=int, default=40)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = parser.parse_args()

    rows = build_full_dataset(
        users_per_group=args.users_per_group,
        questions_per_user=args.questions_per_user,
        seed=args.seed,
    )
    meta = {
        "dataset_name": "合成数据集",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "seed": args.seed,
        "users_per_group": args.users_per_group,
        "questions_per_user": args.questions_per_user,
        "domains": list(DOMAINS),
        "user_scenarios": USER_SCENARIOS,
        "level_score_vector": LEVEL_SCORE_VECTOR,
        "summary": summarize(rows),
    }

    write_json(args.output, rows)
    write_json(args.meta_output, meta)

    summary = meta["summary"]
    print(f"已生成 {args.output}")
    print(f"样本数: {summary['num_samples']}")
    print(f"用户数: {summary['num_users']}")
    print(f"真实等级分布: {summary['level_distribution']}")
    print(f"领域分布: {summary['primary_domain_distribution']}")
    print(f"噪声分布: {summary['noise_type_distribution']}")
    print(f"元信息: {args.meta_output}")


if __name__ == "__main__":
    main()
