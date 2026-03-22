#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单均线策略测试脚本
演示15日均线交叉策略的信号生成逻辑
"""
import sys
import os
import numpy as np
from datetime import datetime, timedelta
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('single_ma_test.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jwquant.trading.strategy.single_ma import SingleMAStrategy
from jwquant.common.types import Bar


def create_sample_data():
    """创建示例数据用于测试"""
    # 模拟股价走势
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(30)]
    base_price = 100.0
    
    # 创建价格序列：先下跌，然后上涨穿过MA
    prices = []
    current_price = base_price
    
    for i in range(len(dates)):
        # 添加随机波动
        change = np.random.normal(0, 0.02)  # ±2%的日波动
        current_price = current_price * (1 + change)
        
        # 在中间阶段制造趋势
        if 10 <= i <= 20:
            trend = 0.005  # 上升趋势
            current_price = current_price * (1 + trend)
            
        prices.append(current_price)
    
    return dates, prices


def test_single_ma_signals():
    """测试单均线策略信号生成"""
    logger.info("=" * 60)
    logger.info("开始单均线交叉策略测试")
    logger.info("=" * 60)
    
    # 创建策略实例
    strategy = SingleMAStrategy("test_single_ma", {
        'ma_period': 15,
        'min_history': 20
    })
    logger.info(f"创建策略实例: {strategy.name}")
    logger.info(f"策略参数 - MA周期: {strategy.ma_period}, 最小历史数据: {strategy.min_history}")
    
    # 创建示例数据
    dates, prices = create_sample_data()
    logger.info(f"生成 {len(dates)} 天的模拟价格数据，起始日期: {dates[0].strftime('%Y-%m-%d')}")
    
    print(f"\n生成 {len(dates)} 天的模拟价格数据:")
    print("日期\t\t价格\t\tMA15\t\t信号")
    print("-" * 60)
    
    # 逐日处理数据
    for i in range(len(dates)):
        # 创建K线数据
        bar = Bar(
            code="000001.SZ",
            dt=dates[i],
            open=prices[i],
            high=prices[i] * 1.01,
            low=prices[i] * 0.99,
            close=prices[i],
            volume=1000000,
            amount=prices[i] * 1000000
        )
        
        # 添加到策略
        strategy.add_bar(bar)
        
        # 生成信号
        signal = strategy.on_bar(bar)
        
        # 计算当前MA值（使用策略内部方法）
        ma_value = "N/A"
        if len(strategy.history_bars) >= 15:
            ma_series = strategy.calculate_moving_average(15)
            if ma_series and len(ma_series) > 0:
                ma_value = f"{ma_series[-1]:.2f}"
        
        # 显示结果
        signal_text = ""
        if signal:
            signal_type = "买入" if signal.signal_type.name == 'BUY' else "卖出"
            signal_text = f"{signal_type}@{signal.price:.2f}"
            logger.info(f"产生{signal_type}信号 - 日期: {dates[i].strftime('%Y-%m-%d')}, 价格: {signal.price:.2f}")
            logger.debug(f"信号详情: {signal.reason}")
        
        print(f"{dates[i].strftime('%Y-%m-%d')}\t{prices[i]:.2f}\t\t{ma_value}\t\t{signal_text}")
        
        # 如果产生信号，显示详细原因
        if signal:
            print(f"  原因: {signal.reason}")
    
    logger.info("=" * 60)
    logger.info("单均线策略测试完成")
    logger.info("=" * 60)
    print("\n" + "=" * 60)
    print("策略测试完成")
    print("=" * 60)


def demonstrate_crossover_logic():
    """演示交叉逻辑"""
    print("\n交叉逻辑说明:")
    print("-" * 40)
    print("买入信号条件:")
    print("  • 昨日收盘价 > 昨日MA15")
    print("  • 前日收盘价 < 前日MA15")
    print("  • 即：价格从下方穿越MA15")
    print()
    print("卖出信号条件:")
    print("  • 昨日收盘价 < 昨日MA15")
    print("  • 前日收盘价 > 前日MA15")
    print("  • 即：价格从上方穿越MA15")


if __name__ == "__main__":
    demonstrate_crossover_logic()
    test_single_ma_signals()