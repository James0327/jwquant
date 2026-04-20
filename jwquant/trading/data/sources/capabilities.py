"""数据源能力声明与通用约定。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import pandas as pd


_STOCK_MARKET_ALIASES = {"stock", "stocks", "equity", "a_share", "ashare"}
_FUTURES_MARKET_ALIASES = {"future", "futures"}


def normalize_market_alias(market: str | None, *, default: str | None = None) -> str:
    """规范化市场标识。"""
    if market is None:
        if default is None:
            raise ValueError("market must not be empty")
        return default
    normalized = str(market).strip().lower()
    if normalized in _STOCK_MARKET_ALIASES:
        return "stock"
    if normalized in _FUTURES_MARKET_ALIASES:
        return "futures"
    raise ValueError(f"unsupported market: {market}")


def infer_market_from_code(code: str) -> str:
    """按代码后缀推断市场。"""
    upper_code = str(code).strip().upper()
    if upper_code.endswith((".SH", ".SZ", ".BJ")):
        return "stock"
    return "futures"


@dataclass(frozen=True)
class SourceCapabilities:
    """统一数据源能力描述。"""

    source_name: str
    supported_markets: tuple[str, ...]
    supported_timeframes: tuple[str, ...]
    supports_adjusted_bars: bool = False
    supports_adjust_factors: bool = False
    supports_main_contract: bool = False
    supports_incremental_safe: bool = True
    data_grade: str = "B"


@runtime_checkable
class MarketDataSource(Protocol):
    """统一市场数据源协议。"""

    def get_capabilities(self) -> SourceCapabilities: ...

    def infer_market(self, code: str, market: str | None = None) -> str: ...

    def download_bars(
        self,
        code: str,
        start: str,
        end: str | None = None,
        timeframe: str = "1d",
        adj: str | None = None,
        market: str | None = None,
    ) -> pd.DataFrame: ...
