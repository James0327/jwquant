"""
MACD 策略公共基类

封装 MACD 类策略共享的参数读取、快照生成和信号决策流程。
"""
from typing import Optional

from jwquant.common.config import get_strategy_config
from jwquant.common.types import Bar, Signal, SignalType
from jwquant.trading.indicator.signal import MACDSignalGenerator, MACDSignalSnapshot, MACDSignalType
from jwquant.trading.strategy.base import BaseStrategy


class BaseMACDStrategy(BaseStrategy):
    """MACD 策略公共基类"""

    def __init__(
        self,
        name: str,
        params: dict | None,
        init_label: str,
        reason_prefix: str,
    ):
        super().__init__(name, params)

        strategy_config = get_strategy_config(name)
        if params:
            strategy_config.update(params)

        self._validate_strategy_config(strategy_config)
        self.strategy_config = strategy_config
        self.macd_fast = strategy_config["macd_fast"]
        self.macd_slow = strategy_config["macd_slow"]
        self.macd_signal = strategy_config["macd_signal"]
        self.min_history = strategy_config["min_history"]
        self.position_ratio = strategy_config["position_ratio"]

        self.init_label = init_label
        self.reason_prefix = reason_prefix
        self.signal_generator = MACDSignalGenerator()
        self.buy_signal_types = self.build_buy_rules(strategy_config)
        self.sell_signal_types = self.build_sell_rules(strategy_config)
        self.in_position = False
        self.last_signal: Optional[SignalType] = None

    def on_init(self) -> None:
        super().on_init()
        print(
            f"{self.init_label}参数: 快线={self.macd_fast}, 慢线={self.macd_slow}, "
            f"信号线={self.macd_signal}, 最小历史数据={self.min_history}"
        )

    def on_bar(self, bar: Bar) -> Signal | None:
        """每根K线触发，执行 MACD 信号逻辑"""
        if len(self.history_bars) < self.min_history:
            return None

        snapshots = self.signal_generator.generate_signals(
            close=[item.close for item in self.history_bars],
            high=[item.high for item in self.history_bars],
            low=[item.low for item in self.history_bars],
            dt_index=[item.dt for item in self.history_bars],
            fast_period=self.macd_fast,
            slow_period=self.macd_slow,
            signal_period=self.macd_signal,
        )
        latest_snapshot = self.signal_generator.get_latest_signal(snapshots)
        if latest_snapshot is None or latest_snapshot.index != len(self.history_bars) - 1:
            return None

        decision = self._resolve_snapshot(latest_snapshot)
        if decision is None:
            return None

        signal_type = decision
        if signal_type == SignalType.BUY and self.in_position:
            return None
        if signal_type == SignalType.SELL and not self.in_position:
            return None

        self.in_position = signal_type == SignalType.BUY
        self.last_signal = signal_type
        return Signal(
            code=bar.code,
            dt=bar.dt,
            signal_type=signal_type,
            price=bar.close,
            reason=self._build_reason(latest_snapshot, signal_type),
        )

    def _resolve_snapshot(self, snapshot: MACDSignalSnapshot) -> SignalType | None:
        has_buy_signal = any(signal_type in self.buy_signal_types for signal_type in snapshot.signal_types)
        has_sell_signal = any(signal_type in self.sell_signal_types for signal_type in snapshot.signal_types)

        if not has_buy_signal and not has_sell_signal:
            return None
        if has_buy_signal and not has_sell_signal:
            return SignalType.BUY
        if has_sell_signal and not has_buy_signal:
            return SignalType.SELL
        return SignalType.SELL if self.in_position else SignalType.BUY

    def _build_reason(self, snapshot: MACDSignalSnapshot, signal_type: SignalType) -> str:
        action = "买入" if signal_type == SignalType.BUY else "卖出"
        signal_text = "、".join(snapshot.signals)
        return f"{self.reason_prefix}{action}: {signal_text}"

    def calculate_position_volume(self, price: float) -> int:
        """计算开仓手数（简化版）"""
        available_cash = self.get_available_cash()
        position_value = available_cash * self.position_ratio
        volume = int(position_value / price / 100) * 100
        return max(volume, 100)

    def on_stop(self) -> None:
        super().on_stop()
        self.in_position = False
        self.last_signal = None

    @staticmethod
    def _validate_strategy_config(strategy_config: dict) -> None:
        required_keys = [
            "macd_fast",
            "macd_slow",
            "macd_signal",
            "min_history",
            "position_ratio",
        ]
        missing_keys = [key for key in required_keys if key not in strategy_config]
        if missing_keys:
            raise ValueError(f"MACD策略缺少配置项: {', '.join(missing_keys)}")

    def build_buy_rules(self, strategy_config: dict) -> set[MACDSignalType]:
        raise NotImplementedError

    def build_sell_rules(self, strategy_config: dict) -> set[MACDSignalType]:
        raise NotImplementedError
