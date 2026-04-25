#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
手动测试脚本：股票账号登录、下载数据、执行回测、输出报表

@description: Manual test script for stock account login, data download, backtest execution, and report generation
@file: /tests/manual/test_stock_backtest.py
@license: com.jw
@author: winnie/james
@contact: guoyiyong2019@163.com
@version: 1.0
@date: 2026/04/16

Copyright (C) 2026 JW All rights reserved.
"""
import time
import os
import sys
from pathlib import Path

import pandas as pd

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from jwquant.common.config import Config, get_strategy_config, load_config
from jwquant.common.log import get_logger
from jwquant.trading.data.feed import DataFeed
from jwquant.trading.data.sync import sync_xtquant_data
from jwquant.trading.data.sources.xtquant_src import XtQuantDataSource
from jwquant.trading.data.store import LocalDataStore
from jwquant.trading.backtest.engine import SimpleBacktester, BacktestConfig
from jwquant.trading.backtest.report import build_backtest_report_output_path, write_backtest_report_html
from jwquant.trading.strategy.registry import create_registered_strategy, list_available_strategies
from jwquant.trading.execution import (
    XtQuantAccountConfig,
    XtQuantConnectError,
    XtQuantConfigError,
    XtQuantImportError,
    XtQuantSession,
    XtQuantTradeCallbackBase,
    connect_xtquant_account,
)

# 初始化日志
logger = get_logger("test_stock_backtest")


class SimpleTradeCallback(XtQuantTradeCallbackBase):
    """简单交易回调类，用于监听连接和账户状态"""

    def on_disconnected(self):
        """连接断开回调"""
        logger.warning("交易客户端连接已断开")
        print("[Callback] 连接已断开")

    def on_account_status(self, status):
        """账户状态变更回调"""
        logger.info(f"账户状态更新: 账号={status.account_id}, 状态={status.status}")
        print(f"[Callback] 账户状态更新: 账号={status.account_id}, 状态={status.status}")


def login_xtquant(qmt_path=None, account_id=None, max_retry=None, retry_interval=None):
    """
    账号连接与登录（包含重试机制）

    Args:
        qmt_path: mini QMT 的 userdata_mini 路径，如果为None则从配置读取
        account_id: 资金账号，如果为None则从配置读取
        max_retry: 最大重试次数，如果为None则使用默认值
        retry_interval: 重试间隔（秒），如果为None则使用默认值

    Returns:
        XtQuantSession | None: 成功时返回会话对象，失败时返回 None
    """
    # 从配置文件读取默认参数
    config = Config(profile="test")
    if qmt_path is None:
        qmt_path = config.get("broker.xtquant.stock.path")
    if account_id is None:
        account_id = config.get("broker.xtquant.stock.account_id")
    if max_retry is None:
        max_retry = config.get("broker.xtquant.stock.max_retry")
    if retry_interval is None:
        retry_interval = config.get("broker.xtquant.stock.retry_interval")

    logger.info(f"开始登录XtQuant交易账户: {account_id}")
    logger.info(f"QMT路径: {qmt_path}")

    session_id = int(time.time())
    logger.info(f"生成的会话ID: {session_id}")
    logger.info("正在初始化XtQuant交易客户端...")

    try:
        session = connect_xtquant_account(
            XtQuantAccountConfig(
                market="stock",
                path=qmt_path,
                account_id=account_id,
                account_type="STOCK",
                max_retry=max_retry,
                retry_interval=retry_interval,
            ),
            callback=SimpleTradeCallback(label="股票账户"),
            session_id=session_id,
        )
    except (XtQuantImportError, XtQuantConfigError, XtQuantConnectError) as exc:
        logger.error(f"QMT 客户端连接或订阅失败: {exc}")
        print(f"QMT 客户端连接或订阅失败: {exc}")
        return None

    logger.info("QMT 客户端连接成功")
    logger.info(f"账户 {account_id} 订阅成功")
    print("QMT 客户端连接成功")
    print(f"账户 {account_id} 订阅成功")
    return session


def download_hongbo_data(code=None, market=None, start_date=None, end_date=None):
    """
    下载指定股票的历史数据

    Args:
        code: 股票代码，如果为None则从配置读取
        market: 市场类型，如果为None则从配置读取
        start_date: 开始日期，如果为None则从配置读取
        end_date: 结束日期，如果为None则从配置读取

    Returns:
        str: 下载的股票代码
    """
    # 从配置文件读取默认参数
    config = Config(profile="test")
    if code is None:
        code = config.get("test.target_stock.code")
    if market is None:
        market = config.get("test.target_stock.market")
    if start_date is None:
        start_date = config.get("test.data_start_date")
    if end_date is None:
        end_date = pd.Timestamp.now().strftime("%Y-%m-%d")

    logger.info(f"开始下载股票数据: {code} ({market})")
    logger.info(f"数据时间范围: {start_date} 到 {end_date}")
    print(f"\n=== 开始下载 {code} 数据 ===")

    # 初始化数据源和存储
    logger.info("初始化本地数据存储...")
    store = LocalDataStore()

    logger.info("初始化XtQuant数据源...")
    source = XtQuantDataSource()

    # 下载日线数据
    logger.info(f"开始下载 {code} 日线数据...")
    print(f"下载 {code} 日线数据...")

    try:
        result = sync_xtquant_data(
            code=code,
            market=market,
            timeframe="1d",
            start=start_date,
            end=end_date,
            store=store,
            source=source
        )

        if result and not result.skipped:
            logger.info(f"成功下载 {result.rows} 条日线数据")
            print(f"成功下载 {result.rows} 条日线数据")
        else:
            logger.info("数据已是最新或下载失败")
            print("数据已是最新或下载失败")

    except Exception as e:
        logger.error(f"下载数据时发生错误: {e}")
        print(f"下载数据时发生错误: {e}")
        raise

    return code


def run_backtest(code, backtest_start=None, backtest_end=None, strategy_name=None):
    """
    执行策略回测

    Args:
        code: 股票代码
        backtest_start: 回测开始日期，如果为None则从配置读取
        backtest_end: 回测结束日期，如果为None则从配置读取
        strategy_name: 策略名称，如果为None则从配置读取

    Returns:
        dict: 回测结果，如果失败返回None
    """
    # 从配置文件读取默认参数
    config = Config(profile="test")
    if backtest_start is None:
        backtest_start = config.get("test.backtest_start_date")
    if backtest_end is None:
        backtest_end = config.get("test.backtest_end_date")
    if strategy_name is None:
        strategy_name = config.get("test.strategy_name")

    logger.info(f"开始执行 {code} 回测")
    logger.info(f"回测时间范围: {backtest_start} 到 {backtest_end}")
    logger.info(f"使用策略: {strategy_name}")
    print(f"\n=== 开始执行 {code} 回测 ===")

    # 初始化数据源
    logger.info("初始化数据源...")
    feed = DataFeed()

    # 获取数据
    logger.info("正在加载历史数据...")
    bars = feed.get_bars(
        code=code,
        start=backtest_start,
        end=backtest_end,
        timeframe="1d",
        market="stock",
        adj="qfq"  # 前复权
    )

    if bars.empty:
        logger.error("未找到历史数据，无法执行回测")
        print("未找到历史数据，无法执行回测")
        return None

    logger.info(f"成功加载数据: {len(bars)} 条记录")
    logger.info(f"数据时间范围: 从 {bars.index[0]} 到 {bars.index[-1]}")
    print(f"加载数据: {len(bars)} 条记录，从 {bars.index[0]} 到 {bars.index[-1]}")

    # 配置回测参数
    logger.info("配置回测参数...")
    backtest_config = BacktestConfig(
        initial_capital=config.get("test.backtest.initial_capital"),  # 初始资金
        commission_rate=config.get("backtest.cost.commission_rate"),  # 佣金率
        slippage=config.get("backtest.cost.slippage"),  # 滑点
        market="stock",
        max_position_pct=config.get("risk.max_position_pct"),  # 最大仓位
        buy_reject_threshold_pct=config.get("backtest.risk.buy_reject_threshold_pct"),
        sell_reject_threshold_pct=config.get("backtest.risk.sell_reject_threshold_pct"),
        limit_up_pct=config.get("backtest.risk.limit_up_pct"),
        limit_down_pct=config.get("backtest.risk.limit_down_pct"),
    )
    logger.info(f"回测配置: 初始资金={backtest_config.initial_capital}, 佣金率={backtest_config.commission_rate}, 最大仓位={backtest_config.max_position_pct}")

    # 初始化策略
    logger.info(f"初始化策略: {strategy_name}")
    try:
        strategy_params = get_strategy_config(strategy_name)
    except (KeyError, TypeError) as exc:
        logger.error(f"读取策略配置失败: strategies.{strategy_name}, 错误: {exc}")
        print(f"读取策略配置失败: strategies.{strategy_name}")
        return None

    strategy = create_registered_strategy(strategy_name, strategy_params)
    if strategy is None:
        available_strategies = ", ".join(list_available_strategies())
        logger.error(f"不支持的策略: {strategy_name}，当前已注册策略: {available_strategies}")
        print(f"不支持的策略: {strategy_name}")
        return None

    logger.info(f"策略参数: {strategy_params}")

    # 初始化回测引擎
    logger.info("初始化回测引擎...")
    engine = SimpleBacktester(config=backtest_config)

    # 执行回测
    logger.info("开始执行回测...")
    try:
        results = engine.run_backtest(strategy, bars)
        logger.info("回测执行完成")
        print("回测执行完成")
        return results
    except Exception as e:
        logger.error(f"回测执行失败: {e}")
        print(f"回测执行失败: {e}")
        raise


def generate_report(
    results,
    report_filename=None,
    report_dir=None,
    chart_mode=None,
    strategy_name=None,
    backtest_start=None,
    backtest_end=None,
):
    """
    生成并输出回测报表

    Args:
        results: 回测结果字典
        report_filename: 报表文件名；未传入时按统一规则自动生成
        report_dir: 报表输出目录；未传入时从配置读取
        chart_mode: 图表模式；未传入时从配置读取，支持 simple/full
        strategy_name: 策略名称；未传入时从配置读取
        backtest_start: 回测开始日期；未传入时从配置读取
        backtest_end: 回测结束日期；未传入时从配置读取
    """
    # 从配置文件读取默认参数
    config = Config(profile="test")
    if report_dir is None:
        report_dir = config.get("test.report.dir")
    if chart_mode is None:
        chart_mode = config.get("test.report.chart_mode")
    if strategy_name is None:
        strategy_name = config.get("test.strategy_name")
    if backtest_start is None:
        backtest_start = config.get("test.backtest_start_date")
    if backtest_end is None:
        backtest_end = config.get("test.backtest_end_date")

    if report_filename is None:
        report_path = build_backtest_report_output_path(
            output_dir=report_dir,
            strategy_name=strategy_name,
            start_date=backtest_start,
            end_date=backtest_end,
        )
    else:
        report_path = Path(report_filename)

    logger.info("开始生成回测报表")
    print("\n=== 生成回测报表 ===")

    if not results:
        logger.error("无回测结果，无法生成报表")
        print("无回测结果，无法生成报表")
        return

    try:
        # 生成并保存HTML报表
        logger.info("正在生成并保存HTML报表...")
        report_path = write_backtest_report_html(results, report_path, chart_mode=chart_mode)
        logger.info(f"保存报表到文件: {report_path.absolute()}")

        print(f"报表已保存到: {report_path.absolute()}")

        # 打印关键指标
        logger.info("提取并打印关键绩效指标")
        report = results.get("report", {})
        summary = report.get("summary", {})

        print("\n=== 回测摘要 ===")
        total_return = summary.get('total_return', 0)
        annual_return = summary.get('annual_return', 0)
        max_drawdown = summary.get('max_drawdown', 0)
        sharpe_ratio = summary.get('sharpe_ratio', 0)
        win_rate = summary.get('win_rate', 0)
        total_trades = summary.get('total_trades', 0)
        execution_timing = summary.get('execution_timing', '')
        execution_price_model = summary.get('execution_price_model', '')
        rejected_orders = summary.get('rejected_orders', 0)
        price_guard_blocked_orders = summary.get('price_guard_blocked_orders', 0)

        print(f"总收益率: {total_return:.2%}")
        print(f"年化收益率: {annual_return:.2%}")
        print(f"最大回撤: {max_drawdown:.2%}")
        print(f"夏普比率: {sharpe_ratio:.2f}")
        print(f"胜率: {win_rate:.2%}")
        print(f"总交易次数: {total_trades}")
        print(f"撮合时机: {execution_timing}")
        print(f"成交价格模型: {execution_price_model}")
        print(f"拒单数: {rejected_orders}")
        print(f"价格阈值/涨跌停拦截数: {price_guard_blocked_orders}")

        # 记录关键指标到日志
        logger.info(f"回测完成 - 总收益率: {total_return:.2%}, 年化收益率: {annual_return:.2%}, 最大回撤: {max_drawdown:.2%}")

    except Exception as e:
        logger.error(f"生成报表时发生错误: {e}")
        print(f"生成报表时发生错误: {e}")
        raise


def main():
    """
    主函数：执行完整的股票交易测试流程

    测试流程：
    1. 加载配置
    2. 股票账号登录
    3. 下载历史数据
    4. 执行策略回测
    5. 生成并输出报表
    6. 清理资源
    """
    logger.info("=== 开始股票账号登录、下载数据、执行回测、输出报表测试 ===")
    print("=== 股票账号登录、下载数据、执行回测、输出报表测试 ===")

    # 加载配置
    logger.info("加载系统配置...")
    load_config(profile="test", extra=["config/strategies.toml"])
    config = Config(profile="test")

    # 从配置获取测试参数
    enable_login = config.get("test.enable_login")
    enable_download = config.get("test.enable_download")
    enable_backtest = config.get("test.enable_backtest")
    enable_report = config.get("test.enable_report")

    logger.info(f"测试配置: 登录={enable_login}, 下载={enable_download}, 回测={enable_backtest}, 报表={enable_report}")

    session: XtQuantSession | None = None

    try:
        # 步骤1: 股票账号登录
        if enable_login:
            logger.info("步骤1: 开始股票账号登录")
            print("\n=== 步骤1: 股票账号登录 ===")
            session = login_xtquant()

            if not session:
                logger.error("登录失败，退出测试")
                print("登录失败，退出测试")
                return
        else:
            logger.info("跳过账号登录步骤")

        # 步骤2: 下载数据
        if enable_download:
            logger.info("步骤2: 开始下载数据")
            print("\n=== 步骤2: 下载数据 ===")
            code = download_hongbo_data()
        else:
            logger.info("跳过数据下载步骤")
            code = config.get("test.target_stock.code")

        # 步骤3: 执行回测
        if enable_backtest:
            logger.info("步骤3: 开始执行回测")
            print("\n=== 步骤3: 执行回测 ===")
            results = run_backtest(code)
        else:
            logger.info("跳过回测步骤")
            results = None

        # 步骤4: 输出报表
        if enable_report and results:
            logger.info("步骤4: 开始生成报表")
            print("\n=== 步骤4: 输出报表 ===")
            generate_report(results)
        else:
            logger.info("跳过报表生成步骤")

        logger.info("=== 测试执行完成 ===")
        print("\n=== 测试完成 ===")

    except Exception as e:
        logger.error(f"测试执行过程中发生错误: {e}")
        print(f"测试执行过程中发生错误: {e}")
        raise

    finally:
        # 清理资源
        if session:
            logger.info("清理交易客户端资源...")
            session.stop()
            print("交易客户端已停止")


if __name__ == "__main__":
    main()
