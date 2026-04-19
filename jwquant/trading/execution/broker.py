"""
XtQuant 账户连接与账户查询管理。

这一层负责两类能力：
1. 连接到 XtQuant 账户并完成订阅
2. 查询账户资产与持仓
"""
from __future__ import annotations

import time
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
class XtQuantAccountSnapshot:
    """统一的账户查询结果。"""

    asset: XtQuantAssetSnapshot | None
    positions: list[XtQuantPositionSnapshot]


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
    """查询账户持仓并转换为稳定结构。"""
    try:
        positions = session.trader.query_stock_positions(session.account) or []
        normalized: list[XtQuantPositionSnapshot] = []
        for pos in positions:
            code = str(getattr(pos, "stock_code", "") or "")
            normalized.append(
                XtQuantPositionSnapshot(
                    code=code,
                    volume=float(getattr(pos, "volume", 0.0) or 0.0),
                    available_volume=float(getattr(pos, "can_use_volume", 0.0) or 0.0),
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
    return XtQuantAccountSnapshot(asset=session.query_asset(), positions=session.query_positions())


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _looks_like_futures_code_for_display(code: str) -> bool:
    normalized = str(code or "").upper()
    indicators = ("IF", "IH", "IC", "IM", "RB", "RU", "CU", "AL", "ZN", "NI")
    return any(indicator in normalized for indicator in indicators)
