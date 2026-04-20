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
    position_records: list[dict[str, Any]] = field(default_factory=list)
    risk_events: list[RiskEvent] = field(default_factory=list)
    signal_records: list[dict[str, Any]] = field(default_factory=list)

    def record_order(self, order: Order) -> None:
        self.orders.append(order)

    def record_trade(self, trade: dict[str, Any]) -> None:
        self.trades.append(trade)

    def record_risk_event(self, event: RiskEvent) -> None:
        self.risk_events.append(event)

    def record_signal(self, signal_record: dict[str, Any]) -> None:
        self.signal_records.append(dict(signal_record))

    def update_signal_status(
        self,
        signal_id: str,
        *,
        status: str,
        execution_dt: datetime | None = None,
        execution_price: float | None = None,
        order_id: str = "",
        order_status: str = "",
        reason: str = "",
        reason_source: str = "",
    ) -> None:
        for record in self.signal_records:
            if str(record.get("signal_id", "")) != str(signal_id):
                continue
            record["status"] = status
            if execution_dt is not None:
                record["execution_dt"] = execution_dt
            if execution_price is not None:
                record["execution_price"] = execution_price
            if order_id:
                record["order_id"] = order_id
            if order_status:
                record["order_status"] = order_status
            if reason:
                record["reason_detail"] = reason
            if reason_source:
                record["reason_source"] = reason_source
            break

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
        for code, snapshot in position_snapshot.items():
            self.position_records.append(
                {
                    "dt": dt,
                    "code": code,
                    "quantity": float(snapshot.get("quantity", 0.0)),
                    "sellable_quantity": float(snapshot.get("sellable_quantity", 0.0)),
                    "avg_price": float(snapshot.get("avg_price", 0.0)),
                    "margin": float(snapshot.get("margin", 0.0)),
                }
            )

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
            "position_records": list(self.position_records),
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
            "signal_records": list(self.signal_records),
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
