#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PyCharm jwquant test_tushare_conn

@descriptions: Tushare API 连接与数据获取测试
@file: /xxxxxx/test_tushare_conn.py
@license: com.jw
@author: chenyy/james
@contact: guoyiyong2019@163.com
@version: 1.0
@date: 2026/03/21 00:13

Copyright (C) 2026 JW All rights reserved.
"""
import logging
import pytest
import tushare as ts
import pandas as pd

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Tushare Token（建议后续移到环境变量或配置文件中）
TOKEN = "6aca1b76071dcb4682ba0fd662f3161ebc617136f7a67b891fa6a2d8"


@pytest.fixture(scope="module")
def tushare_pro():
    """Tushare Pro API 连接 fixture"""
    logger.info("=" * 60)
    logger.info("开始初始化 Tushare Pro API 连接...")
    ts.set_token(TOKEN)
    pro = ts.pro_api()
    logger.info("Tushare Pro API 连接初始化完成")
    logger.info("=" * 60)
    return pro


class TestTushareConnection:
    """Tushare 连接测试类"""

    def test_tushare_connection(self, tushare_pro):
        """测试 Tushare 连接是否成功"""
        logger.info("[测试] Tushare 连接测试开始...")
        assert tushare_pro is not None
        logger.info("[测试] Tushare 连接测试通过 ✓")

    def test_tushare_daily_qfq(self, tushare_pro):
        """测试获取日线前复权行情"""
        logger.info("[测试] 获取日线前复权行情 (000001.SZ, qfq)...")
        df = ts.pro_bar(
            ts_code='000001.SZ',
            adj='qfq',
            start_date='20180101',
            end_date='20181011'
        )
        logger.info(f"[数据] 获取到 {len(df)} 条日线前复权数据")
        logger.info(f"[数据] 数据列: {list(df.columns)}")
        logger.info(f"[数据] 首行数据:\n{df.head(1).to_string()}")

        assert df is not None
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert 'close' in df.columns or 'CLOSE' in df.columns
        logger.info("[测试] 日线前复权行情测试通过 ✓")

    def test_tushare_daily_hfq(self, tushare_pro):
        """测试获取日线后复权行情"""
        logger.info("[测试] 获取日线后复权行情 (000001.SZ, hfq)...")
        df = ts.pro_bar(
            ts_code='000001.SZ',
            adj='hfq',
            start_date='20180101',
            end_date='20181011'
        )
        logger.info(f"[数据] 获取到 {len(df)} 条日线后复权数据")
        logger.info(f"[数据] 最新收盘价: {df['close'].iloc[0] if 'close' in df.columns else 'N/A'}")

        assert df is not None
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        logger.info("[测试] 日线后复权行情测试通过 ✓")

    def test_tushare_weekly_qfq(self, tushare_pro):
        """测试获取周线前复权行情"""
        logger.info("[测试] 获取周线前复权行情 (000001.SZ, W, qfq)...")
        df = ts.pro_bar(
            ts_code='000001.SZ',
            freq='W',
            adj='qfq',
            start_date='20180101',
            end_date='20181011'
        )
        logger.info(f"[数据] 获取到 {len(df)} 条周线前复权数据")

        assert df is not None
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        logger.info("[测试] 周线前复权行情测试通过 ✓")

    def test_tushare_weekly_hfq(self, tushare_pro):
        """测试获取周线后复权行情"""
        logger.info("[测试] 获取周线后复权行情 (000001.SZ, W, hfq)...")
        df = ts.pro_bar(
            ts_code='000001.SZ',
            freq='W',
            adj='hfq',
            start_date='20180101',
            end_date='20181011'
        )
        logger.info(f"[数据] 获取到 {len(df)} 条周线后复权数据")

        assert df is not None
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        logger.info("[测试] 周线后复权行情测试通过 ✓")

    def test_tushare_monthly_qfq(self, tushare_pro):
        """测试获取月线前复权行情"""
        logger.info("[测试] 获取月线前复权行情 (000001.SZ, M, qfq)...")
        df = ts.pro_bar(
            ts_code='000001.SZ',
            freq='M',
            adj='qfq',
            start_date='20180101',
            end_date='20181011'
        )
        logger.info(f"[数据] 获取到 {len(df)} 条月线前复权数据")

        assert df is not None
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        logger.info("[测试] 月线前复权行情测试通过 ✓")

    def test_tushare_monthly_hfq(self, tushare_pro):
        """测试获取月线后复权行情"""
        logger.info("[测试] 获取月线后复权行情 (000001.SZ, M, hfq)...")
        df = ts.pro_bar(
            ts_code='000001.SZ',
            freq='M',
            adj='hfq',
            start_date='20180101',
            end_date='20181011'
        )
        logger.info(f"[数据] 获取到 {len(df)} 条月线后复权数据")

        assert df is not None
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        logger.info("[测试] 月线后复权行情测试通过 ✓")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
