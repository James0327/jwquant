"""
回测订单辅助。
"""
from __future__ import annotations

from jwquant.common.types import Direction, Order, Signal


def build_order_from_signal(
    *,
    signal: Signal,
    quantity: int,
    reference_price: float,
    order_id: str,
    offset: str,
) -> Order:
    """将策略信号转换为最小订单对象。"""
    direction = Direction.BUY if signal.signal_type.name == "BUY" else Direction.SELL
    return Order(
        code=signal.code,
        direction=direction,
        price=signal.price,
        volume=quantity,
        order_type=signal.order_type,
        offset=offset,
        order_id=order_id,
        dt=signal.dt,
    )
