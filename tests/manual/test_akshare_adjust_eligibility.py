#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
手动测试：评估 AkShare 的复权口径是否适合进入系统统一准入流程。

测试目标：
1. 下载同一标的、同一区间的 AkShare 与 Baostock 日线
2. 分别对比 none / qfq / hfq 三种口径
3. 输出每种口径的覆盖率、完全一致率、最大差异
4. 产出差异与摘要文件，供阶段四准入评估使用
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


logger = get_logger("test_akshare_adjust_eligibility")

ADJ_MODES = ("none", "qfq", "hfq")
COMPARE_COLUMNS = ["open", "high", "low", "close", "volume", "amount"]
PRICE_COLUMNS = ["open", "high", "low", "close"]
TRADE_COLUMNS = ["volume", "amount"]


class TestAkShareAdjustEligibility(unittest.TestCase):
    """评估 AkShare 不同复权口径与 Baostock 的一致性。"""

    CODE = "601006.SH"
    NAME = "大秦铁路"
    MARKET = "stock"
    TIMEFRAME = "1d"
    START = "2022-01-01"
    END = "2025-12-31"
    REPORT_DIR = Path("reports/manual")

    @classmethod
    def setUpClass(cls) -> None:
        cls.akshare = AkShareDataSource()
        cls.baostock = BaostockDataSource()
        cls.report_dir = cls.REPORT_DIR
        cls.report_dir.mkdir(parents=True, exist_ok=True)

        cls.result_by_adj: dict[str, dict[str, object]] = {}
        summary_rows: list[dict[str, object]] = []

        for adj in ADJ_MODES:
            logger.info(
                "开始评估 AkShare 复权口径: code=%s, start=%s, end=%s, adj=%s",
                cls.CODE,
                cls.START,
                cls.END,
                adj,
            )
            akshare_bars = cls.akshare.download_bars(
                code=cls.CODE,
                start=cls.START,
                end=cls.END,
                timeframe=cls.TIMEFRAME,
                adj=adj,
                market=cls.MARKET,
            )
            baostock_bars = cls.baostock.download_bars(
                code=cls.CODE,
                start=cls.START,
                end=cls.END,
                timeframe=cls.TIMEFRAME,
                adj=adj,
                market=cls.MARKET,
            )

            comparison = cls._build_comparison_frame(akshare_bars, baostock_bars)
            difference_rows = comparison[comparison["has_diff"]].copy()
            akshare_dt_set = set(pd.to_datetime(akshare_bars["dt"]))
            baostock_dt_set = set(pd.to_datetime(baostock_bars["dt"]))
            missing_in_akshare = sorted(baostock_dt_set - akshare_dt_set)
            missing_in_baostock = sorted(akshare_dt_set - baostock_dt_set)

            diff_output = cls.report_dir / f"akshare_adjust_eligibility_{adj}_diff.csv"
            missing_output = cls.report_dir / f"akshare_adjust_eligibility_{adj}_missing_dates.csv"
            cls._write_diff_report(
                diff_output=diff_output,
                missing_output=missing_output,
                difference_rows=difference_rows,
                missing_in_akshare=missing_in_akshare,
                missing_in_baostock=missing_in_baostock,
            )

            summary = cls._build_summary_row(
                adj=adj,
                akshare_bars=akshare_bars,
                baostock_bars=baostock_bars,
                comparison=comparison,
                difference_rows=difference_rows,
                missing_in_akshare=missing_in_akshare,
                missing_in_baostock=missing_in_baostock,
                diff_output=diff_output,
                missing_output=missing_output,
            )
            summary_rows.append(summary)
            cls.result_by_adj[adj] = {
                "akshare_bars": akshare_bars,
                "baostock_bars": baostock_bars,
                "comparison": comparison,
                "difference_rows": difference_rows,
                "missing_in_akshare": missing_in_akshare,
                "missing_in_baostock": missing_in_baostock,
                "summary": summary,
            }

        cls.summary_frame = pd.DataFrame(summary_rows)
        cls.summary_output = cls.report_dir / "akshare_adjust_eligibility_summary.csv"
        cls.summary_frame.to_csv(cls.summary_output, index=False, encoding="utf-8-sig")

    @staticmethod
    def _build_comparison_frame(akshare_bars: pd.DataFrame, baostock_bars: pd.DataFrame) -> pd.DataFrame:
        ak = akshare_bars[["dt", *COMPARE_COLUMNS]].copy()
        ak = ak.rename(columns={column: f"akshare_{column}" for column in COMPARE_COLUMNS})

        bs = baostock_bars[["dt", *COMPARE_COLUMNS]].copy()
        bs = bs.rename(columns={column: f"baostock_{column}" for column in COMPARE_COLUMNS})

        merged = ak.merge(bs, on="dt", how="inner").sort_values("dt").reset_index(drop=True)

        for column in COMPARE_COLUMNS:
            merged[f"diff_{column}"] = (
                merged[f"akshare_{column}"].astype(float) - merged[f"baostock_{column}"].astype(float)
            ).round(6)

        merged["price_match"] = merged[[f"diff_{column}" for column in PRICE_COLUMNS]].abs().eq(0).all(axis=1)
        merged["trade_match"] = merged[[f"diff_{column}" for column in TRADE_COLUMNS]].abs().eq(0).all(axis=1)
        merged["has_diff"] = ~(
            merged[[f"diff_{column}" for column in COMPARE_COLUMNS]].abs().eq(0).all(axis=1)
        )
        merged["max_abs_price_diff"] = merged[[f"diff_{column}" for column in PRICE_COLUMNS]].abs().max(axis=1)
        merged["max_abs_trade_diff"] = merged[[f"diff_{column}" for column in TRADE_COLUMNS]].abs().max(axis=1)
        return merged

    @classmethod
    def _build_summary_row(
        cls,
        *,
        adj: str,
        akshare_bars: pd.DataFrame,
        baostock_bars: pd.DataFrame,
        comparison: pd.DataFrame,
        difference_rows: pd.DataFrame,
        missing_in_akshare: list[pd.Timestamp],
        missing_in_baostock: list[pd.Timestamp],
        diff_output: Path,
        missing_output: Path,
    ) -> dict[str, object]:
        overlap_rows = len(comparison)
        exact_match_rows = overlap_rows - len(difference_rows)
        price_match_rows = int(comparison["price_match"].sum()) if overlap_rows else 0
        trade_match_rows = int(comparison["trade_match"].sum()) if overlap_rows else 0

        exact_match_ratio = round(exact_match_rows / overlap_rows, 6) if overlap_rows else 0.0
        price_match_ratio = round(price_match_rows / overlap_rows, 6) if overlap_rows else 0.0
        trade_match_ratio = round(trade_match_rows / overlap_rows, 6) if overlap_rows else 0.0
        max_abs_price_diff = round(float(comparison["max_abs_price_diff"].max()), 6) if overlap_rows else 0.0
        max_abs_trade_diff = round(float(comparison["max_abs_trade_diff"].max()), 6) if overlap_rows else 0.0

        if exact_match_ratio == 1.0 and not missing_in_akshare and not missing_in_baostock:
            observed_status = "accepted_candidate"
        elif price_match_ratio >= 0.99:
            observed_status = "limited_candidate"
        else:
            observed_status = "rejected_candidate"

        return {
            "code": cls.CODE,
            "name": cls.NAME,
            "adj": adj,
            "start": cls.START,
            "end": cls.END,
            "akshare_rows": len(akshare_bars),
            "baostock_rows": len(baostock_bars),
            "overlap_rows": overlap_rows,
            "exact_match_rows": exact_match_rows,
            "exact_match_ratio": exact_match_ratio,
            "price_match_rows": price_match_rows,
            "price_match_ratio": price_match_ratio,
            "trade_match_rows": trade_match_rows,
            "trade_match_ratio": trade_match_ratio,
            "missing_in_akshare": len(missing_in_akshare),
            "missing_in_baostock": len(missing_in_baostock),
            "max_abs_price_diff": max_abs_price_diff,
            "max_abs_trade_diff": max_abs_trade_diff,
            "observed_status": observed_status,
            "diff_output": str(diff_output),
            "missing_output": str(missing_output),
        }

    @staticmethod
    def _write_diff_report(
        *,
        diff_output: Path,
        missing_output: Path,
        difference_rows: pd.DataFrame,
        missing_in_akshare: list[pd.Timestamp],
        missing_in_baostock: list[pd.Timestamp],
    ) -> None:
        difference_rows.to_csv(diff_output, index=False, encoding="utf-8-sig")
        missing_rows = []
        missing_rows.extend({"source": "akshare", "dt": dt} for dt in missing_in_akshare)
        missing_rows.extend({"source": "baostock", "dt": dt} for dt in missing_in_baostock)
        pd.DataFrame(missing_rows).to_csv(missing_output, index=False, encoding="utf-8-sig")

    def test_all_adjust_modes_should_return_non_empty_bars(self) -> None:
        for adj in ADJ_MODES:
            result = self.result_by_adj[adj]
            self.assertFalse(result["akshare_bars"].empty, f"AkShare {adj} 返回空数据，无法评估")
            self.assertFalse(result["baostock_bars"].empty, f"Baostock {adj} 返回空数据，无法评估")

    def test_all_adjust_modes_should_have_overlap(self) -> None:
        for adj in ADJ_MODES:
            result = self.result_by_adj[adj]
            self.assertGreater(len(result["comparison"]), 0, f"{adj} 口径没有重叠交易日，无法逐日对比")

    def test_print_summary(self) -> None:
        print("\n=== AkShare 复权准入评估摘要 ===")
        print(f"标的: {self.NAME} ({self.CODE})")
        print(f"时间范围: {self.START} ~ {self.END}")
        print(f"汇总文件: {self.summary_output.absolute()}")

        preview = self.summary_frame[
            [
                "adj",
                "akshare_rows",
                "baostock_rows",
                "overlap_rows",
                "exact_match_ratio",
                "price_match_ratio",
                "trade_match_ratio",
                "missing_in_akshare",
                "missing_in_baostock",
                "max_abs_price_diff",
                "max_abs_trade_diff",
                "observed_status",
            ]
        ]
        print(preview.to_string(index=False))

        for adj in ADJ_MODES:
            result = self.result_by_adj[adj]
            difference_rows = result["difference_rows"]
            if difference_rows.empty:
                continue
            print(f"\n--- {adj} 差异样例 Top 10 ---")
            top_diff = difference_rows.nlargest(10, "max_abs_price_diff")[
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
            print(top_diff.to_string(index=False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
