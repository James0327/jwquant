"""
自动化交易闭环

完整流程：信号触发 → 风控审核 → 下单执行 → 消息推送。
支持模拟盘/实盘切换。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from jwquant.common.types import Asset, Order, RiskEvent
from jwquant.trading.backtest.market_rules import BaseMarketRules, build_market_rules
from jwquant.trading.risk import (
    FuturesDirectionRule,
    MaxHoldingsRule,
    MaxOrderAmountRule,
    MaxPositionPctRule,
    MaxTotalExposureRule,
    NoNakedShortRule,
    RiskCheckContext,
    RiskConfig,
    RiskInterceptor,
)


@dataclass
class ExecutionRiskResult:
    order: Order | None
    events: list[RiskEvent]

    @property
    def blocked(self) -> bool:
        return self.order is None


@dataclass
class ExecutionRiskGuard:
    market: str
    risk_config: RiskConfig = field(default_factory=RiskConfig)
    futures_margin_rate: float = 0.12
    futures_contract_multiplier: float = 300.0
    market_rules: BaseMarketRules | None = None
    _interceptor: RiskInterceptor | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.market_rules is None:
            self.market_rules = build_market_rules(
                self.market,
                futures_margin_rate=self.futures_margin_rate,
                futures_contract_multiplier=self.futures_contract_multiplier,
            )

    def _build_interceptor(self) -> RiskInterceptor:
        if self._interceptor is None:
            rules = self.risk_config.apply_rule_priorities([
                MaxTotalExposureRule(self.risk_config.max_total_exposure),
            ])
            if self.risk_config.max_order_amount > 0:
                rules.insert(0, MaxOrderAmountRule(self.risk_config.max_order_amount))
            if self.risk_config.max_holdings > 0:
                rules.append(MaxHoldingsRule(self.risk_config.max_holdings))
            if self.market == "stock":
                rules.insert(0, MaxPositionPctRule(self.risk_config.max_single_weight))
                rules.insert(0, NoNakedShortRule())
            elif self.market == "futures":
                rules.insert(
                    0,
                    FuturesDirectionRule(
                        allow_long=self.risk_config.allow_futures_long,
                        allow_short=self.risk_config.allow_futures_short,
                    ),
                )
            self._interceptor = RiskInterceptor(
                rules=rules,
                conflict_policy=self.risk_config.conflict_policy,
            )
        return self._interceptor

    def validate_order(
        self,
        *,
        order: Order,
        dt: datetime,
        latest_prices: dict[str, float],
        asset: Asset | None = None,
        position: Any | None = None,
        portfolio_positions: dict[str, Any] | None = None,
        portfolio_equity: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionRiskResult:
        context = RiskCheckContext(
            dt=dt,
            market=self.market,
            code=order.code,
            bar_price=float(latest_prices.get(order.code, order.price)),
            order=order,
            asset=asset,
            position=position,
            portfolio_positions=dict(portfolio_positions or {}),
            portfolio_equity=float(portfolio_equity or (asset.total_asset if asset is not None else 0.0)),
            latest_prices=dict(latest_prices),
            metadata={
                **dict(metadata or {}),
                "contract_multiplier": self.market_rules.calculate_exposure_per_unit(reference_price=1.0),
                "exposure_multipliers": {
                    code: self.market_rules.calculate_exposure_per_unit(reference_price=1.0)
                    for code in set((portfolio_positions or {}).keys()) | set(latest_prices.keys()) | {order.code}
                },
                "exposure_model": "gross_notional",
            },
        )
        decision = self._build_interceptor().check_order(context)
        if decision.action.value == "allow":
            return ExecutionRiskResult(order=order, events=decision.events)
        if decision.action.value == "adjust" and decision.adjusted_order is not None:
            order.code = decision.adjusted_order.code
            order.direction = decision.adjusted_order.direction
            order.price = decision.adjusted_order.price
            order.volume = decision.adjusted_order.volume
            order.order_type = decision.adjusted_order.order_type
            order.offset = decision.adjusted_order.offset
            order.dt = decision.adjusted_order.dt
            return ExecutionRiskResult(order=order, events=decision.events)
        return ExecutionRiskResult(order=None, events=decision.events)
