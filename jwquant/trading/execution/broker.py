"""
XtQuant 账户连接与账户查询管理。

这一层负责两类能力：
1. 连接到 XtQuant 账户并完成订阅
2. 查询账户资产与持仓
"""
from __future__ import annotations

import time
import re
from functools import lru_cache
from dataclasses import dataclass
from typing import Any

from jwquant.common.config import Config
from jwquant.common.log import get_logger


logger = get_logger("jwquant.xtquant")


class XtQuantError(RuntimeError):
    """XtQuant 模块基础异常。"""


class XtQuantImportError(XtQuantError):
    """XtQuant 运行时导入失败。"""


class XtQuantConfigError(XtQuantError):
    """XtQuant 账户配置错误。"""


class XtQuantConnectError(XtQuantError):
    """XtQuant 连接或订阅失败。"""


class XtQuantQueryError(XtQuantError):
    """XtQuant 查询失败。"""


@dataclass(slots=True)
class XtQuantAccountConfig:
    """XtQuant 单个账户连接配置。"""

    market: str
    path: str
    account_id: str
    account_type: str
    max_retry: int = 5
    retry_interval: float = 3.0

    @classmethod
    def from_config(cls, market: str, config: Config | None = None) -> "XtQuantAccountConfig":
        cfg = config or Config()
        normalized_market = str(market).strip().lower()
        if normalized_market not in {"stock", "futures"}:
            raise XtQuantConfigError(f"unsupported xtquant account market: {market}")

        prefix = f"broker.xtquant.{normalized_market}"
        path = str(cfg.get(f"{prefix}.path")).strip()
        account_id = str(cfg.get(f"{prefix}.account_id")).strip()
        account_type = str(cfg.get(f"{prefix}.account_type")).strip()
        max_retry = int(cfg.get(f"{prefix}.max_retry"))
        retry_interval = float(cfg.get(f"{prefix}.retry_interval"))
        return cls(
            market=normalized_market,
            path=path,
            account_id=account_id,
            account_type=account_type,
            max_retry=max_retry,
            retry_interval=retry_interval,
        )


@dataclass(slots=True)
class XtQuantSession:
    """一次成功的 XtQuant 连接会话。"""

    trader: Any
    account: Any
    account_config: XtQuantAccountConfig
    session_id: int

    def stop(self) -> None:
        """停止交易线程并释放连接。"""
        if self.trader is None:
            return
        self.trader.stop()
    
    def query_asset(self) -> XtQuantAssetSnapshot | None:
        """查询当前会话账户资产。"""
        return query_account_asset(self)

    def query_positions(self) -> list[XtQuantPositionSnapshot]:
        """查询当前会话账户持仓。"""
        return query_account_positions(self)

    def query_snapshot(self) -> XtQuantAccountSnapshot:
        """一次性查询账户资产和持仓。"""
        return query_account_snapshot(self)


@dataclass(slots=True)
class XtQuantAssetSnapshot:
    """统一的账户资产快照。"""

    account_id: str
    cash: float
    frozen_cash: float
    market_value: float
    total_asset: float
    native_asset: Any
    fetch_balance: float | None = None
    margin_ratio: float | None = None
    available_margin: float | None = None


@dataclass(slots=True)
class XtQuantPositionSnapshot:
    """统一的持仓快照。"""

    code: str
    volume: float
    available_volume: float
    open_price: float
    is_futures_candidate: bool
    native_position: Any


@dataclass(slots=True)
class XtQuantPositionStatisticsSnapshot:
    """统一的期货持仓统计快照。

    说明：
      - 该结构仅服务期货账户“持仓统计/持仓合计”展示；
      - 数据来源必须是 XtQuant 专用接口 `query_position_statistics`，
        不能由持仓明细手工聚合替代，否则口径会与柜台页面不一致。
    """

    instrument_id: str
    direction: Any
    native_statistics: Any


@dataclass(slots=True)
class XtQuantTradeSnapshot:
    """统一的成交快照。"""

    code: str
    account_id: str
    traded_id: str
    traded_time: Any
    traded_price: float
    traded_volume: float
    traded_amount: float
    order_id: Any
    direction: Any
    offset_flag: Any
    native_trade: Any


@dataclass(slots=True)
class XtQuantOrderSnapshot:
    """统一的委托快照。"""

    code: str
    account_id: str
    order_id: Any
    order_time: Any
    price: float
    order_volume: float
    traded_volume: float
    traded_price: float
    order_status: Any
    status_msg: str
    direction: Any
    offset_flag: Any
    native_order: Any


@dataclass(slots=True)
class XtQuantAccountSnapshot:
    """统一的账户查询结果。"""

    asset: XtQuantAssetSnapshot | None
    positions: list[XtQuantPositionSnapshot]
    position_statistics: list[XtQuantPositionStatisticsSnapshot]
    trades: list[XtQuantTradeSnapshot]
    orders: list[XtQuantOrderSnapshot]


class XtQuantTradeCallbackBase:
    """统一的 XtQuant 回调基类。"""

    def __init__(self, label: str = "账户"):
        self._label = label

    def on_disconnected(self):
        logger.warning("%s连接已断开", self._label)

    def on_account_status(self, status):
        logger.info("%s状态更新: 账号=%s, 状态=%s", self._label, status.account_id, status.status)


@lru_cache(maxsize=1)
def _load_xttrader_types():
    try:
        from xtquant.xttrader import XtQuantTrader
        from xtquant.xttype import StockAccount
    except ImportError as exc:
        raise XtQuantImportError(
            "failed to import xtquant trading runtime; please ensure XtQuant / MiniQMT runtime is installed"
        ) from exc
    return XtQuantTrader, StockAccount


def connect_xtquant_account(
    account_config: XtQuantAccountConfig,
    callback: Any | None = None,
    session_id: int | None = None,
) -> XtQuantSession:
    """连接并订阅一个 XtQuant 账户。

    返回成功连接后的 trader/account 包装对象；失败时抛出 RuntimeError，
    这样调用方可以自行决定是打印提示、重试更上层流程，还是直接中断。
    """

    XtQuantTrader, StockAccount = _load_xttrader_types()

    if not account_config.path:
        raise XtQuantConfigError(f"{account_config.market} xtquant path is empty")
    if not account_config.account_id:
        raise XtQuantConfigError(f"{account_config.market} xtquant account_id is empty")

    resolved_session_id = int(session_id or time.time())
    label = "期货账户" if account_config.market == "futures" else "股票账户"

    logger.info(
        "connecting xtquant account: market=%s, path=%s, account_id=%s, session_id=%s",
        account_config.market,
        account_config.path,
        account_config.account_id,
        resolved_session_id,
    )

    trader = XtQuantTrader(account_config.path, resolved_session_id)
    callback = callback or XtQuantTradeCallbackBase(label=label)
    trader.register_callback(callback)
    trader.start()

    connect_result = trader.connect()
    if connect_result != 0:
        trader.stop()
        raise XtQuantConnectError(f"xtquant connect failed with code={connect_result}")

    account = StockAccount(account_config.account_id, account_type=account_config.account_type)

    for retry_count in range(1, max(int(account_config.max_retry), 1) + 1):
        if retry_count > 1:
            time.sleep(max(float(account_config.retry_interval), 0.0))

        subscribe_result = trader.subscribe(account)
        if subscribe_result == 0:
            return XtQuantSession(
                trader=trader,
                account=account,
                account_config=account_config,
                session_id=resolved_session_id,
            )

        logger.warning(
            "xtquant subscribe failed: market=%s, account_id=%s, retry=%s/%s, code=%s",
            account_config.market,
            account_config.account_id,
            retry_count,
            account_config.max_retry,
            subscribe_result,
        )

    trader.stop()
    raise XtQuantConnectError(
        f"xtquant subscribe failed after {account_config.max_retry} attempts for "
        f"account_id={account_config.account_id}"
    )


def connect_stock_account(
    config: Config | None = None,
    callback: Any | None = None,
    session_id: int | None = None,
) -> XtQuantSession:
    """从配置加载股票账户并完成连接。"""
    return connect_xtquant_account(
        account_config=XtQuantAccountConfig.from_config("stock", config=config),
        callback=callback,
        session_id=session_id,
    )


def connect_futures_account(
    config: Config | None = None,
    callback: Any | None = None,
    session_id: int | None = None,
) -> XtQuantSession:
    """从配置加载期货账户并完成连接。"""
    return connect_xtquant_account(
        account_config=XtQuantAccountConfig.from_config("futures", config=config),
        callback=callback,
        session_id=session_id,
    )


def query_account_asset(session: XtQuantSession) -> XtQuantAssetSnapshot | None:
    """查询账户资产并转换为稳定结构。"""
    try:
        asset = session.trader.query_stock_asset(session.account)
        if not asset:
            return None

        return XtQuantAssetSnapshot(
            account_id=str(getattr(asset, "account_id", session.account_config.account_id)),
            cash=float(getattr(asset, "cash", 0.0) or 0.0),
            frozen_cash=float(getattr(asset, "frozen_cash", 0.0) or 0.0),
            market_value=float(getattr(asset, "market_value", 0.0) or 0.0),
            total_asset=float(getattr(asset, "total_asset", 0.0) or 0.0),
            margin_ratio=_optional_float(getattr(asset, "margin_ratio", None)),
            available_margin=_optional_float(getattr(asset, "available_margin", None)),
            native_asset=asset,
        )
    except Exception as exc:
        raise XtQuantQueryError(
            f"xtquant asset query failed: market={session.account_config.market}, "
            f"account_id={session.account_config.account_id}, session_id={session.session_id}"
        ) from exc


def query_account_positions(session: XtQuantSession) -> list[XtQuantPositionSnapshot]:
    """查询账户持仓并转换为稳定结构。

    关键处理：
      1. 将 XtQuant 原始持仓对象转换为项目内稳定快照；
      2. 对明显已经平仓、但柜台接口仍暂时返回的“残留空记录”做过滤，
         避免诊断页把白天盘/已平仓合约误展示为当前持仓。

    过滤原则：
      - 仅过滤“持仓量=0、可用量=0、保证金=0、市值=0”的记录；
      - 只要任一关键持仓字段仍非 0，就保留，避免误删真实持仓。
    """
    try:
        positions = session.trader.query_stock_positions(session.account) or []
        normalized: list[XtQuantPositionSnapshot] = []
        for pos in positions:
            code = str(getattr(pos, "stock_code", "") or "")
            volume = float(getattr(pos, "volume", 0.0) or 0.0)
            available_volume = float(getattr(pos, "can_use_volume", 0.0) or 0.0)
            market_value = _optional_float(getattr(pos, "market_value", None))
            margin = _optional_float(getattr(pos, "margin", None))
            if _should_skip_closed_position_record(
                volume=volume,
                available_volume=available_volume,
                market_value=market_value,
                margin=margin,
            ):
                logger.info(
                    "skip closed xtquant position residue: market=%s, account_id=%s, code=%s, volume=%s, can_use_volume=%s, market_value=%s, margin=%s",
                    session.account_config.market,
                    session.account_config.account_id,
                    code,
                    volume,
                    available_volume,
                    market_value,
                    margin,
                )
                continue
            normalized.append(
                XtQuantPositionSnapshot(
                    code=code,
                    volume=volume,
                    available_volume=available_volume,
                    open_price=float(getattr(pos, "open_price", 0.0) or 0.0),
                    is_futures_candidate=_looks_like_futures_code_for_display(code),
                    native_position=pos,
                )
            )
        return normalized
    except Exception as exc:
        raise XtQuantQueryError(
            f"xtquant position query failed: market={session.account_config.market}, "
            f"account_id={session.account_config.account_id}, session_id={session.session_id}"
        ) from exc


def query_account_snapshot(session: XtQuantSession) -> XtQuantAccountSnapshot:
    """一次性查询账户资产和持仓。"""
    return XtQuantAccountSnapshot(
        asset=session.query_asset(),
        positions=session.query_positions(),
        position_statistics=query_account_position_statistics(session),
        trades=query_account_trades(session),
        orders=query_account_orders(session),
    )


def query_account_position_statistics(session: XtQuantSession) -> list[XtQuantPositionStatisticsSnapshot]:
    """查询期货持仓统计。

    业务规则：
      - 股票账户没有“期货持仓统计”概念，直接返回空列表；
      - 期货账户必须调用 XtQuant 专用统计接口，避免把明细聚合结果误当成统计结果。

    过滤规则：
      - 持仓统计中 `position=0` 的项目视为已无实际持仓，不进入诊断展示；
      - 这样可以避免已平仓合约仍残留在“持仓统计”页签中。
    """
    if session.account_config.market != "futures":
        return []

    try:
        statistics = session.trader.query_position_statistics(session.account) or []
        normalized: list[XtQuantPositionStatisticsSnapshot] = []
        for item in statistics:
            instrument_id = str(getattr(item, "instrument_id", "") or "")
            position = _optional_float(getattr(item, "position", None))
            if position is not None and abs(position) <= 1e-12:
                logger.info(
                    "skip zero futures position statistics: account_id=%s, instrument_id=%s, direction=%s, position=%s",
                    session.account_config.account_id,
                    instrument_id,
                    getattr(item, "direction", None),
                    position,
                )
                continue
            normalized.append(
                XtQuantPositionStatisticsSnapshot(
                    instrument_id=instrument_id,
                    direction=getattr(item, "direction", None),
                    native_statistics=item,
                )
            )
        logger.info(
            "query futures position statistics finished: account_id=%s, count=%s",
            session.account_config.account_id,
            len(normalized),
        )
        return normalized
    except Exception as exc:
        raise XtQuantQueryError(
            f"xtquant position statistics query failed: market={session.account_config.market}, "
            f"account_id={session.account_config.account_id}, session_id={session.session_id}"
        ) from exc


def query_account_trades(session: XtQuantSession) -> list[XtQuantTradeSnapshot]:
    """查询账户当日成交并转换为稳定结构。"""
    try:
        trades = session.trader.query_stock_trades(session.account) or []
        normalized: list[XtQuantTradeSnapshot] = []
        for trade in trades:
            normalized.append(
                XtQuantTradeSnapshot(
                    code=str(getattr(trade, "stock_code", "") or ""),
                    account_id=str(getattr(trade, "account_id", session.account_config.account_id)),
                    traded_id=str(getattr(trade, "traded_id", "") or ""),
                    traded_time=getattr(trade, "traded_time", None),
                    traded_price=float(getattr(trade, "traded_price", 0.0) or 0.0),
                    traded_volume=float(getattr(trade, "traded_volume", 0.0) or 0.0),
                    traded_amount=float(getattr(trade, "traded_amount", 0.0) or 0.0),
                    order_id=getattr(trade, "order_id", None),
                    direction=getattr(trade, "direction", None),
                    offset_flag=getattr(trade, "offset_flag", None),
                    native_trade=trade,
                )
            )
        logger.info(
            "query account trades finished: market=%s, account_id=%s, count=%s",
            session.account_config.market,
            session.account_config.account_id,
            len(normalized),
        )
        return normalized
    except Exception as exc:
        raise XtQuantQueryError(
            f"xtquant trades query failed: market={session.account_config.market}, "
            f"account_id={session.account_config.account_id}, session_id={session.session_id}"
        ) from exc


def query_account_orders(session: XtQuantSession) -> list[XtQuantOrderSnapshot]:
    """查询账户当日委托并转换为稳定结构。"""
    try:
        orders = session.trader.query_stock_orders(session.account) or []
        normalized: list[XtQuantOrderSnapshot] = []
        for order in orders:
            normalized.append(
                XtQuantOrderSnapshot(
                    code=str(getattr(order, "stock_code", "") or ""),
                    account_id=str(getattr(order, "account_id", session.account_config.account_id)),
                    order_id=getattr(order, "order_id", None),
                    order_time=getattr(order, "order_time", None),
                    price=float(getattr(order, "price", 0.0) or 0.0),
                    order_volume=float(getattr(order, "order_volume", 0.0) or 0.0),
                    traded_volume=float(getattr(order, "traded_volume", 0.0) or 0.0),
                    traded_price=float(getattr(order, "traded_price", 0.0) or 0.0),
                    order_status=getattr(order, "order_status", None),
                    status_msg=str(getattr(order, "status_msg", "") or ""),
                    direction=getattr(order, "direction", None),
                    offset_flag=getattr(order, "offset_flag", None),
                    native_order=order,
                )
            )
        logger.info(
            "query account orders finished: market=%s, account_id=%s, count=%s",
            session.account_config.market,
            session.account_config.account_id,
            len(normalized),
        )
        return normalized
    except Exception as exc:
        raise XtQuantQueryError(
            f"xtquant orders query failed: market={session.account_config.market}, "
            f"account_id={session.account_config.account_id}, session_id={session.session_id}"
        ) from exc


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _should_skip_closed_position_record(
    *,
    volume: float,
    available_volume: float,
    market_value: float | None,
    margin: float | None,
) -> bool:
    """判断一条持仓记录是否属于已平仓残留记录。

    业务背景：
      柜台接口在某些时点会返回已经平仓、但尚未从查询结果中清除的残留记录。
      这类记录通常会同时满足“数量为 0、可用为 0、市值为 0、保证金为 0”。

    输入输出：
      - 输入：持仓记录的关键数量字段
      - 输出：True 表示应在展示前过滤，False 表示保留

    设计原因：
      - 只基于单一字段（例如 volume==0）过滤风险太高；
      - 必须多个关键字段同时为 0 才过滤，尽量降低误判。
    """
    indicators = [volume, available_volume, market_value or 0.0, margin or 0.0]
    return all(abs(float(value)) <= 1e-12 for value in indicators)


def _looks_like_futures_code_for_display(code: str) -> bool:
    """判断持仓代码是否应按期货合约展示。

    设计目标：
      1. 这里只用于诊断展示，不参与真实交易路由；
      2. 需要覆盖不同交易所的期货品种，不能依赖少量品种白名单；
      3. 要避免把股票代码（如 000001.SZ / 600519.SH）误判为期货。

    判断规则：
      - 期货实盘持仓通常表现为“品种字母 + 交割合约数字 + 交易所后缀”，
        例如 IF2406.IF、FG610.ZF、RB2510.SF；
      - 因此这里要求：
        a. 必须包含交易所分隔符 '.'
        b. 点前符号部分必须同时包含字母和数字
        c. 点后交易所后缀必须为纯字母

    这样既能覆盖 FG610.ZF 这类郑商所合约，也能排除纯数字股票代码。
    """
    normalized = str(code or "").strip().upper()
    if "." not in normalized:
        return False

    symbol, exchange = normalized.split(".", 1)
    if not symbol or not exchange or not exchange.isalpha():
        return False

    return re.fullmatch(r"[A-Z]+[0-9]+", symbol) is not None
