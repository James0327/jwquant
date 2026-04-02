import numpy as np
import pandas as pd

from jwquant.common.config import load_config
from jwquant.trading.indicator.signal import MACDSignalGenerator, MACDSignalType, generate_macd_signals


def test_generate_cross_signals_classify_zero_axis():
    generator = MACDSignalGenerator()
    close = np.array([10.0, 10.2, 10.4, 10.6, 10.8, 11.0, 11.2, 11.4, 11.6, 11.8])
    dif = np.array([-0.3, -0.1, 0.2, 0.05, 0.0, 0.2, -0.1, -0.3, 0.05, -0.05])
    dea = np.array([-0.2, -0.15, 0.1, 0.1, 0.02, 0.1, -0.15, -0.2, -0.02, 0.02])
    hist = dif - dea

    signals = generator.generate_cross_signals(close, dif, dea, hist)
    signal_types = [signal.signal_type for signal in signals]

    assert MACDSignalType.GOLDEN_CROSS in signal_types
    assert MACDSignalType.DEAD_CROSS in signal_types
    assert MACDSignalType.ZERO_BELOW_GOLDEN_CROSS in signal_types
    assert MACDSignalType.ZERO_ABOVE_DEAD_CROSS in signal_types
    assert MACDSignalType.ZERO_ABOVE_GOLDEN_CROSS in signal_types
    assert MACDSignalType.ZERO_BELOW_DEAD_CROSS in signal_types

    zero_below_golden_index = next(
        signal.index for signal in signals if signal.signal_type == MACDSignalType.ZERO_BELOW_GOLDEN_CROSS
    )
    generic_golden_same_index = [
        signal for signal in signals
        if signal.signal_type == MACDSignalType.GOLDEN_CROSS and signal.index == zero_below_golden_index
    ]
    assert generic_golden_same_index

    zero_line_golden_index = 8
    zero_line_dead_index = 9
    zero_line_golden_same_index = [
        signal for signal in signals
        if signal.signal_type == MACDSignalType.GOLDEN_CROSS and signal.index == zero_line_golden_index
    ]
    zero_line_dead_same_index = [
        signal for signal in signals
        if signal.signal_type == MACDSignalType.DEAD_CROSS and signal.index == zero_line_dead_index
    ]
    assert zero_line_golden_same_index
    assert zero_line_dead_same_index


def test_generate_divergence_signals_detect_top_and_bottom():
    generator = MACDSignalGenerator()
    close = np.array([10.0, 12.0, 11.0, 14.0, 11.0, 8.0, 10.0, 7.0, 9.0])
    high = close.copy()
    low = close.copy()
    dif = np.array([0.1, 1.2, 0.5, 0.8, 0.2, -1.1, -0.4, -0.6, -0.1])
    dea = np.array([0.0, 1.0, 0.4, 0.7, 0.15, -0.9, -0.3, -0.5, -0.05])
    hist = dif - dea

    signals = generator.generate_divergence_signals(
        close=close,
        high=high,
        low=low,
        dif=dif,
        dea=dea,
        hist=hist,
        pivot_window=1,
    )
    signal_types = {signal.signal_type for signal in signals}

    assert MACDSignalType.TOP_DIVERGENCE in signal_types
    assert MACDSignalType.BOTTOM_DIVERGENCE in signal_types


def test_generate_macd_signals_group_by_index():
    df = pd.DataFrame(
        {
            "dt": list(range(10)),
            "close": [10.0, 10.2, 10.4, 10.6, 10.8, 11.0, 11.2, 11.4, 11.6, 11.8],
        }
    )
    generator = MACDSignalGenerator()
    events = generator.generate_cross_signals(
        close=df["close"].to_numpy(),
        dif=np.array([-0.3, -0.1, 0.2, 0.05, 0.0, 0.2, -0.1, -0.3, 0.05, -0.05]),
        dea=np.array([-0.2, -0.15, 0.1, 0.1, 0.02, 0.1, -0.15, -0.2, -0.02, 0.02]),
        hist=np.array([-0.1, 0.05, 0.1, -0.05, -0.02, 0.1, 0.05, -0.1, 0.07, -0.07]),
        dt_index=df["dt"].tolist(),
    )

    snapshots = generator.aggregate_signals(events)

    zero_below_snapshot = next(snapshot for snapshot in snapshots if snapshot.index == 1)
    assert zero_below_snapshot.signals == ["金叉", "零下金叉"]

    zero_above_dead_snapshot = next(snapshot for snapshot in snapshots if snapshot.index == 3)
    assert zero_above_dead_snapshot.signals == ["死叉", "零上死叉"]

    cross_zero_snapshot = next(snapshot for snapshot in snapshots if snapshot.index == 8)
    assert cross_zero_snapshot.signals == ["金叉"]

    grouped_from_df = generate_macd_signals(df, fast_period=3, slow_period=5, signal_period=2)
    assert isinstance(grouped_from_df, list)


def test_generate_macd_signals_use_indicator_config(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[indicators.macd]
fast_period = 3
slow_period = 5
signal_period = 2
divergence_window = 1
""".strip(),
        encoding="utf-8",
    )
    load_config(config_file)

    df = pd.DataFrame(
        {
            "dt": list(range(10)),
            "close": [10.0, 10.2, 10.4, 10.6, 10.8, 11.0, 11.2, 11.4, 11.6, 11.8],
        }
    )

    grouped_from_df = generate_macd_signals(df)

    assert isinstance(grouped_from_df, list)
