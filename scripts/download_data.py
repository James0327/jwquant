"""
下载历史行情数据到本地

核心功能：
- 从第三方数据源（xtquant/akshare/tushare/baostock）下载历史K线数据
- 支持股票和期货市场
- 支持多种时间周期 (1d/1w/1m/1h/5m 等)
- 支持按月/季/年分段下载，实现大数据量的断点续传
- 自动写入本地存储（parquet/csv）

用法示例:
  # 下载平安银行 2020年的日线数据
  python scripts/download_data.py --code 000001.SZ --start 2020-01-01 --end 2020-12-31
  
  # 下载IF期货 2024年的日线数据，按天分段并重试
  python scripts/download_data.py --code IF.IF --start 2024-01-01 --source xtquant --window day --chunk-retries 3
  
  # 增量下载：从本地最新时间继续下载
  python scripts/download_data.py --code 000001.SZ --start 2020-01-01 --incremental

下载流程：
  1. 解析命令行参数，构建数据源和本地存储
  2. 按指定时间窗口 (day/month/quarter/year) 分段下载
  3. 每个分段失败时自动重试 (默认2次，间隔1秒)
  4. 成功数据立即写入本地存储
  5. 支持中断后恢复：重新执行时从本地最新时间继续

配置来源：config/settings.common.toml 中的 [data.download] 部分
  - window: 默认分段粒度
  - chunk_retries: 默认重试次数
  - retry_interval: 默认重试间隔
  - resume: 是否默认启用断点续传
"""
from __future__ import annotations

import argparse
from datetime import datetime

from jwquant.common.config import Config, load_config
from jwquant.trading.data.sources.akshare_src import AkShareDataSource
from jwquant.trading.data.sources.baostock_src import BaostockDataSource
from jwquant.trading.data.sources.tushare_src import TushareDataSource
from jwquant.trading.data.sources.xtquant_src import XtQuantDataSource
from jwquant.trading.data.store import LocalDataStore
from jwquant.trading.data.sync import sync_market_data


def load_download_defaults() -> dict[str, object]:
    """读取下载脚本默认配置
    
    从 config/settings.common.toml 的 [data.download] 部分读取下载策略配置。
    这些参数只影响"如何分段执行下载"，不改变数据本身的含义。
    
    配置项说明：
    - window (str): 时间窗口粒度，支持 day/month/quarter/year，决定单次下载的时间范围
      * day: 每次下载1天的数据
      * month: 每次下载1个月的数据（推荐用于日线及以上）
      * quarter: 每次下载1个季度的数据
      * year: 每次下载1年的数据
    - chunk_retries (int): 单个时间分段失败时的最大重试次数，默认2次
    - retry_interval (float): 分段重试之间的等待时间（秒），默认1.0秒
    - resume (bool): 是否启用基于本地最新时间的断点续传功能，默认True
    
    返回值:
      dict[str, object]: 包含上述4个配置项的字典，缺少配置项时抛异常
    """
    config = Config()
    payload = dict(config.get("data.download"))
    return {
        "window": str(payload["window"]),
        "chunk_retries": int(payload["chunk_retries"]),
        "retry_interval": float(payload["retry_interval"]),
        "resume": bool(payload["resume"]),
    }


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器
    
    返回配置好的 ArgumentParser，定义所有支持的命令行选项。
    参数分为两类：
    
    必需参数:
      --code, -c: 代码，如 000001.SZ (股票) 或 IF2406.IF (期货，主力合约后缀00)
      --start, -s: 开始日期，格式 YYYY-MM-DD
    
    可选参数 (基础设置):
      --end, -e: 结束日期，默认当前日期
      --source: 数据源，支持 xtquant/akshare/tushare/baostock，默认 xtquant
      --market: 市场类型，支持 stock/futures，默认根据代码推断
      --timeframe, -t: 时间周期，如 1d/1w/1m/1h/5m，默认 1d
    
    可选参数 (下载策略):
      --window: 分段粒度 (day/month/quarter/year)，默认从配置读取
      --chunk-retries: 分段失败重试次数，默认从配置读取
      --retry-interval: 分段重试间隔秒数，默认从配置读取
      --incremental/--no-incremental: 是否启用增量下载，默认从配置读取
      --resume/--no-resume: 是否启用断点续传，默认从配置读取
    
    可选参数 (存储设置):
      --store-format: 本地存储格式 (parquet/csv)，默认从配置读取
      --store-path: 本地存储路径，默认从配置读取
    
    返回值:
      argparse.ArgumentParser: 配置好的解析器
    """
    defaults = load_download_defaults()
    parser = argparse.ArgumentParser(description="下载历史行情并写入本地存储")
    parser.add_argument("--code", "-c", required=True, help="代码，如 000001.SZ 或 IF2406.IF")
    parser.add_argument("--start", "-s", required=True, help="开始日期，如 2020-01-01")
    parser.add_argument("--end", "-e", default=datetime.now().strftime("%Y-%m-%d"), help="结束日期")
    parser.add_argument("--source", default="xtquant", choices=["xtquant", "akshare", "tushare", "baostock"], help="数据源")
    parser.add_argument("--market", default=None, choices=["stock", "futures"], help="市场类型，不传则按代码推断")
    parser.add_argument("--timeframe", "-t", default="1d", help="周期，如 1d/1w/1m")
    parser.add_argument("--adj", default="none", choices=["none"],
        help="下载脚本默认不复权 adj=none；底层始终落原始行情，qfq/hfq 只在读取侧动态生成")
    parser.add_argument("--store-format", default=None, help="本地存储格式，默认读取配置")
    parser.add_argument("--store-path", default=None, help="本地存储路径，默认读取配置")
    parser.add_argument(
        "--window",
        default=defaults["window"],
        choices=["day", "month", "quarter", "year"],
        help="下载分段窗口；支持按日/月/季度/年分页下载，默认读取配置且默认 month",
    )
    parser.add_argument(
        "--chunk-retries",
        type=int,
        default=defaults["chunk_retries"],
        help="单个时间分段失败时的最大重试次数",
    )
    parser.add_argument(
        "--retry-interval",
        type=float,
        default=defaults["retry_interval"],
        help="单个时间分段重试间隔，单位秒",
    )
    parser.add_argument(
        "--incremental",
        action=argparse.BooleanOptionalAction,
        default=defaults["resume"],
        help="是否按本地最新时间做断点续传式增量下载，默认开启",
    )
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=defaults["resume"],
        help="是否启用断点续传；开启时会从本地最新时间继续下载",
    )
    return parser


def build_source(name: str):
    """根据名称构建数据源对象
    
    参数:
      name (str): 数据源名称，支持：
        - 'xtquant': 讯投(XtQuant)数据源，支持股票和期货，推荐使用
        - 'akshare': AkShare 数据源，主要用于A股历史研究与补数
        - 'tushare': TuShare数据源，主要用于A股数据
        - 'baostock': 宝股数据源，备选方案
    
    返回值:
      BarSource: 初始化的数据源对象
    
    异常:
      ValueError: 当指定的数据源名称不支持时抛出
    """
    if name == "xtquant":
        return XtQuantDataSource()
    if name == "akshare":
        return AkShareDataSource()
    if name == "tushare":
        return TushareDataSource()
    if name == "baostock":
        return BaostockDataSource()
    raise ValueError(f"unsupported source: {name}")


def main() -> None:
    """脚本主入口
    
    执行流程：
    1. 解析命令行参数
    2. 加载分层配置文件 (settings.common.toml + settings.live.toml)
    3. 根据参数构建数据源和本地存储对象
    4. 调用 sync_market_data 执行下载和数据同步
    5. 输出下载结果摘要
    
    退出:
      - 下载成功或跳过时正常退出
      - 下载失败时向下抛出异常
    """
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
        incremental=(args.incremental and args.resume),
        download_window=args.window,
        chunk_retries=args.chunk_retries,
        retry_interval=args.retry_interval,
    )
    if result.skipped:
        print(
            f"跳过下载: code={result.code}, market={result.market}, timeframe={result.timeframe}, end={result.end}"
        )
        return
    print(
        f"下载完成: code={result.code}, market={result.market}, timeframe={result.timeframe}, start={result.start}, "
        f"rows={result.rows}, factor_rows={result.factor_rows}, source={args.source}, store={store.fmt}, "
        f"path={store.base_path}, window={args.window}, chunk_retries={args.chunk_retries}, "
        f"resume={args.incremental and args.resume}, main_contract={result.main_contract or ''}"
    )


if __name__ == "__main__":
    main()
