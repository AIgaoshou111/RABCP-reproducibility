"""
认知画像智能体 - 三级火箭流水线

Phase 1: ProfilerExtractor  - 门卫拦截与结构化提取
Phase 2: ProfilerAuditor    - 基于证据的离散评分审计
Phase 3: ProfilerMapper     - Dreyfus概率映射与Bloom门控
Pipeline: CognitiveProfilerPipeline - 按顺序点火
"""

import json
import math
import os
import re
from openai import OpenAI


# ============================================================
# 模型配置
# ============================================================
# 1 = 本地模型 (LM Studio)
# 2 = 阿里百炼
MODEL_SOURCE = 1

# 本地模型配置
LOCAL_MODEL_NAME = "local-model"
LOCAL_API_KEY = "lm-studio"
LOCAL_BASE_URL = "http://localhost:1234/v1"

# 阿里百炼配置
ALI_MODEL_NAME = "kimi-2.5"
ALI_API_KEY = os.environ.get("ALI_API_KEY", "")
ALI_BASE_URL = "https://aliyun.aiapiproxy.cn/v1"


def get_client():
    """根据 MODEL_SOURCE 获取对应客户端"""
    if MODEL_SOURCE == 1:
        return OpenAI(api_key=LOCAL_API_KEY, base_url=LOCAL_BASE_URL)
    elif MODEL_SOURCE == 2:
        return OpenAI(api_key=ALI_API_KEY, base_url=ALI_BASE_URL)
    else:
        raise ValueError(f"未知的 MODEL_SOURCE: {MODEL_SOURCE}")


def get_model_name():
    """根据 MODEL_SOURCE 获取模型名称"""
    if MODEL_SOURCE == 1:
        return LOCAL_MODEL_NAME
    elif MODEL_SOURCE == 2:
        return ALI_MODEL_NAME
    else:
        raise ValueError(f"未知的 MODEL_SOURCE: {MODEL_SOURCE}")


# ============================================================
# 工具函数
# ============================================================
def parse_json_response(raw_content: str) -> dict:
    """
    稳健解析 LLM 返回的 JSON：
    1. 尝试直接解析
    2. 去除 markdown 代码块标记后再解析
    3. 正则提取第一个 JSON 对象
    """
    text = raw_content.strip()

    # 尝试 1: 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试 2: 去除 markdown 代码块
    for pattern in [r"^```json\s*", r"^```\s*", r"\s*```$"]:
        text = re.sub(pattern, "", text, flags=re.MULTILINE)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试 3: 正则提取第一个 {...} 块
    match = re.search(r"\{[\s\S]*\}", raw_content)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise json.JSONDecodeError("无法从响应中提取有效 JSON", raw_content, 0)


# ============================================================
# Phase 1: 门卫拦截与结构化提取
# ============================================================
class ProfilerExtractor:
    """
    第一阶段：接收脏文本，输出干净的结构化证据
    """

    EXTRACTION_PROMPT = """
你是一个挂载在技术问答系统后台的"文本提纯与鉴权智能体"。
你的唯一任务是接收用户杂乱的原始提问，消除所有情绪化噪声，并提取硬核技术骨架。

请严格执行以下三步：
1. 领域鉴权：判断用户的输入是否包含实质性的计算机/软件工程技术探讨或求助。
   如果是纯情绪发泄、纯打招呼或非技术问题，请判定为 false。

2. 领域分类：如果鉴权为 true，判断问题属于哪个技术领域（严格从以下7个中选一个）：

   【领域分类规则】
   - backend:  后端服务、API、数据库操作、缓存、消息队列、认证鉴权
               （Flask/Django/Spring/Redis/Kafka/MySQL）
   - frontend: 界面渲染、交互逻辑、浏览器行为
               （React/Vue/CSS/JavaScript/DOM）
   - devops:   部署运维、容器编排、监控、CI/CD
               （Docker/K8s/Nginx/Jenkins/Terraform）
   - data:     数据处理、查询优化、数仓、ETL
               （SQL/Spark/Hive/ClickHouse/Pandas）
   - ml:       模型训练、推理、AI框架
               （PyTorch/TensorFlow/CUDA/LLM/向量数据库）
   - security: 安全攻防、加密、渗透、权限控制
               （JWT/OAuth/SSL/XSS/SQL注入）
   - system:   操作系统、网络协议、并发原语、编译器
               （Linux/TCP/线程/GIL/内存管理）

   如果问题横跨多个领域，选择 core_entities 中占比最多的那个。
   如果完全无法归类，返回 "backend"（最常见兜底）。

3. 结构化解构：无视情绪词汇，强行提取以下三个维度：

   - core_entities (核心实体): 有技术方向意义的关键词，能用于构建知识图谱
     【提取标准】：
     ✓ 框架/库：Flask, FastAPI, Redis, Celery, PyTorch, TensorFlow
     ✓ 技术概念：异步机制, 持久化, 并发控制, N+1查询, 死锁, 索引优化
     ✓ 架构模式：微服务, 分布式系统, 缓存策略, 负载均衡
     ✓ 工具/组件：Docker, Nginx, Git, Kubernetes, RabbitMQ

     【排除内容】：
     ✗ 通用概念：函数, 变量, 参数, 循环, 数组, 字典
     ✗ 太泛词汇：Python, 数据库, 服务器, 代码, API

   - provided_context (提供语境): 用户提供了什么排错线索
   - true_intent (真实意图): 用户发问的终极技术目的

【输出协议】必须且只能输出如下 JSON，不含任何 markdown 标记：
{
  "is_valid_tech_query": true/false,
  "domain": "backend",
  "deconstruction": {
    "core_entities": ["实体1", "实体2"],
    "provided_context": "客观描述...",
    "true_intent": "一句话意图..."
  }
}
"""

    def __init__(self, llm_client, model: str = None):
        self.llm = llm_client
        self.model = model or get_model_name()

    def extract_information(self, user_query: str) -> dict:
        """接收非结构化语言，返回结构化字典"""
        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.EXTRACTION_PROMPT},
                    {"role": "user", "content": user_query}
                ],
                temperature=0.0
            )
            result_json = response.choices[0].message.content
            return parse_json_response(result_json)
        except Exception as e:
            print(f"[Extractor Error] {e}")
            return {"is_valid_tech_query": False, "deconstruction": {}}


# ============================================================
# Phase 2: 基于证据的离散评分审计
# ============================================================
class ProfilerAuditor:
    """
    第二阶段：接收结构化证据，输出 [L, C, G] 三维离散得分
    """

    AUDIT_PROMPT = """
你是一个精通软件工程实证研究与计算教育学的"特征审计专家"。
我将为你提供一份【用户提问结构化证据】。
请严格对照以下三张量表，给出单选评分（0, 1, 2）。

【量表一：域内语言复杂度 (linguistic_score)】
- [0分]: 通用白话，无专有名词
- [1分]: 高频基础词（Python, PyTorch, 数据库等）
- [2分]: 低频硬核术语（NCCL backend, GIL锁竞争, CUDA流等）

【量表二：语境完备度 (contextual_score)】
- [0分]: 孤立提问，无任何上下文
- [1分]: 局部语境，仅有报错或局部代码
- [2分]: 完备语境，标准 Bug Report 规范

【量表三：认知意图 (cognitive_score)】
- [0分]: 记忆/感知层（索要定义、安装说明）
- [1分]: 理解/应用层（解决眼前 Bug）
- [2分]: 评估/分析层（探寻底层机制、架构权衡）

【输出协议】必须且只能输出如下 JSON：
{
  "audit_scores": {
    "linguistic_score": 0,
    "contextual_score": 0,
    "cognitive_score": 0
  },
  "rationale": "简短解释 cognitive_score 依据"
}
"""

    def __init__(self, llm_client, model: str = None):
        self.llm = llm_client
        self.model = model or get_model_name()

    def audit_features(self, deconstruction: dict) -> dict:
        """接收结构化证据，返回三维得分"""
        evidence_str = json.dumps(deconstruction, ensure_ascii=False, indent=2)
        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.AUDIT_PROMPT},
                    {"role": "user", "content": f"【证据档案】\n{evidence_str}"}
                ],
                temperature=0.0
            )
            result_json = response.choices[0].message.content
            parsed = parse_json_response(result_json)
            return parsed["audit_scores"]
        except Exception as e:
            print(f"[Auditor Error] {e}")
            return {"linguistic_score": 0, "contextual_score": 0, "cognitive_score": 0}


# ============================================================
# Phase 3: Dreyfus 概率映射与 Bloom 门控
# ============================================================
class ProfilerMapper:
    """
    第三阶段：纯 Python 计算，无需大模型
    将 [L, C, G] 映射为 L1-L5 概率分布
    """

    LEVELS = ["L1_Novice", "L2_Advanced_Beginner", "L3_Competent", "L4_Proficient", "L5_Expert"]

    def map_features_to_dreyfus(self, vector_3d: list) -> dict:
        """
        线性映射：G主导等级区间，L/C微调

        映射逻辑：
        - G=0 → 基础区间 L1-L2 (中心 1.5)
        - G=1 → 基础区间 L3 (中心 3.0)
        - G=2 → 基础区间 L4-L5 (中心 4.5)
        - L/C 提供微调 ±0.5
        """
        L, C, G = vector_3d

        # G 主导基础等级
        base_level = 1.5 + 1.5 * G  # G=0→1.5, G=1→3.0, G=2→4.5

        # L/C 微调（范围 -0.5 到 +0.5）
        adjustment = 0.25 * (L + C) - 0.5  # L,C∈{0,1,2} → adjustment∈{-0.5,0,0.5}

        # 精细等级
        fine_level = round(base_level + adjustment, 2)
        fine_level = max(1.0, min(5.0, fine_level))  # 边界约束

        # 生成概率分布（以fine_level为中心的简单正态分布，固定sigma）
        sigma = 0.8
        raw_probs = []
        for x in range(1, 6):
            density = math.exp(-((x - fine_level)**2) / (2 * sigma**2))
            raw_probs.append(density)

        # 归一化
        total = sum(raw_probs)
        normalized = [round(p / total, 4) for p in raw_probs]

        # 显示等级
        display_level = self.LEVELS[round(fine_level) - 1]

        return {
            "score_vector": vector_3d,
            "distribution": normalized,
            "fine_level": fine_level,
            "display_level": display_level
        }


# ============================================================
# Pipeline: 三级火箭总指挥
# ============================================================
class CognitiveProfilerPipeline:
    """
    认知画像流水线：按顺序调用三个阶段
    """

    def __init__(self, llm_client, model: str = None):
        self.extractor = ProfilerExtractor(llm_client, model)
        self.auditor = ProfilerAuditor(llm_client, model)
        self.mapper = ProfilerMapper()

    def process_query(self, user_id: str, user_query: str, domain: str = None) -> dict:
        """
        输入用户ID和问题，输出完整画像数据包

        流程：
        1. 查用户画像（不影响评分，只用于存储）
        2. 处理问题（原有评分流程）
        3. 存数据库
        4. 返回结果
        """
        from db import build_profile_summary, save_question, update_domain, update_user, get_bkt_state, get_user_domains
        from BAE import BayesianLevelEstimator
        from cold_start import ColdStartProfiler

        # 1. 查用户画像摘要（不影响评分）
        profile_summary = build_profile_summary(user_id)

        # 2. 处理问题（原有流程）
        extracted = self.extractor.extract_information(user_query)
        if not extracted.get("is_valid_tech_query", False):
            return None

        deconstruction = extracted.get("deconstruction", {})
        entities = deconstruction.get("core_entities", [])

        # 评分
        scores = self.auditor.audit_features(deconstruction)
        vector = [
            scores.get("linguistic_score", 0),
            scores.get("contextual_score", 0),
            scores.get("cognitive_score", 0)
        ]

        # Dreyfus 映射（线性映射）
        profile = self.mapper.map_features_to_dreyfus(vector)
        distribution = profile["distribution"]
        fine_level = profile["fine_level"]
        display_level = profile["display_level"]

        # 确定领域（优先级：传入参数 > 智能体提取 > 默认backend）
        if domain is None:
            domain = extracted.get("domain", "backend")

        # 3. 存数据库
        # 存问题历史
        save_question(user_id, domain, user_query, vector, fine_level)

        # 加载或创建贝叶斯估计器
        bkt_state = get_bkt_state(user_id, domain)

        is_cold_start = len(bkt_state["observation_history"]) == 0

        if is_cold_start:
            # 新领域
            existing_domains = get_user_domains(user_id)
            cold_start = ColdStartProfiler()
            transfer_level = cold_start.conservative_transfer_level([
                d["level"] for d in existing_domains
            ])
            initial_prior = cold_start.build_prior(
                first_observation_level=fine_level,
                transfer_level=transfer_level,
            )
            estimator = BayesianLevelEstimator(initial_prior=initial_prior)
            if len(existing_domains) > 0:
                # 有已有领域，迁移先验（保守降一级）
                avg_level = sum(d["level"] for d in existing_domains) / len(existing_domains)
                init_level = max(1.0, avg_level - 1.0)
                print(f"[冷启动] 迁移先验：主领域均值 {avg_level:.1f} → 新领域初始 L{init_level}")
        else:
            # 老领域，恢复完整 BAE 状态
            estimator = BayesianLevelEstimator()
            estimator.restore_state(bkt_state)

        # 贝叶斯更新
        result = estimator.update(distribution)
        bkt_fine_level = result["fine_level"]

        # 更新领域画像
        update_domain(
            user_id,
            domain,
            bkt_fine_level,
            estimator.p_levels,
            entities,
            round(fine_level),
            estimator.export_state()
        )

        # 更新用户统计
        update_user(user_id)

        # 4. 返回结果
        return {
            "user_id": user_id,
            "domain": domain,
            "score_vector": vector,
            "fine_level": fine_level,
            "display_level": display_level,
            "bkt_fine_level": bkt_fine_level,
            "bkt_distribution": estimator.p_levels,
            "distribution": distribution,
            "entities": entities,
            "profile_summary": profile_summary,
            "deconstruction": deconstruction,
            "is_cold_start": is_cold_start
        }
