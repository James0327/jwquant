#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
xtquant 期货账户测试：连接、查询期货账户信息、退出登录

@descriptions: xtquant_futures_test.py
@file: /tests/trading/test_xtquant_futures.py
@license: com.jw
@author: winnie/james
@contact: guoyiyong2019@163.com
@version: 1.0
@date: 2025/11/21 22:33

Copyright (C) 2025 JW All rights reserved.
"""
import time
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from jwquant.common.config import Config
from xtquant import xttrader
from xtquant.xttrader import XtQuantTrader
from xtquant.xttype import StockAccount

# 期货账户标识常量
FUTURES_MARKET_ID = "FUTURE"  # 期货市场标识


class FuturesTradeCallback(xttrader.XtQuantTraderCallback):
    """期货交易回调类，用于监听连接和账户状态"""

    def on_disconnected(self):
        print("[Callback] 期货连接已断开")

    def on_account_status(self, status):
        print(f"[Callback] 期货账户状态更新: 账号={status.account_id}, 状态={status.status}")


def login_futures(qmt_path, account_id, account_type=FUTURES_MARKET_ID, max_retry=5, retry_interval=3):
    """
    期货账户连接与登录（包含重试机制）
    :param qmt_path: mini QMT 的 userdata_mini 路径
    :param account_id: 期货资金账号
    :param account_type: 账户类型标识（期货）
    :param max_retry: 最大重试次数
    :param retry_interval: 重试间隔（秒）
    :return: (trader, account)
    """
    # 自动生成session_id（基于时间戳）
    session_id = int(time.time())

    print(f"正在尝试连接 QMT 期货账户: {qmt_path}")
    print(f"会话ID: {session_id}")
    print(f"账户类型: {account_type}")
    trader = XtQuantTrader(qmt_path, session_id)

    # 注册回调
    callback = FuturesTradeCallback()
    trader.register_callback(callback)

    # 启动交易线程
    trader.start()

    # 建立连接
    connect_result = trader.connect()
    if connect_result == 0:
        print("QMT 期货客户端连接成功")
    else:
        print(f"QMT 期货客户端连接失败，错误码: {connect_result}")
        return None, None

    # 订阅期货账户（带重试机制）
    account = StockAccount(account_id, account_type='FUTURE')

    for retry_count in range(1, max_retry + 1):
        if retry_count > 1:
            print(f"\n第 {retry_count}/{max_retry} 次订阅尝试...")
            time.sleep(retry_interval)

        subscribe_result = trader.subscribe(account)

        if subscribe_result == 0:
            if retry_count == 1:
                print(f"期货账户 {account_id} 订阅成功")
            else:
                print(f"期货账户 {account_id} 重试订阅成功！")
            return trader, account
        else:
            if retry_count == 1:
                print(f"期货账户 {account_id} 订阅失败，错误码: {subscribe_result}")
                print("正在尝试延长等待时间后重试...")
            else:
                print(f"第 {retry_count} 次订阅失败，错误码: {subscribe_result}")

            if retry_count == max_retry:
                print(f"\n已达到最大重试次数 ({max_retry})，订阅失败")
                return trader, None

    return trader, None


def query_futures_account_info(trader, account, account_type=FUTURES_MARKET_ID):
    """
    查询期货账户基本信息（资产、持仓）
    :param trader: 交易对象
    :param account: 账户对象
    :param account_type: 账户类型标识
    """
    if not trader or not account:
        print("查询失败：交易对象或账户未就绪")
        return

    print(f"\n--- 期货账户资产信息 (账户类型: {account_type}) ---")
    asset = trader.query_stock_asset(account)
    if asset:
        print(f"账号: {asset.account_id}")
        print(f"可用资金: {asset.cash:.2f}")
        print(f"冻结资金: {asset.frozen_cash:.2f}")
        print(f"持仓市值: {asset.market_value:.2f}")
        print(f"总资产: {asset.total_asset:.2f}")
        
        # 期货特有信息
        if hasattr(asset, 'margin_ratio'):
            print(f"保证金比例: {asset.margin_ratio:.2%}")
        if hasattr(asset, 'available_margin'):
            print(f"可用保证金: {asset.available_margin:.2f}")
    else:
        print("无法获取资产信息")

    print(f"\n--- 期货账户持仓信息 (账户类型: {account_type}) ---")
    positions = trader.query_stock_positions(account)
    if positions:
        futures_count = 0
        for pos in positions:
            # 期货合约代码通常包含特定格式（如 IF2401, rb2401 等）
            if any(indicator in pos.stock_code.upper() for indicator in ['IF', 'IH', 'IC', 'IM', 'RB', 'RU', 'CU', 'AL', 'ZN', 'NI']):
                futures_count += 1
                print(f"期货合约: {pos.stock_code}, 持仓: {pos.volume}, 可用: {pos.can_use_volume}, 成本价: {pos.open_price:.3f}")
            else:
                print(f"代码: {pos.stock_code}, 持仓: {pos.volume}, 可用: {pos.can_use_volume}, 成本价: {pos.open_price:.3f} (非期货)")
        
        if futures_count > 0:
            print(f"共 {futures_count} 个期货合约持仓")
        else:
            print("警告: 未检测到期货合约持仓，请确认账户类型正确")
    else:
        print("当前无持仓或无法获取持仓信息")


def logout_futures(trader):
    """
    退出期货账户登录并停止交易线程
    """
    if trader:
        print("\n正在退出期货账户登录并停止服务...")
        trader.stop()
        print("期货服务已停止")
    else:
        print("期货交易对象不存在，无需退出")


if __name__ == "__main__":
    # 从配置文件读取期货账户配置
    config = Config()
    QMT_PATH = config.get("broker.xtquant.futures.path")
    FUTURES_ACCOUNT_ID = config.get("broker.xtquant.futures.account_id")
    ACCOUNT_TYPE = config.get("broker.xtquant.futures.account_type", "FUTURE")

    print(f"\n=== 期货账户诊断信息 ===")
    print(f"QMT 路径: {QMT_PATH}")
    print(f"期货账户ID: {FUTURES_ACCOUNT_ID}")
    print(f"账户类型: {ACCOUNT_TYPE}")
    print(f"市场类型: {FUTURES_MARKET_ID}")
    print(f"路径是否存在: {os.path.exists(QMT_PATH)}")

    # 1. 实现期货账户连接
    xt_trader, xt_account = login_futures(QMT_PATH, FUTURES_ACCOUNT_ID, ACCOUNT_TYPE)

    if xt_trader and xt_account:
        # 等待一会儿确保数据同步
        time.sleep(1)

        # 2. 实现查询期货账户信息
        query_futures_account_info(xt_trader, xt_account, ACCOUNT_TYPE)

        # 保持运行一下，观察回调
        time.sleep(2)

    else:
        print("\n=== 期货账户故障排查建议 ===")
        print("1. 检查 MiniQMT 客户端是否已启动")
        print("2. 检查期货账户是否已在 QMT 中登录")
        print("3. 确认期货账户ID是否正确")
        print("4. 检查网络连接是否正常")
        print("5. 确认该账户为期货交易账户")

    # 3. 实现退出登录
    logout_futures(xt_trader)