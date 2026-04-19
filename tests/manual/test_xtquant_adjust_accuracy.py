#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
手动测试：验证 XtQuant 原始行情 + 复权因子 计算得到的前复权，是否与 XtQuant 直接返回的前复权完全一致。

测试目标：
1. 下载并落库大秦铁路（601006.SH）2022-01-01 ~ 2025-12-31 的无复权日线
2. 下载对应复权因子
3. 基于“无复权 + 复权因子”计算前复权
4. 直接从 XtQuant 再下载一份前复权日线
5. 逐日逐列比对，输出差异明细
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from jwquant.common.log import get_logger
from jwquant.trading.data.cleaner import PRICE_COLUMNS, PriceAdjuster
from jwquant.trading.data.feed import DataFeed
from jwquant.trading.data.sources.xtquant_src import XtQuantDataSource
from jwquant.trading.data.store import LocalDataStore
from jwquant.trading.data.sync import sync_xtquant_data


logger = get_logger("test_xtquant_adjust_accuracy")


class TestXtQuantAdjustAccuracy(unittest.TestCase):
    """验证券商无复权数据经复权因子计算后的前复权，与券商直下前复权是否一致。"""

    CODE = "601006.SH"
    NAME = "大秦铁路"
    MARKET = "stock"
    TIMEFRAME = "1d"
    START = "2022-01-01"
    END = "2025-12-31"
    STORE_FORMAT = "sqlite"
    DIFF_OUTPUT = Path("reports/manual/xtquant_adjust_accuracy_diff.csv")
    MISSING_DT_OUTPUT = Path("reports/manual/xtquant_adjust_accuracy_missing_dates.csv")

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory(prefix="jwquant_xtquant_adjust_")
        cls.store = LocalDataStore(base_path=cls.temp_dir.name, fmt=cls.STORE_FORMAT)
        cls.feed = DataFeed(store=cls.store)
        cls.source = XtQuantDataSource()
        cls.adjuster = PriceAdjuster()

        logger.info(
            "开始准备测试数据: code=%s, start=%s, end=%s, store=%s",
            cls.CODE,
            cls.START,
            cls.END,
            cls.temp_dir.name,
        )

        cls.sync_result = sync_xtquant_data(
            code=cls.CODE,
            start=cls.START,
            end=cls.END,
            market=cls.MARKET,
            timeframe=cls.TIMEFRAME,
            store=cls.store,
            source=cls.source,
            incremental=False,
            download_window="month",
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
            start=cls.START,
            end=cls.END,
            market=cls.MARKET,
        )
        cls.calculated_qfq = cls.adjuster.adjust(cls.raw_bars, cls.factors, adj="qfq")
        cls.feed_qfq = cls.feed.get_bars(
            code=cls.CODE,
            start=cls.START,
            end=cls.END,
            timeframe=cls.TIMEFRAME,
            market=cls.MARKET,
            adj="qfq",
        )
        cls.broker_qfq = cls.source.download_bars(
            code=cls.CODE,
            start=cls.START,
            end=cls.END,
            timeframe=cls.TIMEFRAME,
            market=cls.MARKET,
            adj="qfq",
        )
        cls.calculated_dt_set = set(pd.to_datetime(cls.calculated_qfq["dt"]))
        cls.feed_dt_set = set(pd.to_datetime(cls.feed_qfq["dt"]))
        cls.broker_dt_set = set(pd.to_datetime(cls.broker_qfq["dt"]))
        cls.missing_in_broker = sorted(cls.calculated_dt_set - cls.broker_dt_set)
        cls.missing_in_calculated = sorted(cls.broker_dt_set - cls.calculated_dt_set)
        cls.missing_in_feed = sorted(cls.broker_dt_set - cls.feed_dt_set)
        cls.comparison = cls._build_comparison_frame()
        cls.difference_rows = cls.comparison[cls.comparison["has_diff"]].copy()
        cls._write_diff_report()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    @classmethod
    def _build_comparison_frame(cls) -> pd.DataFrame:
        calculated = cls.calculated_qfq[["dt", *PRICE_COLUMNS]].copy()
        calculated = calculated.rename(columns={column: f"calc_{column}" for column in PRICE_COLUMNS})

        broker = cls.broker_qfq[["dt", *PRICE_COLUMNS]].copy()
        broker = broker.rename(columns={column: f"broker_{column}" for column in PRICE_COLUMNS})

        feed_qfq = cls.feed_qfq[["dt", *PRICE_COLUMNS]].copy()
        feed_qfq = feed_qfq.rename(columns={column: f"feed_{column}" for column in PRICE_COLUMNS})

        raw = cls.raw_bars[["dt", *PRICE_COLUMNS]].copy()
        raw = raw.rename(columns={column: f"raw_{column}" for column in PRICE_COLUMNS})

        merged = raw.merge(calculated, on="dt", how="inner")
        merged = merged.merge(feed_qfq, on="dt", how="inner")
        merged = merged.merge(broker, on="dt", how="inner")
        merged = merged.sort_values("dt").reset_index(drop=True)

        for column in PRICE_COLUMNS:
            merged[f"diff_{column}"] = (
                merged[f"calc_{column}"].astype(float) - merged[f"broker_{column}"].astype(float)
            ).round(6)
            merged[f"feed_diff_{column}"] = (
                merged[f"feed_{column}"].astype(float) - merged[f"broker_{column}"].astype(float)
            ).round(6)

        diff_columns = [f"diff_{column}" for column in PRICE_COLUMNS]
        feed_diff_columns = [f"feed_diff_{column}" for column in PRICE_COLUMNS]
        merged["has_diff"] = (
            merged[diff_columns].abs().gt(0).any(axis=1)
            | merged[feed_diff_columns].abs().gt(0).any(axis=1)
        )
        merged["max_abs_diff"] = merged[diff_columns].abs().max(axis=1)
        merged["max_abs_feed_diff"] = merged[feed_diff_columns].abs().max(axis=1)
        return merged

    @classmethod
    def _write_diff_report(cls) -> None:
        cls.DIFF_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        cls.difference_rows.to_csv(cls.DIFF_OUTPUT, index=False, encoding="utf-8-sig")
        missing_rows = []
        missing_rows.extend({"source": "broker_qfq", "dt": dt} for dt in cls.missing_in_broker)
        missing_rows.extend({"source": "calculated_qfq", "dt": dt} for dt in cls.missing_in_calculated)
        missing_rows.extend({"source": "feed_qfq", "dt": dt} for dt in cls.missing_in_feed)
        pd.DataFrame(missing_rows).to_csv(cls.MISSING_DT_OUTPUT, index=False, encoding="utf-8-sig")

    def test_sync_download_should_persist_raw_bars_and_factors(self) -> None:
        self.assertFalse(self.raw_bars.empty, "无复权原始行情为空，说明下载或落库失败")
        self.assertFalse(self.factors.empty, "复权因子为空，无法验证前复权准确性")
        self.assertGreater(len(self.raw_bars), 0)
        self.assertGreater(len(self.factors), 0)

    def test_feed_qfq_should_equal_manual_adjustment(self) -> None:
        pd.testing.assert_frame_equal(
            self.calculated_qfq[["dt", *PRICE_COLUMNS]].reset_index(drop=True),
            self.feed_qfq[["dt", *PRICE_COLUMNS]].reset_index(drop=True),
            check_dtype=False,
            check_exact=True,
        )

    def test_qfq_date_sets_should_match(self) -> None:
        self.assertEqual(
            self.missing_in_broker,
            [],
            f"手工计算前复权中存在券商前复权缺失日期，详见 {self.MISSING_DT_OUTPUT.absolute()}",
        )
        self.assertEqual(
            self.missing_in_calculated,
            [],
            f"券商前复权中存在手工计算前复权缺失日期，详见 {self.MISSING_DT_OUTPUT.absolute()}",
        )
        self.assertEqual(
            self.missing_in_feed,
            [],
            f"DataFeed 前复权中存在券商前复权缺失日期，详见 {self.MISSING_DT_OUTPUT.absolute()}",
        )

    def test_manual_adjusted_qfq_should_equal_broker_qfq(self) -> None:
        mismatch_count = len(self.difference_rows)
        if mismatch_count:
            preview = self.difference_rows[
                [
                    "dt",
                    "raw_close",
                    "calc_close",
                    "broker_close",
                    "diff_close",
                    "calc_open",
                    "broker_open",
                    "diff_open",
                    "calc_high",
                    "broker_high",
                    "diff_high",
                    "calc_low",
                    "broker_low",
                    "diff_low",
                ]
            ].head(20)
            logger.error("发现 %s 条前复权差异，样例:\n%s", mismatch_count, preview.to_string(index=False))

        self.assertEqual(
            mismatch_count,
            0,
            (
                f"发现 {mismatch_count} 条前复权差异，"
                f"差异明细已输出到 {self.DIFF_OUTPUT.absolute()}"
            ),
        )

    def test_print_summary(self) -> None:
        print("\n=== XtQuant 前复权准确性验证摘要 ===")
        print(f"标的: {self.NAME} ({self.CODE})")
        print(f"时间范围: {self.START} ~ {self.END}")
        print(f"原始行情条数: {len(self.raw_bars)}")
        print(f"复权因子条数: {len(self.factors)}")
        print(f"手工计算前复权条数: {len(self.calculated_qfq)}")
        print(f"券商直下前复权条数: {len(self.broker_qfq)}")
        print(f"差异条数: {len(self.difference_rows)}")
        print(f"券商缺失日期数: {len(self.missing_in_broker)}")
        print(f"手工计算缺失日期数: {len(self.missing_in_calculated)}")
        print(f"DataFeed 缺失日期数: {len(self.missing_in_feed)}")
        if not self.difference_rows.empty:
            print(f"差异文件: {self.DIFF_OUTPUT.absolute()}")
            top_diff = self.difference_rows.nlargest(10, "max_abs_diff")[
                ["dt", "max_abs_diff", "diff_open", "diff_high", "diff_low", "diff_close"]
            ]
            print("最大差异样例:")
            print(top_diff.to_string(index=False))
        if self.missing_in_broker or self.missing_in_calculated or self.missing_in_feed:
            print(f"缺失日期文件: {self.MISSING_DT_OUTPUT.absolute()}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
