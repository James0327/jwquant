#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tushare API 连接与数据获取检查脚本

@descriptions: Tushare API 连接与数据获取测试
@file: /scripts/check_tushare_conn.py
@license: com.jw
@author: chenyy/james
@contact: guoyiyong2019@163.com
@version: 1.0
@date: 2026/03/21 00:13

Copyright (C) 2026 JW All rights reserved.
"""
import logging

import tushare as ts
import pandas as pd

from jwquant.common.config import get as get_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_tushare_pro():
    """初始化 Tushare Pro API 连接。"""
    logger.info("=" * 60)
    logger.info("开始初始化 Tushare Pro API 连接...")
    token = get_config("data.tushare.token")
    if not token:
        raise ValueError("缺少 Tushare Token，请设置 config/settings.common.toml 的 data.tushare.token")
    ts.set_token(token)
    pro = ts.pro_api()
    logger.info("Tushare Pro API 连接初始化完成")
    logger.info("=" * 60)
    return pro


def check_frame(name: str, **kwargs) -> pd.DataFrame:
    """拉取并检查一组 Tushare 行情数据。"""
    logger.info(f"[检查] {name}...")
    df = ts.pro_bar(**kwargs)
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        raise RuntimeError(f"{name} 失败：未获取到有效数据")
    logger.info(f"[数据] 获取到 {len(df)} 条数据")
    logger.info(f"[数据] 字段: {list(df.columns)}")
    return df


def main() -> None:
    """运行手动 Tushare 连通性检查。"""
    tushare_pro = get_tushare_pro()
    if tushare_pro is None:
        raise RuntimeError("Tushare Pro 初始化失败")

    check_frame(
        "日线前复权行情 (000001.SZ, qfq)",
        ts_code="000001.SZ",
        adj="qfq",
        start_date="20180101",
        end_date="20181011",
    )
    check_frame(
        "日线后复权行情 (000001.SZ, hfq)",
        ts_code="000001.SZ",
        adj="hfq",
        start_date="20180101",
        end_date="20181011",
    )
    check_frame(
        "周线前复权行情 (000001.SZ, W, qfq)",
        ts_code="000001.SZ",
        freq="W",
        adj="qfq",
        start_date="20180101",
        end_date="20181011",
    )
    check_frame(
        "周线后复权行情 (000001.SZ, W, hfq)",
        ts_code="000001.SZ",
        freq="W",
        adj="hfq",
        start_date="20180101",
        end_date="20181011",
    )
    check_frame(
        "月线前复权行情 (000001.SZ, M, qfq)",
        ts_code="000001.SZ",
        freq="M",
        adj="qfq",
        start_date="20180101",
        end_date="20181011",
    )
    check_frame(
        "月线后复权行情 (000001.SZ, M, hfq)",
        ts_code="000001.SZ",
        freq="M",
        adj="hfq",
        start_date="20180101",
        end_date="20181011",
    )
    logger.info("Tushare 连通性检查完成")


if __name__ == "__main__":
    main()
