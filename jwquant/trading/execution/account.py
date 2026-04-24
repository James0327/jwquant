"""
XtQuant 账户级查询编排。

该模块负责把底层账户快照组织成稳定的账户视图：
账户总览/资产 -> 持仓 -> 成交 -> 委托。
格式化细节仍由 xtquant_diagnostics 模块负责，避免账户编排层混入终端展示字段。
"""
from __future__ import annotations

from dataclasses import dataclass

from jwquant.common.log import get_logger
from jwquant.trading.execution.broker import XtQuantSession
from jwquant.trading.execution.xtquant_diagnostics import (
    format_account_asset_lines,
    format_account_order_lines,
    format_account_position_lines,
    format_account_trade_lines,
)

logger = get_logger("jwquant.xtquant.account")


@dataclass(slots=True)
class XtQuantAccountDiagnostics:
    """可直接用于终端展示的账户诊断结果。

    用途：
      - 表达一次账户级查询编排后的四组输出；
      - 固定账户总览/资产、持仓、成交、委托的业务顺序；
      - 供 manual 脚本、后续 CLI 或服务层复用。

    输入输出：
      - 输入：由 build_account_diagnostics 基于 XtQuantSession 查询生成；
      - 输出：四组已格式化文本行，调用方可以打印、记录或测试断言。
    """

    asset_lines: list[str]
    position_lines: list[str]
    trade_lines: list[str]
    order_lines: list[str]


def build_account_diagnostics(
    session: XtQuantSession,
    account_type: str | None = None,
) -> XtQuantAccountDiagnostics:
    """构建账户级诊断结果。

    关键逻辑：
      1. 通过 XtQuantSession.query_snapshot 一次性获取账户资产、持仓、成交、委托；
      2. 根据账户配置和显式 account_type 判断是否按期货口径展示；
      3. 将四类账户信息分别交给格式化模块，保持编排层和展示层分离。

    异常处理：
      - 底层查询异常不在此处吞掉，继续向上抛出；
      - 上层脚本可基于业务场景决定是打印故障提示还是中断流程。
    """
    snapshot = session.query_snapshot()
    resolved_account_type = str(account_type or session.account_config.account_type or "").strip().upper()
    is_futures = session.account_config.market == "futures" or resolved_account_type == "FUTURE"
    logger.info(
        "build xtquant account diagnostics: market=%s, account_id=%s, account_type=%s, is_futures=%s",
        session.account_config.market,
        session.account_config.account_id,
        resolved_account_type,
        is_futures,
    )
    return XtQuantAccountDiagnostics(
        asset_lines=format_account_asset_lines(snapshot.asset, account_type=resolved_account_type, is_futures=is_futures),
        position_lines=format_account_position_lines(
            snapshot.positions,
            account_type=resolved_account_type,
            is_futures=is_futures,
            position_statistics=snapshot.position_statistics,
            asset=snapshot.asset,
        ),
        trade_lines=format_account_trade_lines(snapshot.trades, account_type=resolved_account_type, is_futures=is_futures),
        order_lines=format_account_order_lines(snapshot.orders, account_type=resolved_account_type, is_futures=is_futures),
    )


def print_account_diagnostics(
    session: XtQuantSession,
    account_type: str | None = None,
    printer=print,
) -> None:
    """按统一顺序打印账户诊断信息。

    用途：
      - 复用股票和期货手工诊断脚本中相同的打印流程；
      - 保证账户总览/资产、持仓、成交、委托四类信息的输出顺序稳定；
      - 让脚本入口只负责配置读取、连接和故障提示，避免重复维护展示循环。

    输入输出：
      - 输入：已连接的 XtQuantSession、可选账户类型、可替换的 printer；
      - 输出：无返回值，逐行调用 printer 输出诊断文本。

    关键逻辑：
      1. 先调用 build_account_diagnostics 做真实账户查询和格式化；
      2. 按“资产 -> 持仓 -> 成交 -> 委托”的业务顺序输出；
      3. printer 默认为 print，测试或上层调用可注入 list.append 等收集器。
    """
    diagnostics = build_account_diagnostics(session, account_type=account_type)
    sections = (
        diagnostics.asset_lines,
        diagnostics.position_lines,
        diagnostics.trade_lines,
        diagnostics.order_lines,
    )
    logger.info(
        "print xtquant account diagnostics: market=%s, account_id=%s, account_type=%s, sections=%s",
        session.account_config.market,
        session.account_config.account_id,
        account_type or session.account_config.account_type,
        [len(lines) for lines in sections],
    )
    for lines in sections:
        for line in lines:
            printer(line)
