"""
统一数据接口

当前提供面向本地存储的最小可用数据读取能力，向策略层和回测脚本输出
标准化的 OHLCV DataFrame。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from jwquant.trading.data.cleaner import PriceAdjuster
from jwquant.trading.data.store import LocalDataStore


class DataFeed:
    """统一数据读取入口。"""

    def __init__(
        self,
        store: LocalDataStore | None = None,
        base_path: str | Path | None = None,
        fmt: str | None = None,
    ) -> None:
        self.store = store or LocalDataStore(base_path=base_path, fmt=fmt)
        self.adjuster = PriceAdjuster()

    def get_bars(
        self,
        code: str,
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
        timeframe: str = "1d",
        market: str = "stock",
        adj: str | None = None,
    ) -> pd.DataFrame:
        """获取指定标的的历史 K 线。"""
        bars = self.store.load_bars(code=code, start=start, end=end, timeframe=timeframe, market=market)
        if market != "stock" or not adj or str(adj).lower() == "none" or bars.empty:
            return bars
        factors = self.store.load_adjust_factors(code=code, start=start, end=end, market=market)
        return self.adjuster.adjust(bars, factors, adj=adj)

    def get_latest_bar(
        self,
        code: str,
        timeframe: str = "1d",
        market: str = "stock",
        adj: str | None = None,
    ) -> pd.Series | None:
        """获取最新一根 K 线。"""
        bars = self.get_bars(code=code, timeframe=timeframe, market=market, adj=adj)
        if bars.empty:
            return None
        return bars.iloc[-1]

    def save_bars(self, code: str, bars: pd.DataFrame, timeframe: str = "1d", market: str = "stock") -> int:
        """透传到本地存储层，便于脚本侧直接落盘。"""
        return self.store.upsert_bars(code=code, bars=bars, timeframe=timeframe, market=market)

    def get_adjust_factors(
        self,
        code: str,
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
        market: str = "stock",
    ) -> pd.DataFrame:
        return self.store.load_adjust_factors(code=code, start=start, end=end, market=market)
