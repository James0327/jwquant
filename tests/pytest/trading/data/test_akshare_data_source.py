from __future__ import annotations

import sys

import pandas as pd
import pytest

from jwquant.trading.data.sources.akshare_src import AkShareDataSource


class DummyAkModule:
    def __init__(self, dataframe: pd.DataFrame) -> None:
        self.dataframe = dataframe
        self.calls: list[dict[str, str]] = []
        self.daily_calls: list[dict[str, str]] = []
        self.qfq_factor = pd.DataFrame()
        self.hfq_factor = pd.DataFrame()
        self.raise_hist_error = False

    def stock_zh_a_hist(
        self,
        *,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str,
        adjust: str,
    ) -> pd.DataFrame:
        self.calls.append(
            {
                "symbol": symbol,
                "period": period,
                "start_date": start_date,
                "end_date": end_date,
                "adjust": adjust,
            }
        )
        if self.raise_hist_error:
            raise RuntimeError("hist provider unavailable")
        return self.dataframe.copy()

    def stock_zh_a_daily(
        self,
        *,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str,
    ) -> pd.DataFrame:
        self.daily_calls.append(
            {
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date,
                "adjust": adjust,
            }
        )
        if adjust == "qfq-factor":
            return self.qfq_factor.copy()
        if adjust == "hfq-factor":
            return self.hfq_factor.copy()
        return self.dataframe.copy()


def test_download_bars_should_normalize_akshare_dataframe(monkeypatch) -> None:
    module = DummyAkModule(
        pd.DataFrame(
            [
                {
                    "日期": "2025-01-02",
                    "股票代码": "601006",
                    "开盘": "6.78",
                    "收盘": "6.60",
                    "最高": "6.82",
                    "最低": "6.57",
                    "成交量": "1280947",
                    "成交额": "855720766.0",
                }
            ]
        )
    )
    monkeypatch.setitem(sys.modules, "akshare", module)

    source = AkShareDataSource()
    bars = source.download_bars(
        code="601006.SH",
        start="2025-01-01",
        end="2025-01-10",
        timeframe="1d",
        adj="none",
        market="stock",
    )

    assert module.calls == [
        {
            "symbol": "601006",
            "period": "daily",
            "start_date": "20250101",
            "end_date": "20250110",
            "adjust": "",
        }
    ]
    assert list(bars.columns) == ["code", "market", "dt", "open", "high", "low", "close", "volume", "amount", "open_interest"]
    assert bars.iloc[0]["code"] == "601006.SH"
    assert bars.iloc[0]["market"] == "stock"
    assert bars.iloc[0]["open_interest"] == 0.0


def test_download_bars_should_support_qfq_mapping(monkeypatch) -> None:
    module = DummyAkModule(
        pd.DataFrame(
            [
                {
                    "日期": "2025-01-02",
                    "开盘": 1,
                    "收盘": 1,
                    "最高": 1,
                    "最低": 1,
                    "成交量": 1,
                    "成交额": 1,
                }
            ]
        )
    )
    monkeypatch.setitem(sys.modules, "akshare", module)

    source = AkShareDataSource()
    source.download_bars(code="000001.SZ", start="2025-01-01", end="2025-01-10", timeframe="1w", adj="qfq", market="stock")

    assert module.calls[0]["period"] == "weekly"
    assert module.calls[0]["adjust"] == "qfq"


def test_download_bars_should_reject_futures_market() -> None:
    source = AkShareDataSource()

    with pytest.raises(ValueError, match="akshare only supports stock market data"):
        source.download_bars(code="IF00.IF", start="2025-01-01", end="2025-01-10", market="futures")


def test_download_bars_should_return_empty_standard_frame(monkeypatch) -> None:
    module = DummyAkModule(pd.DataFrame())
    monkeypatch.setitem(sys.modules, "akshare", module)

    source = AkShareDataSource()
    bars = source.download_bars(code="601006.SH", start="2025-01-01", end="2025-01-10", market="stock")

    assert bars.empty
    assert list(bars.columns) == ["code", "market", "dt", "open", "high", "low", "close", "volume", "amount", "open_interest"]


def test_download_bars_should_fallback_to_sina_daily_for_daily_timeframe(monkeypatch) -> None:
    module = DummyAkModule(
        pd.DataFrame(
            [
                {
                    "date": "2025-01-02",
                    "open": 6.4,
                    "close": 6.46,
                    "high": 6.47,
                    "low": 6.38,
                    "volume": 40791805,
                    "amount": 262652631,
                }
            ]
        )
    )
    module.raise_hist_error = True
    monkeypatch.setitem(sys.modules, "akshare", module)

    source = AkShareDataSource()
    bars = source.download_bars(code="601006.SH", start="2025-01-01", end="2025-01-10", timeframe="1d", market="stock")

    assert module.daily_calls == [
        {
            "symbol": "sh601006",
            "start_date": "20250101",
            "end_date": "20250110",
            "adjust": "",
        }
    ]
    assert bars.iloc[0]["close"] == 6.46


def test_download_adjust_factors_should_merge_qfq_and_hfq(monkeypatch) -> None:
    module = DummyAkModule(pd.DataFrame())
    module.qfq_factor = pd.DataFrame(
        [
            {"date": "2025-07-11", "qfq_factor": "1.013698630137"},
            {"date": "1900-01-01", "qfq_factor": "2.6440747749844"},
        ]
    )
    module.hfq_factor = pd.DataFrame(
        [
            {"date": "2025-07-11", "hfq_factor": "2.6083440347819"},
            {"date": "1900-01-01", "hfq_factor": "1.0"},
        ]
    )
    monkeypatch.setitem(sys.modules, "akshare", module)

    source = AkShareDataSource()
    factors = source.download_adjust_factors(
        code="601006.SH",
        start="2022-01-01",
        end="2025-12-31",
        market="stock",
    )

    assert module.daily_calls == [
        {
            "symbol": "sh601006",
            "start_date": "19000101",
            "end_date": "20251231",
            "adjust": "qfq-factor",
        },
        {
            "symbol": "sh601006",
            "start_date": "19000101",
            "end_date": "20251231",
            "adjust": "hfq-factor",
        },
    ]
    assert list(factors.columns) == ["code", "market", "dt", "qfq_factor", "hfq_factor"]
    assert factors.iloc[0]["code"] == "601006.SH"
    assert factors.iloc[0]["market"] == "stock"
