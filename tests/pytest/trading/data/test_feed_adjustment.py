from __future__ import annotations

import pandas as pd

from jwquant.common import config
from jwquant.common.config import Config
from jwquant.trading.data.feed import DataFeed
from jwquant.trading.data.store import LocalDataStore


def test_get_bars_should_include_pre_start_adjust_factor_for_absolute_factor_mode(tmp_path) -> None:
    cfg_file = tmp_path / "adjust_digits.toml"
    cfg_file.write_text("[data.adjust]\nprice_digits = 3\n", encoding="utf-8")
    config.load_config(cfg_file)

    store = LocalDataStore(base_path=tmp_path, fmt="sqlite")
    feed = DataFeed(store=store)

    bars = pd.DataFrame(
        [
            {
                "code": "601006.SH",
                "market": "stock",
                "dt": pd.Timestamp("2022-01-04"),
                "open": 6.40,
                "high": 6.47,
                "low": 6.38,
                "close": 6.46,
                "volume": 40791805.0,
                "amount": 262652631.0,
                "open_interest": 0.0,
            }
        ]
    )
    factors = pd.DataFrame(
        [
            {
                "code": "601006.SH",
                "market": "stock",
                "dt": pd.Timestamp("1900-01-01"),
                "qfq_factor": 2.6440747749844,
                "hfq_factor": 1.0,
            },
            {
                "code": "601006.SH",
                "market": "stock",
                "dt": pd.Timestamp("2021-07-08"),
                "qfq_factor": 1.2850463872839,
                "hfq_factor": 2.0575714629049,
            },
        ]
    )

    store.upsert_bars(code="601006.SH", bars=bars, timeframe="1d", market="stock")
    store.upsert_adjust_factors(code="601006.SH", factors=factors, market="stock")

    qfq_bars = feed.get_bars(
        code="601006.SH",
        start="2022-01-01",
        end="2022-01-31",
        timeframe="1d",
        market="stock",
        adj="qfq",
    )
    hfq_bars = feed.get_bars(
        code="601006.SH",
        start="2022-01-01",
        end="2022-01-31",
        timeframe="1d",
        market="stock",
        adj="hfq",
    )

    assert qfq_bars.iloc[0]["open"] == 4.98
    assert hfq_bars.iloc[0]["open"] == 13.168


def test_price_adjuster_should_allow_configurable_digits_via_env(tmp_path, monkeypatch) -> None:
    cfg_file = tmp_path / "adjust_digits_default.toml"
    cfg_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("JWQUANT_DATA__ADJUST__PRICE_DIGITS", "4")
    config.load_config(cfg_file)

    store = LocalDataStore(base_path=tmp_path / "store", fmt="sqlite")
    feed = DataFeed(store=store)
    bars = pd.DataFrame(
        [
            {
                "code": "601006.SH",
                "market": "stock",
                "dt": pd.Timestamp("2022-01-04"),
                "open": 6.40,
                "high": 6.47,
                "low": 6.38,
                "close": 6.46,
                "volume": 1.0,
                "amount": 1.0,
                "open_interest": 0.0,
            }
        ]
    )
    factors = pd.DataFrame(
        [
            {
                "code": "601006.SH",
                "market": "stock",
                "dt": pd.Timestamp("2021-07-08"),
                "qfq_factor": 1.2850463872839,
                "hfq_factor": 2.0575714629049,
            }
        ]
    )
    store.upsert_bars(code="601006.SH", bars=bars, timeframe="1d", market="stock")
    store.upsert_adjust_factors(code="601006.SH", factors=factors, market="stock")

    qfq_bars = feed.get_bars(
        code="601006.SH",
        start="2022-01-01",
        end="2022-01-31",
        timeframe="1d",
        market="stock",
        adj="qfq",
    )

    assert qfq_bars.iloc[0]["open"] == 4.9804
