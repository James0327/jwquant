# 策略层
"""
交易策略模块

包含多种经典量化策略实现：
- 海龟交易策略 (TurtleStrategy)
- 网格交易策略 (GridStrategy)  
- 轮动策略 (RotationStrategy)
- 缠论策略 (ChanlunStrategy)

提供策略基类、注册中心和管理器等功能。
"""

from .base import BaseStrategy, StrategyManager
from .registry import (
    StrategyRegistry, 
    get_strategy_registry, 
    register_custom_strategy,
    create_registered_strategy,
    list_available_strategies,
    strategy
)

# 策略导入
from .turtle import TurtleStrategy, create_turtle_strategy
from .grid import GridStrategy, create_grid_strategy
from .rotation import RotationStrategy, create_rotation_strategy
from .chanlun import ChanlunStrategy, create_chanlun_strategy
from .single_ma import SingleMAStrategy, create_single_ma_strategy
from .double_ma import DoubleMAStrategy, create_double_ma_strategy
from .three_ma_cross import ThreeMACrossStrategy, create_three_ma_cross_strategy
from .macd_kdj import MACDKDJStrategy, create_macd_kdj_strategy

__all__ = [
    # 基础类
    'BaseStrategy',
    'StrategyManager',
    
    # 注册中心
    'StrategyRegistry',
    'get_strategy_registry',
    'register_custom_strategy',
    'create_registered_strategy',
    'list_available_strategies',
    'strategy',
    
    # 具体策略
    'TurtleStrategy',
    'GridStrategy',
    'RotationStrategy',
    'ChanlunStrategy',
    'SingleMAStrategy',
    'DoubleMAStrategy',
    'ThreeMACrossStrategy',
    'MACDKDJStrategy',
    
    # 工厂函数
    'create_turtle_strategy',
    'create_grid_strategy',
    'create_rotation_strategy',
    'create_chanlun_strategy',
    'create_single_ma_strategy',
    'create_double_ma_strategy',
    'create_three_ma_cross_strategy',
    'create_macd_kdj_strategy'
]