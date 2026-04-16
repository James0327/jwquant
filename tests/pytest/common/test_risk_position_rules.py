from __future__ import annotations

from datetime import datetime

from jwquant.common.types import Asset, Direction, Order, Position
from jwquant.trading.risk import (
    FuturesDirectionRule,
    MaxOrderAmountRule,
    MaxPositionPctRule,
    NoNakedShortRule,
    RiskAction,
    RiskCheckContext,
    RiskInterceptor,
)


def build_order_context(
    *,
    market: str = "stock",
    direction: Direction = Direction.BUY,
    price: float = 10.0,
    volume: int = 100,
    offset: str = "open_long",
    asset: Asset | None = None,
    position: Position | None = None,
    portfolio_equity: float = 10000.0,
) -> RiskCheckContext:
    code = "000001.SZ" if market == "stock" else "IF2406.IF"
    return RiskCheckContext(
        dt=datetime(2024, 1, 2, 9, 30),
        market=market,
        code=code,
        bar_price=price,
        order=Order(
            code=code,
            direction=direction,
            price=price,
            volume=volume,
            offset=offset,
            order_id="risk-order-position",
            dt=datetime(2024, 1, 2, 9, 30),
        ),
        asset=asset,
        position=position,
        portfolio_equity=portfolio_equity,
        latest_prices={code: price},
    )


def test_max_order_amount_rule_blocks_oversized_order():
    interceptor = RiskInterceptor(rules=[MaxOrderAmountRule(500.0)])
    context = build_order_context(price=10.0, volume=100)

    decision = interceptor.check_order(context)

    assert decision.allowed is False
    assert decision.action == RiskAction.BLOCK
    assert decision.events[0].risk_type == "MAX_ORDER_AMOUNT"
    assert decision.events[0].category == "position"
    assert decision.events[0].source == "max_order_amount"


def test_max_position_pct_rule_adjusts_order_volume_when_possible():
    interceptor = RiskInterceptor(rules=[MaxPositionPctRule(0.5)])
    context = build_order_context(
        price=10.0,
        volume=200,
        asset=Asset(cash=10000.0, total_asset=1000.0),
        portfolio_equity=2000.0,
    )

    decision = interceptor.check_order(context)

    assert decision.allowed is True
    assert decision.action == RiskAction.ADJUST
    assert decision.adjusted_order is not None
    assert decision.adjusted_order.volume == 100
    assert decision.events[0].risk_type == "MAX_POSITION_PCT"
    assert decision.events[0].category == "position"
    assert decision.events[0].source == "max_position_pct"


def test_max_position_pct_rule_uses_portfolio_positions_fallback_and_board_lot_rounding():
    interceptor = RiskInterceptor(rules=[MaxPositionPctRule(0.6)])
    context = build_order_context(
        price=10.0,
        volume=200,
        asset=Asset(cash=10000.0, total_asset=2200.0),
        portfolio_equity=2200.0,
    )
    context = context.with_updates(
        position=None,
        portfolio_positions={"000001.SZ": {"quantity": 20, "sellable_quantity": 20}},
        latest_prices={"000001.SZ": 10.0},
    )

    decision = interceptor.check_order(context)

    assert decision.allowed is True
    assert decision.action == RiskAction.ADJUST
    assert decision.adjusted_order is not None
    assert decision.adjusted_order.volume == 100
    assert decision.adjusted_order.volume % 100 == 0


def test_max_position_pct_rule_blocks_when_no_more_room():
    interceptor = RiskInterceptor(rules=[MaxPositionPctRule(0.5)])
    context = build_order_context(
        price=10.0,
        volume=10,
        asset=Asset(cash=10000.0, total_asset=1000.0),
        position=Position(code="000001.SZ", volume=50, available=50, cost_price=10.0),
        portfolio_equity=1000.0,
    )

    decision = interceptor.check_order(context)

    assert decision.allowed is False
    assert decision.action == RiskAction.BLOCK
    assert decision.events[0].risk_type == "MAX_POSITION_PCT"


def test_no_naked_short_rule_blocks_sell_without_available_position():
    interceptor = RiskInterceptor(rules=[NoNakedShortRule()])
    context = build_order_context(
        direction=Direction.SELL,
        volume=100,
        offset="close_long",
        position=Position(code="000001.SZ", volume=50, available=50, cost_price=10.0),
    )

    decision = interceptor.check_order(context)

    assert decision.allowed is False
    assert decision.action == RiskAction.BLOCK
    assert decision.events[0].risk_type == "NAKED_SHORT"


def test_no_naked_short_rule_allows_sell_with_available_position():
    interceptor = RiskInterceptor(rules=[NoNakedShortRule()])
    context = build_order_context(
        direction=Direction.SELL,
        volume=50,
        offset="close_long",
        position=Position(code="000001.SZ", volume=50, available=50, cost_price=10.0),
    )

    decision = interceptor.check_order(context)

    assert decision.allowed is True
    assert decision.action == RiskAction.ALLOW


def test_no_naked_short_rule_uses_portfolio_positions_fallback():
    interceptor = RiskInterceptor(rules=[NoNakedShortRule()])
    context = build_order_context(
        direction=Direction.SELL,
        volume=50,
        offset="close_long",
        position=None,
    )
    context = context.with_updates(
        portfolio_positions={"000001.SZ": {"quantity": 50, "sellable_quantity": 50}},
    )

    decision = interceptor.check_order(context)

    assert decision.allowed is True
    assert decision.action == RiskAction.ALLOW


def test_futures_direction_rule_blocks_disallowed_short_open():
    interceptor = RiskInterceptor(rules=[FuturesDirectionRule(allow_long=True, allow_short=False)])
    context = build_order_context(
        market="futures",
        direction=Direction.SELL,
        volume=1,
        offset="open_short",
        price=4000.0,
        portfolio_equity=100000.0,
    )

    decision = interceptor.check_order(context)

    assert decision.allowed is False
    assert decision.action == RiskAction.BLOCK
    assert decision.events[0].risk_type == "FUTURES_DIRECTION"
