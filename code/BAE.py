"""
贝叶斯能力估计器（BAE）

核心机制：
- 接收观测分布作为似然
- 观测平滑：移动平均处理噪声
- 加权贝叶斯更新：后验 = 先验 × 平滑似然^观测权重
- 初始先验：可由冷启动模块传入
"""

from typing import List


class BayesianLevelEstimator:
    """
    贝叶斯能力估计器
    维护 L1-L5 五个等级的概率分布（信念）
    """

    # 无冷启动信号时采用均匀先验，避免默认假设用户一定偏向初学者。
    PRIOR_TEMPLATE = [0.20, 0.20, 0.20, 0.20, 0.20]

    def __init__(
        self,
        smooth_window: int = 5,
        initial_prior: List[float] = None,
        use_adaptive_prior: bool = False,
        adaptive_threshold: int = 5,
    ):
        """
        Args:
            smooth_window: 观测平滑窗口大小
            initial_prior: 初始先验分布，由冷启动模块生成；为空时使用均匀先验
            use_adaptive_prior: 是否启用旧版自适应先验重置逻辑，默认关闭
            adaptive_threshold: 旧版自适应触发阈值，仅 use_adaptive_prior=True 时生效
        """
        # 初始使用冷启动先验；没有冷启动信号时使用均匀先验。
        self.p_levels = self._normalize_distribution(
            initial_prior or self.PRIOR_TEMPLATE
        )

        # 观测计数
        self.observation_count = 0

        # 观测分布窗口（用于平滑）
        self.observation_window: List[List[float]] = []
        self.smooth_window = smooth_window

        # 观测历史（记录平滑观测等级）
        self.observation_history: List[float] = []

        # 旧版自适应配置。默认关闭，避免中途重置后验。
        self.use_adaptive_prior = use_adaptive_prior
        self.adaptive_threshold = adaptive_threshold

        # 是否已自适应
        self.is_adapted = False

    def _normalize_distribution(self, distribution: List[float]) -> List[float]:
        """校验并归一化 L1-L5 概率分布"""
        if len(distribution) != 5:
            raise ValueError("能力分布必须包含 L1-L5 五个概率")

        total = sum(distribution)
        if total <= 0:
            raise ValueError("能力分布概率和必须大于 0")

        return [p / total for p in distribution]

    def _generate_adaptive_prior(self, center_level: float) -> List[float]:
        """
        根据观测均值生成自适应先验

        Args:
            center_level: 观测均值（先验中心）

        Returns:
            自适应先验分布
        """
        # 以 center_level 为中心生成分布（简单衰减）
        raw_probs = []
        for x in range(1, 6):
            density = max(0.01, 1.0 / (abs(x - center_level) + 1))
            raw_probs.append(density)

        # 归一化
        total = sum(raw_probs)
        return [round(p / total, 4) for p in raw_probs]

    def _smooth_distribution(self, new_distribution: List[float]) -> List[float]:
        """
        观测平滑：加权平均处理噪声

        Args:
            new_distribution: 新观测分布

        Returns:
            平滑后的分布
        """
        # 加入窗口
        self.observation_window.append(new_distribution)
        if len(self.observation_window) > self.smooth_window:
            self.observation_window.pop(0)

        # 线性衰减权重（最近的权重高）
        n = len(self.observation_window)
        weights = [(i + 1) / n for i in range(n)]  # [1/n, 2/n, ..., n/n]
        total_weight = sum(weights)

        # 加权平均
        smoothed = [0.0] * 5
        for i, obs in enumerate(self.observation_window):
            w = weights[i] / total_weight
            for j in range(5):
                smoothed[j] += obs[j] * w

        # 归一化
        total = sum(smoothed)
        return [p / total for p in smoothed]

    def update(
        self,
        observation_distribution: List[float],
        observation_weight: float = 1.0,
    ) -> dict:
        """
        加权贝叶斯更新：后验 = 先验 × 平滑似然^观测权重

        Args:
            observation_distribution: [P(L1), P(L2), P(L3), P(L4), P(L5)]
            observation_weight: 本次观测的可靠性权重。
                1.0 表示正常贝叶斯更新；
                0.0 表示本轮观测不改变后验；
                >1.0 表示高可信观测，对后验影响更强。

        Returns:
            更新后的状态信息
        """
        if observation_weight < 0:
            raise ValueError("观测权重不能为负数")

        # 观测平滑
        smoothed_distribution = self._smooth_distribution(observation_distribution)

        # 记录观测等级（从平滑分布提取中心）
        obs_level = sum((i + 1) * p for i, p in enumerate(smoothed_distribution))
        self.observation_history.append(obs_level)

        # 加权贝叶斯更新（使用平滑后的分布）
        posterior = []
        for i in range(5):
            weighted_likelihood = smoothed_distribution[i] ** observation_weight
            posterior.append(self.p_levels[i] * weighted_likelihood)

        # 归一化
        total = sum(posterior)
        if total > 0:
            self.p_levels = [p / total for p in posterior]

        self.observation_count += 1

        # 旧版自适应触发：达到阈值后重置先验。默认关闭。
        if (
            self.use_adaptive_prior
            and not self.is_adapted
            and self.observation_count >= self.adaptive_threshold
        ):
            # 计算观测均值（基于平滑后的历史）
            avg_level = sum(self.observation_history) / len(self.observation_history)
            # 生成自适应先验
            adaptive_prior = self._generate_adaptive_prior(avg_level)
            # 用自适应先验重置分布
            self.p_levels = adaptive_prior
            self.is_adapted = True

        # 计算精细等级（期望值）
        fine_level = round(sum((i + 1) * p for i, p in enumerate(self.p_levels)), 2)

        # MAP 估计
        map_level = self.p_levels.index(max(self.p_levels)) + 1

        return {
            "distribution": self.p_levels,
            "fine_level": fine_level,
            "map_level": map_level,
            "observation_count": self.observation_count,
            "is_adapted": self.is_adapted,
            "smoothed_distribution": smoothed_distribution,
            "observation_weight": observation_weight,
        }

    def export_state(self) -> dict:
        """导出可持久化的完整估计器状态"""
        return {
            "distribution": self.p_levels.copy(),
            "observation_window": [obs.copy() for obs in self.observation_window],
            "observation_history": self.observation_history.copy(),
            "observation_count": self.observation_count,
            "is_adapted": self.is_adapted
        }

    def restore_state(self, state: dict):
        """从数据库状态恢复估计器"""
        self.p_levels = self._normalize_distribution(
            state.get("distribution", self.PRIOR_TEMPLATE)
        )
        self.observation_window = [
            obs.copy() for obs in state.get("observation_window", [])
        ][-self.smooth_window:]
        self.observation_history = state.get("observation_history", []).copy()
        self.observation_count = state.get(
            "observation_count",
            len(self.observation_history)
        )
        self.is_adapted = state.get(
            "is_adapted",
            self.use_adaptive_prior and self.observation_count >= self.adaptive_threshold
        )

    def get_distribution(self) -> List[float]:
        """获取当前概率分布"""
        return self.p_levels.copy()

    def get_level(self) -> float:
        """获取当前精细等级"""
        return round(sum((i + 1) * p for i, p in enumerate(self.p_levels)), 2)
