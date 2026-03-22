"""
三均线穿越策略（1阳穿3线）
一根阳线上穿短、中、长期三条均线时发出买入信号的强势突破策略

核心原理：
========
当价格同时突破三条不同周期的均线时，表明市场动能强劲，
往往意味着趋势的快速启动或加速。

技术特点：
========
• 强势信号：一阳穿三线是经典的看涨形态
• 多重确认：同时突破三个关键位置，信号更可靠
• 爆发力强：通常出现在趋势启动初期
• 过滤震荡：要求同时突破多条均线，减少假信号

策略逻辑：
- 买入信号：当日阳线收盘价 > 三均线 且 前一日收盘价 < 三均线
- 卖出信号：可根据需要添加（如跌破某条均线）

使用场景：
========
适用市场：
• 适合强势上涨趋势的股票
• 对突破信号较为敏感
• 适合追涨杀跌的交易风格

适用周期：
• 日线级别：捕捉强势股的启动点
• 60分钟级别：适合短线热点炒作
• 周线级别：适合中长线布局

参数配置建议：
• 短期5日 + 中期10日 + 长期20日：最常见的搭配
• 短期3日 + 中期7日 + 长期14日：更加灵敏
• 短期10日 + 中期20日 + 长期60日：适合稳健投资

策略特点：
• 信号较少但质量较高
• 适合捕捉趋势的初期阶段
• 对假突破有一定过滤作用

注意事项：
• 在震荡市中信号稀少
• 需要较强的执行力及时跟进
• 建议设置合理的止损位
"""
import numpy as np
from typing import Optional, Tuple

from jwquant.common.types import Bar, Signal, SignalType
from jwquant.common.config import get_strategy_config
from jwquant.trading.strategy.base import BaseStrategy


class ThreeMACrossStrategy(BaseStrategy):
    """三均线穿越策略实现"""
    
    def __init__(self, name: str = "three_ma_cross", params: dict | None = None):
        super().__init__(name, params)
        
        # 从配置文件获取策略参数
        strategy_config = get_strategy_config(name, {
            'short_ma_period': 5,
            'medium_ma_period': 10,
            'long_ma_period': 20,
            'min_history': 30
        })
        
        # 合并传入的参数（优先级更高）
        if params:
            strategy_config.update(params)
        
        # 设置参数
        self.short_ma_period = strategy_config['short_ma_period']
        self.medium_ma_period = strategy_config['medium_ma_period']
        self.long_ma_period = strategy_config['long_ma_period']
        self.min_history = strategy_config['min_history']
        
        # 策略状态
        self.in_position = False
        self.last_signal = None  # 记录上次信号类型
        self.last_close = 0.0    # 记录前一日收盘价
        
    def on_init(self) -> None:
        """策略初始化"""
        super().on_init()
        print(f"三均线穿越策略参数:")
        print(f"  短期MA: {self.short_ma_period}")
        print(f"  中期MA: {self.medium_ma_period}")  
        print(f"  长期MA: {self.long_ma_period}")
        print(f"  最小历史数据: {self.min_history}")
        
    def calculate_moving_average(self, period: int) -> Optional[list]:
        """计算移动平均线序列"""
        if len(self.history_bars) < period:
            return None
            
        closes = [bar.close for bar in self.history_bars]
        ma_values = []
        
        # 计算每个点的MA值
        for i in range(period - 1, len(closes)):
            ma_value = np.mean(closes[i - period + 1:i + 1])
            ma_values.append(ma_value)
            
        return ma_values
    
    def calculate_three_ma(self) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """计算三条均线的最新值"""
        # 计算短期均线
        short_ma_series = self.calculate_moving_average(self.short_ma_period)
        short_ma = short_ma_series[-1] if short_ma_series else None
        
        # 计算中期均线
        medium_ma_series = self.calculate_moving_average(self.medium_ma_period)
        medium_ma = medium_ma_series[-1] if medium_ma_series else None
        
        # 计算长期均线
        long_ma_series = self.calculate_moving_average(self.long_ma_period)
        long_ma = long_ma_series[-1] if long_ma_series else None
        
        return short_ma, medium_ma, long_ma
    
    def check_bullish_candle(self, bar: Bar) -> bool:
        """判断是否为阳线"""
        return bar.close > bar.open
    
    def check_cross_condition(self, bar: Bar, short_ma: float, medium_ma: float, long_ma: float) -> bool:
        """判断上穿条件"""
        if len(self.history_bars) < 2:
            return False
            
        current_close = bar.close
        previous_close = self.history_bars[-2].close
        
        # 计算三均线的平均值作为穿越基准
        avg_ma = (short_ma + medium_ma + long_ma) / 3
        
        # 上穿条件：当前收盘价 > 均线平均值 且 前一日收盘价 < 均线平均值
        cross_up = current_close > avg_ma and previous_close < avg_ma
        
        return cross_up
    
    def on_bar(self, bar: Bar) -> Signal | None:
        """每根K线触发，执行策略逻辑"""
        # 更新前一日收盘价
        self.last_close = bar.close
        
        # 检查是否有足够历史数据
        if len(self.history_bars) < self.min_history:
            return None
            
        # 计算三条均线
        short_ma, medium_ma, long_ma = self.calculate_three_ma()
        
        # 检查计算结果有效性
        if short_ma is None or medium_ma is None or long_ma is None:
            return None
            
        # 判断是否为阳线
        if not self.check_bullish_candle(bar):
            return None
            
        # 检查穿越条件
        if self.check_cross_condition(bar, short_ma, medium_ma, long_ma) and not self.in_position:
            self.in_position = True
            self.last_signal = SignalType.BUY
            
            signal = Signal(
                code=bar.code,
                dt=bar.dt,
                signal_type=SignalType.BUY,
                price=bar.close,
                reason=f"阳线上穿三均线：收盘价{bar.close:.2f} > 均线({short_ma:.2f},{medium_ma:.2f},{long_ma:.2f})，前收{self.history_bars[-2].close:.2f}"
            )
            return signal
            
        # 可选：添加卖出条件（例如跌破某条均线）
        # 这里可以根据需要实现
        
        return None
    
    def calculate_position_volume(self, price: float) -> int:
        """计算开仓手数（简化版）"""
        available_cash = self.get_available_cash()
        # 使用固定比例的可用资金
        position_value = available_cash * 0.9  # 使用90%可用资金
        volume = int(position_value / price / 100) * 100  # 按手计算（100股一手）
        return max(volume, 100)  # 最少1手
    
    def on_stop(self) -> None:
        """策略停止时的清理操作"""
        super().on_stop()
        self.in_position = False
        self.last_signal = None
        self.last_close = 0.0


def create_three_ma_cross_strategy(params: dict = None) -> ThreeMACrossStrategy:
    """创建三均线穿越策略实例"""
    return ThreeMACrossStrategy("three_ma_cross", params)