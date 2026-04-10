"""
下载历史行情数据到本地

用法: python scripts/download_data.py --code 000001.SZ --start 2020-01-01
"""
from __future__ import annotations

import argparse
from datetime import datetime

from jwquant.common.config import load_config
from jwquant.trading.data.sources.baostock_src import BaostockDataSource
from jwquant.trading.data.sources.tushare_src import TushareDataSource
from jwquant.trading.data.sources.xtquant_src import XtQuantDataSource
from jwquant.trading.data.store import LocalDataStore
from jwquant.trading.data.sync import sync_market_data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="下载历史行情并写入本地存储")
    parser.add_argument("--code", "-c", required=True, help="代码，如 000001.SZ 或 IF2406.IF")
    parser.add_argument("--start", "-s", required=True, help="开始日期，如 2020-01-01")
    parser.add_argument("--end", "-e", default=datetime.now().strftime("%Y-%m-%d"), help="结束日期")
    parser.add_argument("--source", default="xtquant", choices=["xtquant", "tushare", "baostock"], help="数据源")
    parser.add_argument("--market", default=None, choices=["stock", "futures"], help="市场类型，不传则按代码推断")
    parser.add_argument("--timeframe", "-t", default="1d", help="周期，如 1d/1w/1m")
    parser.add_argument(
        "--adj",
        default="qfq",
        help="兼容保留参数；下载时底层始终落原始行情，复权仅在读取侧动态计算",
    )
    parser.add_argument("--store-format", default=None, help="本地存储格式，默认读取配置")
    parser.add_argument("--store-path", default=None, help="本地存储路径，默认读取配置")
    parser.add_argument(
        "--incremental",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="是否按本地最新时间做增量下载，默认开启",
    )
    return parser


def build_source(name: str):
    if name == "xtquant":
        return XtQuantDataSource()
    if name == "tushare":
        return TushareDataSource()
    if name == "baostock":
        return BaostockDataSource()
    raise ValueError(f"unsupported source: {name}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    load_config()

    source = build_source(args.source)
    store = LocalDataStore(base_path=args.store_path, fmt=args.store_format)
    result = sync_market_data(
        code=args.code,
        start=args.start,
        end=args.end,
        market=args.market,
        timeframe=args.timeframe,
        store=store,
        source=source,
        incremental=args.incremental,
    )
    if result.skipped:
        print(
            f"跳过下载: code={result.code}, market={result.market}, timeframe={result.timeframe}, end={result.end}"
        )
        return
    print(
        f"下载完成: code={result.code}, market={result.market}, timeframe={result.timeframe}, start={result.start}, "
        f"rows={result.rows}, factor_rows={result.factor_rows}, source={args.source}, store={store.fmt}, "
        f"path={store.base_path}, main_contract={result.main_contract or ''}"
    )


if __name__ == "__main__":
    main()
