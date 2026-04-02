from datetime import datetime

from jwquant.common.types import Bar, SignalType
from jwquant.trading.indicator.signal import MACDSignalSnapshot, MACDSignalType
from jwquant.trading.strategy.macd_signal import MACDSignalStrategy
from jwquant.trading.strategy.macd_divergence import MACDDivergenceStrategy


def _build_bar(price: float = 10.0) -> Bar:
    return Bar(
        code="000001.SZ",
        dt=datetime(2024, 1, 1),
        open=price,
        high=price + 0.5,
        low=price - 0.5,
        close=price,
        volume=1000,
    )


def test_zero_above_golden_cross_buy():
    strategy = MACDSignalStrategy(
        params={
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "min_history": 1,
            "position_ratio": 0.9,
        }
    )
    bar = _build_bar()
    strategy.add_bar(bar)
    strategy.signal_generator.generate_signals = lambda **kwargs: [
        MACDSignalSnapshot(
            index=0,
            dt=bar.dt,
            price=bar.close,
            dif=0.3,
            dea=0.2,
            hist=0.1,
            signal_types=[MACDSignalType.GOLDEN_CROSS, MACDSignalType.ZERO_ABOVE_GOLDEN_CROSS],
            signals=["金叉", "零上金叉"],
            reasons=["金叉: DIF 上穿 DEA", "零上金叉: DIF 上穿 DEA"],
        )
    ]

    signal = strategy.on_bar(bar)

    assert signal is not None
    assert signal.signal_type == SignalType.BUY
    assert signal.reason == "MACD买入: 金叉、零上金叉"


def test_dead_cross_sell():
    strategy = MACDSignalStrategy(
        params={
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "min_history": 1,
            "position_ratio": 0.9,
        }
    )
    strategy.in_position = True
    bar = _build_bar()
    strategy.add_bar(bar)
    strategy.signal_generator.generate_signals = lambda **kwargs: [
        MACDSignalSnapshot(
            index=0,
            dt=bar.dt,
            price=bar.close,
            dif=-0.1,
            dea=0.0,
            hist=-0.1,
            signal_types=[MACDSignalType.DEAD_CROSS],
            signals=["死叉"],
            reasons=["死叉: DIF 下穿 DEA"],
        )
    ]

    signal = strategy.on_bar(bar)

    assert signal is not None
    assert signal.signal_type == SignalType.SELL
    assert signal.reason == "MACD卖出: 死叉"


def test_plain_golden_cross_no_buy_signal():
    strategy = MACDSignalStrategy(
        params={
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "min_history": 1,
            "position_ratio": 0.9,
        }
    )
    bar = _build_bar()
    strategy.add_bar(bar)
    strategy.signal_generator.generate_signals = lambda **kwargs: [
        MACDSignalSnapshot(
            index=0,
            dt=bar.dt,
            price=bar.close,
            dif=0.1,
            dea=0.05,
            hist=0.05,
            signal_types=[MACDSignalType.GOLDEN_CROSS],
            signals=["金叉"],
            reasons=["金叉: DIF 上穿 DEA"],
        )
    ]

    signal = strategy.on_bar(bar)

    assert signal is None


def test_bottom_divergence_buy():
    strategy = MACDDivergenceStrategy(
        params={
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "min_history": 1,
            "position_ratio": 0.9,
        }
    )
    bar = _build_bar()
    strategy.add_bar(bar)
    strategy.signal_generator.generate_signals = lambda **kwargs: [
        MACDSignalSnapshot(
            index=0,
            dt=bar.dt,
            price=bar.close,
            dif=-0.2,
            dea=-0.3,
            hist=0.1,
            signal_types=[MACDSignalType.BOTTOM_DIVERGENCE],
            signals=["底背离"],
            reasons=["底背离: 价格低点创新低，但 DIF 低点抬高"],
        )
    ]

    signal = strategy.on_bar(bar)

    assert signal is not None
    assert signal.signal_type == SignalType.BUY
    assert signal.reason == "MACD背离买入: 底背离"


def test_top_divergence_sell():
    strategy = MACDDivergenceStrategy(
        params={
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "min_history": 1,
            "position_ratio": 0.9,
        }
    )
    strategy.in_position = True
    bar = _build_bar()
    strategy.add_bar(bar)
    strategy.signal_generator.generate_signals = lambda **kwargs: [
        MACDSignalSnapshot(
            index=0,
            dt=bar.dt,
            price=bar.close,
            dif=0.3,
            dea=0.2,
            hist=-0.1,
            signal_types=[MACDSignalType.TOP_DIVERGENCE],
            signals=["顶背离"],
            reasons=["顶背离: 价格高点创新高，但 DIF 高点走低"],
        )
    ]

    signal = strategy.on_bar(bar)

    assert signal is not None
    assert signal.signal_type == SignalType.SELL
    assert signal.reason == "MACD背离卖出: 顶背离"
