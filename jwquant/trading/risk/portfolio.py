"""
组合级风控规则。
"""
from __future__ import annotations

from jwquant.common.types import Direction, RiskEvent
from jwquant.trading.risk.context import RiskCheckContext
from jwquant.trading.risk.rules import BaseRiskRule, RiskDecision, RiskStage


def _extract_position_quantity(position: object) -> int:
    if position is None:
        return 0
    if isinstance(position, dict):
        if "quantity" in position:
            return int(position["quantity"])
        if "volume" in position:
            return int(position["volume"])
    if hasattr(position, "quantity"):
        return int(getattr(position, "quantity"))
    if hasattr(position, "volume"):
        return int(getattr(position, "volume"))
    return 0


def _resolve_price(context: RiskCheckContext, code: str) -> float:
    if code in context.latest_prices:
        return float(context.latest_prices[code])
    if code == context.code and context.bar_price > 0:
        return float(context.bar_price)
    return 0.0


def _resolve_exposure_multiplier(context: RiskCheckContext, code: str, position: object) -> float:
    metadata = context.metadata or {}
    multipliers = metadata.get("exposure_multipliers", {})
    if isinstance(multipliers, dict) and code in multipliers:
        return float(multipliers[code])
    if isinstance(position, dict):
        if "contract_multiplier" in position:
            return float(position["contract_multiplier"])
        if "exposure_multiplier" in position:
            return float(position["exposure_multiplier"])
    if "contract_multiplier" in metadata:
        return float(metadata["contract_multiplier"])
    if "exposure_multiplier" in metadata:
        return float(metadata["exposure_multiplier"])
    return 1.0


def _resolve_equity(context: RiskCheckContext) -> float:
    if context.portfolio_equity > 0:
        return float(context.portfolio_equity)
    if context.asset is not None and context.asset.total_asset > 0:
        return float(context.asset.total_asset)
    return 0.0


def _build_portfolio_event(
    *,
    risk_type: str,
    severity: str,
    code: str,
    message: str,
    dt,
    action_taken: str,
    source: str,
    metadata: dict | None = None,
) -> RiskEvent:
    return RiskEvent(
        risk_type=risk_type,
        severity=severity,
        code=code,
        message=message,
        dt=dt,
        action_taken=action_taken,
        category="portfolio",
        source=source,
        metadata=dict(metadata or {}),
    )


def _compute_portfolio_exposure(context: RiskCheckContext) -> float:
    exposure = 0.0
    for code, position in context.portfolio_positions.items():
        quantity = abs(_extract_position_quantity(position))
        if quantity <= 0:
            continue
        price = _resolve_price(context, code)
        if price <= 0:
            continue
        multiplier = _resolve_exposure_multiplier(context, code, position)
        exposure += quantity * price * multiplier
    return exposure


def _count_active_positions(context: RiskCheckContext) -> int:
    count = 0
    for position in context.portfolio_positions.values():
        if abs(_extract_position_quantity(position)) > 0:
            count += 1
    return count


def _is_opening_order(context: RiskCheckContext) -> bool:
    order = context.order
    if order is None:
        return False
    if order.offset in {"open_long", "open_short"}:
        return True
    if order.direction == Direction.BUY and not order.offset:
        return True
    return False


class MaxTotalExposureRule(BaseRiskRule):
    """限制组合总暴露。"""

    name = "max_total_exposure"
    stages = (RiskStage.ORDER, RiskStage.PORTFOLIO)

    def __init__(self, max_total_exposure: float, *, tolerance: float = 1e-8):
        self.max_total_exposure = float(max_total_exposure)
        self.tolerance = float(tolerance)

    def check(self, context: RiskCheckContext) -> RiskDecision:
        equity = _resolve_equity(context)
        if equity <= 0 or self.max_total_exposure <= 0:
            return RiskDecision.allow(stage=RiskStage.ORDER if context.order else RiskStage.PORTFOLIO)

        exposure = _compute_portfolio_exposure(context)
        stage = RiskStage.ORDER if context.order is not None else RiskStage.PORTFOLIO
        order_exposure = 0.0
        order_multiplier = 1.0

        if context.order is not None and _is_opening_order(context):
            price = context.order.price if context.order.price > 0 else _resolve_price(context, context.order.code)
            order_multiplier = _resolve_exposure_multiplier(
                context,
                context.order.code,
                context.portfolio_positions.get(context.order.code),
            )
            order_exposure = abs(context.order.volume) * max(price, 0.0) * order_multiplier
            exposure += order_exposure

        exposure_ratio = exposure / equity if equity > 0 else 0.0
        if exposure_ratio <= self.max_total_exposure + self.tolerance:
            return RiskDecision.allow(stage=stage)

        event = _build_portfolio_event(
            risk_type="MAX_TOTAL_EXPOSURE",
            severity="ERROR",
            code=context.code or "__portfolio__",
            message=f"组合总暴露 {exposure_ratio:.4f} 超过上限 {self.max_total_exposure:.4f}",
            dt=context.dt,
            action_taken="BLOCKED",
            source=self.name,
            metadata={
                "exposure_ratio": exposure_ratio,
                "max_total_exposure": self.max_total_exposure,
                "portfolio_exposure": exposure,
                "portfolio_equity": equity,
                "exposure_model": "gross_notional",
                "order_exposure": order_exposure,
                "exposure_multiplier": order_multiplier,
            },
        )
        return RiskDecision.block(stage=stage, events=[event])


class MaxHoldingsRule(BaseRiskRule):
    """限制组合持仓标的数量。"""

    name = "max_holdings"
    stages = (RiskStage.ORDER, RiskStage.PORTFOLIO)

    def __init__(self, max_holdings: int):
        self.max_holdings = int(max_holdings)

    def check(self, context: RiskCheckContext) -> RiskDecision:
        if self.max_holdings <= 0:
            return RiskDecision.allow(stage=RiskStage.ORDER if context.order else RiskStage.PORTFOLIO)

        active_count = _count_active_positions(context)
        stage = RiskStage.ORDER if context.order is not None else RiskStage.PORTFOLIO

        if context.order is None:
            if active_count <= self.max_holdings:
                return RiskDecision.allow(stage=stage)
            event = _build_portfolio_event(
                risk_type="MAX_HOLDINGS",
                severity="ERROR",
                code="__portfolio__",
                message=f"当前持仓标的数 {active_count} 超过上限 {self.max_holdings}",
                dt=context.dt,
                action_taken="BLOCKED",
                source=self.name,
                metadata={"active_count": active_count, "max_holdings": self.max_holdings},
            )
            return RiskDecision.block(stage=stage, events=[event])

        if not _is_opening_order(context):
            return RiskDecision.allow(stage=stage)

        already_holding = abs(_extract_position_quantity(context.portfolio_positions.get(context.order.code))) > 0
        projected_count = active_count if already_holding else active_count + 1
        if projected_count <= self.max_holdings:
            return RiskDecision.allow(stage=stage)

        event = _build_portfolio_event(
            risk_type="MAX_HOLDINGS",
            severity="ERROR",
            code=context.order.code,
            message=f"开仓后持仓标的数 {projected_count} 将超过上限 {self.max_holdings}",
            dt=context.dt,
            action_taken="BLOCKED",
            source=self.name,
            metadata={"projected_count": projected_count, "max_holdings": self.max_holdings},
        )
        return RiskDecision.block(stage=stage, events=[event])


class MaxFuturesMarginRatioRule(BaseRiskRule):
    """限制期货组合保证金占权益比例。"""

    name = "max_futures_margin_ratio"
    stages = (RiskStage.ORDER, RiskStage.PORTFOLIO)

    def __init__(self, max_margin_ratio: float, *, tolerance: float = 1e-8):
        self.max_margin_ratio = float(max_margin_ratio)
        self.tolerance = float(tolerance)

    def _resolve_margin_rate(self, context: RiskCheckContext) -> float:
        metadata = context.metadata or {}
        return float(metadata.get("margin_rate", 0.0))

    def _compute_existing_margin(self, context: RiskCheckContext) -> float:
        total_margin = 0.0
        margin_rate = self._resolve_margin_rate(context)
        for code, position in context.portfolio_positions.items():
            if isinstance(position, dict) and "margin" in position:
                total_margin += float(position.get("margin", 0.0))
                continue
            quantity = abs(_extract_position_quantity(position))
            if quantity <= 0:
                continue
            price = _resolve_price(context, code)
            if price <= 0 or margin_rate <= 0:
                continue
            multiplier = _resolve_exposure_multiplier(context, code, position)
            total_margin += quantity * price * multiplier * margin_rate
        return total_margin

    def check(self, context: RiskCheckContext) -> RiskDecision:
        stage = RiskStage.ORDER if context.order is not None else RiskStage.PORTFOLIO
        if str(context.market).lower() != "futures":
            return RiskDecision.allow(stage=stage)
        if self.max_margin_ratio <= 0:
            return RiskDecision.allow(stage=stage)

        equity = _resolve_equity(context)
        if equity <= 0:
            return RiskDecision.allow(stage=stage)

        margin_rate = self._resolve_margin_rate(context)
        if margin_rate <= 0:
            return RiskDecision.allow(stage=stage)

        existing_margin = self._compute_existing_margin(context)
        order_margin = 0.0
        if context.order is not None and _is_opening_order(context):
            price = context.order.price if context.order.price > 0 else _resolve_price(context, context.order.code)
            multiplier = _resolve_exposure_multiplier(
                context,
                context.order.code,
                context.portfolio_positions.get(context.order.code),
            )
            order_margin = abs(context.order.volume) * max(price, 0.0) * multiplier * margin_rate

        margin_ratio = (existing_margin + order_margin) / equity
        if margin_ratio <= self.max_margin_ratio + self.tolerance:
            return RiskDecision.allow(stage=stage)

        event = _build_portfolio_event(
            risk_type="MAX_FUTURES_MARGIN_RATIO",
            severity="ERROR",
            code=context.code or "__portfolio__",
            message=f"期货保证金占比 {margin_ratio:.4f} 超过上限 {self.max_margin_ratio:.4f}",
            dt=context.dt,
            action_taken="BLOCKED",
            source=self.name,
            metadata={
                "margin_ratio": margin_ratio,
                "max_futures_margin_ratio": self.max_margin_ratio,
                "existing_margin": existing_margin,
                "order_margin": order_margin,
                "portfolio_equity": equity,
            },
        )
        return RiskDecision.block(stage=stage, events=[event])


class TargetWeightsRule(BaseRiskRule):
    """裁剪组合目标权重。"""

    name = "target_weights"
    stages = (RiskStage.PORTFOLIO,)

    def __init__(
        self,
        *,
        max_single_weight: float = 1.0,
        max_total_exposure: float = 1.0,
        allow_negative: bool = False,
    ):
        self.max_single_weight = float(max_single_weight)
        self.max_total_exposure = float(max_total_exposure)
        self.allow_negative = bool(allow_negative)

    def check(self, context: RiskCheckContext) -> RiskDecision:
        raw_target_weights = context.metadata.get("target_weights")
        if not isinstance(raw_target_weights, dict) or not raw_target_weights:
            return RiskDecision.allow(stage=RiskStage.PORTFOLIO)

        adjusted_weights: dict[str, float] = {}
        events: list[RiskEvent] = []

        for code, raw_weight in raw_target_weights.items():
            weight = float(raw_weight)
            if str(context.market).lower() == "stock" and not self.allow_negative and weight < 0:
                events.append(
                    _build_portfolio_event(
                        risk_type="NEGATIVE_TARGET_WEIGHT",
                        severity="WARNING",
                        code=code,
                        message=f"{code} 负权重在当前市场不支持，已裁剪为 0",
                        dt=context.dt,
                        action_taken="ADJUSTED",
                        source=self.name,
                        metadata={"raw_weight": raw_weight, "adjusted_weight": 0.0},
                    )
                )
                weight = 0.0

            if abs(weight) > self.max_single_weight:
                adjusted = self.max_single_weight if weight >= 0 else -self.max_single_weight
                events.append(
                    _build_portfolio_event(
                        risk_type="MAX_SINGLE_WEIGHT",
                        severity="WARNING",
                        code=code,
                        message=f"{code} 目标权重超过单标的上限，已裁剪",
                        dt=context.dt,
                        action_taken="ADJUSTED",
                        source=self.name,
                        metadata={"raw_weight": raw_weight, "adjusted_weight": adjusted},
                    )
                )
                weight = adjusted

            adjusted_weights[code] = weight

        gross_weight = sum(abs(weight) for weight in adjusted_weights.values())
        if gross_weight > self.max_total_exposure and gross_weight > 0:
            scale = self.max_total_exposure / gross_weight
            adjusted_weights = {
                code: weight * scale
                for code, weight in adjusted_weights.items()
            }
            events.append(
                _build_portfolio_event(
                    risk_type="MAX_TOTAL_EXPOSURE",
                    severity="WARNING",
                    code="__portfolio__",
                    message="组合目标总暴露超过上限，已按比例缩放",
                    dt=context.dt,
                    action_taken="ADJUSTED",
                    source=self.name,
                    metadata={
                        "gross_weight": gross_weight,
                        "max_total_exposure": self.max_total_exposure,
                        "scale": scale,
                    },
                )
            )

        if adjusted_weights == raw_target_weights:
            return RiskDecision.allow(stage=RiskStage.PORTFOLIO)

        updated_metadata = dict(context.metadata)
        updated_metadata["target_weights"] = adjusted_weights
        return RiskDecision.adjust(
            stage=RiskStage.PORTFOLIO,
            context_updates={"metadata": updated_metadata},
            events=events,
        )
