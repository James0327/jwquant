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
    conflict_policy: str = "priority_first"
    rule_priorities: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any] | None = None) -> "RiskConfig":
        payload = dict(mapping or {})
        return cls(
            max_total_exposure=float(payload.get("max_total_exposure", 1.0)),
            max_single_weight=float(payload.get("max_single_weight", 1.0)),
            max_futures_margin_ratio=float(payload.get("max_futures_margin_ratio", 1.0)),
            max_holdings=int(payload.get("max_holdings", 0)),
            max_order_amount=float(payload.get("max_order_amount", 0.0)),
            stop_loss_pct=float(payload.get("stop_loss_pct", 0.0)),
            take_profit_pct=float(payload.get("take_profit_pct", 0.0)),
            trailing_stop_pct=float(payload.get("trailing_stop_pct", 0.0)),
            max_drawdown_pct=float(payload.get("max_drawdown_pct", 0.0)),
            allow_futures_long=bool(payload.get("allow_futures_long", True)),
            allow_futures_short=bool(payload.get("allow_futures_short", True)),
            conflict_policy=str(payload.get("conflict_policy", "priority_first")),
            rule_priorities={
                str(name): int(priority)
                for name, priority in dict(payload.get("rule_priorities", {})).items()
            },
        )

    def apply_rule_priorities(self, rules: list[object]) -> list[object]:
        for rule in rules:
            rule_name = getattr(rule, "name", "")
            if rule_name in self.rule_priorities:
                setattr(rule, "priority", int(self.rule_priorities[rule_name]))
        return rules
