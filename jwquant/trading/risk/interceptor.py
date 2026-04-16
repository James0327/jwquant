"""
风控拦截器

风控规则不通过时阻断下单，记录拦截原因，支持盘前检查和盘中实时监控。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from jwquant.trading.risk.context import RiskCheckContext
from jwquant.trading.risk.rules import BaseRiskRule, RiskDecision, RiskStage


@dataclass
class RiskInterceptor:
    """统一风控拦截入口。"""

    rules: list[BaseRiskRule] = field(default_factory=list)
    conflict_policy: str = "priority_first"

    def __post_init__(self) -> None:
        allowed = {"priority_first"}
        if self.conflict_policy not in allowed:
            raise ValueError(f"unsupported conflict_policy: {self.conflict_policy}")

    def _iter_stage_rules(self, stage: RiskStage):
        indexed_rules = [
            (index, rule)
            for index, rule in enumerate(self.rules)
            if rule.applies_to(stage)
        ]
        indexed_rules.sort(key=lambda item: (getattr(item[1], "priority", 100), item[0]))
        for _, rule in indexed_rules:
            yield rule

    def add_rule(self, rule: BaseRiskRule) -> None:
        if not isinstance(rule, BaseRiskRule):
            raise TypeError(f"risk rule must inherit BaseRiskRule, got {type(rule)!r}")
        self.rules.append(rule)

    def add_order_rule(self, rule: BaseRiskRule) -> None:
        if not rule.applies_to(RiskStage.ORDER):
            raise ValueError(f"risk rule {rule.__class__.__name__} does not apply to order stage")
        self.add_rule(rule)

    def add_bar_rule(self, rule: BaseRiskRule) -> None:
        if not rule.applies_to(RiskStage.BAR):
            raise ValueError(f"risk rule {rule.__class__.__name__} does not apply to bar stage")
        self.add_rule(rule)

    def add_portfolio_rule(self, rule: BaseRiskRule) -> None:
        if not rule.applies_to(RiskStage.PORTFOLIO):
            raise ValueError(f"risk rule {rule.__class__.__name__} does not apply to portfolio stage")
        self.add_rule(rule)

    def _run_stage(self, stage: RiskStage, context: RiskCheckContext) -> RiskDecision:
        decision = RiskDecision.allow(stage=stage)
        current_context = context

        for rule in self._iter_stage_rules(stage):
            rule_decision = rule.check(current_context)
            if not isinstance(rule_decision, RiskDecision):
                raise TypeError(
                    f"risk rule {rule.__class__.__name__} must return RiskDecision, got {type(rule_decision)!r}"
                )
            decision = decision.merge(rule_decision)

            if rule_decision.adjusted_order is not None:
                current_context = current_context.with_order(rule_decision.adjusted_order)
            if rule_decision.context_updates:
                current_context = current_context.with_updates(**rule_decision.context_updates)

            if not decision.allowed:
                break

        return decision

    def check(self, context: RiskCheckContext) -> RiskDecision:
        """兼容入口，默认按下单阶段执行。"""
        return self.check_order(context)

    def check_order(self, context: RiskCheckContext) -> RiskDecision:
        return self._run_stage(RiskStage.ORDER, context)

    def check_bar(self, context: RiskCheckContext) -> RiskDecision:
        return self._run_stage(RiskStage.BAR, context)

    def check_portfolio(self, context: RiskCheckContext) -> RiskDecision:
        return self._run_stage(RiskStage.PORTFOLIO, context)
