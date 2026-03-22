"""
策略模块测试用例
测试各种策略的基本功能和边界条件
"""
import unittest
import sys
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# 添加项目路径
sys.path.insert(0, '/Users/james/PycharmProjects/jwquant')

from jwquant.trading.strategy.base import BaseStrategy, StrategyManager
from jwquant.trading.strategy.turtle import TurtleStrategy, create_turtle_strategy
from jwquant.trading.strategy.grid import GridStrategy, create_grid_strategy
from jwquant.trading.strategy.rotation import RotationStrategy, create_rotation_strategy
from jwquant.trading.strategy.chanlun import ChanlunStrategy, create_chanlun_strategy
from jwquant.trading.strategy.registry import get_strategy_registry, create_registered_strategy
from jwquant.common.types import Bar, Signal, SignalType, Asset, Position


class TestBaseStrategy(unittest.TestCase):
    """基础策略类测试"""
    
    def setUp(self):
        """测试前置条件"""
        self.strategy = BaseStrategy("test_strategy", {"param1": 10})
        
    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.strategy.name, "test_strategy")
        self.assertEqual(self.strategy.params["param1"], 10)
        self.assertFalse(self.strategy._initialized)
        
    def test_history_management(self):
        """测试历史数据管理"""
        # 添加K线数据
        bars = [
            Bar("000001.SZ", datetime(2024, 1, i), 10+i, 12+i, 9+i, 11+i, 1000+i)
            for i in range(1, 6)
        ]
        
        for bar in bars:
            self.strategy.add_bar(bar)
            
        self.assertEqual(len(self.strategy.history_bars), 5)
        
        # 测试DataFrame转换
        df = self.strategy.get_history_dataframe()
        self.assertEqual(len(df), 5)
        self.assertIn('close', df.columns)
        
    def test_asset_position_updates(self):
        """测试资产和持仓更新"""
        # 更新资产
        asset = Asset(cash=100000, total_asset=150000)
        self.strategy.update_asset(asset)
        self.assertEqual(self.strategy.get_available_cash(), 100000)
        self.assertEqual(self.strategy.get_total_asset(), 150000)
        
        # 更新持仓
        position = Position("000001.SZ", 1000, 1000, 10.0)
        self.strategy.update_position(position)
        self.assertEqual(self.strategy.get_position_size(), 1000)


class TestTurtleStrategy(unittest.TestCase):
    """海龟策略测试"""
    
    def setUp(self):
        """测试前置条件"""
        self.strategy = create_turtle_strategy({
            'entry_window': 10,
            'exit_window': 5,
            'atr_period': 10,
            'risk_ratio': 0.01
        })
        # 设置资产
        asset = Asset(cash=100000, total_asset=100000)
        self.strategy.update_asset(asset)
        
    def test_donchian_calculation(self):
        """测试唐奇安通道计算"""
        # 生成上升趋势数据
        bars = []
        for i in range(15):
            bar = Bar(
                code="000001.SZ",
                dt=datetime(2024, 1, i+1),
                open=10 + i*0.5,
                high=12 + i*0.5,
                low=8 + i*0.5,
                close=11 + i*0.5,
                volume=1000
            )
            bars.append(bar)
            self.strategy.add_bar(bar)
        
        upper, middle, lower = self.strategy.calculate_donchian_channel(10)
        
        # 在上升趋势中，上轨应该是近期高点
        self.assertGreater(upper, lower)
        self.assertGreater(upper, 15)  # 应该大于大部分价格
        
    def test_atr_calculation(self):
        """测试ATR计算"""
        # 生成波动数据
        bars = []
        for i in range(15):
            bar = Bar(
                code="000001.SZ",
                dt=datetime(2024, 1, i+1),
                open=10,
                high=10 + np.random.uniform(0, 2),
                low=10 - np.random.uniform(0, 2),
                close=10 + np.random.uniform(-1, 1),
                volume=1000
            )
            bars.append(bar)
            self.strategy.add_bar(bar)
        
        atr = self.strategy.calculate_atr(10)
        self.assertGreater(atr, 0)
        self.assertLess(atr, 5)  # ATR应该在合理范围内
        
    def test_entry_condition(self):
        """测试入场条件"""
        # 生成突破数据
        bars = []
        
        # 先建立基础价格
        for i in range(10):
            bar = Bar(
                code="000001.SZ",
                dt=datetime(2024, 1, i+1),
                open=10,
                high=11,
                low=9,
                close=10,
                volume=1000
            )
            bars.append(bar)
            self.strategy.add_bar(bar)
        
        # 突破上涨
        breakout_bar = Bar(
            code="000001.SZ",
            dt=datetime(2024, 1, 12),
            open=11,
            high=13,
            low=11,
            close=12.5,  # 突破上轨
            volume=1500
        )
        
        self.strategy.add_bar(breakout_bar)
        signal = self.strategy.on_bar(breakout_bar)
        
        # 应该产生买入信号
        if signal:
            self.assertEqual(signal.signal_type, SignalType.BUY)
            self.assertEqual(signal.code, "000001.SZ")


class TestGridStrategy(unittest.TestCase):
    """网格策略测试"""
    
    def setUp(self):
        """测试前置条件"""
        self.strategy = create_grid_strategy({
            'grid_count': 5,
            'grid_spacing': 0.05,  # 5%间距
            'base_amount': 10000
        })
        
    def test_grid_initialization(self):
        """测试网格初始化"""
        current_price = 100.0
        self.strategy.initialize_grids(current_price)
        
        self.assertTrue(self.strategy.initialized)
        self.assertEqual(len(self.strategy.grid_levels), 5)
        
        # 检查网格价格分布
        prices = [level.price for level in self.strategy.grid_levels]
        self.assertTrue(all(prices[i] < prices[i+1] for i in range(len(prices)-1)))
        
    def test_grid_navigation(self):
        """测试网格穿越"""
        self.strategy.initialize_grids(100.0)
        
        # 测试价格移动
        test_prices = [95, 97, 102, 105, 108]
        expected_grids = [0, 1, 3, 4, 4]  # 对应的网格索引
        
        for price, expected_idx in zip(test_prices, expected_grids):
            grid_idx = self.strategy.find_grid_index(price)
            self.assertEqual(grid_idx, expected_idx)


class TestRotationStrategy(unittest.TestCase):
    """轮动策略测试"""
    
    def setUp(self):
        """测试前置条件"""
        self.strategy = create_rotation_strategy({
            'holding_count': 3,
            'lookback_period': 10
        })
        
    def test_momentum_calculation(self):
        """测试动量计算"""
        # 添加同一股票的不同价格数据
        stock_code = "000001.SZ"
        
        # 上涨趋势
        rising_prices = [100, 102, 105, 108, 112, 115, 118, 120, 122, 125, 128, 130]
        
        for i, price in enumerate(rising_prices):
            bar = Bar(
                code=stock_code,
                dt=datetime(2024, 1, i+1),
                open=price,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=1000
            )
            self.strategy.add_stock_data(bar)
        
        momentum = self.strategy.calculate_momentum(stock_code)
        self.assertGreater(momentum, 0)  # 应该是正动量
        
    def test_stock_screening(self):
        """测试股票筛选"""
        # 添加多个股票数据
        stocks = ["000001.SZ", "000002.SZ", "000003.SZ"]
        
        for i, stock in enumerate(stocks):
            # 给不同股票不同的表现
            base_price = 100 + i * 10  # 不同基准价格
            for day in range(15):
                price = base_price + day * (0.5 + i * 0.2)  # 不同的增长率
                bar = Bar(
                    code=stock,
                    dt=datetime(2024, 1, day+1),
                    open=price,
                    high=price + 1,
                    low=price - 1,
                    close=price,
                    volume=1000000 + i * 100000
                )
                self.strategy.add_stock_data(bar)
        
        selected = self.strategy.screen_stocks()
        self.assertIsInstance(selected, list)
        self.assertLessEqual(len(selected), 3)


class TestChanlunStrategy(unittest.TestCase):
    """缠论策略测试"""
    
    def setUp(self):
        """测试前置条件"""
        self.strategy = create_chanlun_strategy({
            'min_bi_length': 3,
            'confirm_bars': 2
        })
        
    def test_fractal_identification(self):
        """测试分型识别"""
        # 构造典型的顶分型数据
        prices = [100, 102, 105, 103, 101]  # 高-低-高-低模式
        bars = []
        
        for i, price in enumerate(prices):
            bar = Bar(
                code="000001.SZ",
                dt=datetime(2024, 1, i+1),
                open=price,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=1000
            )
            bars.append(bar)
            self.strategy.add_bar(bar)
        
        fractals = self.strategy.find_valid_fractals(bars)
        # 应该能识别出分型
        self.assertGreater(len(fractals), 0)


class TestStrategyRegistry(unittest.TestCase):
    """策略注册中心测试"""
    
    def setUp(self):
        """测试前置条件"""
        self.registry = get_strategy_registry()
        
    def test_strategy_registration(self):
        """测试策略注册"""
        strategies = self.registry.list_strategies()
        self.assertIn("turtle", strategies)
        self.assertIn("grid", strategies)
        self.assertIn("rotation", strategies)
        self.assertIn("chanlun", strategies)
        
    def test_strategy_creation(self):
        """测试策略创建"""
        strategy = create_registered_strategy("turtle", {"entry_window": 15})
        self.assertIsNotNone(strategy)
        self.assertEqual(strategy.name, "turtle")
        self.assertEqual(strategy.entry_window, 15)
        
    def test_strategy_info(self):
        """测试策略信息获取"""
        info = self.registry.get_strategy_info("turtle")
        self.assertIsNotNone(info)
        self.assertEqual(info['name'], '海龟交易策略')
        self.assertEqual(info['category'], '趋势跟踪')


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def test_multi_strategy_execution(self):
        """测试多策略同时执行"""
        manager = StrategyManager()
        
        # 创建多个策略
        turtle = create_registered_strategy("turtle")
        grid = create_registered_strategy("grid")
        
        # 注册策略
        manager.register_strategy(turtle)
        manager.register_strategy(grid)
        
        # 激活策略
        self.assertTrue(manager.activate_strategy("turtle"))
        self.assertTrue(manager.activate_strategy("grid"))
        
        # 生成测试数据
        bars = [
            Bar("000001.SZ", datetime(2024, 1, i), 100+i, 102+i, 98+i, 101+i, 1000+i)
            for i in range(1, 21)
        ]
        
        # 处理数据
        all_signals = []
        for bar in bars:
            signals = manager.process_bar(bar)
            all_signals.extend(signals)
        
        # 验证策略状态
        status = manager.get_strategy_status()
        self.assertEqual(status["turtle"], "ACTIVE")
        self.assertEqual(status["grid"], "ACTIVE")


def create_test_suite():
    """创建测试套件"""
    suite = unittest.TestSuite()
    
    # 添加各个测试类
    test_classes = [
        TestBaseStrategy,
        TestTurtleStrategy,
        TestGridStrategy,
        TestRotationStrategy,
        TestChanlunStrategy,
        TestStrategyRegistry,
        TestIntegration
    ]
    
    for test_class in test_classes:
        suite.addTest(unittest.makeSuite(test_class))
    
    return suite


if __name__ == "__main__":
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    suite = create_test_suite()
    result = runner.run(suite)
    
    # 输出测试摘要
    print(f"\n测试总结:")
    print(f"运行测试数: {result.testsRun}")
    print(f"失败数: {len(result.failures)}")
    print(f"错误数: {len(result.errors)}")
    
    if result.failures:
        print("\n失败的测试:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
            
    if result.errors:
        print("\n错误的测试:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")