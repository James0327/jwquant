from __future__ import annotations

from datetime import datetime

from jwquant.common.types import Direction, Order, RiskEvent
from jwquant.trading.risk import (
    BaseRiskRule,
    RiskAction,
    RiskCheckContext,
    RiskDecision,
    RiskInterceptor,
    RiskStage,
)


class AllowRule(BaseRiskRule):
    name = "allow_rule"
    stages = (RiskStage.ORDER,)

    def check(self, context: RiskCheckContext) -> RiskDecision:
        return RiskDecision.allow(stage=RiskStage.ORDER)


class AdjustVolumeRule(BaseRiskRule):
    name = "adjust_volume_rule"
    stages = (RiskStage.ORDER,)

    def check(self, context: RiskCheckContext) -> RiskDecision:
        adjusted_order = Order(
            code=context.order.code,
            direction=context.order.direction,
            price=context.order.price,
            volume=50,
            order_type=context.order.order_type,
            offset=context.order.offset,
            order_id=context.order.order_id,
            status=context.order.status,
            dt=context.order.dt,
        )
        event = RiskEvent(
            risk_type="ADJUST_VOLUME",
            severity="WARNING",
            code=adjusted_order.code,
            message="volume adjusted to 50",
            dt=context.dt,
            action_taken="ADJUSTED",
        )
        return RiskDecision.adjust(stage=RiskStage.ORDER, adjusted_order=adjusted_order, events=[event])


class BlockRule(BaseRiskRule):
    name = "block_rule"
    stages = (RiskStage.ORDER,)

    def check(self, context: RiskCheckContext) -> RiskDecision:
        event = RiskEvent(
            risk_type="BLOCK_ORDER",
            severity="ERROR",
            code=context.order.code if context.order else "",
            message="order blocked",
            dt=context.dt,
            action_taken="BLOCKED",
        )
        return RiskDecision.block(stage=RiskStage.ORDER, events=[event])


class InvalidRule(BaseRiskRule):
    name = "invalid_rule"
    stages = (RiskStage.ORDER,)

    def check(self, context: RiskCheckContext):  # type: ignore[override]
        return "invalid"


class BarRule(BaseRiskRule):
    name = "bar_rule"
    stages = (RiskStage.BAR,)

    def check(self, context: RiskCheckContext) -> RiskDecision:
        event = RiskEvent(
            risk_type="BAR_CHECK",
            severity="WARNING",
            code=context.code,
            message="bar stage checked",
            dt=context.dt,
            action_taken="ALLOWED",
        )
        return RiskDecision.allow(stage=RiskStage.BAR, events=[event])


class PortfolioRule(BaseRiskRule):
    name = "portfolio_rule"
    stages = (RiskStage.PORTFOLIO,)

    def check(self, context: RiskCheckContext) -> RiskDecision:
        event = RiskEvent(
            risk_type="PORTFOLIO_CHECK",
            severity="WARNING",
            code=context.code,
            message="portfolio stage checked",
            dt=context.dt,
            action_taken="ALLOWED",
        )
        return RiskDecision.allow(stage=RiskStage.PORTFOLIO, events=[event])


class MultiStageRule(BaseRiskRule):
    name = "multi_stage_rule"
    stages = (RiskStage.ORDER, RiskStage.BAR)

    def check(self, context: RiskCheckContext) -> RiskDecision:
        event = RiskEvent(
            risk_type=f"MULTI_STAGE_{context.metadata.get('stage_name', 'UNKNOWN')}",
            severity="WARNING",
            code=context.code,
            message="multi stage checked",
            dt=context.dt,
            action_taken="ALLOWED",
        )
        stage = RiskStage.ORDER if context.order is not None else RiskStage.BAR
        return RiskDecision.allow(stage=stage, events=[event])


class LowPriorityRule(BaseRiskRule):
    name = "low_priority_rule"
    priority = 90
    stages = (RiskStage.ORDER,)

    def check(self, context: RiskCheckContext) -> RiskDecision:
        event = RiskEvent(
            risk_type="LOW_PRIORITY",
            severity="WARNING",
            code=context.code,
            message="low priority",
            dt=context.dt,
            action_taken="ALLOWED",
        )
        return RiskDecision.allow(stage=RiskStage.ORDER, events=[event])


class HighPriorityRule(BaseRiskRule):
    name = "high_priority_rule"
    priority = 10
    stages = (RiskStage.ORDER,)

    def check(self, context: RiskCheckContext) -> RiskDecision:
        event = RiskEvent(
            risk_type="HIGH_PRIORITY",
            severity="WARNING",
            code=context.code,
            message="high priority",
            dt=context.dt,
            action_taken="ALLOWED",
        )
        return RiskDecision.allow(stage=RiskStage.ORDER, events=[event])


def build_context() -> RiskCheckContext:
    return RiskCheckContext(
        dt=datetime(2024, 1, 2, 9, 30),
        market="stock",
        code="000001.SZ",
        bar_price=10.0,
        order=Order(
            code="000001.SZ",
            direction=Direction.BUY,
            price=10.0,
            volume=100,
            order_id="risk-order-1",
            dt=datetime(2024, 1, 2, 9, 30),
        ),
        portfolio_equity=100000.0,
        latest_prices={"000001.SZ": 10.0},
    )


def test_risk_decision_allow_and_merge():
    first = RiskDecision.allow(stage=RiskStage.ORDER)
    second = RiskDecision.allow(stage=RiskStage.ORDER)

    merged = first.merge(second)

    assert merged.allowed is True
    assert merged.action == RiskAction.ALLOW
    assert merged.stage == RiskStage.ORDER
    assert merged.events == []


def test_risk_interceptor_applies_adjusted_order_to_later_rules():
    interceptor = RiskInterceptor(rules=[AdjustVolumeRule()])

    decision = interceptor.check(build_context())

    assert decision.allowed is True
    assert decision.action == RiskAction.ADJUST
    assert decision.stage == RiskStage.ORDER
    assert decision.adjusted_order is not None
    assert decision.adjusted_order.volume == 50
    assert len(decision.events) == 1
    assert decision.events[0].risk_type == "ADJUST_VOLUME"


def test_risk_interceptor_blocks_and_stops_further_rules():
    interceptor = RiskInterceptor(rules=[AdjustVolumeRule(), BlockRule(), AllowRule()])

    decision = interceptor.check(build_context())

    assert decision.allowed is False
    assert decision.action == RiskAction.BLOCK
    assert decision.stage == RiskStage.ORDER
    assert decision.adjusted_order is not None
    assert decision.adjusted_order.volume == 50
    assert len(decision.events) == 2
    assert decision.events[0].risk_type == "ADJUST_VOLUME"
    assert decision.events[1].risk_type == "BLOCK_ORDER"


def test_risk_interceptor_rejects_invalid_rule_result_type():
    interceptor = RiskInterceptor(rules=[InvalidRule()])

    try:
        interceptor.check(build_context())
    except TypeError as exc:
        assert "must return RiskDecision" in str(exc)
    else:
        raise AssertionError("expected TypeError for invalid risk rule result")


def test_risk_interceptor_routes_by_stage():
    interceptor = RiskInterceptor(rules=[AllowRule(), BarRule(), PortfolioRule()])
    context = build_context()

    order_decision = interceptor.check_order(context)
    bar_decision = interceptor.check_bar(context)
    portfolio_decision = interceptor.check_portfolio(context)

    assert order_decision.action == RiskAction.ALLOW
    assert order_decision.stage == RiskStage.ORDER
    assert order_decision.events == []
    assert len(bar_decision.events) == 1
    assert bar_decision.stage == RiskStage.BAR
    assert bar_decision.events[0].risk_type == "BAR_CHECK"
    assert len(portfolio_decision.events) == 1
    assert portfolio_decision.stage == RiskStage.PORTFOLIO
    assert portfolio_decision.events[0].risk_type == "PORTFOLIO_CHECK"


def test_risk_interceptor_default_check_uses_order_stage():
    interceptor = RiskInterceptor(rules=[AllowRule(), BarRule()])

    decision = interceptor.check(build_context())

    assert decision.action == RiskAction.ALLOW
    assert decision.stage == RiskStage.ORDER
    assert decision.events == []


def test_risk_interceptor_supports_stage_specific_registration_and_multi_stage_rule():
    interceptor = RiskInterceptor()
    interceptor.add_order_rule(AllowRule())
    interceptor.add_bar_rule(BarRule())
    interceptor.add_rule(MultiStageRule())

    context = build_context()
    order_decision = interceptor.check_order(context)
    bar_context = RiskCheckContext(
        dt=context.dt,
        market=context.market,
        code=context.code,
        bar_price=context.bar_price,
        metadata={"stage_name": "BAR"},
    )
    bar_decision = interceptor.check_bar(bar_context)

    assert order_decision.stage == RiskStage.ORDER
    assert len(order_decision.events) == 1
    assert order_decision.events[0].risk_type.startswith("MULTI_STAGE_")
    assert bar_decision.stage == RiskStage.BAR
    assert len(bar_decision.events) == 2


def test_risk_interceptor_orders_rules_by_priority():
    interceptor = RiskInterceptor(rules=[LowPriorityRule(), HighPriorityRule()])

    decision = interceptor.check_order(build_context())

    assert [event.risk_type for event in decision.events] == ["HIGH_PRIORITY", "LOW_PRIORITY"]
