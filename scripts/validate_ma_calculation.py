#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
均线计算方法验证脚本
比较策略内部计算和测试脚本计算的一致性
"""
import sys
import os
import numpy as np
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jwquant.trading.strategy.single_ma import SingleMAStrategy
from jwquant.trading.strategy.double_ma import DoubleMAStrategy
from jwquant.common.types import Bar


def create_sample_data():
    """创建示例数据用于验证"""
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(20)]
    prices = [100 + i * 0.5 + np.random.normal(0, 0.1) for i in range(20)]
    return dates, prices


def calculate_simple_ma(prices, period, index):
    """测试脚本中的均线计算方法"""
    if index < period - 1:
        return None
    return np.mean(prices[index - period + 1:index + 1])


def validate_single_ma():
    """验证单均线策略的计算一致性"""
    print("=" * 60)
    print("单均线策略计算验证")
    print("=" * 60)
    
    # 创建策略实例
    strategy = SingleMAStrategy("validate_single_ma", {
        'ma_period': 5,
        'min_history': 10
    })
    
    # 创建示例数据
    dates, prices = create_sample_data()
    
    print(f"验证 {len(dates)} 天数据的一致性:")
    print("日期\t\t价格\t\t策略MA5\t\t测试MA5\t\t差值")
    print("-" * 60)
    
    inconsistencies = 0
    
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
        
        # 策略内部计算
        strategy_ma = "N/A"
        if len(strategy.history_bars) >= 5:
            ma_series = strategy.calculate_moving_average(5)
            if ma_series and len(ma_series) > 0:
                strategy_ma = f"{ma_series[-1]:.4f}"
        
        # 测试脚本计算
        test_ma = "N/A"
        test_ma_value = calculate_simple_ma(prices, 5, i)
        if test_ma_value is not None:
            test_ma = f"{test_ma_value:.4f}"
        
        # 计算差值
        diff = ""
        if strategy_ma != "N/A" and test_ma != "N/A":
            strategy_val = float(strategy_ma)
            test_val = float(test_ma)
            diff_val = abs(strategy_val - test_val)
            diff = f"{diff_val:.6f}"
            if diff_val > 1e-10:  # 浮点数精度差异阈值
                inconsistencies += 1
        
        print(f"{dates[i].strftime('%Y-%m-%d')}\t{prices[i]:.2f}\t\t{strategy_ma}\t\t{test_ma}\t\t{diff}")
    
    print("-" * 60)
    if inconsistencies == 0:
        print("✓ 单均线计算完全一致")
    else:
        print(f"✗ 发现 {inconsistencies} 处不一致")
    
    return inconsistencies == 0


def validate_double_ma():
    """验证双均线策略的计算一致性"""
    print("\n" + "=" * 60)
    print("双均线策略计算验证")
    print("=" * 60)
    
    # 创建策略实例
    strategy = DoubleMAStrategy("validate_double_ma", {
        'short_ma_period': 5,
        'long_ma_period': 10,
        'min_history': 15
    })
    
    # 创建示例数据
    dates, prices = create_sample_data()
    
    print(f"验证 {len(dates)} 天数据的一致性:")
    print("日期\t\t价格\t\t策略MA5\t\t测试MA5\t\t策略MA10\t测试MA10")
    print("-" * 80)
    
    inconsistencies_5 = 0
    inconsistencies_10 = 0
    
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
        
        # 策略内部计算
        strategy_ma5 = "N/A"
        strategy_ma10 = "N/A"
        
        if len(strategy.history_bars) >= 5:
            short_ma_series = strategy.calculate_moving_average(5)
            if short_ma_series and len(short_ma_series) > 0:
                strategy_ma5 = f"{short_ma_series[-1]:.4f}"
        
        if len(strategy.history_bars) >= 10:
            long_ma_series = strategy.calculate_moving_average(10)
            if long_ma_series and len(long_ma_series) > 0:
                strategy_ma10 = f"{long_ma_series[-1]:.4f}"
        
        # 测试脚本计算
        test_ma5 = "N/A"
        test_ma10 = "N/A"
        
        test_ma5_value = calculate_simple_ma(prices, 5, i)
        if test_ma5_value is not None:
            test_ma5 = f"{test_ma5_value:.4f}"
        
        test_ma10_value = calculate_simple_ma(prices, 10, i)
        if test_ma10_value is not None:
            test_ma10 = f"{test_ma10_value:.4f}"
        
        # 检查一致性
        if strategy_ma5 != "N/A" and test_ma5 != "N/A":
            if abs(float(strategy_ma5) - float(test_ma5)) > 1e-10:
                inconsistencies_5 += 1
        
        if strategy_ma10 != "N/A" and test_ma10 != "N/A":
            if abs(float(strategy_ma10) - float(test_ma10)) > 1e-10:
                inconsistencies_10 += 1
        
        print(f"{dates[i].strftime('%Y-%m-%d')}\t{prices[i]:.2f}\t\t{strategy_ma5}\t\t{test_ma5}\t\t{strategy_ma10}\t\t{test_ma10}")
    
    print("-" * 80)
    if inconsistencies_5 == 0 and inconsistencies_10 == 0:
        print("✓ 双均线计算完全一致")
    else:
        print(f"✗ MA5不一致: {inconsistencies_5} 处, MA10不一致: {inconsistencies_10} 处")
    
    return inconsistencies_5 == 0 and inconsistencies_10 == 0


def analyze_calculation_difference():
    """分析计算方法差异"""
    print("\n" + "=" * 60)
    print("计算方法分析")
    print("=" * 60)
    
    print("1. 策略内部计算方法:")
    print("   - 使用 self.history_bars 中的 Bar 对象")
    print("   - 提取 bar.close 属性进行计算")
    print("   - 返回完整的均线序列")
    
    print("\n2. 测试脚本计算方法:")
    print("   - 直接使用 prices 数组")
    print("   - 对数组切片进行 numpy.mean 计算")
    print("   - 返回单个均线值")
    
    print("\n3. 理论上应该一致，因为:")
    print("   - Bar.close 应该等于对应的 price 值")
    print("   - numpy.mean 的计算逻辑相同")
    print("   - 时间窗口定义相同")


if __name__ == "__main__":
    analyze_calculation_difference()
    
    single_consistent = validate_single_ma()
    double_consistent = validate_double_ma()
    
    print("\n" + "=" * 60)
    print("总体验证结果:")
    if single_consistent and double_consistent:
        print("✓ 所有策略的均线计算方法一致")
        print("✓ 可以放心使用任一计算方法")
    else:
        print("✗ 发现计算不一致，需要进一步检查")
    print("=" * 60)