"""
信号生成

基于指标计算结果生成标准化的指标语义信号。
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

import numpy as np
import pandas as pd

from jwquant.common.config import get, get_all, load_config
from jwquant.trading.indicator.talib_wrap import TechnicalIndicators


class MACDSignalType(Enum):
    """MACD 信号类型"""

    GOLDEN_CROSS = "金叉"
    DEAD_CROSS = "死叉"
    ZERO_ABOVE_GOLDEN_CROSS = "零上金叉"
    ZERO_BELOW_GOLDEN_CROSS = "零下金叉"
    ZERO_ABOVE_DEAD_CROSS = "零上死叉"
    ZERO_BELOW_DEAD_CROSS = "零下死叉"
    TOP_DIVERGENCE = "顶背离"
    BOTTOM_DIVERGENCE = "底背离"


@dataclass
class MACDSignalEvent:
    """MACD 单次信号事件"""

    signal_type: MACDSignalType
    index: int
    dt: object = None
    price: Optional[float] = None
    dif: Optional[float] = None
    dea: Optional[float] = None
    hist: Optional[float] = None
    reason: str = ""


@dataclass
class MACDSignalSnapshot:
    """按单根 K 线聚合后的 MACD 信号"""

    index: int
    dt: object = None
    price: Optional[float] = None
    dif: Optional[float] = None
    dea: Optional[float] = None
    hist: Optional[float] = None
    signal_types: list[MACDSignalType] = None
    signals: list[str] = None
    reasons: list[str] = None


class MACDSignalGenerator:
    """MACD 信号生成器"""

    def __init__(self):
        self.indicators = TechnicalIndicators()

    def generate_signals(
        self,
        close: Sequence[float],
        high: Optional[Sequence[float]] = None,
        low: Optional[Sequence[float]] = None,
        dt_index: Optional[Sequence[object]] = None,
        fast_period: Optional[int] = None,
        slow_period: Optional[int] = None,
        signal_period: Optional[int] = None,
        divergence_window: Optional[int] = None,
    ) -> list[MACDSignalSnapshot]:
        """生成按 K 线聚合后的 MACD 信号列表"""
        fast_period, slow_period, signal_period, divergence_window = _resolve_macd_indicator_config(
            fast_period=fast_period,
            slow_period=slow_period,
            signal_period=signal_period,
            divergence_window=divergence_window,
        )

        events = self.generate_signal_events(
            close=close,
            high=high,
            low=low,
            dt_index=dt_index,
            fast_period=fast_period,
            slow_period=slow_period,
            signal_period=signal_period,
            divergence_window=divergence_window,
        )
        return self.aggregate_signals(events)

    def generate_signal_events(
        self,
        close: Sequence[float],
        high: Optional[Sequence[float]] = None,
        low: Optional[Sequence[float]] = None,
        dt_index: Optional[Sequence[object]] = None,
        fast_period: Optional[int] = None,
        slow_period: Optional[int] = None,
        signal_period: Optional[int] = None,
        divergence_window: Optional[int] = None,
    ) -> list[MACDSignalEvent]:
        """生成完整的 MACD 原始事件列表"""
        fast_period, slow_period, signal_period, divergence_window = _resolve_macd_indicator_config(
            fast_period=fast_period,
            slow_period=slow_period,
            signal_period=signal_period,
            divergence_window=divergence_window,
        )

        close_array = np.asarray(close, dtype=float)
        if len(close_array) < max(slow_period, signal_period) + 2:
            return []

        dif, dea, hist = self.indicators.macd(close_array, fast_period, slow_period, signal_period)
        signals = self.generate_cross_signals(close_array, dif, dea, hist, dt_index=dt_index)

        price_high = np.asarray(high if high is not None else close_array, dtype=float)
        price_low = np.asarray(low if low is not None else close_array, dtype=float)
        signals.extend(
            self.generate_divergence_signals(
                close=close_array,
                high=price_high,
                low=price_low,
                dif=dif,
                dea=dea,
                hist=hist,
                dt_index=dt_index,
                pivot_window=divergence_window,
            )
        )

        signals.sort(key=lambda item: item.index)
        return signals

    def generate_cross_signals(
        self,
        close: Sequence[float],
        dif: Sequence[float],
        dea: Sequence[float],
        hist: Sequence[float],
        dt_index: Optional[Sequence[object]] = None,
    ) -> list[MACDSignalEvent]:
        """生成金叉/死叉类信号"""

        close_array = np.asarray(close, dtype=float)
        dif_array = np.asarray(dif, dtype=float)
        dea_array = np.asarray(dea, dtype=float)
        hist_array = np.asarray(hist, dtype=float)
        signals: list[MACDSignalEvent] = []

        for idx in range(1, len(dif_array)):
            prev_dif = dif_array[idx - 1]
            prev_dea = dea_array[idx - 1]
            curr_dif = dif_array[idx]
            curr_dea = dea_array[idx]

            if not self._is_valid_pair(prev_dif, prev_dea, curr_dif, curr_dea):
                continue

            dt_value = dt_index[idx] if dt_index is not None and idx < len(dt_index) else None

            if prev_dif <= prev_dea and curr_dif > curr_dea:
                signal_types = self._classify_cross(curr_dif, curr_dea, is_golden=True)
                signals.extend(
                    self._build_cross_events(
                        signal_types=signal_types,
                        index=idx,
                        dt_value=dt_value,
                        price=float(close_array[idx]),
                        dif=float(curr_dif),
                        dea=float(curr_dea),
                        hist=float(hist_array[idx]),
                        action_text="DIF 上穿 DEA",
                    )
                )
            elif prev_dif >= prev_dea and curr_dif < curr_dea:
                signal_types = self._classify_cross(curr_dif, curr_dea, is_golden=False)
                signals.extend(
                    self._build_cross_events(
                        signal_types=signal_types,
                        index=idx,
                        dt_value=dt_value,
                        price=float(close_array[idx]),
                        dif=float(curr_dif),
                        dea=float(curr_dea),
                        hist=float(hist_array[idx]),
                        action_text="DIF 下穿 DEA",
                    )
                )

        return signals

    def generate_divergence_signals(
        self,
        close: Sequence[float],
        high: Sequence[float],
        low: Sequence[float],
        dif: Sequence[float],
        dea: Sequence[float],
        hist: Sequence[float],
        dt_index: Optional[Sequence[object]] = None,
        pivot_window: int = 2,
    ) -> list[MACDSignalEvent]:
        """生成顶背离/底背离信号"""

        close_array = np.asarray(close, dtype=float)
        high_array = np.asarray(high, dtype=float)
        low_array = np.asarray(low, dtype=float)
        dif_array = np.asarray(dif, dtype=float)
        dea_array = np.asarray(dea, dtype=float)
        hist_array = np.asarray(hist, dtype=float)
        signals: list[MACDSignalEvent] = []

        high_pivots = self._find_local_extrema(high_array, pivot_window, find_high=True)
        low_pivots = self._find_local_extrema(low_array, pivot_window, find_high=False)

        top_signals = self._build_divergence_signals(
            pivot_indexes=high_pivots,
            price_array=high_array,
            close_array=close_array,
            dif_array=dif_array,
            dea_array=dea_array,
            hist_array=hist_array,
            signal_type=MACDSignalType.TOP_DIVERGENCE,
            dt_index=dt_index,
            bullish=False,
        )
        signals.extend(top_signals)

        bottom_signals = self._build_divergence_signals(
            pivot_indexes=low_pivots,
            price_array=low_array,
            close_array=close_array,
            dif_array=dif_array,
            dea_array=dea_array,
            hist_array=hist_array,
            signal_type=MACDSignalType.BOTTOM_DIVERGENCE,
            dt_index=dt_index,
            bullish=True,
        )
        signals.extend(bottom_signals)

        return signals

    @staticmethod
    def get_latest_signal(signals: Sequence[MACDSignalSnapshot]) -> Optional[MACDSignalSnapshot]:
        """获取最新一条聚合信号"""
        if not signals:
            return None
        return max(signals, key=lambda item: item.index)

    @staticmethod
    def get_latest_event(events: Sequence[MACDSignalEvent]) -> Optional[MACDSignalEvent]:
        """获取最新一条原始事件"""
        if not events:
            return None
        return max(events, key=lambda item: item.index)

    @staticmethod
    def aggregate_signals(events: Sequence[MACDSignalEvent]) -> list[MACDSignalSnapshot]:
        """将同一根 K 线上的多个事件聚合为一条结构化结果"""
        grouped: dict[tuple[int, object], MACDSignalSnapshot] = {}

        for event in sorted(events, key=lambda item: item.index):
            key = (event.index, event.dt)
            if key not in grouped:
                grouped[key] = MACDSignalSnapshot(
                    index=event.index,
                    dt=event.dt,
                    price=event.price,
                    dif=event.dif,
                    dea=event.dea,
                    hist=event.hist,
                    signal_types=[],
                    signals=[],
                    reasons=[],
                )

            snapshot = grouped[key]
            snapshot.price = event.price
            snapshot.dif = event.dif
            snapshot.dea = event.dea
            snapshot.hist = event.hist
            snapshot.signal_types.append(event.signal_type)
            snapshot.signals.append(event.signal_type.value)
            snapshot.reasons.append(event.reason)

        return list(grouped.values())

    @staticmethod
    def _classify_cross(curr_dif: float, curr_dea: float, is_golden: bool) -> list[MACDSignalType]:
        generic_signal = MACDSignalType.GOLDEN_CROSS if is_golden else MACDSignalType.DEAD_CROSS
        if curr_dif > 0 and curr_dea > 0:
            return [
                generic_signal,
                MACDSignalType.ZERO_ABOVE_GOLDEN_CROSS
                if is_golden
                else MACDSignalType.ZERO_ABOVE_DEAD_CROSS
            ]
        if curr_dif < 0 and curr_dea < 0:
            return [
                generic_signal,
                MACDSignalType.ZERO_BELOW_GOLDEN_CROSS
                if is_golden
                else MACDSignalType.ZERO_BELOW_DEAD_CROSS
            ]
        return [generic_signal]

    @staticmethod
    def _build_cross_events(
        signal_types: Sequence[MACDSignalType],
        index: int,
        dt_value: object,
        price: float,
        dif: float,
        dea: float,
        hist: float,
        action_text: str,
    ) -> list[MACDSignalEvent]:
        return [
            MACDSignalEvent(
                signal_type=signal_type,
                index=index,
                dt=dt_value,
                price=price,
                dif=dif,
                dea=dea,
                hist=hist,
                reason=f"{signal_type.value}: {action_text}",
            )
            for signal_type in signal_types
        ]

    @staticmethod
    def _is_valid_pair(*values: float) -> bool:
        return all(np.isfinite(value) for value in values)

    @staticmethod
    def _find_local_extrema(series: np.ndarray, window: int, find_high: bool) -> list[int]:
        if len(series) < window * 2 + 1:
            return []

        pivot_indexes: list[int] = []
        for idx in range(window, len(series) - window):
            value = series[idx]
            if not np.isfinite(value):
                continue

            left = series[idx - window:idx]
            right = series[idx + 1:idx + 1 + window]
            if not np.all(np.isfinite(left)) or not np.all(np.isfinite(right)):
                continue

            if find_high and value >= left.max() and value >= right.max():
                pivot_indexes.append(idx)
            elif not find_high and value <= left.min() and value <= right.min():
                pivot_indexes.append(idx)

        return pivot_indexes

    def _build_divergence_signals(
        self,
        pivot_indexes: Sequence[int],
        price_array: np.ndarray,
        close_array: np.ndarray,
        dif_array: np.ndarray,
        dea_array: np.ndarray,
        hist_array: np.ndarray,
        signal_type: MACDSignalType,
        dt_index: Optional[Sequence[object]],
        bullish: bool,
    ) -> list[MACDSignalEvent]:
        if len(pivot_indexes) < 2:
            return []

        signals: list[MACDSignalEvent] = []
        for prev_idx, curr_idx in zip(pivot_indexes[:-1], pivot_indexes[1:]):
            prev_price = price_array[prev_idx]
            curr_price = price_array[curr_idx]
            prev_dif = dif_array[prev_idx]
            curr_dif = dif_array[curr_idx]

            if not self._is_valid_pair(prev_price, curr_price, prev_dif, curr_dif):
                continue

            if bullish:
                is_divergence = curr_price < prev_price and curr_dif > prev_dif
                reason = (
                    f"{signal_type.value}: 价格低点创新低({prev_price:.2f}->{curr_price:.2f})，"
                    f"但 DIF 低点抬高({prev_dif:.4f}->{curr_dif:.4f})"
                )
            else:
                is_divergence = curr_price > prev_price and curr_dif < prev_dif
                reason = (
                    f"{signal_type.value}: 价格高点创新高({prev_price:.2f}->{curr_price:.2f})，"
                    f"但 DIF 高点走低({prev_dif:.4f}->{curr_dif:.4f})"
                )

            if not is_divergence:
                continue

            dt_value = dt_index[curr_idx] if dt_index is not None and curr_idx < len(dt_index) else None
            signals.append(
                MACDSignalEvent(
                    signal_type=signal_type,
                    index=curr_idx,
                    dt=dt_value,
                    price=float(close_array[curr_idx]),
                    dif=float(dif_array[curr_idx]),
                    dea=float(dea_array[curr_idx]),
                    hist=float(hist_array[curr_idx]),
                    reason=reason,
                )
            )

        return signals


def generate_macd_signals(
    df: pd.DataFrame,
    fast_period: Optional[int] = None,
    slow_period: Optional[int] = None,
    signal_period: Optional[int] = None,
    divergence_window: Optional[int] = None,
) -> list[MACDSignalSnapshot]:
    """基于 DataFrame 生成按 K 线聚合后的 MACD 信号"""

    if "close" not in df.columns:
        raise ValueError("DataFrame 必须包含 close 列")

    generator = MACDSignalGenerator()
    return generator.generate_signals(
        close=df["close"].to_numpy(),
        high=df["high"].to_numpy() if "high" in df.columns else None,
        low=df["low"].to_numpy() if "low" in df.columns else None,
        dt_index=df["dt"].tolist() if "dt" in df.columns else None,
        fast_period=fast_period,
        slow_period=slow_period,
        signal_period=signal_period,
        divergence_window=divergence_window,
    )


def generate_macd_signal_events(
    df: pd.DataFrame,
    fast_period: Optional[int] = None,
    slow_period: Optional[int] = None,
    signal_period: Optional[int] = None,
    divergence_window: Optional[int] = None,
) -> list[MACDSignalEvent]:
    """基于 DataFrame 生成 MACD 原始事件"""

    if "close" not in df.columns:
        raise ValueError("DataFrame 必须包含 close 列")

    generator = MACDSignalGenerator()
    return generator.generate_signal_events(
        close=df["close"].to_numpy(),
        high=df["high"].to_numpy() if "high" in df.columns else None,
        low=df["low"].to_numpy() if "low" in df.columns else None,
        dt_index=df["dt"].tolist() if "dt" in df.columns else None,
        fast_period=fast_period,
        slow_period=slow_period,
        signal_period=signal_period,
        divergence_window=divergence_window,
    )


def _resolve_macd_indicator_config(
    fast_period: Optional[int],
    slow_period: Optional[int],
    signal_period: Optional[int],
    divergence_window: Optional[int],
) -> tuple[int, int, int, int]:
    """解析 MACD 指标参数，显式传参优先，其次读取配置文件。"""
    if not get_all():
        load_config(extra=["config/strategies.toml"])

    indicator_config = get("indicators.macd", {}) or {}
    resolved_fast = fast_period if fast_period is not None else int(indicator_config.get("fast_period", 12))
    resolved_slow = slow_period if slow_period is not None else int(indicator_config.get("slow_period", 26))
    resolved_signal = signal_period if signal_period is not None else int(indicator_config.get("signal_period", 9))
    resolved_window = (
        divergence_window if divergence_window is not None else int(indicator_config.get("divergence_window", 2))
    )
    return resolved_fast, resolved_slow, resolved_signal, resolved_window


__all__ = [
    "MACDSignalEvent",
    "MACDSignalSnapshot",
    "MACDSignalGenerator",
    "MACDSignalType",
    "generate_macd_signal_events",
    "generate_macd_signals",
]
