#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
xtquant 账号管理：连接、查询账户信息、退出登录

@descriptions: xtquant_test.py
@file: /xxxxxx/xtquant_test.py
@license: com.jw
@author: winnie/james
@contact: guoyiyong2019@163.com
@version: 1.0
@date: 2025/11/21 22:33

Copyright (C) 2025 JW All rights reserved.
"""
import time
from xtquant import xttrader
from xtquant.xttrader import XtQuantTrader
from xtquant.xttype import StockAccount


class SimpleTradeCallback(xttrader.XtQuantTraderCallback):
    """简单交易回调类，用于监听连接和账户状态"""

    def on_disconnected(self):
        print("[Callback] 连接已断开")

    def on_account_status(self, status):
        print(f"[Callback] 账户状态更新: 账号={status.account_id}, 状态={status.status}")


def login(qmt_path, account_id, session_id=123456):
    """
    账号连接与登录
    :param qmt_path: mini QMT 的 userdata_mini 路径
    :param account_id: 资金账号
    :param session_id: 会话ID
    :return: (trader, account)
    """
    print(f"正在尝试连接 QMT: {qmt_path}")
    trader = XtQuantTrader(qmt_path, session_id)

    # 注册回调
    callback = SimpleTradeCallback()
    trader.register_callback(callback)

    # 启动交易线程
    trader.start()

    # 建立连接
    connect_result = trader.connect()
    if connect_result == 0:
        print("QMT 客户端连接成功")
    else:
        print(f"QMT 客户端连接失败，错误码: {connect_result}")
        return None, None

    # 订阅账户
    account = StockAccount(account_id)
    subscribe_result = trader.subscribe(account)
    if subscribe_result == 0:
        print(f"账户 {account_id} 订阅成功")
    else:
        print(f"账户 {account_id} 订阅失败，错误码: {subscribe_result}")
        return trader, None

    return trader, account


def query_account_info(trader, account):
    """
    查询账户基本信息（资产、持仓）
    """
    if not trader or not account:
        print("查询失败：交易对象或账户未就绪")
        return

    print("\n--- 账户资产信息 ---")
    asset = trader.query_stock_asset(account)
    if asset:
        print(f"账号: {asset.account_id}")
        print(f"可用资金: {asset.cash:.2f}")
        print(f"冻结资金: {asset.frozen_cash:.2f}")
        print(f"持仓市值: {asset.market_value:.2f}")
        print(f"总资产: {asset.total_asset:.2f}")
    else:
        print("无法获取资产信息")

    print("\n--- 账户持仓信息 ---")
    positions = trader.query_stock_positions(account)
    if positions:
        for pos in positions:
            print(f"代码: {pos.stock_code}, 持仓: {pos.volume}, 可用: {pos.can_use_volume}, 成本价: {pos.open_price:.3f}")
    else:
        print("当前无持仓或无法获取持仓信息")


def logout(trader):
    """
    退出登录并停止交易线程
    """
    if trader:
        print("\n正在退出登录并停止服务...")
        trader.stop()
        print("服务已停止")
    else:
        print("交易对象不存在，无需退出")


if __name__ == "__main__":
    # 配置信息（请根据实际情况修改）
    QMT_PATH = r"D:\zzcf\userdata_mini"
    ACCOUNT_ID = "100571991"  # 替换为真实的资金账号

    print(f"\n=== 诊断信息 ===")
    print(f"QMT 路径: {QMT_PATH}")
    print(f"账户ID: {ACCOUNT_ID}")
    import os

    print(f"路径是否存在: {os.path.exists(QMT_PATH)}")

    # 1. 实现账号连接
    xt_trader, xt_account = login(QMT_PATH, ACCOUNT_ID)

    if xt_trader and xt_account:
        # 等待一会儿确保数据同步
        time.sleep(1)

        # 2. 实现查询账户信息
        query_account_info(xt_trader, xt_account)

        # 保持运行一下，观察回调
        time.sleep(2)

        # 3. 实现退出登录
        logout(xt_trader)
    else:
        print("\n=== 故障排查建议 ===")
        print("1. 检查 MiniQMT 客户端是否已启动")
        print("2. 检查账户是否已在 QMT 中登录")
        print("3. 确认账户ID是否正确")
        print("4. 尝试等待更长时间后再订阅账户")
        print("\n正在尝试延长等待时间后重试...")

        if xt_trader:
            # 延长等待时间重试
            time.sleep(3)
            account = StockAccount(ACCOUNT_ID)
            retry_result = xt_trader.subscribe(account)
            print(f"重试订阅结果: {retry_result}")

            if retry_result == 0:
                print("重试成功！")
                query_account_info(xt_trader, account)

            logout(xt_trader)
