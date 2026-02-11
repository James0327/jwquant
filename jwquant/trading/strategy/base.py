"""
策略基类

定义策略生命周期方法：on_init / on_bar / on_tick / on_order / on_trade。
所有策略需继承此基类。
"""
from abc import ABC, abstractmethod

from jwquant.common.types import Bar, Order, Signal


class BaseStrategy(ABC):
    """策略基类"""

    def __init__(self, name: str, params: dict | None = None):
        self.name = name
        self.params = params or {}

    def on_init(self) -> None:
        """策略初始化，加载参数和指标"""
        pass

    @abstractmethod
    def on_bar(self, bar: Bar) -> Signal | None:
        """每根 K 线触发，执行策略逻辑，返回信号或 None"""
        ...

    def on_tick(self, tick: dict) -> Signal | None:
        """每个 Tick 触发（高频策略可覆写）"""
        return None

    def on_order(self, order: Order) -> None:
        """委托状态变更回调"""
        pass

    def on_stop(self) -> None:
        """策略停止时的清理操作"""
        pass
