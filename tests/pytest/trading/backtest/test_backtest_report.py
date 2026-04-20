from __future__ import annotations

from datetime import datetime

from jwquant.trading.backtest.report import render_backtest_report_html


def _build_results_fixture() -> dict:
    return {
        "report": {
            "summary": {
                "strategy_name": "demo",
                "execution_timing": "T日收盘生成信号，T+1日开盘撮合",
                "execution_price_model": "T+1_open +/- slippage",
                "rejected_orders": 1,
                "price_guard_blocked_orders": 1,
            },
            "equity_records": [
                {"dt": datetime(2024, 1, 2), "equity": 100000.0},
                {"dt": datetime(2024, 1, 3), "equity": 101000.0},
            ],
            "market_data": [
                {"code": "000001.SZ", "dt": datetime(2024, 1, 2), "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.2},
                {"code": "000001.SZ", "dt": datetime(2024, 1, 3), "open": 10.3, "high": 10.8, "low": 10.1, "close": 10.7},
            ],
            "position_records": [
                {"code": "000001.SZ", "dt": datetime(2024, 1, 2), "quantity": 0},
                {"code": "000001.SZ", "dt": datetime(2024, 1, 3), "quantity": 100},
            ],
            "trade_records": [
                {"code": "000001.SZ", "date": datetime(2024, 1, 3), "direction": "BUY", "price": 10.3, "offset": "open_long"},
            ],
            "signal_records": [
                {
                    "signal_id": "bt-signal-1",
                    "code": "000001.SZ",
                    "signal_type": "buy",
                    "signal_dt": datetime(2024, 1, 2),
                    "signal_price": 10.2,
                    "status": "expired",
                    "reason_detail": "无下一根Bar，信号未执行",
                    "reason_source": "no_next_bar",
                }
            ],
            "risk_events": [],
            "latest_positions": {},
            "risk_by_category": {},
            "risk_by_source": {},
            "risk_by_action": {},
        }
    }


def test_render_backtest_report_html_supports_simple_chart_mode():
    html = render_backtest_report_html(_build_results_fixture(), chart_mode="simple")

    assert "价格图与买卖点" in html
    assert "图表模式: 简化折线图" in html
    assert "图例说明" in html
    assert "B" in html
    assert "SB" in html
    assert "仓位变化折线" in html


def test_render_backtest_report_html_supports_full_chart_mode():
    html = render_backtest_report_html(_build_results_fixture(), chart_mode="full")

    assert "价格图与买卖点" in html
    assert "图表模式: 完整K线图" in html
    assert "图例说明" in html
    assert "仓位变化折线" in html
    assert "<rect" in html
