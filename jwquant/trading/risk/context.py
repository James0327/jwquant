"""
风控检查上下文。
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from jwquant.common.types import Asset, Bar, Order, Position


@dataclass
class RiskCheckContext:
    """统一的风控检查输入。"""

    dt: datetime
    market: str
    code: str = ""
    bar_price: float = 0.0
    bar: Bar | None = None
    order: Order | None = None
    asset: Asset | None = None
    position: Position | None = None
    portfolio_positions: dict[str, Any] = field(default_factory=dict)
    portfolio_equity: float = 0.0
    latest_prices: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_order(self, order: Order | None) -> "RiskCheckContext":
        """返回替换订单后的上下文副本。"""
        return replace(
            self,
            order=order,
            portfolio_positions=dict(self.portfolio_positions),
            latest_prices=dict(self.latest_prices),
            metadata=dict(self.metadata),
        )

    def with_updates(self, **updates: Any) -> "RiskCheckContext":
        """返回应用若干字段更新后的上下文副本。"""
        payload = {
            "portfolio_positions": dict(self.portfolio_positions),
            "latest_prices": dict(self.latest_prices),
            "metadata": dict(self.metadata),
        }
        payload.update(updates)
        return replace(self, **payload)
