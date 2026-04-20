from __future__ import annotations

from datetime import datetime

from jwquant.common.types import Asset, Signal, SignalType
from jwquant.trading.risk import (
    FixedStopLossRule,
    FixedTakeProfitRule,
    MaxDrawdownRule,
    RiskAction,
    RiskCheckContext,
    RiskInterceptor,
    RiskStage,
    TrailingStopRule,
)


def build_bar_context(
    *,
    market: str = "stock",
    code: str = "000001.SZ",
    bar_price: float = 10.0,
    quantity: int = 100,
    avg_price: float = 10.0,
    portfolio_positions: dict | None = None,
    portfolio_equity: float = 100000.0,
    metadata: dict | None = None,
) -> RiskCheckContext:
    positions = portfolio_positions or {
        code: {
            "quantity": quantity,
            "avg_price": avg_price,
            "sellable_quantity": abs(quantity),
        }
    }
    return RiskCheckContext(
        dt=datetime(2024, 1, 2, 9, 30),
        market=market,
        code=code,
        bar_price=bar_price,
        asset=Asset(cash=10000.0, total_asset=portfolio_equity),
        position=positions.get(code),
        portfolio_positions=positions,
        portfolio_equity=portfolio_equity,
        latest_prices={code: bar_price, "600519.SH": 20.0},
        metadata=metadata or {},
    )


def test_fixed_stop_loss_rule_emits_exit_signal():
    interceptor = RiskInterceptor(rules=[FixedStopLossRule(0.05)])
    context = build_bar_context(bar_price=9.4, quantity=100, avg_price=10.0)

    decision = interceptor.check_bar(context)

    assert decision.action == RiskAction.ADJUST
    assert decision.stage == RiskStage.BAR
    assert decision.events[0].risk_type == "FIXED_STOP_LOSS"
    signals = decision.context_updates["metadata"]["risk_signals"]
    assert len(signals) == 1
    assert signals[0].signal_type.value == "sell"


def test_fixed_stop_loss_rule_scans_multiple_codes():
    interceptor = RiskInterceptor(rules=[FixedStopLossRule(0.05)])
    context = build_bar_context(
        code="000001.SZ",
        bar_price=9.4,
        quantity=100,
        avg_price=10.0,
        portfolio_positions={
            "000001.SZ": {"quantity": 100, "avg_price": 10.0, "sellable_quantity": 100},
            "600519.SH": {"quantity": 200, "avg_price": 20.0, "sellable_quantity": 200},
        },
    )
    context = context.with_updates(latest_prices={"000001.SZ": 9.4, "600519.SH": 18.8})

    decision = interceptor.check_bar(context)

    assert decision.action == RiskAction.ADJUST
    assert len(decision.events) == 2
    assert {event.code for event in decision.events} == {"000001.SZ", "600519.SH"}
    signals = decision.context_updates["metadata"]["risk_signals"]
    assert len(signals) == 2


def test_fixed_stop_loss_rule_deduplicates_existing_exit_signal():
    interceptor = RiskInterceptor(rules=[FixedStopLossRule(0.05)])
    existing_signal = Signal(
        code="000001.SZ",
        dt=datetime(2024, 1, 2, 9, 30),
        signal_type=SignalType.SELL,
        price=9.4,
        strength=1.0,
        reason="统一止损触发 pct=0.0500",
    )
    context = build_bar_context(
        bar_price=9.4,
        quantity=100,
        avg_price=10.0,
        metadata={"risk_signals": [existing_signal]},
    )

    decision = interceptor.check_bar(context)

    assert decision.action == RiskAction.ADJUST
    signals = decision.context_updates["metadata"]["risk_signals"]
    assert len(signals) == 1
    assert signals[0] == existing_signal


def test_fixed_take_profit_rule_emits_exit_signal():
    interceptor = RiskInterceptor(rules=[FixedTakeProfitRule(0.1)])
    context = build_bar_context(bar_price=11.2, quantity=100, avg_price=10.0)

    decision = interceptor.check_bar(context)

    assert decision.action == RiskAction.ADJUST
    assert decision.events[0].risk_type == "FIXED_TAKE_PROFIT"
    signals = decision.context_updates["metadata"]["risk_signals"]
    assert len(signals) == 1
    assert signals[0].signal_type.value == "sell"


def test_fixed_take_profit_rule_scans_multiple_codes():
    interceptor = RiskInterceptor(rules=[FixedTakeProfitRule(0.05)])
    context = build_bar_context(
        code="000001.SZ",
        bar_price=10.6,
        quantity=100,
        avg_price=10.0,
        portfolio_positions={
            "000001.SZ": {"quantity": 100, "avg_price": 10.0, "sellable_quantity": 100},
            "600519.SH": {"quantity": 200, "avg_price": 20.0, "sellable_quantity": 200},
        },
    )
    context = context.with_updates(latest_prices={"000001.SZ": 10.6, "600519.SH": 21.2})

    decision = interceptor.check_bar(context)

    assert decision.action == RiskAction.ADJUST
    assert len(decision.events) == 2
    assert {event.code for event in decision.events} == {"000001.SZ", "600519.SH"}
    signals = decision.context_updates["metadata"]["risk_signals"]
    assert len(signals) == 2


def test_trailing_stop_rule_updates_anchor_before_trigger():
    interceptor = RiskInterceptor(rules=[TrailingStopRule(0.05)])
    context = build_bar_context(bar_price=10.8, quantity=100, avg_price=10.0)

    decision = interceptor.check_bar(context)

    assert decision.action == RiskAction.ALLOW
    assert decision.context_updates["metadata"]["risk_state"]["trailing_anchor_prices"]["000001.SZ"] == 10.8


def test_trailing_stop_rule_triggers_after_anchor_reversal():
    interceptor = RiskInterceptor(rules=[TrailingStopRule(0.05)])
    context = build_bar_context(
        bar_price=10.1,
        quantity=100,
        avg_price=10.0,
        metadata={"risk_state": {"trailing_anchor_prices": {"000001.SZ": 10.8}}},
    )

    decision = interceptor.check_bar(context)

    assert decision.action == RiskAction.ADJUST
    assert decision.events[0].risk_type == "TRAILING_STOP"
    signals = decision.context_updates["metadata"]["risk_signals"]
    assert len(signals) == 1


def test_trailing_stop_rule_scans_multiple_codes():
    interceptor = RiskInterceptor(rules=[TrailingStopRule(0.05)])
    context = build_bar_context(
        code="000001.SZ",
        bar_price=10.1,
        quantity=100,
        avg_price=10.0,
        portfolio_positions={
            "000001.SZ": {"quantity": 100, "avg_price": 10.0, "sellable_quantity": 100},
            "600519.SH": {"quantity": 200, "avg_price": 20.0, "sellable_quantity": 200},
        },
        metadata={"risk_state": {"trailing_anchor_prices": {"000001.SZ": 10.8, "600519.SH": 21.5}}},
    )
    context = context.with_updates(latest_prices={"000001.SZ": 10.1, "600519.SH": 20.2})

    decision = interceptor.check_bar(context)

    assert decision.action == RiskAction.ADJUST
    assert len(decision.events) == 2
    assert {event.code for event in decision.events} == {"000001.SZ", "600519.SH"}
    signals = decision.context_updates["metadata"]["risk_signals"]
    assert len(signals) == 2


def test_trailing_stop_rule_triggers_on_first_gap_down_without_existing_anchor():
    interceptor = RiskInterceptor(rules=[TrailingStopRule(0.05)])
    context = build_bar_context(
        bar_price=9.4,
        quantity=100,
        avg_price=10.0,
        metadata={},
    )

    decision = interceptor.check_bar(context)

    assert decision.action == RiskAction.ADJUST
    assert decision.events[0].risk_type == "TRAILING_STOP"
    assert decision.context_updates["metadata"]["risk_state"]["trailing_anchor_prices"]["000001.SZ"] == 10.0
    assert decision.events[0].category == "stop"
    assert decision.events[0].source == "trailing_stop"


def test_fixed_stop_loss_rule_supports_short_position_exit_signal():
    interceptor = RiskInterceptor(rules=[FixedStopLossRule(0.05)])
    context = build_bar_context(
        market="futures",
        code="IF2406.IF",
        bar_price=10.6,
        quantity=-1,
        avg_price=10.0,
        portfolio_positions={
            "IF2406.IF": {"quantity": -1, "avg_price": 10.0, "sellable_quantity": 1},
        },
    )

    decision = interceptor.check_bar(context)

    assert decision.action == RiskAction.ADJUST
    assert decision.events[0].risk_type == "FIXED_STOP_LOSS"
    signals = decision.context_updates["metadata"]["risk_signals"]
    assert len(signals) == 1
    assert signals[0].signal_type.value == "buy"


def test_fixed_take_profit_rule_supports_short_position_exit_signal():
    interceptor = RiskInterceptor(rules=[FixedTakeProfitRule(0.05)])
    context = build_bar_context(
        market="futures",
        code="IF2406.IF",
        bar_price=9.4,
        quantity=-1,
        avg_price=10.0,
        portfolio_positions={
            "IF2406.IF": {"quantity": -1, "avg_price": 10.0, "sellable_quantity": 1},
        },
    )

    decision = interceptor.check_bar(context)

    assert decision.action == RiskAction.ADJUST
    assert decision.events[0].risk_type == "FIXED_TAKE_PROFIT"
    signals = decision.context_updates["metadata"]["risk_signals"]
    assert len(signals) == 1
    assert signals[0].signal_type.value == "buy"


def test_trailing_stop_rule_triggers_on_first_gap_up_for_short_without_existing_anchor():
    interceptor = RiskInterceptor(rules=[TrailingStopRule(0.05)])
    context = build_bar_context(
        market="futures",
        code="IF2406.IF",
        bar_price=10.6,
        quantity=-1,
        avg_price=10.0,
        portfolio_positions={
            "IF2406.IF": {"quantity": -1, "avg_price": 10.0, "sellable_quantity": 1},
        },
        metadata={},
    )

    decision = interceptor.check_bar(context)

    assert decision.action == RiskAction.ADJUST
    assert decision.events[0].risk_type == "TRAILING_STOP"
    assert decision.context_updates["metadata"]["risk_state"]["trailing_anchor_prices"]["IF2406.IF"] == 10.0
    signals = decision.context_updates["metadata"]["risk_signals"]
    assert len(signals) == 1
    assert signals[0].signal_type.value == "buy"


def test_max_drawdown_rule_emits_exit_signals_for_all_positions():
    interceptor = RiskInterceptor(rules=[MaxDrawdownRule(0.1)])
    context = build_bar_context(
        code="000001.SZ",
        bar_price=9.0,
        quantity=100,
        avg_price=10.0,
        portfolio_positions={
            "000001.SZ": {"quantity": 100, "avg_price": 10.0, "sellable_quantity": 100},
            "600519.SH": {"quantity": 200, "avg_price": 20.0, "sellable_quantity": 200},
        },
        portfolio_equity=90000.0,
        metadata={"risk_state": {"portfolio_peak_equity": 105000.0}},
    )

    decision = interceptor.check_bar(context)

    assert decision.action == RiskAction.ADJUST
    assert len(decision.events) == 2
    assert all(event.risk_type == "MAX_DRAWDOWN" for event in decision.events)
    assert all(event.category == "stop" for event in decision.events)
    signals = decision.context_updates["metadata"]["risk_signals"]
    assert len(signals) == 2


def test_max_drawdown_rule_deduplicates_existing_exit_signal():
    interceptor = RiskInterceptor(rules=[MaxDrawdownRule(0.1)])
    existing_signal = Signal(
        code="000001.SZ",
        dt=datetime(2024, 1, 2, 9, 30),
        signal_type=SignalType.SELL,
        price=9.0,
        strength=1.0,
        reason="组合最大回撤触发 pct=0.1000",
    )
    context = build_bar_context(
        code="000001.SZ",
        bar_price=9.0,
        quantity=100,
        avg_price=10.0,
        portfolio_positions={
            "000001.SZ": {"quantity": 100, "avg_price": 10.0, "sellable_quantity": 100},
            "600519.SH": {"quantity": 200, "avg_price": 20.0, "sellable_quantity": 200},
        },
        portfolio_equity=90000.0,
        metadata={
            "risk_state": {"portfolio_peak_equity": 105000.0},
            "risk_signals": [existing_signal],
        },
    )

    decision = interceptor.check_bar(context)

    signals = decision.context_updates["metadata"]["risk_signals"]
    assert len(signals) == 2
    assert signals[0] == existing_signal
    assert signals[1].code == "600519.SH"


def test_multiple_stop_rules_merge_events_and_signals():
    interceptor = RiskInterceptor(rules=[FixedStopLossRule(0.05), TrailingStopRule(0.05)])
    context = build_bar_context(
        bar_price=9.4,
        quantity=100,
        avg_price=10.0,
        metadata={"risk_state": {"trailing_anchor_prices": {"000001.SZ": 10.8}}},
    )

    decision = interceptor.check_bar(context)

    assert decision.action == RiskAction.ADJUST
    assert len(decision.events) == 2
    assert [event.risk_type for event in decision.events] == ["FIXED_STOP_LOSS", "TRAILING_STOP"]
    assert {event.category for event in decision.events} == {"stop"}
    signals = decision.context_updates["metadata"]["risk_signals"]
    assert len(signals) == 2
