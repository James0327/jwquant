#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MACD+KDJ组合策略测试脚本
验证MACD和KDJ指标组合的信号生成逻辑
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
        logging.FileHandler('macd_kdj_test.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jwquant.trading.strategy.macd_kdj import MACDKDJStrategy
from jwquant.common.types import Bar


def create_sample_data():
    """创建示例数据用于测试"""
    # 模拟股价走势
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(50)]
    base_price = 100.0
    
    # 创建价格序列：制造趋势和震荡行情
    prices = []
    current_price = base_price
    
    for i in range(len(dates)):
        # 添加随机波动
        change = np.random.normal(0, 0.015)  # ±1.5%的日波动
        current_price = current_price * (1 + change)
        
        # 在特定阶段制造趋势
        if 10 <= i <= 20:  # 上升趋势
            trend = 0.02
            current_price = current_price * (1 + trend)
        elif 30 <= i <= 40:  # 下降趋势
            trend = -0.015
            current_price = current_price * (1 + trend)
        elif 45 <= i <= 49:  # 制造超买情况
            trend = 0.03
            current_price = current_price * (1 + trend)
            
        prices.append(current_price)
    
    return dates, prices


def test_macd_kdj_signals():
    """测试MACD+KDJ策略信号生成"""
    logger.info("=" * 100)
    logger.info("开始MACD+KDJ组合策略测试")
    logger.info("=" * 100)
    
    # 创建策略实例
    strategy = MACDKDJStrategy("test_macd_kdj", {
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'kdj_fastk': 9,
        'kdj_slowk': 3,
        'kdj_slowd': 3,
        'min_history': 34,
        'overbought_threshold': 80
    })
    logger.info(f"创建策略实例: {strategy.name}")
    logger.info(f"MACD参数: 快线{strategy.macd_fast}, 慢线{strategy.macd_slow}, 信号线{strategy.macd_signal}")
    logger.info(f"KDJ参数: K周期{strategy.kdj_fastk}, 平滑周期K{strategy.kdj_slowk}/D{strategy.kdj_slowd}")
    
    # 创建示例数据
    dates, prices = create_sample_data()
    logger.info(f"生成 {len(dates)} 天的模拟价格数据，起始日期: {dates[0].strftime('%Y-%m-%d')}")
    
    print(f"\n生成 {len(dates)} 天的模拟价格数据:")
    print("日期\t\t价格\t\t开盘\t\t最高\t\t最低\t\tMACD\t\tK\t\tD\t\tJ\t\t信号")
    print("-" * 120)
    
    # 逐日处理数据
    for i in range(len(dates)):
        # 创建K线数据
        open_price = prices[i] * (0.995 + np.random.random() * 0.01)
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
        
        # 计算指标值用于显示（简化计算）
        macd_value = "N/A"
        k_value = "N/A"
        d_value = "N/A"
        j_value = "N/A"
        
        # 显示结果
        signal_text = ""
        if signal:
            signal_type = "买入" if signal.signal_type.name == 'BUY' else "卖出"
            signal_text = f"{signal_type}@{signal.price:.2f}"
            logger.info(f"产生{signal_type}信号 - 日期: {dates[i].strftime('%Y-%m-%d')}, 价格: {signal.price:.2f}")
            logger.debug(f"信号详情: {signal.reason}")
        
        print(f"{dates[i].strftime('%Y-%m-%d')}\t{prices[i]:.2f}\t\t{open_price:.2f}\t\t{high_price:.2f}\t\t{low_price:.2f}\t\t{macd_value}\t\t{k_value}\t\t{d_value}\t\t{j_value}\t\t{signal_text}")
        
        # 如果产生信号，显示详细原因
        if signal:
            print(f"  原因: {signal.reason}")
    
    logger.info("=" * 100)
    logger.info("MACD+KDJ组合策略测试完成")
    logger.info("=" * 100)
    print("\n" + "=" * 100)
    print("策略测试完成")
    print("=" * 100)


def demonstrate_strategy_logic():
    """演示策略逻辑"""
    print("\nMACD+KDJ组合策略逻辑说明:")
    print("-" * 60)
    print("买入信号条件:")
    print("  • MACD > 0（在零轴上方）")
    print("  • DIF > DEA（快线在慢线上方）")
    print("  • 即：MACD处于多头趋势")
    print()
    print("卖出信号条件:")
    print("  • K > 80 且 D > 80 且 J > 80（超买区域）")
    print("  • J向下突破D（J值从上方向下穿过D值）")
    print("  • 即：高位反转卖出信号")
    print()
    print("策略特点:")
    print("  • MACD过滤趋势，KDJ把握买卖时机")
    print("  • 适合中短线波段操作")
    print("  • 结合趋势和超买超卖信号")


def test_strategy_creation():
    """测试策略创建和基本功能"""
    print("\n策略创建测试:")
    print("-" * 30)
    
    try:
        # 测试策略创建
        strategy = MACDKDJStrategy("test_instance", {
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9
        })
        
        print("✓ 策略实例创建成功")
        print(f"  策略名称: {strategy.name}")
        print(f"  MACD快线: {strategy.macd_fast}")
        print(f"  MACD慢线: {strategy.macd_slow}")
        print(f"  MACD信号线: {strategy.macd_signal}")
        
        # 测试初始化
        strategy.on_init()
        print("✓ 策略初始化完成")
        
        return True
        
    except Exception as e:
        print(f"✗ 策略创建失败: {e}")
        return False


if __name__ == "__main__":
    # 测试策略创建
    if test_strategy_creation():
        demonstrate_strategy_logic()
        test_macd_kdj_signals()
    else:
        print("策略创建失败，终止测试")