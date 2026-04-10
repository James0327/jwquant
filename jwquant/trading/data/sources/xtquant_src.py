"""
XtQuant 数据源

实时行情数据获取，券商级数据，用于实盘交易。
"""
from __future__ import annotations

from dataclasses import dataclass
import time

import pandas as pd


_FREQ_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "60m": "60m",
    "1d": "1d",
    "d": "1d",
    "daily": "1d",
    "1w": "1w",
    "w": "1w",
    "weekly": "1w",
    "1mth": "1mon",
    "1mon": "1mon",
    "month": "1mon",
    "monthly": "1mon",
}

_ADJ_MAP = {
    None: "none",
    "none": "none",
    "qfq": "front",
    "hfq": "back",
}


@dataclass
class XtQuantDataSource:
    """XtQuant 历史行情数据源。

    当前只走 XtQuant，一套接口同时支持 A 股和期货。
    """

    data_dir: str | None = None
    max_retries: int = 2
    retry_interval: float = 1.0

    def download_bars(
        self,
        code: str,
        start: str,
        end: str | None = None,
        timeframe: str = "1d",
        adj: str | None = None,
        market: str | None = None,
    ) -> pd.DataFrame:
        """下载并读取本地 XtQuant 历史行情。

        存储层默认只落原始行情，因此股票建议使用 ``adj=None``。
        """
        xtdata = self._load_xtdata()
        period = self._normalize_timeframe(timeframe)
        start_time = self._normalize_date(start, period)
        end_time = self._normalize_date(end, period) if end else ""
        normalized_market = self._normalize_market(code, market)
        field_list = self._build_field_list(normalized_market)
        dividend_type = self._normalize_adj(adj, normalized_market)

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                xtdata.download_history_data(code, period, start_time, end_time)
                data = xtdata.get_local_data(
                    field_list=field_list,
                    stock_list=[code],
                    period=period,
                    start_time=start_time,
                    end_time=end_time,
                    dividend_type=dividend_type,
                    fill_data=True,
                    data_dir=self.data_dir,
                )

                if not data or code not in data:
                    if attempt == self.max_retries:
                        raise RuntimeError(
                            f"xtquant returned no local data for code={code}, market={normalized_market}, "
                            f"timeframe={timeframe}, start={start}, end={end or ''}"
                        )
                    time.sleep(self.retry_interval)
                    continue

                normalized = self._normalize_dataframe(code, normalized_market, data[code])
                if normalized.empty:
                    if attempt == self.max_retries:
                        raise RuntimeError(
                            f"xtquant returned empty dataframe after normalization for code={code}, "
                            f"market={normalized_market}, timeframe={timeframe}"
                        )
                    time.sleep(self.retry_interval)
                    continue
                return normalized
            except Exception as exc:
                last_error = exc
                if attempt == self.max_retries:
                    break
                time.sleep(self.retry_interval)

        raise RuntimeError(
            f"xtquant download failed after {self.max_retries} attempts for "
            f"code={code}, market={normalized_market}, timeframe={timeframe}"
        ) from last_error

    def download_adjust_factors(
        self,
        code: str,
        start: str,
        end: str | None = None,
        market: str | None = None,
    ) -> pd.DataFrame:
        normalized_market = self._normalize_market(code, market)
        if normalized_market != "stock":
            return pd.DataFrame(columns=["code", "market", "dt", "factor_data"])

        xtdata = self._load_xtdata()
        start_time = self._normalize_date(start, "1d")
        end_time = self._normalize_date(end, "1d") if end else ""

        try:
            factors = xtdata.get_divid_factors(code, start_time, end_time)
        except Exception as exc:
            raise RuntimeError(
                f"xtquant dividend factor download failed for code={code}, start={start}, end={end or ''}"
            ) from exc

        if factors is None or factors.empty:
            return pd.DataFrame(columns=["code", "market", "dt", "factor_data"])

        df = factors.copy()
        if "time" in df.columns and "dt" not in df.columns:
            if pd.api.types.is_numeric_dtype(df["time"]):
                df["dt"] = pd.to_datetime(df["time"], unit="ms")
            else:
                df["dt"] = pd.to_datetime(df["time"])
        elif "date" in df.columns and "dt" not in df.columns:
            df["dt"] = pd.to_datetime(df["date"])
        elif not isinstance(df.index, pd.RangeIndex):
            df = df.reset_index().rename(columns={df.index.name or "index": "dt"})
            df["dt"] = pd.to_datetime(df["dt"])
        else:
            raise RuntimeError(f"xtquant dividend factors for code={code} do not contain a datetime column")

        df["code"] = code
        df["market"] = normalized_market
        return df.sort_values(["dt"]).reset_index(drop=True)

    def get_main_contract(
        self,
        code: str,
        start: str | None = None,
        end: str | None = None,
    ):
        """获取主连对应的实际合约。

        - 不传时间：返回当前主力合约代码
        - 传 `start`：返回指定日期或区间内的主力合约映射
        """
        xtdata = self._load_xtdata()
        start_time = self._normalize_date(start, "1d") if start else ""
        end_time = self._normalize_date(end, "1d") if end else ""
        try:
            return xtdata.get_main_contract(code, start_time, end_time)
        except Exception as exc:
            raise RuntimeError(
                f"xtquant get_main_contract failed for code={code}, start={start or ''}, end={end or ''}"
            ) from exc

    @staticmethod
    def _load_xtdata():
        try:
            from xtquant import xtdata
        except Exception as exc:
            raise RuntimeError(
                "failed to import xtquant.xtdata; please ensure XtQuant runtime/datacenter is installed correctly"
            ) from exc
        return xtdata

    @staticmethod
    def _normalize_timeframe(timeframe: str) -> str:
        normalized = _FREQ_MAP.get(timeframe.strip().lower())
        if not normalized:
            raise ValueError(f"unsupported xtquant timeframe: {timeframe}")
        return normalized

    @staticmethod
    def _normalize_adj(adj: str | None, market: str) -> str:
        if market == "futures":
            return "none"
        key = None if adj is None else str(adj).strip().lower()
        normalized = _ADJ_MAP.get(key)
        if normalized is None:
            raise ValueError(f"unsupported xtquant adjust type: {adj}")
        return normalized

    @staticmethod
    def _normalize_market(code: str, market: str | None = None) -> str:
        if market:
            normalized = str(market).strip().lower()
            if normalized in {"stock", "stocks", "equity", "a_share", "ashare"}:
                return "stock"
            if normalized in {"future", "futures"}:
                return "futures"
            raise ValueError(f"unsupported xtquant market: {market}")

        upper_code = code.upper()
        stock_suffixes = (".SH", ".SZ", ".BJ")
        if upper_code.endswith(stock_suffixes):
            return "stock"
        return "futures"

    @staticmethod
    def _build_field_list(market: str) -> list[str]:
        base_fields = ["time", "open", "high", "low", "close", "volume", "amount"]
        if market == "futures":
            return base_fields + ["openInterest"]
        return base_fields

    @staticmethod
    def _normalize_date(value: str, period: str) -> str:
        ts = pd.to_datetime(value)
        if period in {"1d", "1w", "1mon"}:
            return ts.strftime("%Y%m%d")
        return ts.strftime("%Y%m%d%H%M%S")

    @staticmethod
    def _normalize_dataframe(code: str, market: str, df: pd.DataFrame) -> pd.DataFrame:
        normalized = df.copy()
        if "time" in normalized.columns:
            time_series = normalized["time"]
            if pd.api.types.is_numeric_dtype(time_series):
                normalized["dt"] = pd.to_datetime(time_series, unit="ms")
            else:
                normalized["dt"] = pd.to_datetime(time_series)
        else:
            normalized["dt"] = pd.to_datetime(normalized.index)

        if "amount" not in normalized.columns:
            normalized["amount"] = 0.0
        if "openInterest" in normalized.columns and "open_interest" not in normalized.columns:
            normalized = normalized.rename(columns={"openInterest": "open_interest"})
        if "open_interest" not in normalized.columns:
            normalized["open_interest"] = 0.0

        normalized["code"] = code
        normalized["market"] = market
        result = normalized[["code", "market", "dt", "open", "high", "low", "close", "volume", "amount", "open_interest"]]
        return result.sort_values(["market", "code", "dt"]).reset_index(drop=True)
