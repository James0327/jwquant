"""
回测层组合风控兼容封装。

当前保留 `PortfolioRiskManager` 对外接口，
内部逻辑统一收敛到 `jwquant.trading.risk`。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from jwquant.common.types import Order, RiskEvent, Signal
from jwquant.trading.backtest.market_rules import BaseMarketRules
from jwquant.trading.backtest.portfolio import Portfolio
from jwquant.trading.risk import (
    FixedStopLossRule,
    FixedTakeProfitRule,
    FuturesDirectionRule,
    MaxFuturesMarginRatioRule,
    MaxHoldingsRule,
    MaxOrderAmountRule,
    MaxPositionPctRule,
    MaxTotalExposureRule,
    MaxDrawdownRule,
    NoNakedShortRule,
    RiskCheckContext,
    RiskDecision,
    RiskConfig,
    RiskInterceptor,
    TargetWeightsRule,
    TrailingStopRule,
)


@dataclass
class OrderValidationResult:
    order: Order | None
    events: list[RiskEvent]

    @property
    def blocked(self) -> bool:
        return self.order is None


@dataclass
class BarValidationResult:
    signals: list[Signal]
    events: list[RiskEvent]


@dataclass
class PortfolioRiskManager:
    market: str
    market_rules: BaseMarketRules
    risk_config: RiskConfig | None = None
    max_total_exposure: float = 1.0
    max_single_weight: float = 1.0
    max_futures_margin_ratio: float = 1.0
    max_holdings: int = 0
    max_order_amount: float = 0.0
    tolerance: float = 1e-4
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    trailing_stop_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    allow_futures_long: bool = True
    allow_futures_short: bool = True
    _bar_metadata: dict = field(default_factory=dict)
    _adjustment_interceptor: RiskInterceptor | None = field(default=None, init=False, repr=False)
    _validation_interceptor: RiskInterceptor | None = field(default=None, init=False, repr=False)
    _bar_interceptor: RiskInterceptor | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.risk_config is None:
            self.risk_config = RiskConfig(
                max_total_exposure=self.max_total_exposure,
                max_single_weight=self.max_single_weight,
                max_futures_margin_ratio=self.max_futures_margin_ratio,
                max_holdings=self.max_holdings,
                max_order_amount=self.max_order_amount,
                stop_loss_pct=self.stop_loss_pct,
                take_profit_pct=self.take_profit_pct,
                trailing_stop_pct=self.trailing_stop_pct,
                max_drawdown_pct=self.max_drawdown_pct,
                allow_futures_long=self.allow_futures_long,
                allow_futures_short=self.allow_futures_short,
            )
        else:
            self.max_total_exposure = self.risk_config.max_total_exposure
            self.max_single_weight = self.risk_config.max_single_weight
            self.max_futures_margin_ratio = self.risk_config.max_futures_margin_ratio
            self.max_holdings = self.risk_config.max_holdings
            self.max_order_amount = self.risk_config.max_order_amount
            self.stop_loss_pct = self.risk_config.stop_loss_pct
            self.take_profit_pct = self.risk_config.take_profit_pct
            self.trailing_stop_pct = self.risk_config.trailing_stop_pct
            self.max_drawdown_pct = self.risk_config.max_drawdown_pct
            self.allow_futures_long = self.risk_config.allow_futures_long
            self.allow_futures_short = self.risk_config.allow_futures_short

    def reset(self) -> None:
        self._bar_metadata = {}

    def _build_portfolio_context(
        self,
        *,
        dt: datetime,
        code: str,
        bar_price: float,
        order: Order | None = None,
        portfolio: Portfolio | None = None,
        current_prices: dict[str, float] | None = None,
        metadata: dict | None = None,
    ) -> RiskCheckContext:
        latest_prices = dict(current_prices or {})
        snapshot_positions = portfolio.snapshot_positions() if portfolio is not None else {}
        asset = portfolio.to_asset(latest_prices) if portfolio is not None else None
        portfolio_equity = portfolio.calculate_equity(latest_prices) if portfolio is not None else 0.0
        position_snapshot = snapshot_positions.get(code)
        tracked_codes = set(snapshot_positions.keys()) | set(latest_prices.keys())
        if order is not None:
            tracked_codes.add(order.code)
        exposure_multipliers = {
            tracked_code: self.market_rules.calculate_exposure_per_unit(reference_price=1.0)
            for tracked_code in tracked_codes
        }
        merged_metadata = {
            **(metadata or {}),
            "contract_multiplier": self.market_rules.calculate_exposure_per_unit(reference_price=1.0),
            "margin_rate": getattr(self.market_rules, "margin_rate", 0.0),
            "exposure_multipliers": exposure_multipliers,
            "exposure_model": "gross_notional",
        }
        return RiskCheckContext(
            dt=dt,
            market=self.market,
            code=code,
            bar_price=float(bar_price),
            order=order,
            asset=asset,
            position=position_snapshot,
            portfolio_positions=snapshot_positions,
            portfolio_equity=portfolio_equity,
            latest_prices=latest_prices,
            metadata=merged_metadata,
        )

    def _build_adjustment_interceptor(self) -> RiskInterceptor:
        if self._adjustment_interceptor is None:
            rules = self.risk_config.apply_rule_priorities([
                TargetWeightsRule(
                    max_single_weight=self.max_single_weight,
                    max_total_exposure=self.max_total_exposure,
                    allow_negative=self.market != "stock",
                )
            ])
            self._adjustment_interceptor = RiskInterceptor(
                rules=rules,
                conflict_policy=self.risk_config.conflict_policy,
            )
        return self._adjustment_interceptor

    def _build_validation_interceptor(self) -> RiskInterceptor:
        if self._validation_interceptor is None:
            rules = self.risk_config.apply_rule_priorities([
                MaxTotalExposureRule(
                    self.max_total_exposure,
                    tolerance=self.tolerance,
                ),
            ])
            if self.max_order_amount > 0:
                rules.insert(0, MaxOrderAmountRule(self.max_order_amount))
            if self.max_holdings > 0:
                rules.append(MaxHoldingsRule(self.max_holdings))
            if self.market == "stock":
                rules.insert(0, MaxPositionPctRule(self.max_single_weight))
                rules.insert(0, NoNakedShortRule())
            elif self.market == "futures":
                rules.insert(
                    0,
                    FuturesDirectionRule(
                        allow_long=self.allow_futures_long,
                        allow_short=self.allow_futures_short,
                    ),
                )
                if self.max_futures_margin_ratio > 0:
                    rules.append(MaxFuturesMarginRatioRule(self.max_futures_margin_ratio))
            self._validation_interceptor = RiskInterceptor(
                rules=rules,
                conflict_policy=self.risk_config.conflict_policy,
            )
        return self._validation_interceptor

    def _build_bar_interceptor(self) -> RiskInterceptor:
        if self._bar_interceptor is None:
            rules = []
            if self.stop_loss_pct > 0:
                rules.append(FixedStopLossRule(self.stop_loss_pct))
            if self.take_profit_pct > 0:
                rules.append(FixedTakeProfitRule(self.take_profit_pct))
            if self.trailing_stop_pct > 0:
                rules.append(TrailingStopRule(self.trailing_stop_pct))
            if self.max_drawdown_pct > 0:
                rules.append(MaxDrawdownRule(self.max_drawdown_pct))
            self.risk_config.apply_rule_priorities(rules)
            self._bar_interceptor = RiskInterceptor(
                rules=rules,
                conflict_policy=self.risk_config.conflict_policy,
            )
        return self._bar_interceptor

    def _apply_adjusted_order(
        self,
        *,
        order: Order,
        adjusted_order: Order,
    ) -> Order:
        order.code = adjusted_order.code
        order.direction = adjusted_order.direction
        order.price = adjusted_order.price
        order.volume = adjusted_order.volume
        order.order_type = adjusted_order.order_type
        order.offset = adjusted_order.offset
        order.dt = adjusted_order.dt
        return order

    def adjust_target_weights(
        self,
        *,
        raw_weights: dict[str, float],
        dt: datetime,
    ) -> tuple[dict[str, float], list[RiskEvent]]:
        context = self._build_portfolio_context(
            dt=dt,
            code="__portfolio__",
            bar_price=0.0,
            metadata={"target_weights": dict(raw_weights)},
        )
        decision = self._build_adjustment_interceptor().check_portfolio(context)
        adjusted_weights = raw_weights
        if decision.context_updates:
            updated_metadata = decision.context_updates.get("metadata", {})
            updated_target_weights = updated_metadata.get("target_weights")
            if isinstance(updated_target_weights, dict):
                adjusted_weights = {
                    code: float(weight)
                    for code, weight in updated_target_weights.items()
                }
        return adjusted_weights, decision.events

    def validate_order(
        self,
        *,
        order: Order,
        reference_price: float,
        portfolio: Portfolio,
        current_prices: dict[str, float],
        dt: datetime,
    ) -> OrderValidationResult:
        if order.volume <= 0:
            return OrderValidationResult(order=order, events=[])

        simulated_prices = dict(current_prices)
        simulated_prices[order.code] = reference_price
        context = self._build_portfolio_context(
            dt=dt,
            code=order.code,
            bar_price=reference_price,
            order=order,
            portfolio=portfolio,
            current_prices=simulated_prices,
        )
        decision = self._build_validation_interceptor().check_order(context)
        if decision.action.value == "allow":
            return OrderValidationResult(order=order, events=decision.events)
        if decision.action.value == "adjust" and decision.adjusted_order is not None:
            return OrderValidationResult(
                order=self._apply_adjusted_order(order=order, adjusted_order=decision.adjusted_order),
                events=decision.events,
            )
        return OrderValidationResult(order=None, events=decision.events)

    def check_bar(
        self,
        *,
        dt: datetime,
        portfolio: Portfolio,
        current_prices: dict[str, float],
    ) -> BarValidationResult:
        interceptor = self._build_bar_interceptor()
        if not interceptor.rules:
            return BarValidationResult(signals=[], events=[])

        primary_code = next(iter(current_prices.keys()), "__portfolio__")
        primary_price = float(current_prices.get(primary_code, 0.0))
        context = self._build_portfolio_context(
            dt=dt,
            code=primary_code,
            bar_price=primary_price,
            portfolio=portfolio,
            current_prices=current_prices,
            metadata=self._bar_metadata,
        )
        decision = interceptor.check_bar(context)
        updated_metadata = dict(self._bar_metadata)
        if decision.context_updates:
            updated_metadata = dict(decision.context_updates.get("metadata", updated_metadata))
        signals = list(updated_metadata.pop("risk_signals", []))
        self._bar_metadata = updated_metadata
        return BarValidationResult(signals=signals, events=decision.events)
