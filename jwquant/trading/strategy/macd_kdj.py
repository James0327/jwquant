"""
MACD+KDJ组合策略
结合MACD趋势指标和KDJ超买超卖指标的复合策略

核心原理：
========
• MACD（平滑异同移动平均线）：识别市场趋势方向和动能
• KDJ（随机指标）：判断超买超卖状态和转折点
• 双指标融合：趋势过滤 + 时机把握，提高信号质量

技术优势：
========
• 优势互补：MACD擅长趋势跟踪，KDJ擅长反转预警
• 信号过滤：只在MACD多头时做多，避免逆势交易
• 精准择时：利用KDJ在超买区寻找卖出时机
• 风险可控：双重确认机制降低假信号概率

策略逻辑：
========
买入条件：
- MACD > 0 且 DIF > DEA（MACD在零轴上方且快线在慢线上方）

卖出条件：
- K > 80 且 D > 80 且 J > 80（超买区域）
- 且 J向下突破D（J值从上方向下穿过D值）

使用场景：
========
适用市场：
• 适合大多数股票和指数
• 对趋势和超买超卖都很敏感
• 适合中短线波段操作

适用周期：
• 日线级别：最佳应用场景
• 60分钟级别：适合日内交易
• 30分钟级别：适合高频交易

策略优势：
• MACD过滤趋势方向，避免逆势操作
• KDJ提供精确的买卖时机
• 组合使用提高信号准确率
• 既有趋势跟踪又有反转预警

参数优化建议：
• MACD参数：(12,26,9)是标准配置
• KDJ参数：(9,3,3)较为常用
• 可根据品种特性微调参数

注意事项：
• 需要足够的历史数据计算指标
• 在极端行情中可能出现延迟信号
• 建议结合基本面分析使用
"""
import numpy as np
from typing import Optional, Tuple

from jwquant.common.types import Bar, Signal, SignalType
from jwquant.common.config import get_strategy_config
from jwquant.trading.strategy.base import BaseStrategy


class MACDKDJStrategy(BaseStrategy):
    """MACD+KDJ组合策略实现"""
    
    def __init__(self, name: str = "macd_kdj", params: dict | None = None):
        super().__init__(name, params)
        
        # 从配置文件获取策略参数
        strategy_config = get_strategy_config(name, {
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'kdj_fastk': 9,
            'kdj_slowk': 3,
            'kdj_slowd': 3,
            'min_history': 34,
            'overbought_threshold': 80
        })
        
        # 合并传入的参数（优先级更高）
        if params:
            strategy_config.update(params)
        
        # MACD参数
        self.macd_fast = strategy_config['macd_fast']      # 快线周期
        self.macd_slow = strategy_config['macd_slow']      # 慢线周期
        self.macd_signal = strategy_config['macd_signal']  # 信号线周期
        
        # KDJ参数
        self.kdj_fastk = strategy_config['kdj_fastk']      # K周期
        self.kdj_slowk = strategy_config['kdj_slowk']      # K平滑周期
        self.kdj_slowd = strategy_config['kdj_slowd']      # D平滑周期
        
        # 策略参数
        self.min_history = strategy_config['min_history']  # 最小历史数据
        self.overbought_threshold = strategy_config['overbought_threshold']  # 超买阈值
        
        # 策略状态
        self.in_position = False
        self.last_signal = None
        self.previous_j = None  # 记录前一个J值用于判断突破方向
        
    def on_init(self) -> None:
        """策略初始化"""
        super().on_init()
        print(f"MACD+KDJ组合策略参数:")
        print(f"  MACD: 快线{self.macd_fast}, 慢线{self.macd_slow}, 信号线{self.macd_signal}")
        print(f"  KDJ: K周期{self.kdj_fastk}, K平滑{self.kdj_slowk}, D平滑{self.kdj_slowd}")
        print(f"  超买阈值: {self.overbought_threshold}")
        
    def calculate_macd(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
        """计算MACD指标"""
        if len(self.history_bars) < max(self.macd_slow, self.macd_signal):
            return None, None, None
            
        closes = [bar.close for bar in self.history_bars]
        macd_line, signal_line, hist = self.indicators.macd(
            closes, self.macd_fast, self.macd_slow, self.macd_signal
        )
        
        return macd_line, signal_line, hist
    
    def calculate_kdj(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
        """计算KDJ指标"""
        if len(self.history_bars) < self.kdj_fastk:
            return None, None, None
            
        highs = [bar.high for bar in self.history_bars]
        lows = [bar.low for bar in self.history_bars]
        closes = [bar.close for bar in self.history_bars]
        
        k, d, j = self.indicators.kdj(
            highs, lows, closes, self.kdj_fastk, self.kdj_slowk, self.kdj_slowd
        )
        
        return k, d, j
    
    def check_buy_signal(self, macd_line: np.ndarray, signal_line: np.ndarray, 
                        hist: np.ndarray) -> bool:
        """检查买入信号条件"""
        if len(macd_line) < 2 or len(signal_line) < 2:
            return False
            
        # 获取最新的MACD值
        current_macd = macd_line[-1]
        current_dea = signal_line[-1]
        current_dif = current_macd  # DIF就是MACD线本身
        
        # 买入条件：MACD > 0 且 DIF > DEA
        macd_positive = current_macd > 0
        dif_above_dea = current_dif > current_dea
        
        return macd_positive and dif_above_dea
    
    def check_sell_signal(self, k: np.ndarray, d: np.ndarray, j: np.ndarray) -> bool:
        """检查卖出信号条件"""
        if len(k) < 2 or len(d) < 2 or len(j) < 2:
            return False
            
        # 获取最新的KDJ值
        current_k = k[-1]
        current_d = d[-1]
        current_j = j[-1]
        
        # 检查前一个J值
        if self.previous_j is None:
            self.previous_j = current_j
            return False
            
        # 超买条件：K > 80 且 D > 80 且 J > 80
        overbought_k = current_k > self.overbought_threshold
        overbought_d = current_d > self.overbought_threshold
        overbought_j = current_j > self.overbought_threshold
        overbought_condition = overbought_k and overbought_d and overbought_j
        
        # J向下突破D：当前J < D 且 前一个J > 前一个D
        j_below_d = current_j < current_d
        prev_j_above_prev_d = self.previous_j > d[-2] if len(d) >= 2 else False
        downward_cross = j_below_d and prev_j_above_prev_d
        
        # 更新前一个J值
        self.previous_j = current_j
        
        return overbought_condition and downward_cross
    
    def on_bar(self, bar: Bar) -> Signal | None:
        """每根K线触发，执行策略逻辑"""
        # 检查是否有足够历史数据
        if len(self.history_bars) < self.min_history:
            return None
            
        # 计算MACD指标
        macd_line, signal_line, hist = self.calculate_macd()
        if macd_line is None or signal_line is None or hist is None:
            return None
            
        # 计算KDJ指标
        k, d, j = self.calculate_kdj()
        if k is None or d is None or j is None:
            return None
            
        # 检查买入信号
        if self.check_buy_signal(macd_line, signal_line, hist) and not self.in_position:
            self.in_position = True
            self.last_signal = SignalType.BUY
            
            current_macd = macd_line[-1]
            current_dea = signal_line[-1]
            
            signal = Signal(
                code=bar.code,
                dt=bar.dt,
                signal_type=SignalType.BUY,
                price=bar.close,
                reason=f"MACD+KDJ买入：MACD({current_macd:.2f})>0 且 DIF>DEA({current_dea:.2f})"
            )
            return signal
            
        # 检查卖出信号
        elif self.check_sell_signal(k, d, j) and self.in_position:
            self.in_position = False
            self.last_signal = SignalType.SELL
            
            current_k = k[-1]
            current_d = d[-1]
            current_j = j[-1]
            
            signal = Signal(
                code=bar.code,
                dt=bar.dt,
                signal_type=SignalType.SELL,
                price=bar.close,
                reason=f"MACD+KDJ卖出：K({current_k:.1f})D({current_d:.1f})J({current_j:.1f})超买区且J下穿D"
            )
            return signal
            
        return None
    
    def calculate_position_volume(self, price: float) -> int:
        """计算开仓手数（简化版）"""
        available_cash = self.get_available_cash()
        position_value = available_cash * 0.9  # 使用90%可用资金
        volume = int(position_value / price / 100) * 100  # 按手计算
        return max(volume, 100)  # 最少1手
    
    def on_stop(self) -> None:
        """策略停止时的清理操作"""
        super().on_stop()
        self.in_position = False
        self.last_signal = None
        self.previous_j = None


def create_macd_kdj_strategy(params: dict = None) -> MACDKDJStrategy:
    """创建MACD+KDJ策略实例"""
    return MACDKDJStrategy("macd_kdj", params)