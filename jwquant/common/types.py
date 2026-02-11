"""
公共数据类型定义

定义系统中所有模块共享的数据结构：
- Bar: K线数据
- Tick: 逐笔数据
- Order: 委托订单
- Trade: 成交记录
- Position: 持仓信息
- Signal: 交易信号
- Asset: 账户资产
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Direction(Enum):
    """交易方向"""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class SignalType(Enum):
    """信号类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Bar:
    """K线数据"""
    code: str
    dt: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float = 0.0


@dataclass
class Signal:
    """交易信号"""
    code: str
    dt: datetime
    signal_type: SignalType
    price: float
    strength: float = 1.0
    reason: str = ""


@dataclass
class Order:
    """委托订单"""
    code: str
    direction: Direction
    price: float
    volume: int
    order_id: str = ""
    status: OrderStatus = OrderStatus.PENDING
    dt: Optional[datetime] = None


@dataclass
class Position:
    """持仓信息"""
    code: str
    volume: int
    available: int
    cost_price: float
    market_value: float = 0.0


@dataclass
class Asset:
    """账户资产"""
    cash: float
    frozen_cash: float = 0.0
    market_value: float = 0.0
    total_asset: float = 0.0


@dataclass
class Tick:
    """逐笔行情"""
    code: str
    dt: datetime
    last_price: float
    volume: int
    bid_price: float
    bid_volume: int
    ask_price: float
    ask_volume: int
    open_interest: float = 0.0


@dataclass
class Trade:
    """成交记录"""
    trade_id: str
    order_id: str
    code: str
    direction: Direction
    price: float
    volume: int
    dt: datetime
    commission: float = 0.0
    slippage: float = 0.0


@dataclass
class RiskEvent:
    """风控事件"""
    risk_type: str          # "MAX_POSITION" | "BLACKLIST" | "DRAWDOWN" ...
    severity: str           # "WARNING" | "ERROR" | "CRITICAL"
    code: str
    message: str
    dt: datetime
    action_taken: str = ""  # "BLOCKED" | "ALERT_SENT"
    metadata: dict = field(default_factory=dict)


@dataclass
class StrategyMeta:
    """策略元信息"""
    name: str
    version: str
    params: dict = field(default_factory=dict)
    status: str = "INITIALIZED"  # INITIALIZED | RUNNING | STOPPED | ERROR
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
