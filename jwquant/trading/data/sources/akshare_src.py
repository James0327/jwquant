"""AkShare 数据源。"""
from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType

import pandas as pd

from jwquant.trading.data.sources.capabilities import SourceCapabilities, normalize_market_alias


_PERIOD_MAP = {
    "1d": "daily",
    "d": "daily",
    "day": "daily",
    "daily": "daily",
    "1w": "weekly",
    "w": "weekly",
    "week": "weekly",
    "weekly": "weekly",
    "1m": "monthly",
    "m": "monthly",
    "month": "monthly",
    "monthly": "monthly",
}

_ADJUST_MAP = {
    None: "",
    "none": "",
    "qfq": "qfq",
    "hfq": "hfq",
}


@dataclass
class AkShareDataSource:
    """AkShare 历史行情数据源。

    当前仅支持 A 股日/周/月历史行情。
    """

    _CAPABILITIES = SourceCapabilities(
        source_name="akshare",
        supported_markets=("stock",),
        supported_timeframes=("1d", "1w", "1m"),
        supports_adjusted_bars=True,
        supports_adjust_factors=True,
        supports_main_contract=False,
        data_grade="B",
    )

    def get_capabilities(self) -> SourceCapabilities:
        return self._CAPABILITIES

    def infer_market(self, code: str, market: str | None = None) -> str:
        del code
        return self._normalize_market(market)

    def download_bars(
        self,
        code: str,
        start: str,
        end: str | None = None,
        timeframe: str = "1d",
        adj: str | None = None,
        market: str | None = None,
    ) -> pd.DataFrame:
        normalized_market = self._normalize_market(market)
        if normalized_market != "stock":
            raise ValueError("akshare only supports stock market data")

        ak = self._load_akshare()
        symbol = self._normalize_code_for_akshare(code)
        period = self._normalize_timeframe(timeframe)
        adjust = self._normalize_adj(adj)
        start_date = self._normalize_date(start)
        end_date = self._normalize_date(end) if end else pd.Timestamp.today().strftime("%Y%m%d")

        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
        except Exception as exc:
            if period == "daily":
                try:
                    df = ak.stock_zh_a_daily(
                        symbol=self._normalize_code_for_sina(code),
                        start_date=start_date,
                        end_date=end_date,
                        adjust=adjust,
                    )
                except Exception as fallback_exc:
                    raise RuntimeError(
                        f"akshare history download failed for code={code}, timeframe={timeframe}, "
                        f"start={start}, end={end or ''}"
                    ) from fallback_exc
            else:
                raise RuntimeError(
                    f"akshare history download failed for code={code}, timeframe={timeframe}, start={start}, end={end or ''}"
                ) from exc

        if df is None or df.empty:
            return pd.DataFrame(
                columns=["code", "market", "dt", "open", "high", "low", "close", "volume", "amount", "open_interest"]
            )

        return self._normalize_dataframe(df, code=code, market=normalized_market)

    def download_adjust_factors(
        self,
        code: str,
        start: str,
        end: str | None = None,
        market: str | None = None,
    ) -> pd.DataFrame:
        normalized_market = self._normalize_market(market)
        if normalized_market != "stock":
            return pd.DataFrame(columns=["code", "market", "dt", "qfq_factor", "hfq_factor"])

        ak = self._load_akshare()
        symbol = self._normalize_code_for_sina(code)
        # AkShare 的绝对复权因子只在除权事件日变化。为保证 start 之前最近一次事件可用于前向填充，
        # 这里固定回拉完整历史至请求截止日，而不是只截取 [start, end]。
        end_date = self._normalize_date(end) if end else pd.Timestamp.today().strftime("%Y%m%d")

        try:
            qfq = ak.stock_zh_a_daily(symbol=symbol, start_date="19000101", end_date=end_date, adjust="qfq-factor")
            hfq = ak.stock_zh_a_daily(symbol=symbol, start_date="19000101", end_date=end_date, adjust="hfq-factor")
        except Exception as exc:
            raise RuntimeError(
                f"akshare adjust factor download failed for code={code}, start={start}, end={end or ''}"
            ) from exc

        qfq_normalized = self._normalize_factor_frame(qfq, factor_column="qfq_factor")
        hfq_normalized = self._normalize_factor_frame(hfq, factor_column="hfq_factor")
        merged = qfq_normalized.merge(hfq_normalized, on="dt", how="outer").sort_values("dt").reset_index(drop=True)
        if merged.empty:
            return pd.DataFrame(columns=["code", "market", "dt", "qfq_factor", "hfq_factor"])
        merged["code"] = code
        merged["market"] = normalized_market
        return merged[["code", "market", "dt", "qfq_factor", "hfq_factor"]]

    @staticmethod
    def _load_akshare() -> ModuleType:
        try:
            import akshare as ak
        except ImportError as exc:
            raise RuntimeError("akshare is not installed; please install it before using this source") from exc
        return ak

    @staticmethod
    def _normalize_market(market: str | None) -> str:
        return normalize_market_alias(market, default="stock")

    @staticmethod
    def _normalize_code_for_akshare(code: str) -> str:
        return str(code).split(".", 1)[0].strip().upper()

    @staticmethod
    def _normalize_code_for_sina(code: str) -> str:
        symbol, _, market = str(code).partition(".")
        if market:
            return f"{market.lower()}{symbol}"
        return symbol.lower()

    @staticmethod
    def _normalize_timeframe(timeframe: str) -> str:
        normalized = _PERIOD_MAP.get(str(timeframe).strip().lower())
        if normalized is None:
            raise ValueError(f"unsupported akshare timeframe: {timeframe}")
        return normalized

    @staticmethod
    def _normalize_adj(adj: str | None) -> str:
        key = None if adj is None else str(adj).strip().lower()
        normalized = _ADJUST_MAP.get(key)
        if normalized is None:
            raise ValueError(f"unsupported akshare adjust type: {adj}")
        return normalized

    @staticmethod
    def _normalize_date(value: str) -> str:
        return pd.to_datetime(value).strftime("%Y%m%d")

    @staticmethod
    def _normalize_dataframe(df: pd.DataFrame, *, code: str, market: str) -> pd.DataFrame:
        normalized = df.rename(
            columns={
                "日期": "dt",
                "date": "dt",
                "开盘": "open",
                "open": "open",
                "收盘": "close",
                "close": "close",
                "最高": "high",
                "high": "high",
                "最低": "low",
                "low": "low",
                "成交量": "volume",
                "volume": "volume",
                "成交额": "amount",
                "amount": "amount",
            }
        ).copy()
        normalized["dt"] = pd.to_datetime(normalized["dt"])
        for column in ["open", "high", "low", "close", "volume", "amount"]:
            if column not in normalized.columns:
                if column == "amount":
                    normalized[column] = 0.0
                else:
                    raise RuntimeError(f"akshare dataframe missing required column: {column}")
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

        normalized["code"] = code
        normalized["market"] = market
        normalized["open_interest"] = 0.0
        result = normalized[
            ["code", "market", "dt", "open", "high", "low", "close", "volume", "amount", "open_interest"]
        ]
        return result.sort_values(["market", "code", "dt"]).reset_index(drop=True)

    @staticmethod
    def _normalize_factor_frame(df: pd.DataFrame, *, factor_column: str) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame(columns=["dt", factor_column])
        normalized = df.rename(columns={"date": "dt"}).copy()
        normalized["dt"] = pd.to_datetime(normalized["dt"])
        normalized[factor_column] = pd.to_numeric(normalized[factor_column], errors="coerce")
        return normalized[["dt", factor_column]].dropna(subset=[factor_column]).sort_values("dt").reset_index(drop=True)
