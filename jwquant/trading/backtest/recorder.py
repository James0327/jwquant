"""
回测记录器。

负责记录订单、成交、权益曲线、日期与持仓快照。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from jwquant.common.types import Order, RiskEvent


@dataclass
class BacktestRecorder:
    orders: list[Order] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    dates: list[datetime] = field(default_factory=list)
    equity_records: list[dict[str, Any]] = field(default_factory=list)
    position_snapshots: list[dict[str, dict[str, float]]] = field(default_factory=list)
    risk_events: list[RiskEvent] = field(default_factory=list)

    def record_order(self, order: Order) -> None:
        self.orders.append(order)

    def record_trade(self, trade: dict[str, Any]) -> None:
        self.trades.append(trade)

    def record_risk_event(self, event: RiskEvent) -> None:
        self.risk_events.append(event)

    def record_bar_close(
        self,
        *,
        dt: datetime,
        equity: float,
        position_snapshot: dict[str, dict[str, float]],
    ) -> None:
        self.dates.append(dt)
        self.equity_curve.append(equity)
        self.equity_records.append(
            {
                "dt": dt,
                "equity": equity,
                "position_count": len(position_snapshot),
            }
        )
        self.position_snapshots.append(position_snapshot)

    def build_report_payload(self) -> dict[str, Any]:
        order_status_counts: dict[str, int] = {}
        risk_by_type: dict[str, int] = {}
        risk_by_category: dict[str, int] = {}
        risk_by_source: dict[str, int] = {}
        risk_by_action: dict[str, int] = {}
        for order in self.orders:
            status = order.status.value
            order_status_counts[status] = order_status_counts.get(status, 0) + 1
        for event in self.risk_events:
            risk_by_type[event.risk_type] = risk_by_type.get(event.risk_type, 0) + 1
            if event.category:
                risk_by_category[event.category] = risk_by_category.get(event.category, 0) + 1
            if event.source:
                risk_by_source[event.source] = risk_by_source.get(event.source, 0) + 1
            if event.action_taken:
                risk_by_action[event.action_taken] = risk_by_action.get(event.action_taken, 0) + 1

        return {
            "start_dt": self.dates[0] if self.dates else None,
            "end_dt": self.dates[-1] if self.dates else None,
            "equity_records": list(self.equity_records),
            "latest_positions": self.position_snapshots[-1] if self.position_snapshots else {},
            "order_status_counts": order_status_counts,
            "risk_by_type": risk_by_type,
            "risk_by_category": risk_by_category,
            "risk_by_source": risk_by_source,
            "risk_by_action": risk_by_action,
            "risk_events": [
                {
                    "risk_type": event.risk_type,
                    "severity": event.severity,
                    "code": event.code,
                    "message": event.message,
                    "dt": event.dt,
                    "action_taken": event.action_taken,
                    "category": event.category,
                    "source": event.source,
                    "metadata": dict(event.metadata),
                }
                for event in self.risk_events
            ],
            "trade_records": list(self.trades),
            "order_records": [
                {
                    "order_id": order.order_id,
                    "code": order.code,
                    "direction": order.direction.value,
                    "order_type": order.order_type.value,
                    "offset": order.offset,
                    "price": order.price,
                    "volume": order.volume,
                    "status": order.status.value,
                    "dt": order.dt,
                }
                for order in self.orders
            ],
        }
