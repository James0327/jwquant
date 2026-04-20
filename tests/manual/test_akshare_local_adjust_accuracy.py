#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
手动测试：验证 AkShare 原始行情 + 复权因子 计算得到的 qfq，是否与 AkShare 直接返回的 qfq 一致。

测试目标：
1. 下载并落库大秦铁路（601006.SH）2022-01-01 ~ 2025-12-31 的无复权日线
2. 下载对应 AkShare 复权因子
3. 基于“无复权 + 复权因子”计算 qfq
4. 直接从 AkShare 再下载一份 qfq 日线
5. 逐日逐列比对，并保留中间数据用于人工排查
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from jwquant.common.log import get_logger
from jwquant.trading.data.cleaner import PRICE_COLUMNS, PriceAdjuster
from jwquant.trading.data.feed import DataFeed
from jwquant.trading.data.sources.akshare_src import AkShareDataSource
from jwquant.trading.data.store import LocalDataStore
from jwquant.trading.data.sync import sync_market_data


logger = get_logger("test_akshare_local_adjust_accuracy")


class TestAkShareLocalAdjustAccuracy(unittest.TestCase):
    CODE = "601006.SH"
    NAME = "大秦铁路"
    MARKET = "stock"
    TIMEFRAME = "1d"
    START = "2022-01-01"
    END = "2025-12-31"
    OUTPUT_DIR = Path("reports/manual/akshare_local_adjust_accuracy")
    STORE_DIR = OUTPUT_DIR / "store"
    STORE_FORMAT = "sqlite"
    ADJ_MODES = ("qfq",)

    @classmethod
    def setUpClass(cls) -> None:
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls._cleanup_legacy_outputs()
        cls.store = LocalDataStore(base_path=cls.STORE_DIR, fmt=cls.STORE_FORMAT)
        cls.feed = DataFeed(store=cls.store)
        cls.source = AkShareDataSource()
        cls.adjuster = PriceAdjuster()

        logger.info(
            "开始准备 AkShare 本地复权验证数据: code=%s, start=%s, end=%s, store=%s",
            cls.CODE,
            cls.START,
            cls.END,
            cls.STORE_DIR,
        )

        cls.sync_result = sync_market_data(
            code=cls.CODE,
            start=cls.START,
            end=cls.END,
            market=cls.MARKET,
            timeframe=cls.TIMEFRAME,
            store=cls.store,
            source=cls.source,
            incremental=False,
            download_window="year",
            chunk_retries=2,
            retry_interval=1.0,
        )

        cls.raw_bars = cls.feed.get_bars(
            code=cls.CODE,
            start=cls.START,
            end=cls.END,
            timeframe=cls.TIMEFRAME,
            market=cls.MARKET,
            adj="none",
        )
        cls.factors = cls.feed.get_adjust_factors(
            code=cls.CODE,
            start=None,
            end=cls.END,
            market=cls.MARKET,
        )
        cls._write_base_outputs()
        cls.results = {}
        for adj in cls.ADJ_MODES:
            cls.results[adj] = cls._prepare_adj_result(adj)

    @classmethod
    def _cleanup_legacy_outputs(cls) -> None:
        for path in cls.OUTPUT_DIR.glob("*hfq*.csv"):
            if path.is_file():
                path.unlink()

    @classmethod
    def _write_base_outputs(cls) -> None:
        cls.raw_bars.to_csv(cls.OUTPUT_DIR / "raw_none_bars.csv", index=False, encoding="utf-8-sig")
        cls.factors.to_csv(cls.OUTPUT_DIR / "adjust_factors.csv", index=False, encoding="utf-8-sig")

    @classmethod
    def _prepare_adj_result(cls, adj: str) -> dict[str, object]:
        calculated = cls.adjuster.adjust(cls.raw_bars, cls.factors, adj=adj)
        direct = cls.source.download_bars(
            code=cls.CODE,
            start=cls.START,
            end=cls.END,
            timeframe=cls.TIMEFRAME,
            market=cls.MARKET,
            adj=adj,
        )
        feed_bars = cls.feed.get_bars(
            code=cls.CODE,
            start=cls.START,
            end=cls.END,
            timeframe=cls.TIMEFRAME,
            market=cls.MARKET,
            adj=adj,
        )
        export_calculated = cls._round_price_columns(calculated, digits=2)
        export_feed_bars = cls._round_price_columns(feed_bars, digits=2)
        calculated.to_csv(cls.OUTPUT_DIR / f"calculated_{adj}_bars.csv", index=False, encoding="utf-8-sig")
        direct.to_csv(cls.OUTPUT_DIR / f"direct_{adj}_bars.csv", index=False, encoding="utf-8-sig")
        export_calculated.to_csv(
            cls.OUTPUT_DIR / f"calculated_{adj}_bars_2dp.csv",
            index=False,
            encoding="utf-8-sig",
        )
        export_feed_bars.to_csv(cls.OUTPUT_DIR / f"feed_{adj}_bars.csv", index=False, encoding="utf-8-sig")

        calculated_dt_set = set(pd.to_datetime(calculated["dt"]))
        direct_dt_set = set(pd.to_datetime(direct["dt"]))
        feed_dt_set = set(pd.to_datetime(feed_bars["dt"]))
        missing_in_direct = sorted(calculated_dt_set - direct_dt_set)
        missing_in_calculated = sorted(direct_dt_set - calculated_dt_set)
        missing_in_feed = sorted(direct_dt_set - feed_dt_set)

        comparison = cls._build_comparison_frame(
            calculated=calculated,
            direct=direct,
            feed_bars=feed_bars,
        )
        difference_rows = comparison[~comparison["within_direct_tolerance"]].copy()
        comparison.to_csv(cls.OUTPUT_DIR / f"comparison_{adj}.csv", index=False, encoding="utf-8-sig")
        difference_rows.to_csv(cls.OUTPUT_DIR / f"diff_{adj}.csv", index=False, encoding="utf-8-sig")
        pd.DataFrame(
            [
                {"source": "direct", "dt": dt} for dt in missing_in_direct
            ]
            + [{"source": "calculated", "dt": dt} for dt in missing_in_calculated]
            + [{"source": "feed", "dt": dt} for dt in missing_in_feed]
        ).to_csv(cls.OUTPUT_DIR / f"missing_dates_{adj}.csv", index=False, encoding="utf-8-sig")

        return {
            "calculated": calculated,
            "direct": direct,
            "feed_bars": feed_bars,
            "export_calculated": export_calculated,
            "export_feed_bars": export_feed_bars,
            "comparison": comparison,
            "difference_rows": difference_rows,
            "missing_in_direct": missing_in_direct,
            "missing_in_calculated": missing_in_calculated,
            "missing_in_feed": missing_in_feed,
        }

    @staticmethod
    def _round_price_columns(frame: pd.DataFrame, *, digits: int) -> pd.DataFrame:
        rounded = frame.copy()
        for column in PRICE_COLUMNS:
            rounded[column] = rounded[column].astype(float).round(digits)
        return rounded

    @classmethod
    def _build_comparison_frame(
        cls,
        *,
        calculated: pd.DataFrame,
        direct: pd.DataFrame,
        feed_bars: pd.DataFrame,
    ) -> pd.DataFrame:
        raw = cls.raw_bars[["dt", *PRICE_COLUMNS]].copy()
        raw = raw.rename(columns={column: f"raw_{column}" for column in PRICE_COLUMNS})
        calculated = calculated[["dt", *PRICE_COLUMNS]].copy()
        calculated = calculated.rename(columns={column: f"calc_{column}" for column in PRICE_COLUMNS})
        direct = direct[["dt", *PRICE_COLUMNS]].copy()
        direct = direct.rename(columns={column: f"direct_{column}" for column in PRICE_COLUMNS})
        feed_bars = feed_bars[["dt", *PRICE_COLUMNS]].copy()
        feed_bars = feed_bars.rename(columns={column: f"feed_{column}" for column in PRICE_COLUMNS})

        merged = raw.merge(calculated, on="dt", how="inner")
        merged = merged.merge(direct, on="dt", how="inner")
        merged = merged.merge(feed_bars, on="dt", how="inner")
        merged = merged.sort_values("dt").reset_index(drop=True)

        for column in PRICE_COLUMNS:
            merged[f"diff_{column}"] = (
                merged[f"calc_{column}"].astype(float) - merged[f"direct_{column}"].astype(float)
            ).round(6)
            merged[f"feed_diff_{column}"] = (
                merged[f"feed_{column}"].astype(float) - merged[f"direct_{column}"].astype(float)
            ).round(6)
            merged[f"calc_{column}_2dp"] = merged[f"calc_{column}"].astype(float).round(2)
            merged[f"feed_{column}_2dp"] = merged[f"feed_{column}"].astype(float).round(2)
            merged[f"direct_{column}_2dp"] = merged[f"direct_{column}"].astype(float).round(2)
            merged[f"round_diff_{column}"] = (
                merged[f"calc_{column}_2dp"] - merged[f"direct_{column}_2dp"]
            ).round(2)

        diff_columns = [f"diff_{column}" for column in PRICE_COLUMNS]
        feed_diff_columns = [f"feed_diff_{column}" for column in PRICE_COLUMNS]
        merged["within_direct_tolerance"] = merged[diff_columns].abs().le(0.005).all(axis=1)
        merged["has_diff"] = (
            merged[diff_columns].abs().gt(0).any(axis=1)
            | merged[feed_diff_columns].abs().gt(0).any(axis=1)
        )
        merged["max_abs_diff"] = merged[diff_columns].abs().max(axis=1)
        return merged

    def test_sync_download_should_persist_raw_bars_and_factors(self) -> None:
        self.assertFalse(self.raw_bars.empty, "AkShare 无复权原始行情为空，说明下载或落库失败")
        self.assertFalse(self.factors.empty, "AkShare 复权因子为空，无法验证本地 qfq 准确性")

    def test_feed_adjusted_should_equal_manual_adjustment(self) -> None:
        for adj, result in self.results.items():
            with self.subTest(adj=adj):
                pd.testing.assert_frame_equal(
                    result["calculated"][["dt", *PRICE_COLUMNS]].reset_index(drop=True),
                    result["feed_bars"][["dt", *PRICE_COLUMNS]].reset_index(drop=True),
                    check_dtype=False,
                    check_exact=True,
                )

    def test_adjusted_date_sets_should_match(self) -> None:
        for adj, result in self.results.items():
            with self.subTest(adj=adj):
                self.assertEqual(result["missing_in_direct"], [])
                self.assertEqual(result["missing_in_calculated"], [])
                self.assertEqual(result["missing_in_feed"], [])

    def test_manual_adjusted_should_equal_direct_adjusted(self) -> None:
        for adj, result in self.results.items():
            with self.subTest(adj=adj):
                mismatch_count = int((~result["comparison"]["within_direct_tolerance"]).sum())
                self.assertEqual(
                    mismatch_count,
                    0,
                    f"发现 {mismatch_count} 条 {adj} 超出 0.005 容差的差异，请检查 {self.OUTPUT_DIR / f'diff_{adj}.csv'}",
                )

    def test_print_summary(self) -> None:
        print("\n=== AkShare 本地复权准确性验证摘要 ===")
        print(f"标的: {self.NAME} ({self.CODE})")
        print(f"时间范围: {self.START} ~ {self.END}")
        print(f"原始行情条数: {len(self.raw_bars)}")
        print(f"复权因子条数: {len(self.factors)}")
        print(f"中间文件目录: {self.OUTPUT_DIR.resolve()}")
        for adj, result in self.results.items():
            print(f"\n[{adj}]")
            print(f"本地计算条数: {len(result['calculated'])}")
            print(f"直下复权条数: {len(result['direct'])}")
            print(f"差异条数: {len(result['difference_rows'])}")
            print(f"容差内匹配率(<=0.005): {result['comparison']['within_direct_tolerance'].mean():.4%}")
            print(f"最大绝对价差: {result['comparison']['max_abs_diff'].max():.6f}")
            print(f"直下缺失日期数: {len(result['missing_in_direct'])}")
            print(f"本地计算缺失日期数: {len(result['missing_in_calculated'])}")
            print(f"DataFeed 缺失日期数: {len(result['missing_in_feed'])}")
            print(f"真正差异文件: {self.OUTPUT_DIR / f'diff_{adj}.csv'}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
