#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双均线策略测试脚本
演示5日均线和10日均线交叉策略的信号生成逻辑
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
        logging.FileHandler('double_ma_test.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jwquant.trading.strategy.double_ma import DoubleMAStrategy
from jwquant.common.types import Bar


def create_sample_data():
    """创建示例数据用于测试"""
    # 模拟股价走势
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(30)]
    base_price = 100.0
    
    # 创建价格序列：制造均线交叉情况
    prices = []
    current_price = base_price
    
    for i in range(len(dates)):
        # 添加随机波动
        change = np.random.normal(0, 0.015)  # ±1.5%的日波动
        current_price = current_price * (1 + change)
        
        # 在特定阶段制造趋势转换
        if 8 <= i <= 12:  # 制造上升趋势
            trend = 0.008
            current_price = current_price * (1 + trend)
        elif 18 <= i <= 22:  # 制造下降趋势
            trend = -0.006
            current_price = current_price * (1 + trend)
            
        prices.append(current_price)
    
    return dates, prices


# 注：使用策略内部的calculate_moving_average方法替代独立计算函数


def test_double_ma_signals():
    """测试双均线策略信号生成"""
    logger.info("=" * 80)
    logger.info("开始双均线交叉策略测试")
    logger.info("=" * 80)
    
    # 创建策略实例
    strategy = DoubleMAStrategy("test_double_ma", {
        'short_ma_period': 5,
        'long_ma_period': 10,
        'min_history': 15
    })
    logger.info(f"创建策略实例: {strategy.name}")
    logger.info(f"策略参数 - 短期MA: {strategy.short_ma_period}, 长期MA: {strategy.long_ma_period}, 最小历史数据: {strategy.min_history}")
    
    # 创建示例数据
    dates, prices = create_sample_data()
    logger.info(f"生成 {len(dates)} 天的模拟价格数据，起始日期: {dates[0].strftime('%Y-%m-%d')}")
    
    print(f"\n生成 {len(dates)} 天的模拟价格数据:")
    print("日期\t\t价格\t\tMA5\t\tMA10\t\t信号")
    print("-" * 80)
    
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
        ma5_value = None
        ma10_value = None
        ma5_str = "N/A"
        ma10_str = "N/A"
        
        if len(strategy.history_bars) >= 5:
            ma5_series = strategy.calculate_moving_average(5)
            if ma5_series and len(ma5_series) > 0:
                ma5_value = ma5_series[-1]
                ma5_str = f"{ma5_value:.2f}"
        
        if len(strategy.history_bars) >= 10:
            ma10_series = strategy.calculate_moving_average(10)
            if ma10_series and len(ma10_series) > 0:
                ma10_value = ma10_series[-1]
                ma10_str = f"{ma10_value:.2f}"
        
        # 显示结果
        signal_text = ""
        if signal:
            signal_type = "买入" if signal.signal_type.name == 'BUY' else "卖出"
            signal_text = f"{signal_type}@{signal.price:.2f}"
            logger.info(f"产生{signal_type}信号 - 日期: {dates[i].strftime('%Y-%m-%d')}, 价格: {signal.price:.2f}")
            logger.info(f"  MA5: {ma5_value:.2f}, MA10: {ma10_value:.2f}")
            logger.debug(f"信号详情: {signal.reason}")
        
        print(f"{dates[i].strftime('%Y-%m-%d')}\t{prices[i]:.2f}\t\t{ma5_str}\t\t{ma10_str}\t\t{signal_text}")
        
        # 如果产生信号，显示详细原因
        if signal:
            print(f"  原因: {signal.reason}")
    
    logger.info("=" * 80)
    logger.info("双均线策略测试完成")
    logger.info("=" * 80)
    print("\n" + "=" * 80)
    print("策略测试完成")
    print("=" * 80)


def demonstrate_crossover_logic():
    """演示交叉逻辑"""
    print("\n双均线交叉逻辑说明:")
    print("-" * 50)
    print("买入信号条件:")
    print("  • 前5日均价 > 10日均价")
    print("  • 前1日5日均价 < 10日均价")
    print("  • 即：短期均线上穿长期均线（金叉）")
    print()
    print("卖出信号条件:")
    print("  • 前5日均价 < 10日均价")
    print("  • 前1日5日均价 > 10日均价")
    print("  • 即：短期均线下穿长期均线（死叉）")
    print()
    print("优势:")
    print("  • 比单均线更稳定，减少假信号")
    print("  • 短期MA(5)反应灵敏，长期MA(10)过滤噪音")
    print("  • 适合中短期趋势跟踪")


if __name__ == "__main__":
    demonstrate_crossover_logic()
    test_double_ma_signals()