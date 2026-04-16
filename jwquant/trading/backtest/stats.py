"""
回测绩效统计。
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def calculate_performance(
    *,
    equity_curve: list[float],
    initial_capital: float,
    trades: list[dict[str, Any]],
) -> dict[str, float]:
    """根据权益曲线和交易记录计算基础绩效指标。"""
    if not equity_curve:
        return {
            "total_return": 0.0,
            "annual_return": 0.0,
            "volatility": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_trade_profit": 0.0,
            "avg_win_profit": 0.0,
            "avg_loss_profit": 0.0,
            "total_commission": 0.0,
        }

    equity_series = pd.Series(equity_curve, dtype=float)
    returns = equity_series.pct_change().dropna()

    total_return = (equity_series.iloc[-1] - initial_capital) / initial_capital
    annual_return = (1 + total_return) ** (252 / len(equity_series)) - 1 if len(equity_series) > 0 else 0.0
    volatility = returns.std() * np.sqrt(252) if not returns.empty else 0.0
    sharpe_ratio = annual_return / volatility if volatility > 0 else 0.0

    rolling_max = equity_series.expanding().max()
    drawdown = (equity_series - rolling_max) / rolling_max
    max_drawdown = float(drawdown.min()) if not drawdown.empty else 0.0

    closing_offsets = {"close_long", "close_short"}
    closing_trades = [
        trade
        for trade in trades
        if (
            trade.get("offset") in closing_offsets
            or ("offset" not in trade and trade["direction"] == "SELL")
        )
    ]
    profitable_trades = [trade for trade in closing_trades if trade["profit"] > 0]
    losing_trades = [trade for trade in closing_trades if trade["profit"] < 0]
    win_rate = len(profitable_trades) / len(closing_trades) if closing_trades else 0.0
    gross_profit = float(sum(trade["profit"] for trade in profitable_trades))
    gross_loss = float(sum(-trade["profit"] for trade in losing_trades))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
    avg_trade_profit = (
        float(sum(trade["profit"] for trade in closing_trades)) / len(closing_trades)
        if closing_trades
        else 0.0
    )
    avg_win_profit = gross_profit / len(profitable_trades) if profitable_trades else 0.0
    avg_loss_profit = -gross_loss / len(losing_trades) if losing_trades else 0.0

    return {
        "total_return": float(total_return),
        "annual_return": float(annual_return),
        "volatility": float(volatility),
        "sharpe_ratio": float(sharpe_ratio),
        "max_drawdown": max_drawdown,
        "win_rate": float(win_rate),
        "profit_factor": float(profit_factor),
        "avg_trade_profit": float(avg_trade_profit),
        "avg_win_profit": float(avg_win_profit),
        "avg_loss_profit": float(avg_loss_profit),
        "total_commission": float(sum(trade["commission"] for trade in trades)),
    }
