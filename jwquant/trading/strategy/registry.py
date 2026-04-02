"""
策略注册中心
策略统一注册、发现与管理，支持多策略并行运行。
"""
from typing import Dict, Type, Callable, Optional, List
from datetime import datetime
import importlib
import inspect

from jwquant.trading.strategy.base import BaseStrategy
from jwquant.trading.strategy.turtle import TurtleStrategy, create_turtle_strategy
from jwquant.trading.strategy.grid import GridStrategy, create_grid_strategy
from jwquant.trading.strategy.rotation import RotationStrategy, create_rotation_strategy
from jwquant.trading.strategy.chanlun import ChanlunStrategy, create_chanlun_strategy
from jwquant.trading.strategy.single_ma import SingleMAStrategy, create_single_ma_strategy
from jwquant.trading.strategy.double_ma import DoubleMAStrategy, create_double_ma_strategy
from jwquant.trading.strategy.three_ma_cross import ThreeMACrossStrategy, create_three_ma_cross_strategy
from jwquant.trading.strategy.macd_kdj import MACDKDJStrategy, create_macd_kdj_strategy
from jwquant.trading.strategy.macd_signal import MACDSignalStrategy, create_macd_signal_strategy
from jwquant.trading.strategy.macd_divergence import MACDDivergenceStrategy, create_macd_divergence_strategy


class StrategyRegistry:
    """策略注册中心"""
    
    def __init__(self):
        self._strategies: Dict[str, Type[BaseStrategy]] = {}
        self._factories: Dict[str, Callable] = {}
        self._metadata: Dict[str, dict] = {}
        self._initialized = False
        
    def initialize(self) -> None:
        """初始化注册中心，注册内置策略"""
        if self._initialized:
            return
            
        # 注册内置策略
        self.register_strategy("turtle", TurtleStrategy, create_turtle_strategy, {
            'name': '海龟交易策略',
            'description': '基于唐奇安通道的趋势跟踪策略，支持动态加仓和ATR止损',
            'category': '趋势跟踪',
            'complexity': '中等',
            'risk_level': '中等'
        })
        
        self.register_strategy("grid", GridStrategy, create_grid_strategy, {
            'name': '网格交易策略',
            'description': '均值回归策略，在预设价格网格内自动低买高卖',
            'category': '均值回归',
            'complexity': '简单',
            'risk_level': '低'
        })
        
        self.register_strategy("rotation", RotationStrategy, create_rotation_strategy, {
            'name': '轮动策略',
            'description': '基于动量效应的多股票轮动策略，定期调仓',
            'category': '轮动择时',
            'complexity': '复杂',
            'risk_level': '中高'
        })
        
        self.register_strategy("chanlun", ChanlunStrategy, create_chanlun_strategy, {
            'name': '缠论策略',
            'description': '基于缠论理论的技术分析策略，识别买卖点',
            'category': '技术分析',
            'complexity': '复杂',
            'risk_level': '中等'
        })
        
        
        self.register_strategy("single_ma", SingleMAStrategy, create_single_ma_strategy, {
            'name': '单均线策略',
            'description': '基于15日移动平均线的价格交叉信号策略',
            'category': '趋势跟踪',
            'complexity': '简单',
            'risk_level': '中等'
        })
        
        self.register_strategy("double_ma", DoubleMAStrategy, create_double_ma_strategy, {
            'name': '双均线策略',
            'description': '基于5日和10日移动平均线的交叉信号策略',
            'category': '趋势跟踪',
            'complexity': '简单',
            'risk_level': '中等'
        })
        
        self.register_strategy("three_ma_cross", ThreeMACrossStrategy, create_three_ma_cross_strategy, {
            'name': '三均线穿越策略',
            'description': '一根阳线上穿短中长期三条均线的买入信号策略',
            'category': '趋势跟踪',
            'complexity': '中等',
            'risk_level': '中等'
        })
        
        self.register_strategy("macd_kdj", MACDKDJStrategy, create_macd_kdj_strategy, {
            'name': 'MACD+KDJ组合策略',
            'description': '结合MACD趋势指标和KDJ超买超卖指标的复合策略',
            'category': '复合指标',
            'complexity': '中等',
            'risk_level': '中等'
        })
        self.register_strategy("macd_signal", MACDSignalStrategy, create_macd_signal_strategy, {
            'name': 'MACD趋势信号策略',
            'description': '基于MACD零上金叉买入、死叉卖出的趋势策略',
            'category': '技术分析',
            'complexity': '简单',
            'risk_level': '中等'
        })
        self.register_strategy("macd_divergence", MACDDivergenceStrategy, create_macd_divergence_strategy, {
            'name': 'MACD背离策略',
            'description': '基于MACD底背离买入、顶背离卖出的反转策略',
            'category': '技术分析',
            'complexity': '简单',
            'risk_level': '中等'
        })
        self._initialized = True
        print(f"策略注册中心初始化完成，已注册 {len(self._strategies)} 个策略")
        
    def register_strategy(self, name: str, strategy_class: Type[BaseStrategy], 
                         factory_func: Callable, metadata: dict = None) -> bool:
        """注册策略"""
        if name in self._strategies:
            print(f"警告: 策略 '{name}' 已存在，将被覆盖")
            
        self._strategies[name] = strategy_class
        self._factories[name] = factory_func
        self._metadata[name] = metadata or {}
        
        # 添加注册时间
        self._metadata[name]['registered_at'] = datetime.now().isoformat()
        self._metadata[name]['class_name'] = strategy_class.__name__
        
        print(f"注册策略: {name} ({strategy_class.__name__})")
        return True
    
    def unregister_strategy(self, name: str) -> bool:
        """注销策略"""
        if name in self._strategies:
            del self._strategies[name]
            del self._factories[name]
            del self._metadata[name]
            print(f"注销策略: {name}")
            return True
        return False
    
    def get_strategy_class(self, name: str) -> Optional[Type[BaseStrategy]]:
        """获取策略类"""
        return self._strategies.get(name)
    
    def create_strategy(self, name: str, params: dict = None) -> Optional[BaseStrategy]:
        """创建策略实例"""
        if name not in self._factories:
            print(f"错误: 未找到策略 '{name}'")
            return None
            
        try:
            factory = self._factories[name]
            strategy = factory(params)
            print(f"创建策略实例: {name}")
            return strategy
        except Exception as e:
            print(f"创建策略失败 {name}: {e}")
            return None
    
    def get_strategy_info(self, name: str) -> Optional[dict]:
        """获取策略信息"""
        if name not in self._metadata:
            return None
            
        info = self._metadata[name].copy()
        info['name'] = name
        info['available'] = name in self._strategies
        return info
    
    def list_strategies(self) -> List[str]:
        """列出所有注册的策略名称"""
        return list(self._strategies.keys())
    
    def list_strategies_detailed(self) -> List[dict]:
        """列出详细策略信息"""
        result = []
        for name in self._strategies:
            info = self.get_strategy_info(name)
            if info:
                result.append(info)
        return result
    
    def get_strategies_by_category(self, category: str) -> List[str]:
        """按类别获取策略"""
        result = []
        for name, metadata in self._metadata.items():
            if metadata.get('category', '').lower() == category.lower():
                result.append(name)
        return result
    
    def get_strategy_parameters(self, name: str) -> dict:
        """获取策略参数模板"""
        strategy_class = self.get_strategy_class(name)
        if not strategy_class:
            return {}
            
        # 尝试从策略类的__init__方法获取参数信息
        try:
            init_signature = inspect.signature(strategy_class.__init__)
            params = {}
            for param_name, param in init_signature.parameters.items():
                if param_name not in ['self', 'name', 'params']:
                    params[param_name] = {
                        'default': param.default if param.default != inspect.Parameter.empty else None,
                        'annotation': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'Any'
                    }
            return params
        except Exception:
            return {}
    
    def validate_strategy_params(self, name: str, params: dict) -> tuple[bool, List[str]]:
        """验证策略参数"""
        errors = []
        
        if name not in self._strategies:
            errors.append(f"策略 '{name}' 未注册")
            return False, errors
            
        # 获取策略参数模板
        param_template = self.get_strategy_parameters(name)
        
        # 检查必需参数
        for param_name, param_info in param_template.items():
            if param_info.get('default') is None and param_name not in params:
                errors.append(f"缺少必需参数: {param_name}")
        
        # 检查参数类型和范围（简单验证）
        for param_name, value in params.items():
            if param_name in param_template:
                annotation = param_template[param_name].get('annotation', '')
                # 这里可以添加更详细的类型检查
                
        return len(errors) == 0, errors
    
    def batch_register_from_module(self, module_name: str) -> int:
        """从模块批量注册策略"""
        try:
            module = importlib.import_module(module_name)
            registered_count = 0
            
            # 查找BaseStrategy的子类
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseStrategy) and obj != BaseStrategy:
                    # 查找对应的工厂函数
                    factory_name = f"create_{name.lower()}"
                    factory_func = getattr(module, factory_name, None)
                    
                    if factory_func:
                        self.register_strategy(
                            name.lower(), 
                            obj, 
                            factory_func,
                            {'name': name, 'source': 'dynamic'}
                        )
                        registered_count += 1
                        
            print(f"从模块 {module_name} 注册了 {registered_count} 个策略")
            return registered_count
            
        except Exception as e:
            print(f"从模块注册策略失败: {e}")
            return 0


# 全局策略注册中心实例
strategy_registry = StrategyRegistry()


def get_strategy_registry() -> StrategyRegistry:
    """获取全局策略注册中心"""
    if not strategy_registry._initialized:
        strategy_registry.initialize()
    return strategy_registry


def register_custom_strategy(name: str, strategy_class: Type[BaseStrategy], 
                           factory_func: Callable, metadata: dict = None) -> bool:
    """注册自定义策略的便捷函数"""
    registry = get_strategy_registry()
    return registry.register_strategy(name, strategy_class, factory_func, metadata)


def create_registered_strategy(name: str, params: dict = None) -> Optional[BaseStrategy]:
    """创建已注册策略的便捷函数"""
    registry = get_strategy_registry()
    return registry.create_strategy(name, params)


def list_available_strategies() -> List[str]:
    """列出可用策略的便捷函数"""
    registry = get_strategy_registry()
    return registry.list_strategies()


# 策略装饰器
def strategy(name: str, metadata: dict = None):
    """策略类装饰器"""
    def decorator(cls):
        # 创建工厂函数
        def factory(params=None):
            return cls(name, params)
        
        # 注册策略
        register_custom_strategy(name, cls, factory, metadata)
        return cls
    return decorator
