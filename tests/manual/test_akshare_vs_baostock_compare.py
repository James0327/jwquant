#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
手动测试：对比 AkShare 与 Baostock 的股票历史日线数据差异。

测试目标：
1. 下载并标准化同一标的、同一区间的 AkShare 与 Baostock 日线
2. 对比日期覆盖、OHLC、成交量、成交额差异
3. 输出差异明细与缺失日期清单，作为后续数据源准入依据
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from jwquant.common.log import get_logger
from jwquant.trading.data.sources.akshare_src import AkShareDataSource
from jwquant.trading.data.sources.baostock_src import BaostockDataSource


logger = get_logger("test_akshare_vs_baostock_compare")

COMPARE_COLUMNS = ["open", "high", "low", "close", "volume", "amount"]


class TestAkShareVsBaostockCompare(unittest.TestCase):
    """对比 AkShare 与 Baostock 的原始日线行情差异。"""

    CODE = "601006.SH"
    NAME = "大秦铁路"
    MARKET = "stock"
    TIMEFRAME = "1d"
    ADJ = "none"
    START = "2022-01-01"
    END = "2025-12-31"
    DIFF_OUTPUT = Path("reports/manual/akshare_vs_baostock_diff.csv")
    MISSING_DT_OUTPUT = Path("reports/manual/akshare_vs_baostock_missing_dates.csv")
    SUMMARY_OUTPUT = Path("reports/manual/akshare_vs_baostock_summary.csv")

    @classmethod
    def setUpClass(cls) -> None:
        cls.akshare = AkShareDataSource()
        cls.baostock = BaostockDataSource()

        logger.info(
            "开始对比 AkShare 与 Baostock: code=%s, start=%s, end=%s, adj=%s",
            cls.CODE,
            cls.START,
            cls.END,
            cls.ADJ,
        )

        cls.akshare_bars = cls.akshare.download_bars(
            code=cls.CODE,
            start=cls.START,
            end=cls.END,
            timeframe=cls.TIMEFRAME,
            adj=cls.ADJ,
            market=cls.MARKET,
        )
        cls.baostock_bars = cls.baostock.download_bars(
            code=cls.CODE,
            start=cls.START,
            end=cls.END,
            timeframe=cls.TIMEFRAME,
            adj=cls.ADJ,
            market=cls.MARKET,
        )

        cls.akshare_dt_set = set(pd.to_datetime(cls.akshare_bars["dt"]))
        cls.baostock_dt_set = set(pd.to_datetime(cls.baostock_bars["dt"]))
        cls.missing_in_akshare = sorted(cls.baostock_dt_set - cls.akshare_dt_set)
        cls.missing_in_baostock = sorted(cls.akshare_dt_set - cls.baostock_dt_set)
        cls.comparison = cls._build_comparison_frame()
        cls.difference_rows = cls.comparison[cls.comparison["has_diff"]].copy()
        cls.summary_frame = cls._build_summary_frame()
        cls._write_reports()

    @classmethod
    def _build_comparison_frame(cls) -> pd.DataFrame:
        ak = cls.akshare_bars[["dt", *COMPARE_COLUMNS]].copy()
        ak = ak.rename(columns={column: f"akshare_{column}" for column in COMPARE_COLUMNS})

        bs = cls.baostock_bars[["dt", *COMPARE_COLUMNS]].copy()
        bs = bs.rename(columns={column: f"baostock_{column}" for column in COMPARE_COLUMNS})

        merged = ak.merge(bs, on="dt", how="inner").sort_values("dt").reset_index(drop=True)

        diff_columns: list[str] = []
        for column in COMPARE_COLUMNS:
            diff_column = f"diff_{column}"
            merged[diff_column] = (
                merged[f"akshare_{column}"].astype(float) - merged[f"baostock_{column}"].astype(float)
            ).round(6)
            diff_columns.append(diff_column)

        merged["has_diff"] = merged[diff_columns].abs().gt(0).any(axis=1)
        merged["max_abs_price_diff"] = merged[[f"diff_{column}" for column in ["open", "high", "low", "close"]]].abs().max(axis=1)
        merged["max_abs_trade_diff"] = merged[[f"diff_{column}" for column in ["volume", "amount"]]].abs().max(axis=1)
        return merged

    @classmethod
    def _build_summary_frame(cls) -> pd.DataFrame:
        overlap_count = len(cls.comparison)
        diff_count = len(cls.difference_rows)
        exact_match_count = overlap_count - diff_count
        price_match_count = int(
            cls.comparison[[f"diff_{column}" for column in ["open", "high", "low", "close"]]].abs().eq(0).all(axis=1).sum()
        )
        volume_amount_match_count = int(
            cls.comparison[[f"diff_{column}" for column in ["volume", "amount"]]].abs().eq(0).all(axis=1).sum()
        )

        summary = {
            "code": cls.CODE,
            "name": cls.NAME,
            "start": cls.START,
            "end": cls.END,
            "adj": cls.ADJ,
            "akshare_rows": len(cls.akshare_bars),
            "baostock_rows": len(cls.baostock_bars),
            "overlap_rows": overlap_count,
            "exact_match_rows": exact_match_count,
            "exact_match_ratio": round((exact_match_count / overlap_count), 6) if overlap_count else 0.0,
            "price_match_rows": price_match_count,
            "price_match_ratio": round((price_match_count / overlap_count), 6) if overlap_count else 0.0,
            "volume_amount_match_rows": volume_amount_match_count,
            "volume_amount_match_ratio": round((volume_amount_match_count / overlap_count), 6) if overlap_count else 0.0,
            "missing_in_akshare": len(cls.missing_in_akshare),
            "missing_in_baostock": len(cls.missing_in_baostock),
            "max_abs_price_diff": round(float(cls.comparison["max_abs_price_diff"].max()), 6) if overlap_count else 0.0,
            "max_abs_trade_diff": round(float(cls.comparison["max_abs_trade_diff"].max()), 6) if overlap_count else 0.0,
        }
        return pd.DataFrame([summary])

    @classmethod
    def _write_reports(cls) -> None:
        cls.DIFF_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        cls.difference_rows.to_csv(cls.DIFF_OUTPUT, index=False, encoding="utf-8-sig")
        missing_rows = []
        missing_rows.extend({"source": "akshare", "dt": dt} for dt in cls.missing_in_akshare)
        missing_rows.extend({"source": "baostock", "dt": dt} for dt in cls.missing_in_baostock)
        pd.DataFrame(missing_rows).to_csv(cls.MISSING_DT_OUTPUT, index=False, encoding="utf-8-sig")
        cls.summary_frame.to_csv(cls.SUMMARY_OUTPUT, index=False, encoding="utf-8-sig")

    def test_download_should_return_non_empty_bars(self) -> None:
        self.assertFalse(self.akshare_bars.empty, "AkShare 返回空数据，无法进行对账")
        self.assertFalse(self.baostock_bars.empty, "Baostock 返回空数据，无法进行对账")

    def test_compare_should_produce_overlap(self) -> None:
        self.assertGreater(len(self.comparison), 0, "两数据源没有重叠交易日，无法进行逐日对比")

    def test_print_summary(self) -> None:
        summary = self.summary_frame.iloc[0]
        print("\n=== AkShare vs Baostock 对账摘要 ===")
        print(f"标的: {self.NAME} ({self.CODE})")
        print(f"时间范围: {self.START} ~ {self.END}")
        print(f"AkShare 条数: {int(summary['akshare_rows'])}")
        print(f"Baostock 条数: {int(summary['baostock_rows'])}")
        print(f"重叠日期条数: {int(summary['overlap_rows'])}")
        print(f"完全一致条数: {int(summary['exact_match_rows'])}")
        print(f"完全一致占比: {summary['exact_match_ratio']}")
        print(f"价格完全一致条数: {int(summary['price_match_rows'])}")
        print(f"价格完全一致占比: {summary['price_match_ratio']}")
        print(f"量额完全一致条数: {int(summary['volume_amount_match_rows'])}")
        print(f"量额完全一致占比: {summary['volume_amount_match_ratio']}")
        print(f"AkShare 缺失日期数: {int(summary['missing_in_akshare'])}")
        print(f"Baostock 缺失日期数: {int(summary['missing_in_baostock'])}")
        print(f"最大价格绝对差: {summary['max_abs_price_diff']}")
        print(f"最大量额绝对差: {summary['max_abs_trade_diff']}")
        print(f"差异文件: {self.DIFF_OUTPUT.absolute()}")
        print(f"缺失日期文件: {self.MISSING_DT_OUTPUT.absolute()}")
        print(f"汇总文件: {self.SUMMARY_OUTPUT.absolute()}")

        if not self.difference_rows.empty:
            preview = self.difference_rows.nlargest(10, "max_abs_price_diff")[
                [
                    "dt",
                    "akshare_open",
                    "baostock_open",
                    "diff_open",
                    "akshare_close",
                    "baostock_close",
                    "diff_close",
                    "diff_volume",
                    "diff_amount",
                ]
            ]
            print("价格差异 Top 10 样例:")
            print(preview.to_string(index=False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
