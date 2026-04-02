"""
MACD 趋势信号策略

基于 MACD 趋势信号生成买卖决策：
- 买入：零上金叉
- 卖出：死叉
"""
from jwquant.trading.indicator.signal import MACDSignalType
from jwquant.trading.strategy.macd_base import BaseMACDStrategy


class MACDSignalStrategy(BaseMACDStrategy):
    """MACD 趋势信号策略"""

    def __init__(self, name: str = "macd_signal", params: dict | None = None):
        super().__init__(
            name=name,
            params=params,
            init_label="MACD趋势信号策略",
            reason_prefix="MACD",
        )

    def build_buy_rules(self, strategy_config: dict) -> set[MACDSignalType]:
        return {MACDSignalType.ZERO_ABOVE_GOLDEN_CROSS}

    def build_sell_rules(self, strategy_config: dict) -> set[MACDSignalType]:
        return {MACDSignalType.DEAD_CROSS}


def create_macd_signal_strategy(params: dict | None = None) -> MACDSignalStrategy:
    """创建 MACD 趋势信号策略实例"""
    return MACDSignalStrategy("macd_signal", params)
