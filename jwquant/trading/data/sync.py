"""
数据同步

核心职责：将第三方数据源的行情数据和复权因子同步到本地存储，提供断点续传支持。

主要功能：
1. 支持多个数据源（xtquant/tushare/baostock）
2. 支持股票和期货市场
3. 支持多种时间周期（日/周/月线，分钟线等）
4. 按时间窗口分段下载（天/月/季度/年），便于大数据量下载和断点续传
5. 窗口级重试机制，提高下载稳定性
6. 增量更新模式，避免重复下载已存在数据
7. 自动处理复权因子（仅A股）
8. 期货主力合约追踪

核心流程：
  iter_download_windows()
    ↓ 按时间窗口分段
  sync_market_data() / sync_xtquant_data()
    ↓ 逐个窗口下载和重试
  store.upsert_bars() / store.upsert_adjust_factors()
    ↓ 实时写入本地存储
"""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Protocol, runtime_checkable

import pandas as pd

from jwquant.trading.data.sources.xtquant_src import XtQuantDataSource
from jwquant.trading.data.store import LocalDataStore


@dataclass
class SyncResult:
    """数据同步结果对象
    
    存储单次同步操作的结果摘要，用于上层判断是否成功及统计数据量。
    
    属性说明：
      code (str): 证券代码，如 000001.SZ 或 IF2406.IF
      market (str): 规范化后的市场标识，stock 或 futures
      timeframe (str): 时间周期，如 1d/5m
      start (str): 实际开始下载的时间（若启用 incremental，可能与请求不同）
      end (str): 结束下载时间
      rows (int): 新写入的K线数据行数
      factor_rows (int): 新写入的复权因子行数（仅A股，期货为0）
      skipped (bool): 是否跳过下载。当本地已有比 end 更新的数据时为 True
      main_contract (str | None): 期货主力合约代码。仅在 market=futures 且
                                 数据源支持时填充，如 IF2406
    
    使用示例：
      result = sync_market_data(...)
      if result.skipped:
          print(f"数据已最新，跳过下载")
      else:
          print(f"新增 {result.rows} 条K线，{result.factor_rows} 条复权因子")
    """


@runtime_checkable
class BarSource(Protocol):
    def download_bars(
        self,
        code: str,
        start: str,
        end: str | None = None,
        timeframe: str = "1d",
        adj: str | None = None,
        market: str | None = None,
    ) -> pd.DataFrame: ...


DownloadWindow = str


def next_download_start(latest_dt: pd.Timestamp, timeframe: str) -> str:
    """根据最新时间戳和周期推断下次下载的起点

    用于增量下载场景。当启用 incremental=True 时，本系统会查询本地最新数据时间，
    然后调用此函数计算下次应从何处开始下载，以避免重复下载。

    参数说明：
      latest_dt (pd.Timestamp): 本地存储中最新的数据时间戳
      timeframe (str): 时间周期，如 1d/5m/1h 等

    返回值：
      str: 下次应开始下载的时间，格式与 timeframe 匹配：
        - 对于日线及以上（1d/1w/1m）：返回 YYYY-MM-DD 格式的下一天
        - 对于分钟线（1m/5m/15m/30m/60m）：返回 YYYY-MM-DD HH:MM:SS 格式的下一秒

    设计理由：
      - 日线：最新数据时间为 2024-01-15，则返回 2024-01-16
        这样重新调用时不会下载已有的 2024-01-15 收盘数据
      - 分钟线：最新数据时间为 2024-01-15 14:30:00，则返回 2024-01-15 14:30:01
        这样重新调用时从下一秒继续下载

    示例：
      # 日线增量下载
      latest = pd.Timestamp('2024-01-15')
      next_start = next_download_start(latest, '1d')
      # 返回 '2024-01-16'

      # 分钟线增量下载
      latest = pd.Timestamp('2024-01-15 14:30:00')
      next_start = next_download_start(latest, '5m')
      # 返回 '2024-01-15 14:30:01'
    """


def _normalize_download_window(window: str) -> DownloadWindow:
    normalized = str(window).strip().lower()
    aliases = {
        "d": "day",
        "day": "day",
        "daily": "day",
        "m": "month",
        "mon": "month",
        "month": "month",
        "monthly": "month",
        "q": "quarter",
        "quarter": "quarter",
        "quarterly": "quarter",
        "y": "year",
        "year": "year",
        "yearly": "year",
        "annual": "year",
    }
    resolved = aliases.get(normalized)
    if resolved is None:
        raise ValueError(f"unsupported download window: {window}")
    return resolved


def _is_intraday_timeframe(timeframe: str) -> bool:
    return timeframe.strip().lower() in {"1m", "5m", "15m", "30m", "60m"}


def _format_window_boundary(value: pd.Timestamp, timeframe: str) -> str:
    if _is_intraday_timeframe(timeframe):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value.strftime("%Y-%m-%d")


def _next_window_start(value: pd.Timestamp, timeframe: str) -> pd.Timestamp:
    if _is_intraday_timeframe(timeframe):
        return value + pd.Timedelta(seconds=1)
    return value + pd.Timedelta(days=1)


def iter_download_windows(
    start: str,
    end: str,
    *,
    timeframe: str,
    window: str,
) -> list[tuple[str, str]]:
    """按自然日/月/季度/年切分下载时间窗口

    设计目标"让上层可以顺序写入并天然具备断点续传能力"：
    - 每个窗口单独下载、单独落库
    - 某个窗口失败时，前面已完成窗口的数据已经安全保存在本地
    - 下次再次执行时，可通过本地最新时间继续从失败窗口开始

    参数说明：
      start (str): 下载起始时间，格式为 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS
      end (str): 下载结束时间，格式为 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS
      timeframe (str): 时间周期，支持 1d/1w/1m/1h/5m/15m/30m/60m 等。
                      用于判断起止截点的格式（日线用日期，分钟线用时间戳）
      window (str): 窗口粒度，支持以下别名：
        - day/d: 每个自然日为一个窗口
        - month/mon/m: 每个自然月为一个窗口（推荐用于日线及以上）
        - quarter/q: 每个自然季度为一个窗口
        - year/annual/y: 每个自然年为一个窗口

    返回值：
      list[tuple[str, str]]: 时间窗口列表，每个元素是 (window_start, window_end) 元组。
                            返回的开始/结束时间遵循 timeframe 的格式约定。

    异常：
      ValueError: 当 start > end 或 window 值无效时抛出

    示例：
      # 日线数据按月分窗口
      windows = iter_download_windows('2024-01-01', '2024-12-31', timeframe='1d', window='month')
      # 返回: [('2024-01-01', '2024-01-31'), ('2024-02-01', '2024-02-29'), ...]

      # 分钟线数据按天分窗口
      windows = iter_download_windows('2024-01-01 09:30:00', '2024-01-05 16:00:00', 
                                      timeframe='5m', window='day')
      # 返回: [('2024-01-01 09:30:00', '2024-01-01 23:59:59'), 
      #        ('2024-01-02 09:30:00', '2024-01-02 23:59:59'), ...]
    """
    normalized_window = _normalize_download_window(window)
    start_ts = pd.to_datetime(start)
    end_ts = pd.to_datetime(end)
    if start_ts > end_ts:
        raise ValueError(f"download start must not be later than end: {start} > {end}")

    windows: list[tuple[str, str]] = []
    cursor = start_ts
    while cursor <= end_ts:
        base = cursor.normalize()
        if normalized_window == "day":
            natural_end = base + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        elif normalized_window == "month":
            natural_end = base + pd.offsets.MonthEnd(0) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        elif normalized_window == "quarter":
            natural_end = base + pd.offsets.QuarterEnd(0) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        else:
            natural_end = base + pd.offsets.YearEnd(0) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

        window_end = min(natural_end, end_ts)
        windows.append(
            (
                _format_window_boundary(cursor, timeframe),
                _format_window_boundary(window_end, timeframe),
            )
        )
        cursor = _next_window_start(window_end, timeframe)
    return windows


def _download_chunk_with_retries(
    *,
    source: BarSource,
    code: str,
    start: str,
    end: str,
    timeframe: str,
    market: str,
    chunk_retries: int,
    retry_interval: float,
) -> pd.DataFrame:
    """下载单个时间窗口的K线数据，并在窗口级别做重试

    数据源自身可能已经有内部重试；这里再补一层"窗口级"重试，
    用来处理长时间区间分页下载时的临时失败（网络波动、服务抖动等）。

    参数说明：
      source (BarSource): 实现了 BarSource 接口的数据源对象
      code (str): 证券代码，如 000001.SZ (股票) 或 IF2406.IF (期货)
      start (str): 窗口起始时间
      end (str): 窗口结束时间
      timeframe (str): 时间周期，如 1d/5m
      market (str): 市场标识，stock/futures
      chunk_retries (int): 失败重试次数，应 >= 1
      retry_interval (float): 每次重试的等待时间（秒）

    返回值：
      pd.DataFrame: K线数据，列名通常包括 [time, open, close, high, low, volume, ...] 等

    异常：
      RuntimeError: 当所有重试都失败时抛出，包含详细的参数信息

    工作原理：
      第1次尝试 → (失败) → 等待 → 第2次尝试 → ... → 第N次尝试 → 仍失败则抛异常
    """
    last_error: Exception | None = None
    attempts = max(1, int(chunk_retries))
    for attempt in range(1, attempts + 1):
        try:
            return source.download_bars(
                code=code,
                start=start,
                end=end,
                timeframe=timeframe,
                adj=None,
                market=market,
            )
        except Exception as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(retry_interval)
    raise RuntimeError(
        f"download chunk failed after {attempts} attempts for code={code}, market={market}, "
        f"timeframe={timeframe}, start={start}, end={end}"
    ) from last_error


def _download_factor_chunk_with_retries(
    *,
    source: BarSource,
    code: str,
    start: str,
    end: str,
    market: str,
    chunk_retries: int,
    retry_interval: float,
) -> pd.DataFrame:
    """下载单个时间窗口的复权因子，并在窗口级别做重试

    复权因子用于将K线数据从前复权/后复权转换为另一种形式。
    此函数仅适用于A股（stock），期货无此需求。
    
    参数说明：
      source (BarSource): 实现了 BarSource 接口的数据源对象。
                         应具有 download_adjust_factors 方法才能正常工作。
      code (str): 股票代码，如 000001.SZ
      start (str): 窗口起始日期
      end (str): 窗口结束日期
      market (str): 市场标识，仅应为 stock
      chunk_retries (int): 失败重试次数，应 >= 1
      retry_interval (float): 每次重试的等待时间（秒）

    返回值：
      pd.DataFrame: 复权因子数据，若数据源不支持或无数据则返回空DataFrame

    异常：
      RuntimeError: 当数据源支持该功能但所有重试都失败时抛出

    设计说明：
      - 如果 source 不具有 download_adjust_factors 方法，直接返回空DataFrame（静默降级）
      - 只有在数据源明确支持该方法时才会触发重试和异常

    与 _download_chunk_with_retries 的区别：
      - 更宽松的异常处理（不支持的数据源不抛异常）
      - 仅用于A股复权因子
    """

    last_error: Exception | None = None
    attempts = max(1, int(chunk_retries))
    for attempt in range(1, attempts + 1):
        try:
            return getattr(source, "download_adjust_factors")(
                code=code,
                start=start,
                end=end,
                market=market,
            )
        except Exception as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(retry_interval)
    raise RuntimeError(
        f"download factor chunk failed after {attempts} attempts for code={code}, market={market}, "
        f"start={start}, end={end}"
    ) from last_error


def sync_xtquant_data(
    *,
    code: str,
    start: str,
    end: str,
    market: str | None,
    timeframe: str,
    store: LocalDataStore,
    source: XtQuantDataSource,
    incremental: bool = True,
    download_window: str = "month",
    chunk_retries: int = 2,
    retry_interval: float = 1.0,
) -> SyncResult:
    """同步 XtQuant 数据源的行情数据到本地存储（XtQuant 专用接口）
    
    这是 sync_market_data() 的类型特化版本，数据源类型已确定为 XtQuantDataSource。
    功能完全相同，仅在类型签名上提供更精确的类型提示。
    
    参数说明：
      参数与 sync_market_data() 完全相同，只是 source 参数类型限制为 XtQuantDataSource
    
    返回值：
      SyncResult: 同步结果对象，属性说明见 SyncResult 文档
    
    说明：
      这是一个简单的转发函数，直接调用 sync_market_data()。
      提供此接口主要是为了让类型检查器能够正确推断类型。
    """
    return sync_market_data(
        code=code,
        start=start,
        end=end,
        market=market,
        timeframe=timeframe,
        store=store,
        source=source,
        incremental=incremental,
        download_window=download_window,
        chunk_retries=chunk_retries,
        retry_interval=retry_interval,
    )


def sync_market_data(
    *,
    code: str,
    start: str,
    end: str,
    market: str | None,
    timeframe: str,
    store: LocalDataStore,
    source: BarSource,
    incremental: bool = True,
    download_window: str = "month",
    chunk_retries: int = 2,
    retry_interval: float = 1.0,
) -> SyncResult:
    """同步市场行情数据到本地存储（通用接口）

    这是数据同步的核心函数。从指定数据源下载行情数据，按时间窗口分段处理，
    支持断点续传，最后写入本地存储。

    参数说明：
      code (str): 证券代码，如 000001.SZ (A股) 或 IF2406.IF (期货主力合约)
      start (str): 下载起始时间，格式 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS
      end (str): 下载结束时间，格式 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS
      market (str | None): 市场类型，支持 stock/futures。
                           若为 None，则自动根据代码推断（通常由 XtQuantDataSource 实现）
      timeframe (str): 时间周期，如 1d/1w/1m/1h/5m 等
      store (LocalDataStore): 本地存储对象，负责保存/读取数据
      source (BarSource): 数据源对象，需实现 BarSource 协议
      incremental (bool): 是否启用增量下载模式，默认True
                         开启时会查询本地最新时间，从此处继续下载
      download_window (str): 下载时间窗口粒度，支持 day/month/quarter/year
      chunk_retries (int): 单个时间窗口失败时的最大重试次数，默认2
      retry_interval (float): 窗口重试之间的等待时间（秒），默认1.0

    返回值：
      SyncResult: 包含同步结果的对象，包括：
        - code: 证券代码
        - market: 规范化后的市场标识
        - timeframe: 时间周期
        - start: 实际开始下载时间（可能因 incremental=True 而改变）
        - end: 原始结束时间
        - rows: 新写入的K线数据行数
        - factor_rows: 新写入的复权因子行数（仅股票）
        - skipped: 是否被跳过（当本地已有更新数据时）
        - main_contract: 期货主力合约代码（仅在 market=futures 且数据源支持时）

    工作流程：
      1. 推断市场类型（若 market 为 None）
      2. 若 incremental=True，查询本地最新时间，修改 download_start
      3. 若本地已有比 end 更新的数据，则跳过下载并返回 skipped=True
      4. 对期货主力合约，尝试获取主力合约代码
      5. 按 download_window 切分时间区间
      6. 逐个窗口下载K线，调用 _download_chunk_with_retries() 处理重试
      7. 实时写入 store，每个窗口成功就保存，便于断点续传
      8. 对A股，下载复权因子（若数据源支持）
      9. 返回同步结果摘要

    异常：
      RuntimeError: 当下载返回空数据、数据源错误等情况

    使用建议：
      - 首次下载：incremental=False，手动指定 start/end
      - 后续增量更新：incremental=True，仅需指定 start（通常为历史起点）
      - 大数据量下载：使用 download_window='month' 或更粗粒度窗口
      - 网络环境差：增加 chunk_retries，调整 retry_interval
    """
    normalized_market = market or XtQuantDataSource._normalize_market(code)
    download_start = start
    main_contract_hint = None

    if incremental:
        latest_dt = store.get_latest_dt(code=code, timeframe=timeframe, market=normalized_market)
        if latest_dt is not None:
            end_dt = pd.to_datetime(end)
            if latest_dt >= end_dt:
                return SyncResult(
                    code=code,
                    market=normalized_market,
                    timeframe=timeframe,
                    start=download_start,
                    end=end,
                    rows=0,
                    factor_rows=0,
                    skipped=True,
                )
            download_start = next_download_start(latest_dt, timeframe)

    if normalized_market == "futures" and _is_main_contract_code(code) and hasattr(source, "get_main_contract"):
        try:
            main_contract_hint = getattr(source, "get_main_contract")(code, start=download_start, end=end)
        except RuntimeError:
            main_contract_hint = None

    written = 0
    windows = iter_download_windows(
        download_start,
        end,
        timeframe=timeframe,
        window=download_window,
    )
    for window_start, window_end in windows:
        bars = _download_chunk_with_retries(
            source=source,
            code=code,
            start=window_start,
            end=window_end,
            timeframe=timeframe,
            market=normalized_market,
            chunk_retries=chunk_retries,
            retry_interval=retry_interval,
        )
        if bars.empty:
            raise RuntimeError(
                f"download returned empty bars for code={code}, market={normalized_market}, timeframe={timeframe}, "
                f"start={window_start}, end={window_end}"
            )
        written += store.upsert_bars(code=code, bars=bars, timeframe=timeframe, market=normalized_market)

    factor_rows = 0
    if normalized_market == "stock" and hasattr(source, "download_adjust_factors"):
        factor_start = start
        if incremental:
            latest_factor_dt = store.get_latest_factor_dt(code=code, market=normalized_market)
            if latest_factor_dt is not None:
                end_dt = pd.to_datetime(end)
                if latest_factor_dt < end_dt:
                    factor_start = latest_factor_dt.strftime("%Y-%m-%d")
        factor_windows = iter_download_windows(
            factor_start,
            end,
            timeframe="1d",
            window=download_window,
        )
        for window_start, window_end in factor_windows:
            factors = _download_factor_chunk_with_retries(
                source=source,
                code=code,
                start=window_start,
                end=window_end,
                market=normalized_market,
                chunk_retries=chunk_retries,
                retry_interval=retry_interval,
            )
            if not factors.empty:
                factor_rows += store.upsert_adjust_factors(code=code, factors=factors, market=normalized_market)

    return SyncResult(
        code=code,
        market=normalized_market,
        timeframe=timeframe,
        start=download_start,
        end=end,
        rows=written,
        factor_rows=factor_rows,
        skipped=False,
        main_contract=main_contract_hint if isinstance(main_contract_hint, str) else None,
    )


def _is_main_contract_code(code: str) -> bool:
    """判断给定代码是否为期货主力合约代码
    
    期货代码格式：符号代码.交易所，如 IF2406.IF
    主力合约特征：符号部分以 00 结尾（规范化表示）
    
    参数说明：
      code (str): 期货代码，应包含 . 分隔符，如 IF.IF 或 IF2406.IF
    
    返回值：
      bool: 是否为主力合约代码（符号以 00 结尾）
    
    示例：
      _is_main_contract_code('IF.IF')      # True - IF00 的规范形式
      _is_main_contract_code('IF2406.IF')  # False - 指定月份的合约
      _is_main_contract_code('IC00.IC')    # True
      _is_main_contract_code('IC2406.IC')  # False
      _is_main_contract_code('SH.SH')      # False - 没有 00 后缀
    
    用途：
      当下载期货数据时，如果给定的是主力合约代码，系统会尝试获取
      实际有效的主力合约代码（月份具体值），以便追踪主力合约的连续性。
    """
