"""
统一止盈止损规则。
"""
from __future__ import annotations

from jwquant.common.types import Signal, SignalType, RiskEvent
from jwquant.trading.risk.context import RiskCheckContext
from jwquant.trading.risk.rules import BaseRiskRule, RiskDecision, RiskStage


def _resolve_price(context: RiskCheckContext, code: str) -> float:
    if code in context.latest_prices and context.latest_prices[code] > 0:
        return float(context.latest_prices[code])
    if code == context.code and context.bar_price > 0:
        return float(context.bar_price)
    return 0.0


def _resolve_position(context: RiskCheckContext, code: str) -> object | None:
    if code == context.code and context.position is not None:
        return context.position
    return context.portfolio_positions.get(code)


def _extract_quantity(position: object | None) -> int:
    if position is None:
        return 0
    if isinstance(position, dict):
        if "quantity" in position:
            return int(position["quantity"])
        if "volume" in position:
            return int(position["volume"])
        return 0
    if hasattr(position, "quantity"):
        return int(getattr(position, "quantity"))
    if hasattr(position, "volume"):
        return int(getattr(position, "volume"))
    return 0


def _extract_avg_price(position: object | None) -> float:
    if position is None:
        return 0.0
    if isinstance(position, dict):
        if "avg_price" in position:
            return float(position["avg_price"])
        if "cost_price" in position:
            return float(position["cost_price"])
        return 0.0
    if hasattr(position, "avg_price"):
        return float(getattr(position, "avg_price"))
    if hasattr(position, "cost_price"):
        return float(getattr(position, "cost_price"))
    return 0.0


def _get_risk_state(metadata: dict) -> dict:
    state = metadata.get("risk_state", {})
    if isinstance(state, dict):
        return dict(state)
    return {}


def _with_risk_state(metadata: dict, **updates) -> dict:
    updated = dict(metadata)
    state = _get_risk_state(updated)
    state.update(updates)
    updated["risk_state"] = state
    return updated


def _build_stop_event(
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
        category="stop",
        source=source,
        metadata=dict(metadata or {}),
    )


def _append_risk_signal(context: RiskCheckContext, signal: Signal) -> dict:
    metadata = dict(context.metadata)
    risk_signals = list(metadata.get("risk_signals", []))
    for existing_signal in risk_signals:
        if not isinstance(existing_signal, Signal):
            continue
        if (
            existing_signal.code == signal.code
            and existing_signal.dt == signal.dt
            and existing_signal.signal_type == signal.signal_type
            and existing_signal.reason == signal.reason
        ):
            metadata["risk_signals"] = risk_signals
            return metadata
    risk_signals.append(signal)
    metadata["risk_signals"] = risk_signals
    return metadata


def _append_risk_signals(context: RiskCheckContext, signals: list[Signal]) -> dict:
    metadata = dict(context.metadata)
    for signal in signals:
        metadata = _append_risk_signal(context.with_updates(metadata=metadata), signal)
    return metadata


def _build_exit_signal(*, code: str, dt, quantity: int, price: float, reason: str) -> Signal:
    signal_type = SignalType.SELL if quantity > 0 else SignalType.BUY
    return Signal(
        code=code,
        dt=dt,
        signal_type=signal_type,
        price=price,
        strength=1.0,
        reason=reason,
    )


def _iter_active_positions(context: RiskCheckContext) -> list[tuple[str, object]]:
    positions: list[tuple[str, object]] = []
    seen: set[str] = set()
    if context.code:
        position = _resolve_position(context, context.code)
        if _extract_quantity(position) != 0:
            positions.append((context.code, position))
            seen.add(context.code)
    for code, position in context.portfolio_positions.items():
        if code in seen:
            continue
        if _extract_quantity(position) != 0:
            positions.append((code, position))
    return positions


def _build_single_position_exit_decision(
    *,
    context: RiskCheckContext,
    risk_type: str,
    severity: str,
    reason_template: str,
    message_template: str,
    metadata_builder,
    trigger_predicate,
) -> RiskDecision:
    signals: list[Signal] = []
    events: list[RiskEvent] = []

    for code, position in _iter_active_positions(context):
        quantity = _extract_quantity(position)
        avg_price = _extract_avg_price(position)
        current_price = _resolve_price(context, code)
        if quantity == 0 or avg_price <= 0 or current_price <= 0:
            continue
        if not trigger_predicate(quantity, avg_price, current_price):
            continue

        signals.append(
            _build_exit_signal(
                code=code,
                dt=context.dt,
                quantity=quantity,
                price=current_price,
                reason=reason_template,
            )
        )
        events.append(
            _build_stop_event(
                risk_type=risk_type,
                severity=severity,
                code=code,
                message=message_template.format(code=code),
                dt=context.dt,
                action_taken="SIGNALLED",
                source=risk_type.lower(),
                metadata=metadata_builder(
                    code=code,
                    quantity=quantity,
                    avg_price=avg_price,
                    current_price=current_price,
                ),
            )
        )

    if not events:
        return RiskDecision.allow(stage=RiskStage.BAR)

    return RiskDecision.adjust(
        stage=RiskStage.BAR,
        context_updates={"metadata": _append_risk_signals(context, signals)},
        events=events,
    )


class FixedStopLossRule(BaseRiskRule):
    """固定止损规则。"""

    name = "fixed_stop_loss"
    stages = (RiskStage.BAR,)

    def __init__(self, stop_loss_pct: float):
        self.stop_loss_pct = float(stop_loss_pct)

    def check(self, context: RiskCheckContext) -> RiskDecision:
        if self.stop_loss_pct <= 0:
            return RiskDecision.allow(stage=RiskStage.BAR)
        return _build_single_position_exit_decision(
            context=context,
            risk_type="FIXED_STOP_LOSS",
            severity="WARNING",
            reason_template=f"统一止损触发 pct={self.stop_loss_pct:.4f}",
            message_template="{code} 触发固定止损",
            metadata_builder=lambda **kwargs: {
                "stop_loss_pct": self.stop_loss_pct,
                "avg_price": kwargs["avg_price"],
                "current_price": kwargs["current_price"],
            },
            trigger_predicate=lambda quantity, avg_price, current_price: (
                quantity > 0 and current_price <= avg_price * (1 - self.stop_loss_pct)
            ) or (
                quantity < 0 and current_price >= avg_price * (1 + self.stop_loss_pct)
            ),
        )


class FixedTakeProfitRule(BaseRiskRule):
    """固定止盈规则。"""

    name = "fixed_take_profit"
    stages = (RiskStage.BAR,)

    def __init__(self, take_profit_pct: float):
        self.take_profit_pct = float(take_profit_pct)

    def check(self, context: RiskCheckContext) -> RiskDecision:
        if self.take_profit_pct <= 0:
            return RiskDecision.allow(stage=RiskStage.BAR)
        return _build_single_position_exit_decision(
            context=context,
            risk_type="FIXED_TAKE_PROFIT",
            severity="WARNING",
            reason_template=f"统一止盈触发 pct={self.take_profit_pct:.4f}",
            message_template="{code} 触发固定止盈",
            metadata_builder=lambda **kwargs: {
                "take_profit_pct": self.take_profit_pct,
                "avg_price": kwargs["avg_price"],
                "current_price": kwargs["current_price"],
            },
            trigger_predicate=lambda quantity, avg_price, current_price: (
                quantity > 0 and current_price >= avg_price * (1 + self.take_profit_pct)
            ) or (
                quantity < 0 and current_price <= avg_price * (1 - self.take_profit_pct)
            ),
        )


class TrailingStopRule(BaseRiskRule):
    """移动止损规则。"""

    name = "trailing_stop"
    stages = (RiskStage.BAR,)

    def __init__(self, trailing_pct: float):
        self.trailing_pct = float(trailing_pct)

    def check(self, context: RiskCheckContext) -> RiskDecision:
        if self.trailing_pct <= 0:
            return RiskDecision.allow(stage=RiskStage.BAR)
        metadata = dict(context.metadata)
        state = _get_risk_state(metadata)
        anchors = dict(state.get("trailing_anchor_prices", metadata.get("trailing_anchor_prices", {})))
        signals: list[Signal] = []
        events: list[RiskEvent] = []

        for code, position in _iter_active_positions(context):
            quantity = _extract_quantity(position)
            avg_price = _extract_avg_price(position)
            current_price = _resolve_price(context, code)
            if quantity == 0 or current_price <= 0:
                continue

            default_anchor = avg_price if avg_price > 0 else current_price
            previous_anchor = float(anchors.get(code, default_anchor))
            updated_anchor = max(previous_anchor, current_price) if quantity > 0 else min(previous_anchor, current_price)
            anchors[code] = updated_anchor

            triggered = (
                quantity > 0 and current_price <= updated_anchor * (1 - self.trailing_pct)
            ) or (
                quantity < 0 and current_price >= updated_anchor * (1 + self.trailing_pct)
            )
            if not triggered:
                continue

            signals.append(
                _build_exit_signal(
                    code=code,
                    dt=context.dt,
                    quantity=quantity,
                    price=current_price,
                    reason=f"移动止损触发 pct={self.trailing_pct:.4f}",
                )
            )
            events.append(
                _build_stop_event(
                    risk_type="TRAILING_STOP",
                    severity="WARNING",
                    code=code,
                    message=f"{code} 触发移动止损",
                    dt=context.dt,
                    action_taken="SIGNALLED",
                    source=self.name,
                    metadata={
                        "trailing_pct": self.trailing_pct,
                        "anchor_price": updated_anchor,
                        "current_price": current_price,
                    },
                )
            )

        metadata = _with_risk_state(metadata, trailing_anchor_prices=anchors)
        if not events:
            return RiskDecision.allow(
                stage=RiskStage.BAR,
                context_updates={"metadata": metadata},
            )

        metadata = _append_risk_signals(context.with_updates(metadata=metadata), signals)
        return RiskDecision.adjust(
            stage=RiskStage.BAR,
            context_updates={"metadata": metadata},
            events=events,
        )


class MaxDrawdownRule(BaseRiskRule):
    """组合最大回撤止损。"""

    name = "max_drawdown"
    stages = (RiskStage.BAR,)

    def __init__(self, max_drawdown_pct: float):
        self.max_drawdown_pct = float(max_drawdown_pct)

    def check(self, context: RiskCheckContext) -> RiskDecision:
        if self.max_drawdown_pct <= 0:
            return RiskDecision.allow(stage=RiskStage.BAR)
        if context.portfolio_equity <= 0:
            return RiskDecision.allow(stage=RiskStage.BAR)

        metadata = dict(context.metadata)
        state = _get_risk_state(metadata)
        peak_equity = float(state.get("portfolio_peak_equity", metadata.get("portfolio_peak_equity", context.portfolio_equity)))
        peak_equity = max(peak_equity, context.portfolio_equity)
        metadata = _with_risk_state(metadata, portfolio_peak_equity=peak_equity)
        drawdown = 0.0 if peak_equity <= 0 else 1 - float(context.portfolio_equity) / peak_equity

        if drawdown < self.max_drawdown_pct:
            return RiskDecision.allow(
                stage=RiskStage.BAR,
                context_updates={"metadata": metadata},
            )

        risk_signals: list[Signal] = []
        events: list[RiskEvent] = []
        for code, position in _iter_active_positions(context):
            quantity = _extract_quantity(position)
            current_price = _resolve_price(context, code)
            if quantity == 0 or current_price <= 0:
                continue
            signal = _build_exit_signal(
                code=code,
                dt=context.dt,
                quantity=quantity,
                price=current_price,
                reason=f"组合最大回撤触发 pct={self.max_drawdown_pct:.4f}",
            )
            risk_signals.append(signal)
            events.append(
                _build_stop_event(
                    risk_type="MAX_DRAWDOWN",
                    severity="ERROR",
                    code=code,
                    message=f"{code} 因组合最大回撤触发统一退出",
                    dt=context.dt,
                    action_taken="SIGNALLED",
                    source=self.name,
                    metadata={
                        "max_drawdown_pct": self.max_drawdown_pct,
                        "drawdown": drawdown,
                        "portfolio_peak_equity": peak_equity,
                        "portfolio_equity": context.portfolio_equity,
                    },
                )
            )

        if not events:
            return RiskDecision.allow(
                stage=RiskStage.BAR,
                context_updates={"metadata": metadata},
            )

        metadata = _append_risk_signals(context.with_updates(metadata=metadata), risk_signals)
        return RiskDecision.adjust(
            stage=RiskStage.BAR,
            context_updates={"metadata": metadata},
            events=events,
        )
