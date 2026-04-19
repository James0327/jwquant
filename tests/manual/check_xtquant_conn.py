#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
xtquant 股票账户诊断脚本：连接、查询账户信息、退出登录

@descriptions: xtquant stock account check
@file: /scripts/check_xtquant_conn.py
@license: com.jw
@author: winnie/james
@contact: guoyiyong2019@163.com
@version: 1.0
@date: 2025/11/21 22:33

Copyright (C) 2025 JW All rights reserved.
"""
import time
import os
import sys

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
    build_account_diagnostics,
    connect_xtquant_account,
)


class SimpleTradeCallback(XtQuantTradeCallbackBase):
    """简单交易回调类，用于监听连接和账户状态"""

    def on_disconnected(self):
        print("[Callback] 连接已断开")

    def on_account_status(self, status):
        print(f"[Callback] 账户状态更新: 账号={status.account_id}, 状态={status.status}")


def login(qmt_path, account_id, max_retry=5, retry_interval=3):
    """
    账号连接与登录（包含重试机制）
    :param qmt_path: mini QMT 的 userdata_mini 路径
    :param account_id: 资金账号
    :param max_retry: 最大重试次数
    :param retry_interval: 重试间隔（秒）
    :return: XtQuantSession | None
    """
    session_id = int(time.time())
    print(f"正在尝试连接 QMT: {qmt_path}")
    print(f"会话ID: {session_id}")
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
        print(f"QMT 客户端连接或订阅失败: {exc}")
        return None

    print("QMT 客户端连接成功")
    print(f"账户 {account_id} 订阅成功")
    return session


def query_account_info(session: XtQuantSession | None):
    """
    查询账户基本信息（资产、持仓）
    """
    if session is None:
        print("查询失败：交易对象或账户未就绪")
        return

    diagnostics = build_account_diagnostics(session)
    for line in diagnostics.asset_lines:
        print(line)
    for line in diagnostics.position_lines:
        print(line)


def logout(session: XtQuantSession | None):
    """
    退出登录并停止交易线程
    """
    if session:
        print("\n正在退出登录并停止服务...")
        session.stop()
        print("服务已停止")
    else:
        print("交易对象不存在，无需退出")


if __name__ == "__main__":
    # 从配置文件读取股票账户配置
    config = Config()
    QMT_PATH = config.get("broker.xtquant.stock.path")
    ACCOUNT_ID = config.get("broker.xtquant.stock.account_id")

    print(f"\n=== 股票账户诊断信息 ===")
    print(f"QMT 路径: {QMT_PATH}")
    print(f"股票账户ID: {ACCOUNT_ID}")
    print(f"路径是否存在: {os.path.exists(QMT_PATH)}")

    # 1. 实现账号连接
    session = login(QMT_PATH, ACCOUNT_ID)

    if session:
        # 等待一会儿确保数据同步
        time.sleep(1)

        # 2. 实现查询账户信息
        query_account_info(session)

        # 保持运行一下，观察回调
        time.sleep(2)

    else:
        print("\n=== 股票账户故障排查建议 ===")
        print("1. 检查 MiniQMT 客户端是否已启动")
        print("2. 检查股票账户是否已在 QMT 中登录")
        print("3. 确认股票账户ID是否正确")
        print("4. 检查网络连接是否正常")

    # 3. 实现退出登录
    logout(session)
