from __future__ import annotations

from datetime import datetime

from jwquant.common.types import Asset, Direction, Order, Position
from jwquant.trading.risk import (
    MaxFuturesMarginRatioRule,
    MaxHoldingsRule,
    MaxTotalExposureRule,
    RiskAction,
    RiskCheckContext,
    RiskInterceptor,
    RiskStage,
    TargetWeightsRule,
)


def build_portfolio_context(
    *,
    market: str = "stock",
    code: str = "000001.SZ",
    bar_price: float = 10.0,
    order: Order | None = None,
    portfolio_positions: dict | None = None,
    portfolio_equity: float = 1000.0,
    metadata: dict | None = None,
) -> RiskCheckContext:
    latest_prices = {"000001.SZ": 10.0, "600519.SH": 20.0, "300750.SZ": 30.0, "IF2406.IF": 4000.0}
    return RiskCheckContext(
        dt=datetime(2024, 1, 2, 9, 30),
        market=market,
        code=code,
        bar_price=bar_price,
        order=order,
        asset=Asset(cash=10000.0, total_asset=portfolio_equity),
        portfolio_positions=portfolio_positions or {},
        portfolio_equity=portfolio_equity,
        latest_prices=latest_prices,
        metadata=metadata or {},
    )


def test_max_total_exposure_rule_blocks_oversized_order():
    interceptor = RiskInterceptor(rules=[MaxTotalExposureRule(0.5)])
    context = build_portfolio_context(
        order=Order(
            code="000001.SZ",
            direction=Direction.BUY,
            price=10.0,
            volume=60,
            offset="open_long",
            order_id="portfolio-risk-order-1",
            dt=datetime(2024, 1, 2, 9, 30),
        ),
        portfolio_positions={"600519.SH": {"quantity": 10}},
        portfolio_equity=1000.0,
    )

    decision = interceptor.check_order(context)

    assert decision.allowed is False
    assert decision.action == RiskAction.BLOCK
    assert decision.events[0].risk_type == "MAX_TOTAL_EXPOSURE"
    assert decision.events[0].category == "portfolio"
    assert decision.events[0].source == "max_total_exposure"
    assert decision.events[0].metadata["exposure_model"] == "gross_notional"


def test_max_holdings_rule_blocks_new_position_when_limit_reached():
    interceptor = RiskInterceptor(rules=[MaxHoldingsRule(2)])
    context = build_portfolio_context(
        code="300750.SZ",
        order=Order(
            code="300750.SZ",
            direction=Direction.BUY,
            price=30.0,
            volume=100,
            offset="open_long",
            order_id="portfolio-risk-order-2",
            dt=datetime(2024, 1, 2, 9, 30),
        ),
        portfolio_positions={
            "000001.SZ": {"quantity": 100},
            "600519.SH": {"quantity": 100},
        },
    )

    decision = interceptor.check_order(context)

    assert decision.allowed is False
    assert decision.action == RiskAction.BLOCK
    assert decision.events[0].risk_type == "MAX_HOLDINGS"


def test_target_weights_rule_adjusts_negative_and_oversized_weights():
    interceptor = RiskInterceptor(rules=[TargetWeightsRule(max_single_weight=0.4, max_total_exposure=0.6)])
    context = build_portfolio_context(
        metadata={
            "target_weights": {
                "000001.SZ": 0.8,
                "600519.SH": -0.2,
                "300750.SZ": 0.3,
            }
        }
    )

    decision = interceptor.check_portfolio(context)

    assert decision.allowed is True
    assert decision.action == RiskAction.ADJUST
    assert decision.stage == RiskStage.PORTFOLIO
    adjusted_weights = decision.context_updates["metadata"]["target_weights"]
    assert adjusted_weights["600519.SH"] == 0.0
    assert sum(abs(weight) for weight in adjusted_weights.values()) <= 0.6000001
    assert len(decision.events) == 3


def test_target_weights_rule_keeps_valid_weights_unchanged():
    interceptor = RiskInterceptor(rules=[TargetWeightsRule(max_single_weight=0.6, max_total_exposure=1.0)])
    context = build_portfolio_context(
        metadata={"target_weights": {"000001.SZ": 0.4, "600519.SH": 0.3}}
    )

    decision = interceptor.check_portfolio(context)

    assert decision.allowed is True
    assert decision.action == RiskAction.ALLOW
    assert decision.context_updates == {}


def test_max_total_exposure_rule_blocks_portfolio_stage_when_current_exposure_exceeds_limit():
    interceptor = RiskInterceptor(rules=[MaxTotalExposureRule(0.5)])
    context = build_portfolio_context(
        portfolio_positions={
            "000001.SZ": Position(code="000001.SZ", volume=30, available=30, cost_price=10.0),
            "600519.SH": Position(code="600519.SH", volume=20, available=20, cost_price=20.0),
        },
        portfolio_equity=1000.0,
    )

    decision = interceptor.check_portfolio(context)

    assert decision.allowed is False
    assert decision.action == RiskAction.BLOCK
    assert decision.events[0].risk_type == "MAX_TOTAL_EXPOSURE"


def test_max_total_exposure_rule_respects_exposure_multiplier_metadata():
    interceptor = RiskInterceptor(rules=[MaxTotalExposureRule(0.5)])
    context = build_portfolio_context(
        market="futures",
        code="IF2406.IF",
        portfolio_positions={"IF2406.IF": {"quantity": 1}},
        portfolio_equity=10000.0,
        metadata={"exposure_multipliers": {"IF2406.IF": 300.0}},
    )

    decision = interceptor.check_portfolio(context)

    assert decision.allowed is False
    assert decision.action == RiskAction.BLOCK
    assert decision.events[0].risk_type == "MAX_TOTAL_EXPOSURE"
    assert decision.events[0].metadata["exposure_model"] == "gross_notional"


def test_max_futures_margin_ratio_rule_blocks_oversized_futures_order():
    interceptor = RiskInterceptor(rules=[MaxFuturesMarginRatioRule(0.2)])
    context = build_portfolio_context(
        market="futures",
        code="IF2406.IF",
        order=Order(
            code="IF2406.IF",
            direction=Direction.BUY,
            price=4000.0,
            volume=1,
            offset="open_long",
            order_id="portfolio-risk-order-3",
            dt=datetime(2024, 1, 2, 9, 30),
        ),
        portfolio_equity=100000.0,
        metadata={
            "margin_rate": 0.12,
            "exposure_multipliers": {"IF2406.IF": 300.0},
        },
    )

    decision = interceptor.check_order(context)

    assert decision.allowed is False
    assert decision.action == RiskAction.BLOCK
    assert decision.events[0].risk_type == "MAX_FUTURES_MARGIN_RATIO"
