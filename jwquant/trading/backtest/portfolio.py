"""
账户与持仓状态。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from jwquant.common.types import Asset
from jwquant.trading.backtest.market_rules import BaseMarketRules


@dataclass
class PositionState:
    quantity: int
    avg_price: float
    sellable_quantity: int = 0
    margin: float = 0.0


@dataclass
class Portfolio:
    initial_cash: float
    market_rules: BaseMarketRules
    cash: float = field(init=False)
    positions: dict[str, PositionState] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.cash = float(self.initial_cash)

    def buy(
        self,
        *,
        code: str,
        quantity: int,
        price: float,
        commission: float,
        sellable_quantity: int,
    ) -> None:
        total_cost = quantity * price + commission
        if total_cost > self.cash:
            raise ValueError("insufficient cash for buy order")

        current = self.positions.get(code)
        if current is None:
            self.positions[code] = PositionState(
                quantity=quantity,
                avg_price=price,
                sellable_quantity=sellable_quantity,
                margin=0.0,
            )
        else:
            total_quantity = current.quantity + quantity
            avg_price = (current.quantity * current.avg_price + quantity * price) / total_quantity
            self.positions[code] = PositionState(
                quantity=total_quantity,
                avg_price=avg_price,
                sellable_quantity=current.sellable_quantity + sellable_quantity,
                margin=0.0,
            )

        self.cash -= total_cost

    def sell(self, *, code: str, quantity: int, price: float, commission: float) -> float:
        current = self.positions.get(code)
        if current is None or current.quantity < quantity or current.sellable_quantity < quantity:
            raise ValueError("insufficient position for sell order")

        self.cash += quantity * price - commission
        realized_profit = (price - current.avg_price) * quantity - commission

        remaining = current.quantity - quantity
        if remaining <= 0:
            del self.positions[code]
        else:
            self.positions[code] = PositionState(
                quantity=remaining,
                avg_price=current.avg_price,
                sellable_quantity=current.sellable_quantity - quantity,
                margin=0.0,
            )

        return realized_profit

    def open_futures(self, *, code: str, quantity: int, price: float, commission: float, direction_sign: int) -> None:
        if quantity <= 0:
            raise ValueError("futures open quantity must be positive")
        signed_quantity = quantity * direction_sign
        margin = self.market_rules.calculate_margin(quantity=quantity, price=price)
        total_cost = margin + commission
        if total_cost > self.cash:
            raise ValueError("insufficient cash for futures order")

        current = self.positions.get(code)
        if current is None:
            self.positions[code] = PositionState(
                quantity=signed_quantity,
                avg_price=price,
                sellable_quantity=quantity,
                margin=margin,
            )
        else:
            if current.quantity == 0 or (current.quantity > 0) != (signed_quantity > 0):
                raise ValueError("opposite futures position must be closed before opening new side")
            total_quantity = abs(current.quantity) + quantity
            avg_price = (abs(current.quantity) * current.avg_price + quantity * price) / total_quantity
            self.positions[code] = PositionState(
                quantity=current.quantity + signed_quantity,
                avg_price=avg_price,
                sellable_quantity=abs(current.quantity + signed_quantity),
                margin=current.margin + margin,
            )

        self.cash -= total_cost

    def close_futures(self, *, code: str, quantity: int, price: float, commission: float) -> float:
        if quantity <= 0:
            raise ValueError("futures close quantity must be positive")

        current = self.positions.get(code)
        if current is None or abs(current.quantity) < quantity:
            raise ValueError("insufficient futures position for close order")

        released_margin = current.margin * quantity / abs(current.quantity)
        gross_profit = self.market_rules.calculate_close_profit(
            position_quantity=current.quantity,
            close_quantity=quantity,
            avg_price=current.avg_price,
            close_price=price,
        )
        realized_profit = gross_profit - commission
        self.cash += released_margin + realized_profit

        remaining = abs(current.quantity) - quantity
        if remaining <= 0:
            del self.positions[code]
        else:
            direction_sign = 1 if current.quantity > 0 else -1
            self.positions[code] = PositionState(
                quantity=remaining * direction_sign,
                avg_price=current.avg_price,
                sellable_quantity=remaining,
                margin=current.margin - released_margin,
            )

        return realized_profit

    def settle_positions(self, settle_sellable_quantity: Callable[[int, int], int]) -> None:
        for code, position in list(self.positions.items()):
            self.positions[code] = PositionState(
                quantity=position.quantity,
                avg_price=position.avg_price,
                sellable_quantity=settle_sellable_quantity(
                    abs(position.quantity),
                    position.sellable_quantity,
                ),
                margin=position.margin,
            )

    def calculate_equity(self, current_prices: dict[str, float]) -> float:
        position_value = 0.0
        for code, pos in self.positions.items():
            if code in current_prices:
                position_value += self.market_rules.calculate_position_value(
                    quantity=pos.quantity,
                    avg_price=pos.avg_price,
                    current_price=current_prices[code],
                    margin=pos.margin,
                )
        return self.cash + position_value

    def get_frozen_cash(self) -> float:
        return float(sum(position.margin for position in self.positions.values()))

    def get_position_exposure(self, code: str, current_price: float) -> float:
        position = self.positions.get(code)
        if position is None:
            return 0.0
        return self.market_rules.calculate_risk_exposure(
            quantity=position.quantity,
            avg_price=position.avg_price,
            current_price=current_price,
            margin=position.margin,
        )

    def calculate_gross_exposure(self, current_prices: dict[str, float]) -> float:
        gross_exposure = 0.0
        for code, position in self.positions.items():
            price = current_prices.get(code)
            if price is None:
                continue
            gross_exposure += self.market_rules.calculate_risk_exposure(
                quantity=position.quantity,
                avg_price=position.avg_price,
                current_price=price,
                margin=position.margin,
            )
        return gross_exposure

    def snapshot_positions(self) -> dict[str, dict[str, float]]:
        return {
            code: {
                "quantity": position.quantity,
                "avg_price": position.avg_price,
                "sellable_quantity": position.sellable_quantity,
                "margin": position.margin,
            }
            for code, position in self.positions.items()
        }

    def to_asset(self, current_prices: dict[str, float] | None = None) -> Asset:
        prices = current_prices or {}
        market_value = 0.0
        for code, pos in self.positions.items():
            if code in prices:
                market_value += self.market_rules.calculate_position_value(
                    quantity=pos.quantity,
                    avg_price=pos.avg_price,
                    current_price=prices[code],
                    margin=pos.margin,
                )
        return Asset(
            cash=self.cash,
            frozen_cash=self.get_frozen_cash(),
            market_value=market_value,
            total_asset=self.cash + market_value,
        )
