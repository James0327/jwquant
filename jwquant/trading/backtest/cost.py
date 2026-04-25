"""
回测金额与成本配置。

这层配置只描述回测里和金额直接相关的默认参数：
- 佣金费率
- 滑点比例
- 单笔下单金额上限
- 期货保证金率
- 期货合约乘数

脚本层会优先从 ``config/settings.common.toml`` 的 ``[backtest.cost]`` 读取，
再把这些值传给 ``BacktestConfig`` 和 ``SimBroker``。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BacktestCostConfig:
    """统一承接回测金额相关默认值。"""

    commission_rate: float = 0.0003
    slippage: float = 0.0001
    max_order_value: float = 100000.0
    futures_margin_rate: float = 0.12
    futures_contract_multiplier: float = 300.0

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any] | None = None) -> "BacktestCostConfig":
        if mapping is None:
            raise KeyError("missing backtest cost config mapping")
        payload = dict(mapping)
        return cls(
            commission_rate=float(payload["commission_rate"]),
            slippage=float(payload["slippage"]),
            max_order_value=float(payload["max_order_value"]),
            futures_margin_rate=float(payload["futures_margin_rate"]),
            futures_contract_multiplier=float(payload["futures_contract_multiplier"]),
        )
