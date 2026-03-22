"""
网格交易策略
均值回归逻辑，在价格网格内自动低买高卖。
"""
from typing import List, Optional
import numpy as np

from jwquant.common.types import Bar, Signal, SignalType, Position
from jwquant.trading.strategy.base import BaseStrategy


class GridLevel:
    """网格层级"""
    def __init__(self, price: float, buy_volume: int = 0, sell_volume: int = 0):
        self.price = price
        self.buy_volume = buy_volume      # 该价位已买入数量
        self.sell_volume = sell_volume    # 该价位已卖出数量
        self.max_volume = buy_volume      # 该价位最大持仓量


class GridStrategy(BaseStrategy):
    """网格交易策略实现"""
    
    def __init__(self, name: str = "grid", params: dict | None = None):
        super().__init__(name, params)
        
        # 网格参数
        self.grid_count = params.get('grid_count', 10)          # 网格数量
        self.grid_spacing = params.get('grid_spacing', 0.02)    # 网格间距(百分比)
        self.base_amount = params.get('base_amount', 10000)     # 每格交易金额
        self.center_price = params.get('center_price', 0.0)     # 网格中心价格
        self.max_position_per_grid = params.get('max_position_per_grid', 1)  # 每格最大持仓
        
        # 网格状态
        self.grid_levels: List[GridLevel] = []
        self.current_grid_index = -1
        self.initialized = False
        
    def on_init(self) -> None:
        """策略初始化"""
        super().on_init()
        print(f"网格策略参数: 网格数={self.grid_count}, 间距={self.grid_spacing*100:.1f}%")
        print(f"每格金额={self.base_amount}, 中心价={self.center_price}")
        
    def initialize_grids(self, current_price: float) -> None:
        """初始化网格"""
        if self.initialized:
            return
            
        # 如果没有设置中心价格，使用当前价格
        center = self.center_price if self.center_price > 0 else current_price
        
        # 计算网格价格
        half_grids = self.grid_count // 2
        self.grid_levels = []
        
        for i in range(-half_grids, half_grids + 1):
            price = center * (1 + i * self.grid_spacing)
            level = GridLevel(price, 0, 0)
            # 计算每格的最大持仓量
            level.max_volume = max(1, int(self.base_amount / price))
            self.grid_levels.append(level)
        
        # 找到当前价格对应的网格
        self.current_grid_index = self.find_grid_index(current_price)
        self.initialized = True
        
        print(f"网格初始化完成，中心价: {center:.2f}")
        for i, level in enumerate(self.grid_levels):
            print(f"网格{i}: 价格{level.price:.2f}, 最大持仓{level.max_volume}")
        
    def find_grid_index(self, price: float) -> int:
        """找到价格对应的网格索引"""
        for i, level in enumerate(self.grid_levels):
            if price <= level.price:
                return i
        return len(self.grid_levels) - 1
    
    def get_grid_info(self, index: int) -> Optional[GridLevel]:
        """获取指定网格信息"""
        if 0 <= index < len(self.grid_levels):
            return self.grid_levels[index]
        return None
    
    def can_buy(self, grid_index: int) -> bool:
        """判断是否可以在该网格买入"""
        grid = self.get_grid_info(grid_index)
        if not grid:
            return False
        return grid.buy_volume < grid.max_volume * self.max_position_per_grid
    
    def can_sell(self, grid_index: int) -> bool:
        """判断是否可以在该网格卖出"""
        grid = self.get_grid_info(grid_index)
        if not grid:
            return False
        return grid.buy_volume > grid.sell_volume
    
    def check_buy_opportunity(self, bar: Bar, current_grid: int) -> Optional[Signal]:
        """检查买入机会"""
        # 向下穿越网格时买入
        if current_grid < self.current_grid_index and self.can_buy(current_grid):
            grid = self.grid_levels[current_grid]
            
            signal = Signal(
                code=bar.code,
                dt=bar.dt,
                signal_type=SignalType.BUY,
                price=grid.price,
                strength=0.8,
                reason=f"网格买入: 价格下跌至{grid.price:.2f}"
            )
            
            grid.buy_volume += 1
            return signal
        
        return None
    
    def check_sell_opportunity(self, bar: Bar, current_grid: int) -> Optional[Signal]:
        """检查卖出机会"""
        # 向上穿越网格时卖出
        if current_grid > self.current_grid_index and self.can_sell(self.current_grid_index):
            grid = self.grid_levels[self.current_grid_index]
            
            signal = Signal(
                code=bar.code,
                dt=bar.dt,
                signal_type=SignalType.SELL,
                price=grid.price,
                strength=0.8,
                reason=f"网格卖出: 价格上涨至{grid.price:.2f}"
            )
            
            grid.sell_volume += 1
            return signal
        
        return None
    
    def rebalance_position(self, bar: Bar) -> List[Signal]:
        """仓位再平衡"""
        signals = []
        current_price = bar.close
        current_grid = self.find_grid_index(current_price)
        
        # 如果跨越多个网格，可能产生多个信号
        if current_grid != self.current_grid_index:
            step = 1 if current_grid > self.current_grid_index else -1
            
            for grid_idx in range(self.current_grid_index + step, current_grid + step, step):
                if 0 <= grid_idx < len(self.grid_levels):
                    if step > 0:  # 向上移动
                        sell_signal = self.check_sell_opportunity(bar, grid_idx)
                        if sell_signal:
                            signals.append(sell_signal)
                    else:  # 向下移动
                        buy_signal = self.check_buy_opportunity(bar, grid_idx)
                        if buy_signal:
                            signals.append(buy_signal)
            
            self.current_grid_index = current_grid
            
        return signals
    
    def on_bar(self, bar: Bar) -> Signal | None:
        """每根K线执行策略逻辑"""
        # 更新数据
        self.add_bar(bar)
        
        # 初始化网格
        if not self.initialized:
            self.initialize_grids(bar.close)
            return None
        
        # 执行仓位再平衡
        signals = self.rebalance_position(bar)
        
        # 返回第一个信号（如果有）
        return signals[0] if signals else None
    
    def get_grid_statistics(self) -> dict:
        """获取网格统计信息"""
        if not self.initialized:
            return {}
            
        total_buy = sum(level.buy_volume for level in self.grid_levels)
        total_sell = sum(level.sell_volume for level in self.grid_levels)
        active_positions = total_buy - total_sell
        
        return {
            'total_buy_orders': total_buy,
            'total_sell_orders': total_sell,
            'net_positions': active_positions,
            'current_grid_index': self.current_grid_index,
            'current_price_level': self.grid_levels[self.current_grid_index].price if 0 <= self.current_grid_index < len(self.grid_levels) else 0
        }
    
    def on_stop(self) -> None:
        """策略停止"""
        self.grid_levels.clear()
        self.current_grid_index = -1
        self.initialized = False
        super().on_stop()


# 快捷创建函数
def create_grid_strategy(params: dict | None = None) -> GridStrategy:
    """创建网格策略实例"""
    default_params = {
        'grid_count': 10,
        'grid_spacing': 0.02,      # 2%
        'base_amount': 10000,
        'center_price': 0.0,
        'max_position_per_grid': 1
    }
    
    if params:
        default_params.update(params)
        
    return GridStrategy("grid", default_params)