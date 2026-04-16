"""
单标的仓位相关风控规则。
"""
from __future__ import annotations

from dataclasses import replace

from jwquant.common.types import Direction, Order, Position, RiskEvent
from jwquant.trading.risk.context import RiskCheckContext
from jwquant.trading.risk.rules import BaseRiskRule, RiskDecision, RiskStage


def _resolve_order_price(context: RiskCheckContext) -> float:
    if context.order is not None and context.order.price > 0:
        return float(context.order.price)
    if context.bar_price > 0:
        return float(context.bar_price)
    if context.code and context.code in context.latest_prices:
        return float(context.latest_prices[context.code])
    return 0.0


def _resolve_total_equity(context: RiskCheckContext) -> float:
    if context.portfolio_equity > 0:
        return float(context.portfolio_equity)
    if context.asset is not None and context.asset.total_asset > 0:
        return float(context.asset.total_asset)
    return 0.0


def _resolve_market_price(context: RiskCheckContext, code: str) -> float:
    if code in context.latest_prices and context.latest_prices[code] > 0:
        return float(context.latest_prices[code])
    if code == context.code and context.bar_price > 0:
        return float(context.bar_price)
    return _resolve_order_price(context)


def _normalize_order_volume(context: RiskCheckContext, volume: int) -> int:
    if volume <= 0:
        return 0
    if str(context.market).lower() == "stock":
        return max((int(volume) // 100) * 100, 0)
    return max(int(volume), 0)


def _resolve_position(context: RiskCheckContext) -> Position | dict | None:
    if context.position is not None:
        return context.position
    code = context.order.code if context.order is not None else context.code
    if not code:
        return None
    return context.portfolio_positions.get(code)


def _extract_position_volume(position: Position | dict | None) -> int:
    if position is None:
        return 0
    if isinstance(position, dict):
        if "quantity" in position:
            return int(position["quantity"])
        if "volume" in position:
            return int(position["volume"])
        return 0
    return int(position.volume)


def _extract_available_volume(position: Position | dict | None) -> int:
    if position is None:
        return 0
    if isinstance(position, dict):
        if "available" in position:
            return int(position["available"])
        if "sellable_quantity" in position:
            return int(position["sellable_quantity"])
        if "quantity" in position:
            return int(position["quantity"])
        if "volume" in position:
            return int(position["volume"])
        return 0
    return int(position.available)


def _build_position_event(
    *,
    risk_type: str,
    severity: str,
    code: str,
    message: str,
    dt,
    action_taken: str,
    source: str,
    metadata: dict | None = None,
) -> RiskEvent:
    return RiskEvent(
        risk_type=risk_type,
        severity=severity,
        code=code,
        message=message,
        dt=dt,
        action_taken=action_taken,
        category="position",
        source=source,
        metadata=dict(metadata or {}),
    )


class MaxOrderAmountRule(BaseRiskRule):
    """限制单笔下单金额。"""

    name = "max_order_amount"
    stages = (RiskStage.ORDER,)

    def __init__(self, max_order_amount: float):
        self.max_order_amount = float(max_order_amount)

    def check(self, context: RiskCheckContext) -> RiskDecision:
        if context.order is None or self.max_order_amount <= 0:
            return RiskDecision.allow(stage=RiskStage.ORDER)

        price = _resolve_order_price(context)
        amount = abs(price * context.order.volume)
        if amount <= self.max_order_amount:
            return RiskDecision.allow(stage=RiskStage.ORDER)

        event = _build_position_event(
            risk_type="MAX_ORDER_AMOUNT",
            severity="ERROR",
            code=context.order.code,
            message=f"单笔下单金额 {amount:.2f} 超过限制 {self.max_order_amount:.2f}",
            dt=context.dt,
            action_taken="BLOCKED",
            source=self.name,
            metadata={
                "amount": amount,
                "max_order_amount": self.max_order_amount,
            },
        )
        return RiskDecision.block(stage=RiskStage.ORDER, events=[event])


class MaxPositionPctRule(BaseRiskRule):
    """限制单标的仓位占权益比例。"""

    name = "max_position_pct"
    stages = (RiskStage.ORDER,)

    def __init__(self, max_position_pct: float, *, adjust_order_volume: bool = True, tolerance: float = 1e-8):
        self.max_position_pct = float(max_position_pct)
        self.adjust_order_volume = bool(adjust_order_volume)
        self.tolerance = float(tolerance)

    def check(self, context: RiskCheckContext) -> RiskDecision:
        if context.order is None or self.max_position_pct <= 0:
            return RiskDecision.allow(stage=RiskStage.ORDER)

        order = context.order
        if order.direction != Direction.BUY:
            return RiskDecision.allow(stage=RiskStage.ORDER)
        if order.offset and order.offset != "open_long":
            return RiskDecision.allow(stage=RiskStage.ORDER)

        equity = _resolve_total_equity(context)
        order_price = _resolve_order_price(context)
        market_price = _resolve_market_price(context, order.code)
        if equity <= 0 or order_price <= 0 or market_price <= 0:
            return RiskDecision.allow(stage=RiskStage.ORDER)

        position = _resolve_position(context)
        current_volume = max(_extract_position_volume(position), 0)
        current_exposure = current_volume * market_price
        projected_exposure = current_exposure + order.volume * order_price
        limit_exposure = equity * self.max_position_pct

        if projected_exposure <= limit_exposure + self.tolerance:
            return RiskDecision.allow(stage=RiskStage.ORDER)

        allowed_amount = max(limit_exposure - current_exposure, 0.0)
        adjusted_volume = _normalize_order_volume(context, int(allowed_amount / order_price))

        if self.adjust_order_volume and adjusted_volume > 0:
            adjusted_order = replace(order, volume=adjusted_volume)
            event = _build_position_event(
                risk_type="MAX_POSITION_PCT",
                severity="WARNING",
                code=order.code,
                message=f"{order.code} 下单后仓位将超过上限，已裁减数量",
                dt=context.dt,
                action_taken="ADJUSTED",
                source=self.name,
                metadata={
                    "original_volume": order.volume,
                    "adjusted_volume": adjusted_volume,
                    "max_position_pct": self.max_position_pct,
                    "current_exposure": current_exposure,
                    "limit_exposure": limit_exposure,
                },
            )
            return RiskDecision.adjust(
                stage=RiskStage.ORDER,
                adjusted_order=adjusted_order,
                events=[event],
            )

        event = _build_position_event(
            risk_type="MAX_POSITION_PCT",
            severity="ERROR",
            code=order.code,
            message=f"{order.code} 下单后仓位将超过上限，订单被阻断",
            dt=context.dt,
            action_taken="BLOCKED",
            source=self.name,
            metadata={
                "projected_exposure": projected_exposure,
                "limit_exposure": limit_exposure,
                "max_position_pct": self.max_position_pct,
            },
        )
        return RiskDecision.block(stage=RiskStage.ORDER, events=[event])


class NoNakedShortRule(BaseRiskRule):
    """禁止股票裸卖空。"""

    name = "no_naked_short"
    stages = (RiskStage.ORDER,)

    def check(self, context: RiskCheckContext) -> RiskDecision:
        if context.order is None:
            return RiskDecision.allow(stage=RiskStage.ORDER)
        if str(context.market).lower() != "stock":
            return RiskDecision.allow(stage=RiskStage.ORDER)

        order = context.order
        if order.direction != Direction.SELL:
            return RiskDecision.allow(stage=RiskStage.ORDER)
        if order.offset == "open_short":
            event = _build_position_event(
                risk_type="NAKED_SHORT",
                severity="ERROR",
                code=order.code,
                message="股票市场不允许开空仓",
                dt=context.dt,
                action_taken="BLOCKED",
                source=self.name,
            )
            return RiskDecision.block(stage=RiskStage.ORDER, events=[event])

        available = _extract_available_volume(_resolve_position(context))
        if order.volume <= available:
            return RiskDecision.allow(stage=RiskStage.ORDER)

        event = _build_position_event(
            risk_type="NAKED_SHORT",
            severity="ERROR",
            code=order.code,
            message=f"{order.code} 可卖数量不足，禁止裸卖空",
            dt=context.dt,
            action_taken="BLOCKED",
            source=self.name,
            metadata={
                "requested_volume": order.volume,
                "available_volume": available,
            },
        )
        return RiskDecision.block(stage=RiskStage.ORDER, events=[event])


class FuturesDirectionRule(BaseRiskRule):
    """限制期货允许的开仓方向。"""

    name = "futures_direction"
    stages = (RiskStage.ORDER,)

    def __init__(self, *, allow_long: bool = True, allow_short: bool = True):
        self.allow_long = bool(allow_long)
        self.allow_short = bool(allow_short)

    def check(self, context: RiskCheckContext) -> RiskDecision:
        if context.order is None:
            return RiskDecision.allow(stage=RiskStage.ORDER)
        if str(context.market).lower() != "futures":
            return RiskDecision.allow(stage=RiskStage.ORDER)

        order = context.order
        if order.offset == "open_long" and not self.allow_long:
            event = _build_position_event(
                risk_type="FUTURES_DIRECTION",
                severity="ERROR",
                code=order.code,
                message="当前风控不允许期货开多",
                dt=context.dt,
                action_taken="BLOCKED",
                source=self.name,
                metadata={"offset": order.offset},
            )
            return RiskDecision.block(stage=RiskStage.ORDER, events=[event])

        if order.offset == "open_short" and not self.allow_short:
            event = _build_position_event(
                risk_type="FUTURES_DIRECTION",
                severity="ERROR",
                code=order.code,
                message="当前风控不允许期货开空",
                dt=context.dt,
                action_taken="BLOCKED",
                source=self.name,
                metadata={"offset": order.offset},
            )
            return RiskDecision.block(stage=RiskStage.ORDER, events=[event])

        return RiskDecision.allow(stage=RiskStage.ORDER)
