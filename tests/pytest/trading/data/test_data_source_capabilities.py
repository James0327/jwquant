from __future__ import annotations

import pandas as pd

from jwquant.trading.data.sources.akshare_src import AkShareDataSource
from jwquant.trading.data.sources.baostock_src import BaostockDataSource
from jwquant.trading.data.sources.capabilities import SourceCapabilities
from jwquant.trading.data.sources.tushare_src import TushareDataSource
from jwquant.trading.data.sources.xtquant_src import XtQuantDataSource
from jwquant.trading.data.store import LocalDataStore
from jwquant.trading.data.sync import sync_market_data


class DummySource:
    def __init__(self, capabilities: SourceCapabilities) -> None:
        self._capabilities = capabilities
        self.factor_called = False
        self.main_contract_called = False

    def get_capabilities(self) -> SourceCapabilities:
        return self._capabilities

    def infer_market(self, code: str, market: str | None = None) -> str:
        del code
        return market or "stock"

    def download_bars(
        self,
        code: str,
        start: str,
        end: str | None = None,
        timeframe: str = "1d",
        adj: str | None = None,
        market: str | None = None,
    ) -> pd.DataFrame:
        del start, end, timeframe, adj
        normalized_market = market or "stock"
        return pd.DataFrame(
            [
                {
                    "code": code,
                    "market": normalized_market,
                    "dt": pd.Timestamp("2024-01-02"),
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.5,
                    "close": 10.5,
                    "volume": 1000.0,
                    "amount": 10500.0,
                    "open_interest": 0.0,
                }
            ]
        )

    def download_adjust_factors(
        self,
        code: str,
        start: str,
        end: str | None = None,
        market: str | None = None,
    ) -> pd.DataFrame:
        del start, end, market
        self.factor_called = True
        return pd.DataFrame(
            [{"code": code, "market": "stock", "dt": pd.Timestamp("2024-01-02"), "factor_data": {"factor": 1.0}}]
        )

    def get_main_contract(
        self,
        code: str,
        start: str | None = None,
        end: str | None = None,
    ) -> str:
        del start, end
        self.main_contract_called = True
        return code


def test_builtin_sources_should_expose_capabilities() -> None:
    akshare = AkShareDataSource()
    xtquant = XtQuantDataSource()
    tushare = object.__new__(TushareDataSource)
    baostock = BaostockDataSource()

    assert akshare.get_capabilities().supports_adjust_factors is True
    assert xtquant.get_capabilities().supports_adjust_factors is True
    assert xtquant.get_capabilities().supports_main_contract is True
    assert tushare.get_capabilities().source_name == "tushare"
    assert baostock.get_capabilities().supported_markets == ("stock",)


def test_sync_market_data_should_skip_factor_download_when_capability_disabled(tmp_path) -> None:
    source = DummySource(
        SourceCapabilities(
            source_name="dummy",
            supported_markets=("stock",),
            supported_timeframes=("1d",),
            supports_adjust_factors=False,
        )
    )
    store = LocalDataStore(base_path=tmp_path, fmt="sqlite")

    result = sync_market_data(
        code="000001.SZ",
        start="2024-01-01",
        end="2024-01-31",
        market="stock",
        timeframe="1d",
        store=store,
        source=source,
        incremental=False,
    )

    assert result.factor_rows == 0
    assert source.factor_called is False


def test_sync_market_data_should_use_explicit_main_contract_capability(tmp_path) -> None:
    source = DummySource(
        SourceCapabilities(
            source_name="dummy_futures",
            supported_markets=("futures",),
            supported_timeframes=("1d",),
            supports_main_contract=True,
        )
    )
    store = LocalDataStore(base_path=tmp_path, fmt="sqlite")

    result = sync_market_data(
        code="IF.IF",
        start="2024-01-01",
        end="2024-01-31",
        market="futures",
        timeframe="1d",
        store=store,
        source=source,
        incremental=False,
    )

    assert source.main_contract_called is True
    assert result.main_contract == "IF.IF"
