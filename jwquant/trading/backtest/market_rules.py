"""
市场规则。

当前先提供最小规则层，用于让回测内核不再把股票整手逻辑写死在引擎里。
"""
from __future__ import annotations

from dataclasses import dataclass

from jwquant.common.types import Direction


@dataclass
class BaseMarketRules:
    market: str
    lot_size: int = 1

    def normalize_quantity(self, quantity: int) -> int:
        if quantity <= 0:
            return 0
        return max((quantity // self.lot_size) * self.lot_size, 0)

    def calculate_sell_quantity(self, *, held_quantity: int, sellable_quantity: int) -> int:
        return self.normalize_quantity(min(held_quantity, sellable_quantity))

    def resolve_order_offset(self, *, direction: Direction, position_quantity: int) -> str:
        if direction == Direction.BUY:
            return "open_long"
        if direction == Direction.SELL:
            return "close_long"
        raise ValueError(f"unsupported direction: {direction}")

    def calculate_order_quantity(
        self,
        *,
        available_cash: float,
        reference_price: float,
        max_order_value: float,
        max_position_pct: float,
    ) -> int:
        if reference_price <= 0:
            return 0
        target_value = min(max_order_value, available_cash * max_position_pct)
        unit_cost = self.calculate_open_cost(reference_price=reference_price, quantity=1)
        if unit_cost <= 0:
            return 0
        raw_quantity = int(target_value / unit_cost)
        return self.normalize_quantity(raw_quantity)

    def calculate_buy_sellable_quantity(self, quantity: int) -> int:
        return self.normalize_quantity(quantity)

    def settle_sellable_quantity(self, quantity: int, sellable_quantity: int) -> int:
        return self.normalize_quantity(quantity)

    def calculate_open_cost(self, *, reference_price: float, quantity: int) -> float:
        return reference_price * quantity

    def calculate_margin(self, *, quantity: int, price: float) -> float:
        return 0.0

    def calculate_position_value(self, *, quantity: int, avg_price: float, current_price: float, margin: float) -> float:
        return quantity * current_price

    def calculate_exposure_per_unit(self, *, reference_price: float) -> float:
        return abs(reference_price)

    def calculate_risk_exposure(
        self,
        *,
        quantity: int,
        avg_price: float,
        current_price: float,
        margin: float,
    ) -> float:
        return abs(quantity) * self.calculate_exposure_per_unit(reference_price=current_price)

    def calculate_close_profit(
        self,
        *,
        position_quantity: int,
        close_quantity: int,
        avg_price: float,
        close_price: float,
    ) -> float:
        return (close_price - avg_price) * close_quantity


@dataclass
class StockMarketRules(BaseMarketRules):
    market: str = "stock"
    lot_size: int = 100

    def calculate_buy_sellable_quantity(self, quantity: int) -> int:
        return 0

    def settle_sellable_quantity(self, quantity: int, sellable_quantity: int) -> int:
        return self.normalize_quantity(quantity)


@dataclass
class FuturesMarketRules(BaseMarketRules):
    market: str = "futures"
    lot_size: int = 1
    contract_multiplier: float = 300.0
    margin_rate: float = 0.12

    def resolve_order_offset(self, *, direction: Direction, position_quantity: int) -> str:
        if direction == Direction.BUY:
            return "close_short" if position_quantity < 0 else "open_long"
        if direction == Direction.SELL:
            return "close_long" if position_quantity > 0 else "open_short"
        raise ValueError(f"unsupported direction: {direction}")

    def calculate_open_cost(self, *, reference_price: float, quantity: int) -> float:
        return self.calculate_margin(quantity=quantity, price=reference_price)

    def calculate_margin(self, *, quantity: int, price: float) -> float:
        return abs(quantity) * price * self.contract_multiplier * self.margin_rate

    def calculate_position_value(self, *, quantity: int, avg_price: float, current_price: float, margin: float) -> float:
        unrealized_pnl = (current_price - avg_price) * quantity * self.contract_multiplier
        return margin + unrealized_pnl

    def calculate_exposure_per_unit(self, *, reference_price: float) -> float:
        return abs(reference_price) * self.contract_multiplier

    def calculate_close_profit(
        self,
        *,
        position_quantity: int,
        close_quantity: int,
        avg_price: float,
        close_price: float,
    ) -> float:
        direction_sign = 1 if position_quantity > 0 else -1
        return (close_price - avg_price) * close_quantity * self.contract_multiplier * direction_sign


def build_market_rules(
    market: str,
    *,
    futures_contract_multiplier: float = 300.0,
    futures_margin_rate: float = 0.12,
) -> BaseMarketRules:
    normalized = str(market).strip().lower()
    if normalized == "stock":
        return StockMarketRules()
    if normalized == "futures":
        return FuturesMarketRules(
            contract_multiplier=futures_contract_multiplier,
            margin_rate=futures_margin_rate,
        )
    raise ValueError(f"unsupported backtest market: {market}")
