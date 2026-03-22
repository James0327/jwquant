"""
策略基类
定义策略生命周期方法：on_init / on_bar / on_tick / on_order / on_trade。
所有策略需继承此基类。
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

from jwquant.common.types import Bar, Order, Signal, Position, Asset
from jwquant.trading.indicator.talib_wrap import TechnicalIndicators


class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self, name: str, params: dict | None = None):
        self.name = name
        self.params = params or {}
        self.position: Optional[Position] = None
        self.asset: Optional[Asset] = None
        self.history_bars: List[Bar] = []
        self.signals: List[Signal] = []
        self.orders: List[Order] = []
        self.indicators = TechnicalIndicators()
        self._initialized = False
        
    def on_init(self) -> None:
        """策略初始化，加载参数和指标"""
        self._initialized = True
        print(f"策略 {self.name} 初始化完成")
        
    def update_position(self, position: Position) -> None:
        """更新当前持仓"""
        self.position = position
        
    def update_asset(self, asset: Asset) -> None:
        """更新账户资产"""
        self.asset = asset
        
    def add_bar(self, bar: Bar) -> None:
        """添加新的K线数据"""
        self.history_bars.append(bar)
        # 保持历史数据长度合理
        max_history = self.params.get('max_history', 1000)
        if len(self.history_bars) > max_history:
            self.history_bars = self.history_bars[-max_history:]
            
    def get_history_dataframe(self) -> pd.DataFrame:
        """获取历史数据DataFrame"""
        if not self.history_bars:
            return pd.DataFrame()
            
        data = []
        for bar in self.history_bars:
            data.append({
                'code': bar.code,
                'dt': bar.dt,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume,
                'amount': bar.amount
            })
        
        return pd.DataFrame(data)
    
    def get_current_price(self) -> float:
        """获取当前价格"""
        if self.history_bars:
            return self.history_bars[-1].close
        return 0.0
    
    def get_position_size(self) -> int:
        """获取当前持仓数量"""
        if self.position:
            return self.position.volume
        return 0
    
    def get_available_cash(self) -> float:
        """获取可用资金"""
        if self.asset:
            return self.asset.cash
        return 0.0
    
    def calculate_position_value(self) -> float:
        """计算持仓价值"""
        if self.position and self.history_bars:
            current_price = self.get_current_price()
            return self.position.volume * current_price
        return 0.0
    
    def get_total_asset(self) -> float:
        """获取总资产"""
        if self.asset:
            return self.asset.total_asset
        return 0.0
    
    @abstractmethod
    def on_bar(self, bar: Bar) -> Signal | None:
        """每根 K 线触发，执行策略逻辑，返回信号或 None"""
        ...
    
    def on_tick(self, tick: dict) -> Signal | None:
        """每个 Tick 触发（高频策略可覆写）"""
        return None
    
    def on_order(self, order: Order) -> None:
        """委托状态变更回调"""
        self.orders.append(order)
        print(f"订单状态更新: {order.code} {order.direction.value} {order.status.value}")
    
    def record_signal(self, signal: Signal) -> None:
        """记录交易信号"""
        self.signals.append(signal)
        print(f"产生信号: {signal.code} {signal.signal_type.value} @{signal.price:.2f} - {signal.reason}")
    
    def get_recent_signals(self, count: int = 10) -> List[Signal]:
        """获取最近的交易信号"""
        return self.signals[-count:] if self.signals else []
    
    def on_stop(self) -> None:
        """策略停止时的清理操作"""
        print(f"策略 {self.name} 已停止")
        self._initialized = False


class StrategyManager:
    """策略管理器"""
    
    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {}
        self.active_strategies: List[str] = []
    
    def register_strategy(self, strategy: BaseStrategy) -> None:
        """注册策略"""
        self.strategies[strategy.name] = strategy
        print(f"注册策略: {strategy.name}")
    
    def activate_strategy(self, strategy_name: str) -> bool:
        """激活策略"""
        if strategy_name in self.strategies:
            if strategy_name not in self.active_strategies:
                self.active_strategies.append(strategy_name)
                self.strategies[strategy_name].on_init()
                print(f"激活策略: {strategy_name}")
            return True
        return False
    
    def deactivate_strategy(self, strategy_name: str) -> bool:
        """停用策略"""
        if strategy_name in self.active_strategies:
            self.active_strategies.remove(strategy_name)
            self.strategies[strategy_name].on_stop()
            print(f"停用策略: {strategy_name}")
            return True
        return False
    
    def get_strategy(self, strategy_name: str) -> Optional[BaseStrategy]:
        """获取策略实例"""
        return self.strategies.get(strategy_name)
    
    def get_active_strategies(self) -> List[BaseStrategy]:
        """获取活跃策略列表"""
        return [self.strategies[name] for name in self.active_strategies]
    
    def process_bar(self, bar: Bar) -> List[Signal]:
        """处理K线数据，返回所有策略产生的信号"""
        signals = []
        for strategy in self.get_active_strategies():
            strategy.add_bar(bar)
            signal = strategy.on_bar(bar)
            if signal:
                strategy.record_signal(signal)
                signals.append(signal)
        return signals
    
    def get_strategy_status(self) -> Dict[str, str]:
        """获取所有策略状态"""
        status = {}
        for name, strategy in self.strategies.items():
            status[name] = "ACTIVE" if name in self.active_strategies else "INACTIVE"
        return status