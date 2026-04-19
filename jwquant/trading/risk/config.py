"""
统一风控配置。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RiskConfig:
    max_total_exposure: float = 1.0
    max_single_weight: float = 1.0
    max_futures_margin_ratio: float = 1.0
    max_holdings: int = 0
    max_order_amount: float = 0.0
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    trailing_stop_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    allow_futures_long: bool = True
    allow_futures_short: bool = True
    buy_reject_threshold_pct: float = 0.0
    sell_reject_threshold_pct: float = 0.0
    limit_up_pct: float = 0.1
    limit_down_pct: float = 0.1
    conflict_policy: str = "priority_first"
    rule_priorities: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any] | None = None) -> "RiskConfig":
        if mapping is None:
            raise KeyError("missing risk config mapping")
        payload = dict(mapping)
        return cls(
            max_total_exposure=float(payload["max_total_exposure"]),
            max_single_weight=float(payload["max_single_weight"]),
            max_futures_margin_ratio=float(payload["max_futures_margin_ratio"]),
            max_holdings=int(payload["max_holdings"]),
            max_order_amount=float(payload["max_order_amount"]),
            stop_loss_pct=float(payload["stop_loss_pct"]),
            take_profit_pct=float(payload["take_profit_pct"]),
            trailing_stop_pct=float(payload["trailing_stop_pct"]),
            max_drawdown_pct=float(payload["max_drawdown_pct"]),
            allow_futures_long=bool(payload["allow_futures_long"]),
            allow_futures_short=bool(payload["allow_futures_short"]),
            buy_reject_threshold_pct=float(payload.get("buy_reject_threshold_pct", 0.0)),
            sell_reject_threshold_pct=float(payload.get("sell_reject_threshold_pct", 0.0)),
            limit_up_pct=float(payload.get("limit_up_pct", 0.1)),
            limit_down_pct=float(payload.get("limit_down_pct", 0.1)),
            conflict_policy=str(payload["conflict_policy"]),
            rule_priorities={
                str(name): int(priority)
                for name, priority in dict(payload["rule_priorities"]).items()
            },
        )

    def apply_rule_priorities(self, rules: list[object]) -> list[object]:
        for rule in rules:
            rule_name = getattr(rule, "name", "")
            if rule_name in self.rule_priorities:
                setattr(rule, "priority", int(self.rule_priorities[rule_name]))
        return rules
