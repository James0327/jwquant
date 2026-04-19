"""
简易回测引擎

当前提供最小可用的单账户、单策略、按 Bar 驱动的回测能力。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from jwquant.common.types import Bar, Direction, Order, OrderType, OrderStatus, RiskEvent, Signal, SignalType
from jwquant.trading.backtest.broker import SimBroker
from jwquant.trading.backtest.market_rules import build_market_rules
from jwquant.trading.backtest.order import build_order_from_signal
from jwquant.trading.backtest.portfolio import Portfolio
from jwquant.trading.backtest.recorder import BacktestRecorder
from jwquant.trading.backtest.risk import PortfolioRiskManager
from jwquant.trading.backtest.stats import calculate_performance
from jwquant.trading.risk import RiskConfig


@dataclass
class BacktestConfig:
    """回测核心配置。

    金额相关字段集中放在这里，便于脚本层统一从配置文件注入：
    - ``commission_rate``: 佣金费率，成交时按成交额比例收取
    - ``slippage``: 滑点比例，成交价会按买卖方向做不利偏移
    - ``max_order_value``: broker 估算单笔可下金额时使用的第一层限制
    - ``futures_margin_rate`` / ``futures_contract_multiplier``:
      期货开仓手数、保证金占用和盈亏计算的基础参数
    """

    initial_capital: float = 1_000_000
    commission_rate: float = 0.0003
    slippage: float = 0.0001
    market: str = "stock"
    max_position_pct: float = 0.1
    max_order_value: float = 100000.0
    futures_margin_rate: float = 0.12
    futures_contract_multiplier: float = 300.0
    portfolio_weights: dict[str, float] | None = None
    rebalance_frequency: str = "none"
    rebalance_tolerance: float = 0.02
    risk_max_total_exposure: float = 1.0
    risk_max_single_weight: float = 1.0
    risk_max_futures_margin_ratio: float = 1.0
    risk_max_holdings: int = 0
    risk_max_order_amount: float = 0.0
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    trailing_stop_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    buy_reject_threshold_pct: float = 0.0
    sell_reject_threshold_pct: float = 0.0
    limit_up_pct: float = 0.1
    limit_down_pct: float = 0.1
    risk_conflict_policy: str = "priority_first"
    risk_rule_priorities: dict[str, int] | None = None


@dataclass
class PendingSignalIntent:
    signal: Signal
    quantity: int | None = None
    offset: str | None = None


class SimpleBacktester:
    """简易回测引擎。

    设计目标：
    - 先复用现有 `strategy.on_bar(bar)` 接口
    - 提供脚本和测试可复用的最小回测内核
    - 暂时聚焦单账户、单标的、按 Bar 顺序驱动
    """

    def __init__(self, config: BacktestConfig | None = None, initial_capital: float | None = None):
        if config is None:
            config = BacktestConfig(
                initial_capital=initial_capital if initial_capital is not None else 1_000_000,
            )
        elif initial_capital is not None:
            config.initial_capital = initial_capital

        self.config = config
        self.initial_capital = config.initial_capital
        self.market_rules = build_market_rules(
            config.market,
            futures_contract_multiplier=config.futures_contract_multiplier,
            futures_margin_rate=config.futures_margin_rate,
        )
        self.portfolio = Portfolio(
            initial_cash=config.initial_capital,
            market_rules=self.market_rules,
        )
        # broker 只负责把“金额参数”转换成成交价、佣金和可下单量，
        # 更高层的统一风控金额限制仍走 PortfolioRiskManager。
        self.broker = SimBroker(
            commission_rate=config.commission_rate,
            slippage=config.slippage,
            market_rules=self.market_rules,
            max_position_pct=config.max_position_pct,
            max_order_value=config.max_order_value,
        )
        self.recorder = BacktestRecorder()
        risk_config = RiskConfig(
            max_total_exposure=config.risk_max_total_exposure,
            max_single_weight=config.risk_max_single_weight,
            max_futures_margin_ratio=config.risk_max_futures_margin_ratio,
            max_holdings=config.risk_max_holdings,
            max_order_amount=config.risk_max_order_amount,
            stop_loss_pct=config.stop_loss_pct,
            take_profit_pct=config.take_profit_pct,
            trailing_stop_pct=config.trailing_stop_pct,
            max_drawdown_pct=config.max_drawdown_pct,
            conflict_policy=config.risk_conflict_policy,
            rule_priorities=dict(config.risk_rule_priorities or {}),
        )
        self.risk_manager = PortfolioRiskManager(
            market=config.market,
            market_rules=self.market_rules,
            risk_config=risk_config,
        )
        self._order_seq = 0
        self._rebalance_count = 0
        self._last_rebalance_key: tuple[Any, ...] | None = None
        self._pending_signal_intents: dict[str, list[PendingSignalIntent]] = {}

    def _reset_runtime_state(self) -> None:
        self.portfolio = Portfolio(
            initial_cash=self.config.initial_capital,
            market_rules=self.market_rules,
        )
        self.recorder = BacktestRecorder()
        self.risk_manager.reset()
        self._order_seq = 0
        self._rebalance_count = 0
        self._last_rebalance_key = None
        self._pending_signal_intents = {}

    @property
    def orders(self) -> list[Order]:
        return self.recorder.orders

    @property
    def trades(self) -> list[dict[str, Any]]:
        return self.recorder.trades

    @property
    def equity_curve(self) -> list[float]:
        return self.recorder.equity_curve

    @property
    def dates(self) -> list[datetime]:
        return self.recorder.dates

    @property
    def position_snapshots(self) -> list[dict[str, dict[str, float]]]:
        return self.recorder.position_snapshots

    def create_order(
        self,
        signal: Signal,
        reference_price: float,
        *,
        quantity: int | None = None,
        offset: str | None = None,
        order_dt: datetime | None = None,
    ) -> Order | None:
        """根据信号创建最小订单对象。"""
        resolved_offset = offset or self.broker.resolve_order_offset(signal, self.portfolio)
        resolved_quantity = quantity
        if resolved_quantity is None:
            resolved_quantity = self.broker.calculate_order_quantity(signal, reference_price, self.portfolio)
        self._order_seq += 1
        order = build_order_from_signal(
            signal=signal,
            quantity=resolved_quantity,
            reference_price=reference_price,
            order_id=f"bt-order-{self._order_seq}",
            offset=resolved_offset,
        )
        if order_dt is not None:
            order.dt = order_dt
        self.recorder.record_order(order)
        return order

    def _prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        if data.empty:
            raise ValueError("backtest data must not be empty")
        sort_columns = ["dt"]
        if "code" in data.columns:
            sort_columns.append("code")
        return data.sort_values(sort_columns, kind="stable").reset_index(drop=True)

    def _build_bar(self, row: pd.Series) -> Bar:
        return Bar(
            code=row["code"],
            dt=row["dt"],
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
            amount=float(row.get("amount", 0)),
        )

    def _settle_trading_day(self, bar: Bar, current_trading_day: Any) -> Any:
        trading_day = pd.Timestamp(bar.dt).date()
        if trading_day != current_trading_day:
            self.portfolio.settle_positions(self.market_rules.settle_sellable_quantity)
            return trading_day
        return current_trading_day

    def _submit_order(
        self,
        *,
        order: Order,
        reference_price: float,
        latest_prices: dict[str, float],
        previous_close: float | None = None,
    ) -> None:
        validation = self.risk_manager.validate_order(
            order=order,
            reference_price=reference_price,
            portfolio=self.portfolio,
            current_prices=latest_prices,
            dt=order.dt or datetime.now(),
        )
        for risk_event in validation.events:
            self.recorder.record_risk_event(risk_event)
        if validation.blocked:
            order.status = OrderStatus.REJECTED
            return

        price_guard_event = self._validate_stock_price_guard(
            order=order,
            reference_price=reference_price,
            previous_close=previous_close,
        )
        if price_guard_event is not None:
            self.recorder.record_risk_event(price_guard_event)
            order.status = OrderStatus.REJECTED
            return

        trade = self.broker.execute_order(order, reference_price, self.portfolio)
        if trade is not None:
            self.recorder.record_trade(trade)

    def _queue_signal_intent(
        self,
        *,
        signal: Signal,
        quantity: int | None = None,
        offset: str | None = None,
    ) -> None:
        intents = self._pending_signal_intents.setdefault(signal.code, [])
        intents.append(
            PendingSignalIntent(
                signal=signal,
                quantity=quantity,
                offset=offset,
            )
        )

    def _execute_pending_signals_for_bar(
        self,
        *,
        bar: Bar,
        latest_prices: dict[str, float],
        previous_close: float | None,
    ) -> None:
        intents = self._pending_signal_intents.pop(bar.code, [])
        if not intents:
            return

        execution_prices = dict(latest_prices)
        execution_prices[bar.code] = bar.open

        for intent in intents:
            order = self.create_order(
                intent.signal,
                bar.open,
                quantity=intent.quantity,
                offset=intent.offset,
                order_dt=pd.Timestamp(bar.dt).to_pydatetime(),
            )
            self._submit_order(
                order=order,
                reference_price=bar.open,
                latest_prices=execution_prices,
                previous_close=previous_close,
            )

    def _validate_stock_price_guard(
        self,
        *,
        order: Order,
        reference_price: float,
        previous_close: float | None,
    ) -> RiskEvent | None:
        if self.config.market != "stock":
            return None
        if previous_close is None or previous_close <= 0 or reference_price <= 0:
            return None

        pct_change = (float(reference_price) - float(previous_close)) / float(previous_close)
        is_buy = order.direction == Direction.BUY
        is_sell = order.direction == Direction.SELL

        buy_threshold = max(float(self.config.buy_reject_threshold_pct), 0.0)
        sell_threshold = max(float(self.config.sell_reject_threshold_pct), 0.0)
        limit_up_pct = max(float(self.config.limit_up_pct), 0.0)
        limit_down_pct = max(float(self.config.limit_down_pct), 0.0)

        blocked_reason = None
        if is_buy and limit_up_pct > 0 and pct_change >= limit_up_pct:
            blocked_reason = f"涨幅达到涨停阈值 {limit_up_pct:.2%}"
        elif is_buy and buy_threshold > 0 and pct_change >= buy_threshold:
            blocked_reason = f"涨幅达到买入拦截阈值 {buy_threshold:.2%}"
        elif is_sell and limit_down_pct > 0 and pct_change <= -limit_down_pct:
            blocked_reason = f"跌幅达到跌停阈值 {-limit_down_pct:.2%}"
        elif is_sell and sell_threshold > 0 and pct_change <= -sell_threshold:
            blocked_reason = f"跌幅达到卖出拦截阈值 {-sell_threshold:.2%}"

        if blocked_reason is None:
            return None

        return RiskEvent(
            risk_type="PRICE_LIMIT_GUARD",
            severity="WARNING",
            code=order.code,
            message=(
                f"订单被价格约束拦截: {blocked_reason}, "
                f"昨收={previous_close:.4f}, 当前价={reference_price:.4f}, 涨跌幅={pct_change:.2%}"
            ),
            dt=order.dt or datetime.now(),
            action_taken="BLOCKED",
            category="execution",
            source="stock_price_guard",
            metadata={
                "previous_close": float(previous_close),
                "reference_price": float(reference_price),
                "pct_change": float(round(pct_change, 6)),
                "direction": order.direction.value,
            },
        )

    def _apply_bar_risk(
        self,
        *,
        dt: datetime,
        latest_prices: dict[str, float],
        previous_closes: dict[str, float],
    ) -> None:
        result = self.risk_manager.check_bar(
            dt=dt,
            portfolio=self.portfolio,
            current_prices=latest_prices,
        )
        for risk_event in result.events:
            self.recorder.record_risk_event(risk_event)
        for signal in result.signals:
            self._queue_signal_intent(signal=signal)

    def _rebalance_key(self, dt: pd.Timestamp) -> tuple[Any, ...]:
        frequency = str(self.config.rebalance_frequency).lower()
        if frequency == "daily":
            return ("daily", dt.date())
        if frequency == "weekly":
            iso = dt.isocalendar()
            return ("weekly", iso.year, iso.week)
        if frequency == "monthly":
            return ("monthly", dt.year, dt.month)
        return ("none",)

    def _resolve_target_weights(self, latest_prices: dict[str, float]) -> dict[str, float]:
        configured = self.config.portfolio_weights
        if configured:
            return {
                code: float(weight)
                for code, weight in configured.items()
                if code in latest_prices or code in self.portfolio.positions
            }

        if self.config.rebalance_frequency == "none":
            return {}

        tradable_codes = sorted(latest_prices.keys())
        if not tradable_codes:
            return {}
        equal_weight = 1.0 / len(tradable_codes)
        return {code: equal_weight for code in tradable_codes}

    def _build_rebalance_signal(
        self,
        *,
        code: str,
        dt: datetime,
        price: float,
        signal_type: SignalType,
        target_weight: float,
    ) -> Signal:
        return Signal(
            code=code,
            dt=dt,
            signal_type=signal_type,
            price=price,
            order_type=OrderType.MARKET,
            strength=1.0,
            reason=f"rebalance_target_weight={target_weight:.4f}",
        )

    def _build_rebalance_orders(
        self,
        *,
        dt: datetime,
        target_weights: dict[str, float],
        latest_prices: dict[str, float],
    ) -> list[PendingSignalIntent]:
        total_equity = self.portfolio.calculate_equity(latest_prices)
        if total_equity <= 0:
            return []

        sell_orders: list[Order] = []
        buy_orders: list[Order] = []
        codes = sorted(set(target_weights) | set(self.portfolio.positions))
        tolerance = max(float(self.config.rebalance_tolerance), 0.0)

        for code in codes:
            price = latest_prices.get(code)
            if price is None or price <= 0:
                continue

            target_weight = float(target_weights.get(code, 0.0))
            current_exposure = self.portfolio.get_position_exposure(code, price)
            current_weight = current_exposure / total_equity if total_equity > 0 else 0.0
            if abs(target_weight - current_weight) <= tolerance:
                continue

            target_exposure = total_equity * target_weight
            delta_exposure = target_exposure - current_exposure
            unit_exposure = self.market_rules.calculate_exposure_per_unit(reference_price=price)
            if unit_exposure <= 0:
                continue
            quantity = self.market_rules.normalize_quantity(int(abs(delta_exposure) / unit_exposure))
            if quantity <= 0:
                continue

            if delta_exposure < 0:
                current = self.portfolio.positions.get(code)
                if current is None:
                    continue
                quantity = min(quantity, current.sellable_quantity)
                quantity = self.market_rules.normalize_quantity(quantity)
                if quantity <= 0:
                    continue
                signal = self._build_rebalance_signal(
                    code=code,
                    dt=dt,
                    price=price,
                    signal_type=SignalType.SELL,
                    target_weight=target_weight,
                )
                sell_orders.append(
                    PendingSignalIntent(signal=signal, quantity=quantity, offset="close_long")
                )
            else:
                signal = self._build_rebalance_signal(
                    code=code,
                    dt=dt,
                    price=price,
                    signal_type=SignalType.BUY,
                    target_weight=target_weight,
                )
                buy_orders.append(
                    PendingSignalIntent(signal=signal, quantity=quantity, offset="open_long")
                )

        return sell_orders + buy_orders

    def _maybe_rebalance(
        self,
        *,
        dt: datetime,
        latest_prices: dict[str, float],
        previous_closes: dict[str, float],
    ) -> None:
        if self.config.rebalance_frequency == "none":
            return
        if self.config.market != "stock":
            return

        rebalance_key = self._rebalance_key(pd.Timestamp(dt))
        if rebalance_key == ("none",) or rebalance_key == self._last_rebalance_key:
            return

        raw_target_weights = self._resolve_target_weights(latest_prices)
        if not raw_target_weights:
            self._last_rebalance_key = rebalance_key
            return

        adjusted_weights, risk_events = self.risk_manager.adjust_target_weights(
            raw_weights=raw_target_weights,
            dt=dt,
        )
        for risk_event in risk_events:
            self.recorder.record_risk_event(risk_event)

        signal_intents = self._build_rebalance_orders(
            dt=dt,
            target_weights=adjusted_weights,
            latest_prices=latest_prices,
        )
        for intent in signal_intents:
            self._queue_signal_intent(
                signal=intent.signal,
                quantity=intent.quantity,
                offset=intent.offset,
            )

        self._rebalance_count += 1
        self._last_rebalance_key = rebalance_key

    def _record_market_state(self, *, dt: datetime, latest_prices: dict[str, float]) -> None:
        equity = self.portfolio.calculate_equity(latest_prices)
        self.recorder.record_bar_close(
            dt=dt,
            equity=equity,
            position_snapshot=self.portfolio.snapshot_positions(),
        )

    def _build_results(self, strategy: Any) -> dict[str, Any]:
        results = calculate_performance(
            equity_curve=self.recorder.equity_curve,
            initial_capital=self.initial_capital,
            trades=self.recorder.trades,
        )
        results["strategy_name"] = strategy.name
        results["total_orders"] = len(self.recorder.orders)
        results["total_trades"] = len(self.recorder.trades)
        results["total_rebalances"] = self._rebalance_count
        results["risk_event_count"] = len(self.recorder.risk_events)
        results["final_equity"] = (
            self.recorder.equity_curve[-1] if self.recorder.equity_curve else self.initial_capital
        )
        report = self.recorder.build_report_payload()
        report["summary"] = {
            "strategy_name": results["strategy_name"],
            "initial_capital": self.initial_capital,
            "final_equity": results["final_equity"],
            "total_orders": results["total_orders"],
            "total_trades": results["total_trades"],
            "total_rebalances": results["total_rebalances"],
            "risk_event_count": results["risk_event_count"],
            "risk_by_category": report.get("risk_by_category", {}),
            "risk_by_source": report.get("risk_by_source", {}),
            "risk_by_action": report.get("risk_by_action", {}),
            "total_return": results["total_return"],
            "annual_return": results["annual_return"],
            "volatility": results["volatility"],
            "sharpe_ratio": results["sharpe_ratio"],
            "max_drawdown": results["max_drawdown"],
            "win_rate": results["win_rate"],
            "profit_factor": results["profit_factor"],
            "avg_trade_profit": results["avg_trade_profit"],
            "avg_win_profit": results["avg_win_profit"],
            "avg_loss_profit": results["avg_loss_profit"],
            "total_commission": results["total_commission"],
        }
        results["report"] = report
        return results

    def run_backtest(self, strategy: Any, data: pd.DataFrame) -> dict[str, Any]:
        """运行回测。"""
        self._reset_runtime_state()
        sorted_data = self._prepare_data(data)

        strategy.on_init()
        strategy.update_asset(self.portfolio.to_asset())
        current_trading_day = None
        latest_prices: dict[str, float] = {}
        previous_closes: dict[str, float] = {}

        for dt, group in sorted_data.groupby("dt", sort=False):
            bars = [self._build_bar(row) for _, row in group.iterrows()]
            bar = bars[0]
            current_trading_day = self._settle_trading_day(bar, current_trading_day)

            for bar in bars:
                previous_close = previous_closes.get(bar.code)
                self._execute_pending_signals_for_bar(
                    bar=bar,
                    latest_prices=dict(latest_prices),
                    previous_close=previous_close,
                )
                latest_prices[bar.code] = bar.close
                signal = strategy.on_bar(bar)
                if signal:
                    self._queue_signal_intent(signal=signal)
                strategy.update_asset(self.portfolio.to_asset(dict(latest_prices)))
                previous_closes[bar.code] = bar.close

            self._apply_bar_risk(
                dt=pd.Timestamp(dt).to_pydatetime(),
                latest_prices=dict(latest_prices),
                previous_closes=dict(previous_closes),
            )

            self._maybe_rebalance(
                dt=pd.Timestamp(dt).to_pydatetime(),
                latest_prices=dict(latest_prices),
                previous_closes=dict(previous_closes),
            )
            strategy.update_asset(self.portfolio.to_asset(dict(latest_prices)))
            self._record_market_state(dt=pd.Timestamp(dt).to_pydatetime(), latest_prices=dict(latest_prices))

        return self._build_results(strategy)
