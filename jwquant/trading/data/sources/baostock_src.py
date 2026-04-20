"""
Baostock 数据源

A 股历史日线/周线数据获取，免费无需注册。
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from jwquant.trading.data.sources.capabilities import SourceCapabilities, normalize_market_alias


_FREQ_MAP = {
    "1d": "d",
    "d": "d",
    "day": "d",
    "daily": "d",
    "1w": "w",
    "w": "w",
    "week": "w",
    "weekly": "w",
    "1m": "m",
    "m": "m",
    "month": "m",
    "monthly": "m",
}

_ADJ_MAP = {
    None: "3",
    "none": "3",
    "qfq": "2",
    "hfq": "1",
}


@dataclass
class BaostockDataSource:
    """Baostock 历史行情数据源。"""

    _CAPABILITIES = SourceCapabilities(
        source_name="baostock",
        supported_markets=("stock",),
        supported_timeframes=("1d", "1w", "1m"),
        supports_adjusted_bars=True,
        supports_adjust_factors=False,
        supports_main_contract=False,
        data_grade="B",
    )

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
            raise ValueError("baostock only supports stock market data")
        try:
            import baostock as bs
        except ImportError as exc:
            raise RuntimeError("baostock is not installed; please install it before using this source") from exc

        login_result = bs.login()
        if getattr(login_result, "error_code", "0") != "0":
            raise RuntimeError(f"baostock login failed: {login_result.error_msg}")

        try:
            rs = bs.query_history_k_data_plus(
                self._normalize_code(code),
                "date,open,high,low,close,volume,amount",
                start_date=self._normalize_date(start),
                end_date=self._normalize_date(end) if end else "",
                frequency=self._normalize_timeframe(timeframe),
                adjustflag=self._normalize_adj(adj),
            )
            if getattr(rs, "error_code", "0") != "0":
                raise RuntimeError(f"baostock query failed: {rs.error_msg}")

            rows: list[list[str]] = []
            while rs.next():
                rows.append(rs.get_row_data())
        finally:
            bs.logout()

        if not rows:
            return pd.DataFrame(columns=["code", "dt", "open", "high", "low", "close", "volume", "amount"])

        df = pd.DataFrame(rows, columns=rs.fields)
        df["code"] = code
        df["dt"] = pd.to_datetime(df["date"])
        for column in ["open", "high", "low", "close", "volume", "amount"]:
            df[column] = pd.to_numeric(df[column], errors="coerce")
        return df[["code", "dt", "open", "high", "low", "close", "volume", "amount"]].sort_values(
            ["code", "dt"]
        ).reset_index(drop=True)

    def get_capabilities(self) -> SourceCapabilities:
        return self._CAPABILITIES

    def infer_market(self, code: str, market: str | None = None) -> str:
        del code
        return self._normalize_market(market)

    @staticmethod
    def _normalize_code(code: str) -> str:
        if "." not in code:
            return code
        symbol, market = code.split(".", 1)
        return f"{market.lower()}.{symbol}"

    @staticmethod
    def _normalize_date(value: str) -> str:
        return pd.to_datetime(value).strftime("%Y-%m-%d")

    @staticmethod
    def _normalize_timeframe(timeframe: str) -> str:
        normalized = _FREQ_MAP.get(timeframe.strip().lower())
        if not normalized:
            raise ValueError(f"unsupported baostock timeframe: {timeframe}")
        return normalized

    @staticmethod
    def _normalize_adj(adj: str | None) -> str:
        key = None if adj is None else str(adj).strip().lower()
        normalized = _ADJ_MAP.get(key)
        if normalized is None:
            raise ValueError(f"unsupported baostock adjust type: {adj}")
        return normalized

    @staticmethod
    def _normalize_market(market: str | None) -> str:
        return normalize_market_alias(market, default="stock")
