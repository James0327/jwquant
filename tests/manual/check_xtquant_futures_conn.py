#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
xtquant 期货账户诊断脚本：连接、查询期货账户信息、退出登录

@descriptions: xtquant futures account check
@file: /scripts/check_xtquant_futures.py
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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from jwquant.common.config import Config
from jwquant.trading.execution import (
    XtQuantAccountConfig,
    XtQuantConnectError,
    XtQuantConfigError,
    XtQuantImportError,
    XtQuantSession,
    XtQuantTradeCallbackBase,
    connect_xtquant_account,
    print_account_diagnostics,
)

# 期货账户标识常量
FUTURES_MARKET_ID = "FUTURE"  # 期货市场标识


class FuturesTradeCallback(XtQuantTradeCallbackBase):
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
    :return: XtQuantSession | None
    """
    session_id = int(time.time())
    print(f"正在尝试连接 QMT 期货账户: {qmt_path}")
    print(f"会话ID: {session_id}")
    print(f"账户类型: {account_type}")
    try:
        session = connect_xtquant_account(
            XtQuantAccountConfig(
                market="futures",
                path=qmt_path,
                account_id=account_id,
                account_type=account_type,
                max_retry=max_retry,
                retry_interval=retry_interval,
            ),
            callback=FuturesTradeCallback(label="期货账户"),
            session_id=session_id,
        )
    except (XtQuantImportError, XtQuantConfigError, XtQuantConnectError) as exc:
        print(f"QMT 期货客户端连接或订阅失败: {exc}")
        return None

    print("QMT 期货客户端连接成功")
    print(f"期货账户 {account_id} 订阅成功")
    return session


def query_futures_account_info(
    session: XtQuantSession | None,
    account_type=FUTURES_MARKET_ID,
):
    """
    查询期货账户基本信息（资产、持仓）
    :param trader: 交易对象
    :param account: 账户对象
    :param account_type: 账户类型标识
    """
    if session is None:
        print("查询失败：交易对象或账户未就绪")
        return

    print_account_diagnostics(session, account_type=account_type)


def logout_futures(session: XtQuantSession | None):
    """
    退出期货账户登录并停止交易线程
    """
    if session:
        print("\n正在退出期货账户登录并停止服务...")
        session.stop()
        print("期货服务已停止")
    else:
        print("期货交易对象不存在，无需退出")


if __name__ == "__main__":
    # 从配置文件读取期货账户配置
    config = Config()
    QMT_PATH = config.get("broker.xtquant.futures.path")
    FUTURES_ACCOUNT_ID = config.get("broker.xtquant.futures.account_id")
    ACCOUNT_TYPE = config.get("broker.xtquant.futures.account_type")

    print(f"\n=== 期货账户诊断信息 ===")
    print(f"QMT 路径: {QMT_PATH}")
    print(f"期货账户ID: {FUTURES_ACCOUNT_ID}")
    print(f"账户类型: {ACCOUNT_TYPE}")
    print(f"市场类型: {FUTURES_MARKET_ID}")
    print(f"路径是否存在: {os.path.exists(QMT_PATH)}")

    # 1. 实现期货账户连接
    session = login_futures(QMT_PATH, FUTURES_ACCOUNT_ID, ACCOUNT_TYPE)

    if session:
        # 等待一会儿确保数据同步
        time.sleep(1)

        # 2. 实现查询期货账户信息
        query_futures_account_info(
            session,
            ACCOUNT_TYPE,
        )

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
    logout_futures(session)
