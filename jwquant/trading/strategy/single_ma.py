"""
单均线交叉策略
基于移动平均线的价格交叉信号进行买卖决策的经典趋势跟踪策略

核心原理：
========
该策略利用移动平均线的平滑特性来识别价格趋势方向，
当价格突破均线时视为趋势转换信号。

技术特点：
========
• 趋势跟踪：能够有效跟随市场主要趋势
• 信号简洁：买入卖出信号明确，易于执行
• 参数灵活：可根据不同市场调整均线周期
• 计算简单：资源消耗低，适合批量回测

策略逻辑：
- 买入信号：价格上穿均线（由下向上突破）
- 卖出信号：价格下穿均线（由上向下突破）

使用场景：
========
适用市场：
• 趋势性较强的股票或指数
• 波段操作的理想选择
• 适合中短期交易（日线、小时线）

适用周期：
• 日线级别：适合捕捉中期趋势
• 小时线级别：适合日内波段操作
• 周线级别：适合长线趋势跟踪

参数建议：
• 均线周期：15-30日较为常见
• 周期越短：反应越灵敏但假信号较多
• 周期越长：趋势更稳定但滞后性较强

注意事项：
• 在震荡市中容易产生频繁的假信号
• 建议结合成交量或其他指标过滤信号
• 可适当调整均线周期适应不同品种特性
"""
import numpy as np
from typing import Optional

from jwquant.common.types import Bar, Signal, SignalType
from jwquant.common.config import get_strategy_config
from jwquant.trading.strategy.base import BaseStrategy


class SingleMAStrategy(BaseStrategy):
    """单均线交叉策略实现"""
    
    def __init__(self, name: str = "single_ma", params: dict | None = None):
        super().__init__(name, params)
        
        # 从配置文件获取策略参数
        strategy_config = get_strategy_config(name)
        
        # 合并传入的参数（优先级更高）
        if params:
            strategy_config.update(params)
        
        # 设置参数
        self.ma_period = strategy_config['ma_period']
        self.min_history = strategy_config['min_history']
        
        # 策略状态
        self.in_position = False
        self.last_signal = None  # 记录上次信号类型
        
    def on_init(self) -> None:
        """策略初始化"""
        super().on_init()
        print(f"单均线策略参数: MA周期={self.ma_period}, 最小历史数据={self.min_history}")
        
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
    
    def get_price_and_ma_yesterday(self) -> tuple[Optional[float], Optional[float]]:
        """获取昨日收盘价和昨日MA值"""
        if len(self.history_bars) < self.ma_period + 1:
            return None, None
            
        # 昨日收盘价
        yesterday_close = self.history_bars[-2].close
        
        # 计算到昨日为止的MA序列
        ma_series = self.calculate_moving_average(self.ma_period)
        if not ma_series:
            return None, None
            
        # 昨日的MA值（倒数第二个）
        yesterday_ma = ma_series[-2] if len(ma_series) >= 2 else None
        
        return yesterday_close, yesterday_ma
    
    def get_price_and_ma_day_before_yesterday(self) -> tuple[Optional[float], Optional[float]]:
        """获取前日收盘价和前日MA值"""
        if len(self.history_bars) < self.ma_period + 2:
            return None, None
            
        # 前日收盘价
        day_before_yesterday_close = self.history_bars[-3].close
        
        # 计算到前日为止的MA序列
        ma_series = self.calculate_moving_average(self.ma_period)
        if not ma_series:
            return None, None
            
        # 前日的MA值（倒数第三个）
        day_before_yesterday_ma = ma_series[-3] if len(ma_series) >= 3 else None
        
        return day_before_yesterday_close, day_before_yesterday_ma
    
    def check_buy_signal(self) -> bool:
        """检查买入信号条件"""
        # 获取昨日数据
        yesterday_close, yesterday_ma = self.get_price_and_ma_yesterday()
        if yesterday_close is None or yesterday_ma is None:
            return False
            
        # 获取前日数据
        day_before_yesterday_close, day_before_yesterday_ma = self.get_price_and_ma_day_before_yesterday()
        if day_before_yesterday_close is None or day_before_yesterday_ma is None:
            return False
            
        # 买入条件：
        # 1. 昨日收盘价 > 昨日MA15
        # 2. 前日收盘价 < 前日MA15
        condition1 = yesterday_close > yesterday_ma
        condition2 = day_before_yesterday_close < day_before_yesterday_ma
        
        return condition1 and condition2
    
    def check_sell_signal(self) -> bool:
        """检查卖出信号条件"""
        # 获取昨日数据
        yesterday_close, yesterday_ma = self.get_price_and_ma_yesterday()
        if yesterday_close is None or yesterday_ma is None:
            return False
            
        # 获取前日数据
        day_before_yesterday_close, day_before_yesterday_ma = self.get_price_and_ma_day_before_yesterday()
        if day_before_yesterday_close is None or day_before_yesterday_ma is None:
            return False
            
        # 卖出条件：
        # 1. 昨日收盘价 < 昨日MA15
        # 2. 前日收盘价 > 前日MA15
        condition1 = yesterday_close < yesterday_ma
        condition2 = day_before_yesterday_close > day_before_yesterday_ma
        
        return condition1 and condition2
    
    def on_bar(self, bar: Bar) -> Signal | None:
        """每根K线触发，执行策略逻辑"""
        # 检查是否有足够历史数据
        if len(self.history_bars) < self.min_history:
            return None
            
        # 检查买入信号
        if self.check_buy_signal() and not self.in_position:
            self.in_position = True
            self.last_signal = SignalType.BUY
            
            signal = Signal(
                code=bar.code,
                dt=bar.dt,
                signal_type=SignalType.BUY,
                price=bar.close,
                reason=f"MA{self.ma_period}金叉：昨收{bar.close:.2f}>昨MA{self.get_price_and_ma_yesterday()[1]:.2f}，前收{self.history_bars[-3].close:.2f}<{self.get_price_and_ma_day_before_yesterday()[1]:.2f}"
            )
            return signal
            
        # 检查卖出信号
        elif self.check_sell_signal() and self.in_position:
            self.in_position = False
            self.last_signal = SignalType.SELL
            
            signal = Signal(
                code=bar.code,
                dt=bar.dt,
                signal_type=SignalType.SELL,
                price=bar.close,
                reason=f"MA{self.ma_period}死叉：昨收{bar.close:.2f}<{self.get_price_and_ma_yesterday()[1]:.2f}，前收{self.history_bars[-3].close:.2f}>{self.get_price_and_ma_day_before_yesterday()[1]:.2f}"
            )
            return signal
            
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

def create_single_ma_strategy(params: dict = None) -> SingleMAStrategy:
    """创建单均线策略实例"""
    return SingleMAStrategy("single_ma", params)
