"""
风控规则协议与基础决策对象。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from jwquant.common.types import Order, RiskEvent
from jwquant.trading.risk.context import RiskCheckContext


class RiskAction(Enum):
    """风控动作。"""

    ALLOW = "allow"
    ADJUST = "adjust"
    BLOCK = "block"


class RiskStage(Enum):
    """风控检查阶段。"""

    ORDER = "order"
    BAR = "bar"
    PORTFOLIO = "portfolio"


@dataclass
class RiskDecision:
    """统一风控决策。"""

    action: RiskAction = RiskAction.ALLOW
    stage: RiskStage | None = None
    adjusted_order: Order | None = None
    context_updates: dict[str, Any] = field(default_factory=dict)
    events: list[RiskEvent] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.action != RiskAction.BLOCK

    def merge(self, other: "RiskDecision") -> "RiskDecision":
        action = self.action
        if other.action == RiskAction.BLOCK:
            action = RiskAction.BLOCK
        elif other.action == RiskAction.ADJUST and action == RiskAction.ALLOW:
            action = RiskAction.ADJUST

        adjusted_order = other.adjusted_order if other.adjusted_order is not None else self.adjusted_order
        return RiskDecision(
            action=action,
            stage=other.stage if other.stage is not None else self.stage,
            adjusted_order=adjusted_order,
            context_updates={**self.context_updates, **other.context_updates},
            events=[*self.events, *other.events],
        )

    @classmethod
    def allow(
        cls,
        *,
        stage: RiskStage | None = None,
        events: list[RiskEvent] | None = None,
        adjusted_order: Order | None = None,
        context_updates: dict[str, Any] | None = None,
    ) -> "RiskDecision":
        return cls(
            action=RiskAction.ALLOW,
            stage=stage,
            adjusted_order=adjusted_order,
            context_updates=dict(context_updates or {}),
            events=list(events or []),
        )

    @classmethod
    def adjust(
        cls,
        *,
        stage: RiskStage | None = None,
        adjusted_order: Order | None = None,
        context_updates: dict[str, Any] | None = None,
        events: list[RiskEvent] | None = None,
    ) -> "RiskDecision":
        return cls(
            action=RiskAction.ADJUST,
            stage=stage,
            adjusted_order=adjusted_order,
            context_updates=dict(context_updates or {}),
            events=list(events or []),
        )

    @classmethod
    def block(
        cls,
        *,
        stage: RiskStage | None = None,
        context_updates: dict[str, Any] | None = None,
        events: list[RiskEvent] | None = None,
    ) -> "RiskDecision":
        return cls(
            action=RiskAction.BLOCK,
            stage=stage,
            adjusted_order=None,
            context_updates=dict(context_updates or {}),
            events=list(events or []),
        )


class BaseRiskRule(ABC):
    """风控规则基类。"""

    name: str = "base_risk_rule"
    priority: int = 100
    stages: tuple[RiskStage, ...] = (
        RiskStage.ORDER,
        RiskStage.BAR,
        RiskStage.PORTFOLIO,
    )

    def applies_to(self, stage: RiskStage) -> bool:
        return stage in self.stages

    @abstractmethod
    def check(self, context: RiskCheckContext) -> RiskDecision:
        """执行规则检查。"""
        raise NotImplementedError
