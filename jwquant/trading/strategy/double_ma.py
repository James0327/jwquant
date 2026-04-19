"""
双均线交叉策略
基于两条不同周期移动平均线的金叉死叉信号进行趋势判断的经典策略

核心原理：
========
利用快慢两条均线的相对位置关系来判断市场趋势：
• 金叉（短期均线上穿长期均线）：上升趋势信号
• 死叉（短期均线下穿长期均线）：下降趋势信号

技术优势：
========
• 趋势过滤：双均线组合能更好地过滤震荡市噪音
• 信号确认：相比单均线具有更强的信号确认能力
• 参数组合：多种周期搭配适应不同市场环境
• 应用广泛：是最经典的均线交易策略之一

策略逻辑：
- 买入信号：短期均线上穿长期均线（金叉）
- 卖出信号：短期均线下穿长期均线（死叉）

参数建议：
========
• 短线组合：5日 + 10日，适合活跃品种
• 中线组合：10日 + 30日，平衡灵敏度与稳定性
• 长线组合：20日 + 60日，适合稳健型投资者

使用场景：
========
适用市场：
• 适合大多数股票和指数品种
• 对趋势转换较为敏感
• 适合中短线波段操作

适用周期：
• 日线级别：最常用的时间框架
• 60分钟级别：适合日内交易
• 周线级别：适合中长线投资

参数搭配建议：
• 短期5日 + 长期10日：反应灵敏，适合活跃品种
• 短期10日 + 长期30日：平衡灵敏度与稳定性
• 短期20日 + 长期60日：适合稳健型投资者

优势特点：
• 过滤掉部分假信号
• 趋势识别能力较强
• 信号相对可靠

注意事项：
• 在震荡行情中可能产生反复交叉信号
• 需要注意参数设置的合理性
• 可结合其他技术指标提高准确率
"""
import numpy as np
from typing import Optional

from jwquant.common.types import Bar, Signal, SignalType
from jwquant.common.config import get_strategy_config
from jwquant.trading.strategy.base import BaseStrategy


class DoubleMAStrategy(BaseStrategy):
    """双均线交叉策略实现"""
    
    def __init__(self, name: str = "double_ma", params: dict | None = None):
        super().__init__(name, params)
        
        # 从配置文件获取策略参数
        strategy_config = get_strategy_config(name)
        
        # 合并传入的参数（优先级更高）
        if params:
            strategy_config.update(params)
        
        # 设置参数
        self.short_ma_period = strategy_config['short_ma_period']
        self.long_ma_period = strategy_config['long_ma_period']
        self.min_history = strategy_config['min_history']
        
        # 策略状态
        self.in_position = False
        self.last_signal = None  # 记录上次信号类型
        
    def on_init(self) -> None:
        """策略初始化"""
        super().on_init()
        print(f"双均线策略参数: 短期MA={self.short_ma_period}, 长期MA={self.long_ma_period}, 最小历史数据={self.min_history}")
        
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
    
    def get_ma_values_yesterday(self) -> tuple[Optional[float], Optional[float]]:
        """获取昨日的短期和长期MA值"""
        if len(self.history_bars) < max(self.short_ma_period, self.long_ma_period) + 1:
            return None, None
            
        # 计算短期MA序列
        short_ma_series = self.calculate_moving_average(self.short_ma_period)
        # 计算长期MA序列
        long_ma_series = self.calculate_moving_average(self.long_ma_period)
        
        if not short_ma_series or not long_ma_series:
            return None, None
            
        # 昨日的MA值（倒数第二个）
        yesterday_short_ma = short_ma_series[-2] if len(short_ma_series) >= 2 else None
        yesterday_long_ma = long_ma_series[-2] if len(long_ma_series) >= 2 else None
        
        return yesterday_short_ma, yesterday_long_ma
    
    def get_ma_values_day_before_yesterday(self) -> tuple[Optional[float], Optional[float]]:
        """获取前日的短期和长期MA值"""
        if len(self.history_bars) < max(self.short_ma_period, self.long_ma_period) + 2:
            return None, None
            
        # 计算短期MA序列
        short_ma_series = self.calculate_moving_average(self.short_ma_period)
        # 计算长期MA序列
        long_ma_series = self.calculate_moving_average(self.long_ma_period)
        
        if not short_ma_series or not long_ma_series:
            return None, None
            
        # 前日的MA值（倒数第三个）
        day_before_yesterday_short_ma = short_ma_series[-3] if len(short_ma_series) >= 3 else None
        day_before_yesterday_long_ma = long_ma_series[-3] if len(long_ma_series) >= 3 else None
        
        return day_before_yesterday_short_ma, day_before_yesterday_long_ma
    
    def check_buy_signal(self) -> bool:
        """检查买入信号条件"""
        # 获取昨日数据
        yesterday_short_ma, yesterday_long_ma = self.get_ma_values_yesterday()
        if yesterday_short_ma is None or yesterday_long_ma is None:
            return False
            
        # 获取前日数据
        day_before_yesterday_short_ma, day_before_yesterday_long_ma = self.get_ma_values_day_before_yesterday()
        if day_before_yesterday_short_ma is None or day_before_yesterday_long_ma is None:
            return False
            
        # 买入条件：
        # 1. 昨日短期MA > 昨日长期MA
        # 2. 前日短期MA < 前日长期MA
        condition1 = yesterday_short_ma > yesterday_long_ma
        condition2 = day_before_yesterday_short_ma < day_before_yesterday_long_ma
        
        return condition1 and condition2
    
    def check_sell_signal(self) -> bool:
        """检查卖出信号条件"""
        # 获取昨日数据
        yesterday_short_ma, yesterday_long_ma = self.get_ma_values_yesterday()
        if yesterday_short_ma is None or yesterday_long_ma is None:
            return False

        # 获取前日数据
        day_before_yesterday_short_ma, day_before_yesterday_long_ma = self.get_ma_values_day_before_yesterday()
        if day_before_yesterday_short_ma is None or day_before_yesterday_long_ma is None:
            return False

        # 卖出条件：
        # 1. 昨日短期MA < 昨日长期MA
        # 2. 前日短期MA > 前日长期MA
        condition1 = yesterday_short_ma < yesterday_long_ma
        condition2 = day_before_yesterday_short_ma > day_before_yesterday_long_ma
        
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
            
            yesterday_short_ma, yesterday_long_ma = self.get_ma_values_yesterday()
            day_before_yesterday_short_ma, day_before_yesterday_long_ma = self.get_ma_values_day_before_yesterday()
            
            signal = Signal(
                code=bar.code,
                dt=bar.dt,
                signal_type=SignalType.BUY,
                price=bar.close,
                reason=f"双MA金叉：昨MA{self.short_ma_period}({yesterday_short_ma:.2f})>昨MA{self.long_ma_period}({yesterday_long_ma:.2f})，前MA{self.short_ma_period}({day_before_yesterday_short_ma:.2f})<前MA{self.long_ma_period}({day_before_yesterday_long_ma:.2f})"
            )
            return signal
            
        # 检查卖出信号
        elif self.check_sell_signal() and self.in_position:
            self.in_position = False
            self.last_signal = SignalType.SELL
            
            yesterday_short_ma, yesterday_long_ma = self.get_ma_values_yesterday()
            day_before_yesterday_short_ma, day_before_yesterday_long_ma = self.get_ma_values_day_before_yesterday()
            
            signal = Signal(
                code=bar.code,
                dt=bar.dt,
                signal_type=SignalType.SELL,
                price=bar.close,
                reason=f"双MA死叉：昨MA{self.short_ma_period}({yesterday_short_ma:.2f})<昨MA{self.long_ma_period}({yesterday_long_ma:.2f})，前MA{self.short_ma_period}({day_before_yesterday_short_ma:.2f})>前MA{self.long_ma_period}({day_before_yesterday_long_ma:.2f})"
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


def create_double_ma_strategy(params: dict = None) -> DoubleMAStrategy:
    """创建双均线策略实例"""
    return DoubleMAStrategy("double_ma", params)
