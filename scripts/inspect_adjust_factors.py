"""
检查本地复权因子与原始行情

示例:
python scripts/inspect_adjust_factors.py --code 000001.SZ --start 2024-01-01 --end 2024-12-31
"""
from __future__ import annotations

import argparse

from jwquant.trading.data.feed import DataFeed


def main() -> None:
    parser = argparse.ArgumentParser(description="检查本地原始行情与复权因子")
    parser.add_argument("--code", "-c", required=True, help="股票代码，如 000001.SZ")
    parser.add_argument("--start", required=True, help="开始日期")
    parser.add_argument("--end", required=True, help="结束日期")
    args = parser.parse_args()

    feed = DataFeed()
    raw_bars = feed.get_bars(args.code, start=args.start, end=args.end, market="stock", adj="none")
    qfq_bars = feed.get_bars(args.code, start=args.start, end=args.end, market="stock", adj="qfq")
    factors = feed.get_adjust_factors(args.code, start=args.start, end=args.end, market="stock")

    print("=" * 60)
    print(f"代码: {args.code}")
    print(f"原始行情条数: {len(raw_bars)}")
    print(f"复权因子条数: {len(factors)}")
    print("=" * 60)

    if not factors.empty:
        print("最近复权因子:")
        print(factors.tail(5).to_string(index=False))
    else:
        print("未找到复权因子")

    if not raw_bars.empty and not qfq_bars.empty:
        merged = raw_bars[["dt", "close"]].rename(columns={"close": "raw_close"}).merge(
            qfq_bars[["dt", "close"]].rename(columns={"close": "qfq_close"}),
            on="dt",
            how="left",
        )
        print("最近价格对比:")
        print(merged.tail(10).to_string(index=False))


if __name__ == "__main__":
    main()
