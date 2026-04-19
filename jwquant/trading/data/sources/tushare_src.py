"""
Tushare 数据源

A 股日线/分钟线/财务数据获取，需要 Token。
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import tushare as ts

from jwquant.common.config import get


_FREQ_MAP = {
    "1d": "D",
    "d": "D",
    "day": "D",
    "daily": "D",
    "1w": "W",
    "w": "W",
    "week": "W",
    "weekly": "W",
    "1m": "M",
    "m": "M",
    "month": "M",
    "monthly": "M",
}


@dataclass
class TushareDataSource:
    """Tushare 历史行情数据源。"""

    token: str | None = None

    def __post_init__(self) -> None:
        self.token = self.token or get("data.tushare.token")
        if not self.token:
            raise ValueError("missing tushare token: please set data.tushare.token in config")
        ts.set_token(self.token)
        self.pro = ts.pro_api()

    def download_bars(
        self,
        code: str,
        start: str,
        end: str | None = None,
        timeframe: str = "1d",
        adj: str | None = "qfq",
        market: str | None = None,
    ) -> pd.DataFrame:
        """下载并标准化历史 K 线数据。"""
        normalized_market = self._normalize_market(market)
        if normalized_market != "stock":
            raise ValueError("tushare only supports stock market data")
        freq = self._normalize_timeframe(timeframe)
        start_date = self._normalize_date(start)
        end_date = self._normalize_date(end) if end else None

        df = ts.pro_bar(
            ts_code=code,
            start_date=start_date,
            end_date=end_date,
            freq=freq,
            adj=adj,
        )

        if df is None or df.empty:
            return pd.DataFrame(columns=["code", "dt", "open", "high", "low", "close", "volume", "amount"])

        return self._normalize_dataframe(df)

    @staticmethod
    def _normalize_timeframe(timeframe: str) -> str:
        normalized = _FREQ_MAP.get(timeframe.strip().lower())
        if not normalized:
            raise ValueError(f"unsupported tushare timeframe: {timeframe}")
        return normalized

    @staticmethod
    def _normalize_date(value: str) -> str:
        return pd.to_datetime(value).strftime("%Y%m%d")

    @staticmethod
    def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        normalized = df.rename(columns={"ts_code": "code", "trade_date": "dt"}).copy()
        normalized["dt"] = pd.to_datetime(normalized["dt"])

        if "amount" not in normalized.columns:
            normalized["amount"] = 0.0

        result = normalized[["code", "dt", "open", "high", "low", "close", "vol", "amount"]].rename(
            columns={"vol": "volume"}
        )
        result = result.sort_values(["code", "dt"]).reset_index(drop=True)
        return result

    @staticmethod
    def _normalize_market(market: str | None) -> str:
        if market is None:
            return "stock"
        normalized = str(market).strip().lower()
        if normalized in {"stock", "stocks", "equity", "a_share", "ashare"}:
            return "stock"
        if normalized in {"future", "futures"}:
            return "futures"
        raise ValueError(f"unsupported tushare market: {market}")
