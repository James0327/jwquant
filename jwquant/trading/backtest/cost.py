"""
回测金额与成本配置。

这层配置只描述回测里和金额直接相关的默认参数：
- 佣金费率
- 滑点比例
- 单笔下单金额上限
- 期货保证金率
- 期货合约乘数

脚本层会优先从 ``config/settings.toml`` 的 ``[backtest.cost]`` 读取，
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
        payload = dict(mapping or {})
        return cls(
            commission_rate=float(payload.get("commission_rate", 0.0003)),
            slippage=float(payload.get("slippage", 0.0001)),
            max_order_value=float(payload.get("max_order_value", 100000.0)),
            futures_margin_rate=float(payload.get("futures_margin_rate", 0.12)),
            futures_contract_multiplier=float(payload.get("futures_contract_multiplier", 300.0)),
        )
