"""
海龟交易策略
唐奇安通道突破入场，ATR 动态止损与加仓，科学仓位管理。
"""
import numpy as np
from typing import Optional

from jwquant.common.types import Bar, Signal, SignalType
from jwquant.trading.strategy.base import BaseStrategy


class TurtleStrategy(BaseStrategy):
    """海龟交易策略实现"""
    
    def __init__(self, name: str = "turtle", params: dict | None = None):
        super().__init__(name, params)
        
        # 默认参数
        self.entry_window = params.get('entry_window', 20)      # 入场突破窗口
        self.exit_window = params.get('exit_window', 10)        # 离场突破窗口
        self.atr_period = params.get('atr_period', 20)          # ATR 计算周期
        self.risk_ratio = params.get('risk_ratio', 0.01)        # 单次风险比例
        self.max_positions = params.get('max_positions', 4)     # 最大加仓次数
        self.pyramid_ratio = params.get('pyramid_ratio', 0.5)   # 加仓比例
        
        # 策略状态
        self.in_position = False
        self.entry_price = 0.0
        self.stop_loss_price = 0.0
        self.position_count = 0
        self.last_entry_price = 0.0
        
    def on_init(self) -> None:
        """策略初始化"""
        super().on_init()
        print(f"海龟策略参数: 入场窗口={self.entry_window}, 离场窗口={self.exit_window}")
        print(f"ATR周期={self.atr_period}, 风险比例={self.risk_ratio}")
        
    def calculate_donchian_channel(self, period: int) -> tuple[float, float, float]:
        """计算唐奇安通道"""
        if len(self.history_bars) < period:
            return 0.0, 0.0, 0.0
            
        highs = [bar.high for bar in self.history_bars[-period:]]
        lows = [bar.low for bar in self.history_bars[-period:]]
        
        upper = max(highs)
        lower = min(lows)
        middle = (upper + lower) / 2
        
        return upper, middle, lower
    
    def calculate_atr(self, period: int) -> float:
        """计算ATR"""
        if len(self.history_bars) < period + 1:
            return 0.0
            
        tr_values = []
        for i in range(len(self.history_bars) - period, len(self.history_bars)):
            bar = self.history_bars[i]
            if i > 0:
                prev_close = self.history_bars[i-1].close
                tr1 = bar.high - bar.low
                tr2 = abs(bar.high - prev_close)
                tr3 = abs(bar.low - prev_close)
                tr = max(tr1, tr2, tr3)
                tr_values.append(tr)
        
        return np.mean(tr_values) if tr_values else 0.0
    
    def calculate_position_size(self, atr: float) -> int:
        """根据ATR计算仓位大小"""
        if atr <= 0 or not self.asset:
            return 0
            
        # 风险金额 = 总资产 × 风险比例
        risk_amount = self.get_total_asset() * self.risk_ratio
        
        # 每手风险 = ATR × 合约乘数(股票为1)
        per_unit_risk = atr
        
        # 仓位大小 = 风险金额 / 每手风险
        position_size = int(risk_amount / per_unit_risk)
        
        # 限制最小交易单位
        min_size = self.params.get('min_position', 100)
        position_size = max(position_size, min_size)
        
        return position_size
    
    def check_entry_condition(self, bar: Bar) -> Optional[Signal]:
        """检查入场条件"""
        if len(self.history_bars) < self.entry_window:
            return None
            
        # 计算唐奇安通道
        entry_upper, _, _ = self.calculate_donchian_channel(self.entry_window)
        
        # 突破上轨且未持仓
        if not self.in_position and bar.close > entry_upper:
            atr = self.calculate_atr(self.atr_period)
            if atr > 0:
                position_size = self.calculate_position_size(atr)
                
                signal = Signal(
                    code=bar.code,
                    dt=bar.dt,
                    signal_type=SignalType.BUY,
                    price=bar.close,
                    strength=1.0,
                    reason=f"海龟突破入场: 价格{bar.close:.2f}突破{entry_upper:.2f}"
                )
                
                self.in_position = True
                self.entry_price = bar.close
                self.last_entry_price = bar.close
                self.position_count = 1
                self.stop_loss_price = bar.close - 2 * atr
                
                return signal
                
        # 加仓条件：价格上涨超过N/2且未达到最大仓位
        elif self.in_position and self.position_count < self.max_positions:
            atr = self.calculate_atr(self.atr_period)
            add_price = self.last_entry_price + 0.5 * atr
            
            if bar.close > add_price:
                position_size = self.calculate_position_size(atr)
                add_size = int(position_size * (self.pyramid_ratio ** self.position_count))
                
                if add_size > 0:
                    signal = Signal(
                        code=bar.code,
                        dt=bar.dt,
                        signal_type=SignalType.BUY,
                        price=bar.close,
                        strength=0.7,
                        reason=f"海龟加仓: 第{self.position_count + 1}次加仓"
                    )
                    
                    self.last_entry_price = bar.close
                    self.position_count += 1
                    return signal
        
        return None
    
    def check_exit_condition(self, bar: Bar) -> Optional[Signal]:
        """检查离场条件"""
        if not self.in_position:
            return None
            
        # 计算离场通道
        _, _, exit_lower = self.calculate_donchian_channel(self.exit_window)
        
        # 止损出场
        if bar.close < self.stop_loss_price:
            signal = Signal(
                code=bar.code,
                dt=bar.dt,
                signal_type=SignalType.SELL,
                price=bar.close,
                strength=1.0,
                reason=f"海龟止损出场: 价格{bar.close:.2f}跌破止损{self.stop_loss_price:.2f}"
            )
            
            self.reset_position()
            return signal
            
        # 离场通道出场
        elif bar.close < exit_lower:
            signal = Signal(
                code=bar.code,
                dt=bar.dt,
                signal_type=SignalType.SELL,
                price=bar.close,
                strength=0.8,
                reason=f"海龟通道离场: 价格{bar.close:.2f}跌破{exit_lower:.2f}"
            )
            
            self.reset_position()
            return signal
            
        return None
    
    def reset_position(self) -> None:
        """重置持仓状态"""
        self.in_position = False
        self.entry_price = 0.0
        self.stop_loss_price = 0.0
        self.position_count = 0
        self.last_entry_price = 0.0
    
    def on_bar(self, bar: Bar) -> Signal | None:
        """每根K线执行策略逻辑"""
        # 更新数据
        self.add_bar(bar)
        
        # 检查离场条件（优先）
        exit_signal = self.check_exit_condition(bar)
        if exit_signal:
            return exit_signal
            
        # 检查入场条件
        entry_signal = self.check_entry_condition(bar)
        if entry_signal:
            return entry_signal
            
        return None
    
    def on_stop(self) -> None:
        """策略停止"""
        self.reset_position()
        super().on_stop()


# 快捷创建函数
def create_turtle_strategy(params: dict | None = None) -> TurtleStrategy:
    """创建海龟策略实例"""
    default_params = {
        'entry_window': 20,
        'exit_window': 10,
        'atr_period': 20,
        'risk_ratio': 0.01,
        'max_positions': 4,
        'pyramid_ratio': 0.5,
        'min_position': 100
    }
    
    if params:
        default_params.update(params)
        
    return TurtleStrategy("turtle", default_params)