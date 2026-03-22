#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三均线穿越策略测试脚本
验证1阳穿3线策略的信号生成逻辑
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
        logging.FileHandler('three_ma_cross_test.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jwquant.trading.strategy.three_ma_cross import ThreeMACrossStrategy
from jwquant.common.types import Bar


def create_sample_data():
    """创建示例数据用于测试"""
    # 模拟股价走势
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(40)]
    base_price = 100.0
    
    # 创建价格序列：先震荡，然后制造向上突破
    prices = []
    current_price = base_price
    
    for i in range(len(dates)):
        # 添加随机波动
        change = np.random.normal(0, 0.01)  # ±1%的日波动
        current_price = current_price * (1 + change)
        
        # 在特定阶段制造趋势转换
        if 15 <= i <= 20:  # 制造上升趋势
            trend = 0.015
            current_price = current_price * (1 + trend)
        elif 25 <= i <= 30:  # 继续上升
            trend = 0.01
            current_price = current_price * (1 + trend)
            
        prices.append(current_price)
    
    return dates, prices


def calculate_simple_ma(prices, period, index):
    """计算简单移动平均线（用于验证）"""
    if index < period - 1:
        return None
    return np.mean(prices[index - period + 1:index + 1])


def test_three_ma_cross_signals():
    """测试三均线穿越策略信号生成"""
    logger.info("=" * 80)
    logger.info("开始三均线穿越策略测试")
    logger.info("=" * 80)
    
    # 创建策略实例
    strategy = ThreeMACrossStrategy("test_three_ma_cross", {
        'short_ma_period': 5,
        'medium_ma_period': 10,
        'long_ma_period': 20,
        'min_history': 30
    })
    logger.info(f"创建策略实例: {strategy.name}")
    logger.info(f"策略参数 - 短期MA: {strategy.short_ma_period}, 中期MA: {strategy.medium_ma_period}, 长期MA: {strategy.long_ma_period}")
    
    # 创建示例数据
    dates, prices = create_sample_data()
    logger.info(f"生成 {len(dates)} 天的模拟价格数据，起始日期: {dates[0].strftime('%Y-%m-%d')}")
    
    print(f"\n生成 {len(dates)} 天的模拟价格数据:")
    print("日期\t\t价格\t\t开盘\t\tMA5\t\tMA10\t\tMA20\t\t信号")
    print("-" * 100)
    
    # 逐日处理数据
    for i in range(len(dates)):
        # 创建K线数据（模拟阳线）
        open_price = prices[i] * (0.99 + np.random.random() * 0.01)  # 开盘价略低于收盘价
        high_price = prices[i] * (1 + np.random.random() * 0.02)
        low_price = prices[i] * (1 - np.random.random() * 0.02)
        
        bar = Bar(
            code="000001.SZ",
            dt=dates[i],
            open=open_price,
            high=high_price,
            low=low_price,
            close=prices[i],
            volume=1000000,
            amount=prices[i] * 1000000
        )
        
        # 添加到策略
        strategy.add_bar(bar)
        
        # 生成信号
        signal = strategy.on_bar(bar)
        
        # 计算当前MA值
        ma5_value = calculate_simple_ma(prices, 5, i)
        ma10_value = calculate_simple_ma(prices, 10, i)
        ma20_value = calculate_simple_ma(prices, 20, i)
        
        ma5_str = f"{ma5_value:.2f}" if ma5_value else "N/A"
        ma10_str = f"{ma10_value:.2f}" if ma10_value else "N/A"
        ma20_str = f"{ma20_value:.2f}" if ma20_value else "N/A"
        
        # 判断是否为阳线
        is_bullish = "✓" if bar.close > bar.open else "✗"
        
        # 显示结果
        signal_text = ""
        if signal:
            signal_type = "买入" if signal.signal_type.name == 'BUY' else "卖出"
            signal_text = f"{signal_type}@{signal.price:.2f}"
            logger.info(f"产生{signal_type}信号 - 日期: {dates[i].strftime('%Y-%m-%d')}, 价格: {signal.price:.2f}")
            logger.info(f"  MA5: {ma5_value:.2f}, MA10: {ma10_value:.2f}, MA20: {ma20_value:.2f}")
            logger.debug(f"信号详情: {signal.reason}")
        
        print(f"{dates[i].strftime('%Y-%m-%d')}\t{prices[i]:.2f}\t\t{open_price:.2f}\t\t{ma5_str}\t\t{ma10_str}\t\t{ma20_str}\t\t{is_bullish}\t{signal_text}")
        
        # 如果产生信号，显示详细原因
        if signal:
            print(f"  原因: {signal.reason}")
    
    logger.info("=" * 80)
    logger.info("三均线穿越策略测试完成")
    logger.info("=" * 80)
    print("\n" + "=" * 80)
    print("策略测试完成")
    print("=" * 80)


def demonstrate_strategy_logic():
    """演示策略逻辑"""
    print("\n三均线穿越策略逻辑说明:")
    print("-" * 50)
    print("买入信号条件:")
    print("  1. 当日为阳线：收盘价 > 开盘价")
    print("  2. 阳线上穿三均线：")
    print("     • 当日收盘价 > 三均线平均值")
    print("     • 前一日收盘价 < 三均线平均值")
    print()
    print("均线配置:")
    print("  • 短期MA: 5日")
    print("  • 中期MA: 10日")
    print("  • 长期MA: 20日")
    print()
    print("策略特点:")
    print("  • 捕捉趋势启动点")
    print("  • 结合价格形态和均线穿越")
    print("  • 适合中长期趋势跟踪")


if __name__ == "__main__":
    demonstrate_strategy_logic()
    test_three_ma_cross_signals()