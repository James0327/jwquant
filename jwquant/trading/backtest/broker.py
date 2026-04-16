"""
简易撮合器。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jwquant.common.types import Direction, Order, OrderStatus, OrderType, Signal
from jwquant.trading.backtest.market_rules import BaseMarketRules
from jwquant.trading.backtest.portfolio import Portfolio


@dataclass
class SimBroker:
    commission_rate: float
    slippage: float
    market_rules: BaseMarketRules
    max_position_pct: float = 0.1
    max_order_value: float = 100000.0

    def _execution_price(self, direction: Direction, reference_price: float) -> float:
        # 回测里把滑点建模为“成交方向上的不利价格偏移”：
        # 买入比参考价更贵，卖出比参考价更便宜。
        if direction == Direction.BUY:
            return reference_price * (1 + self.slippage)
        if direction == Direction.SELL:
            return reference_price * (1 - self.slippage)
        return reference_price

    def _can_fill_limit_order(self, order: Order, reference_price: float) -> bool:
        if order.direction == Direction.BUY:
            return order.price >= reference_price
        if order.direction == Direction.SELL:
            return order.price <= reference_price
        return False

    def calculate_order_quantity(self, signal: Signal, reference_price: float, portfolio: Portfolio) -> int:
        current = portfolio.positions.get(signal.code)
        position_quantity = 0 if current is None else current.quantity
        offset = self.market_rules.resolve_order_offset(
            direction=Direction.BUY if signal.signal_type.name == "BUY" else Direction.SELL,
            position_quantity=position_quantity,
        )

        if offset == "close_long":
            if current is None:
                return 0
            return self.market_rules.calculate_sell_quantity(
                held_quantity=abs(current.quantity),
                sellable_quantity=current.sellable_quantity,
            )
        if offset == "close_short":
            return 0 if current is None else abs(current.quantity)
        if offset in {"open_long", "open_short"}:
            # 这里先用 broker 自己的金额约束估算“最多能下多少”，
            # 后面统一风控层还会再按 max_order_amount / 暴露等规则做二次校验。
            return self.market_rules.calculate_order_quantity(
                available_cash=portfolio.cash,
                reference_price=reference_price,
                max_order_value=self.max_order_value,
                max_position_pct=self.max_position_pct,
            )
        return 0

    def resolve_order_offset(self, signal: Signal, portfolio: Portfolio) -> str:
        current = portfolio.positions.get(signal.code)
        position_quantity = 0 if current is None else current.quantity
        return self.market_rules.resolve_order_offset(
            direction=Direction.BUY if signal.signal_type.name == "BUY" else Direction.SELL,
            position_quantity=position_quantity,
        )

    def execute_order(self, order: Order, reference_price: float, portfolio: Portfolio) -> dict[str, Any] | None:
        order.status = OrderStatus.SUBMITTED
        if order.volume <= 0:
            order.status = OrderStatus.REJECTED
            return None
        if order.order_type == OrderType.LIMIT and not self._can_fill_limit_order(order, reference_price):
            order.status = OrderStatus.CANCELLED
            return None

        executed_price = self._execution_price(order.direction, reference_price)
        # 当前回测的手续费模型保持最小口径：佣金 = 成交额 * commission_rate。
        # 这里先不额外引入印花税、最低佣金、分市场差异费率，避免和现有结果口径冲突。
        commission = order.volume * executed_price * self.commission_rate

        if order.offset == "open_long":
            if self.market_rules.market == "futures":
                try:
                    portfolio.open_futures(
                        code=order.code,
                        quantity=order.volume,
                        price=executed_price,
                        commission=commission,
                        direction_sign=1,
                    )
                except ValueError:
                    order.status = OrderStatus.REJECTED
                    return None
            else:
                try:
                    portfolio.buy(
                        code=order.code,
                        quantity=order.volume,
                        price=executed_price,
                        commission=commission,
                        sellable_quantity=self.market_rules.calculate_buy_sellable_quantity(order.volume),
                    )
                except ValueError:
                    order.status = OrderStatus.REJECTED
                    return None
            realized_profit = 0.0
        elif order.offset == "open_short":
            try:
                portfolio.open_futures(
                    code=order.code,
                    quantity=order.volume,
                    price=executed_price,
                    commission=commission,
                    direction_sign=-1,
                )
            except ValueError:
                order.status = OrderStatus.REJECTED
                return None
            realized_profit = 0.0
        elif order.offset == "close_long":
            if self.market_rules.market == "futures":
                try:
                    realized_profit = portfolio.close_futures(
                        code=order.code,
                        quantity=order.volume,
                        price=executed_price,
                        commission=commission,
                    )
                except ValueError:
                    order.status = OrderStatus.REJECTED
                    return None
            else:
                try:
                    realized_profit = portfolio.sell(
                        code=order.code,
                        quantity=order.volume,
                        price=executed_price,
                        commission=commission,
                    )
                except ValueError:
                    order.status = OrderStatus.REJECTED
                    return None
        elif order.offset == "close_short":
            try:
                realized_profit = portfolio.close_futures(
                    code=order.code,
                    quantity=order.volume,
                    price=executed_price,
                    commission=commission,
                )
            except ValueError:
                order.status = OrderStatus.REJECTED
                return None
        else:
            order.status = OrderStatus.REJECTED
            return None

        order.status = OrderStatus.FILLED
        return {
            "order_id": order.order_id,
            "date": order.dt,
            "code": order.code,
            "direction": order.direction.name,
            "offset": order.offset,
            "price": executed_price,
            "quantity": order.volume,
            "profit": realized_profit,
            "commission": commission,
            "slippage": abs(executed_price - reference_price) * order.volume,
        }
