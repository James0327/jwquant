"""
MACD 背离策略

基于 MACD 背离信号生成买卖决策：
- 买入：底背离
- 卖出：顶背离
"""
from jwquant.trading.indicator.signal import MACDSignalType
from jwquant.trading.strategy.macd_base import BaseMACDStrategy


class MACDDivergenceStrategy(BaseMACDStrategy):
    """MACD 背离策略"""

    def __init__(self, name: str = "macd_divergence", params: dict | None = None):
        super().__init__(
            name=name,
            params=params,
            init_label="MACD背离策略",
            reason_prefix="MACD背离",
        )

    def build_buy_rules(self, strategy_config: dict) -> set[MACDSignalType]:
        return {MACDSignalType.BOTTOM_DIVERGENCE}

    def build_sell_rules(self, strategy_config: dict) -> set[MACDSignalType]:
        return {MACDSignalType.TOP_DIVERGENCE}


def create_macd_divergence_strategy(params: dict | None = None) -> MACDDivergenceStrategy:
    """创建 MACD 背离策略实例"""
    return MACDDivergenceStrategy("macd_divergence", params)
