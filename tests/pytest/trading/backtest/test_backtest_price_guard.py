from __future__ import annotations

from datetime import datetime

import pandas as pd

from jwquant.common.types import Bar, Signal, SignalType
from jwquant.trading.backtest.engine import BacktestConfig, SimpleBacktester
from jwquant.trading.strategy.base import BaseStrategy


class BuyOnSecondBarStrategy(BaseStrategy):
    def on_bar(self, bar: Bar) -> Signal | None:
        self.add_bar(bar)
        if len(self.history_bars) == 2:
            return Signal(
                code=bar.code,
                dt=bar.dt,
                signal_type=SignalType.BUY,
                price=bar.close,
                reason="buy_on_second_bar",
            )
        return None


class BuyThenSellStrategy(BaseStrategy):
    def on_bar(self, bar: Bar) -> Signal | None:
        self.add_bar(bar)
        if len(self.history_bars) == 1:
            return Signal(
                code=bar.code,
                dt=bar.dt,
                signal_type=SignalType.BUY,
                price=bar.close,
                reason="buy_first_bar",
            )
        if len(self.history_bars) == 2:
            return Signal(
                code=bar.code,
                dt=bar.dt,
                signal_type=SignalType.SELL,
                price=bar.close,
                reason="sell_second_bar",
            )
        return None


def test_backtest_blocks_buy_when_price_rise_exceeds_threshold():
    data = pd.DataFrame(
        [
            {"code": "000001.SZ", "dt": datetime(2024, 1, 2), "open": 10.0, "high": 10.0, "low": 10.0, "close": 10.0, "volume": 1000},
            {"code": "000001.SZ", "dt": datetime(2024, 1, 3), "open": 10.5, "high": 10.9, "low": 10.5, "close": 10.8, "volume": 1000},
            {"code": "000001.SZ", "dt": datetime(2024, 1, 4), "open": 11.8, "high": 11.9, "low": 11.7, "close": 11.8, "volume": 1000},
        ]
    )
    engine = SimpleBacktester(
        BacktestConfig(
            initial_capital=100000.0,
            market="stock",
            slippage=0.0,
            commission_rate=0.0,
            max_position_pct=1.0,
            buy_reject_threshold_pct=0.08,
            limit_up_pct=0.2,
        )
    )

    results = engine.run_backtest(BuyOnSecondBarStrategy("buy_guard"), data)

    assert results["total_orders"] == 1
    assert results["total_trades"] == 0
    assert results["report"]["order_status_counts"]["rejected"] == 1
    assert results["report"]["risk_by_source"]["stock_price_guard"] == 1


def test_backtest_blocks_sell_when_price_falls_to_limit_down():
    data = pd.DataFrame(
        [
            {"code": "000001.SZ", "dt": datetime(2024, 1, 2), "open": 10.0, "high": 10.0, "low": 10.0, "close": 10.0, "volume": 1000},
            {"code": "000001.SZ", "dt": datetime(2024, 1, 3), "open": 10.2, "high": 10.2, "low": 10.0, "close": 10.1, "volume": 1000},
            {"code": "000001.SZ", "dt": datetime(2024, 1, 4), "open": 9.0, "high": 9.1, "low": 9.0, "close": 9.0, "volume": 1000},
        ]
    )
    engine = SimpleBacktester(
        BacktestConfig(
            initial_capital=100000.0,
            market="stock",
            slippage=0.0,
            commission_rate=0.0,
            max_position_pct=1.0,
            sell_reject_threshold_pct=0.0,
            limit_down_pct=0.1,
        )
    )

    results = engine.run_backtest(BuyThenSellStrategy("sell_guard"), data)

    assert results["total_orders"] == 2
    assert results["total_trades"] == 1
    assert results["report"]["order_status_counts"]["filled"] == 1
    assert results["report"]["order_status_counts"]["rejected"] == 1
    assert results["report"]["risk_by_source"]["stock_price_guard"] == 1


def test_backtest_executes_signal_on_next_bar_open():
    data = pd.DataFrame(
        [
            {"code": "000001.SZ", "dt": datetime(2024, 1, 2), "open": 10.0, "high": 10.0, "low": 10.0, "close": 10.0, "volume": 1000},
            {"code": "000001.SZ", "dt": datetime(2024, 1, 3), "open": 10.1, "high": 10.8, "low": 10.1, "close": 10.8, "volume": 1000},
            {"code": "000001.SZ", "dt": datetime(2024, 1, 4), "open": 10.3, "high": 10.4, "low": 10.2, "close": 10.3, "volume": 1000},
        ]
    )
    engine = SimpleBacktester(
        BacktestConfig(
            initial_capital=100000.0,
            market="stock",
            slippage=0.0,
            commission_rate=0.0,
            max_position_pct=1.0,
            buy_reject_threshold_pct=0.0,
            limit_up_pct=0.2,
        )
    )

    results = engine.run_backtest(BuyOnSecondBarStrategy("next_open_execution"), data)

    assert results["total_orders"] == 1
    assert results["total_trades"] == 1
    trade = results["report"]["trade_records"][0]
    assert pd.Timestamp(trade["date"]) == pd.Timestamp(datetime(2024, 1, 4))
    assert trade["price"] == 10.3
