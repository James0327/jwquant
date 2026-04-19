"""
XtQuant 账户诊断展示辅助。

这一层只负责把账户查询结果格式化为适合终端展示的文本，
不承担连接、查询或状态管理。
"""
from __future__ import annotations

from dataclasses import dataclass

from jwquant.trading.execution.broker import (
    XtQuantAccountSnapshot,
    XtQuantAssetSnapshot,
    XtQuantPositionSnapshot,
    XtQuantSession,
)


@dataclass(slots=True)
class XtQuantAccountDiagnostics:
    """可直接用于终端展示的账户诊断结果。"""

    asset_lines: list[str]
    position_lines: list[str]


def build_account_diagnostics(
    session: XtQuantSession,
    account_type: str | None = None,
) -> XtQuantAccountDiagnostics:
    """把账户查询结果转换为可直接打印的文本行。"""
    snapshot = session.query_snapshot()
    resolved_account_type = str(account_type or session.account_config.account_type or "").strip().upper()
    is_futures = session.account_config.market == "futures" or resolved_account_type == "FUTURE"
    return XtQuantAccountDiagnostics(
        asset_lines=format_account_asset_lines(snapshot.asset, account_type=resolved_account_type, is_futures=is_futures),
        position_lines=format_account_position_lines(snapshot.positions, account_type=resolved_account_type, is_futures=is_futures),
    )


def format_account_asset_lines(
    asset: XtQuantAssetSnapshot | None,
    account_type: str = "",
    is_futures: bool = False,
) -> list[str]:
    """格式化资产信息。"""
    prefix = "期货账户资产信息" if is_futures else "账户资产信息"
    lines = [f"\n--- {prefix}" + (f" (账户类型: {account_type})" if is_futures and account_type else "") + " ---"]
    if asset is None:
        lines.append("无法获取资产信息")
        return lines
    lines.extend(
        [
            f"账号: {asset.account_id}",
            f"可用资金: {asset.cash:.2f}",
            f"冻结资金: {asset.frozen_cash:.2f}",
            f"持仓市值: {asset.market_value:.2f}",
            f"总资产: {asset.total_asset:.2f}",
        ]
    )
    if is_futures and asset.margin_ratio is not None:
        lines.append(f"保证金比例: {asset.margin_ratio:.2%}")
    if is_futures and asset.available_margin is not None:
        lines.append(f"可用保证金: {asset.available_margin:.2f}")
    return lines


def format_account_position_lines(
    positions: list[XtQuantPositionSnapshot],
    account_type: str = "",
    is_futures: bool = False,
) -> list[str]:
    """格式化持仓信息。"""
    prefix = "期货账户持仓信息" if is_futures else "账户持仓信息"
    lines = [f"\n--- {prefix}" + (f" (账户类型: {account_type})" if is_futures and account_type else "") + " ---"]
    if not positions:
        lines.append("当前无持仓或无法获取持仓信息")
        return lines

    futures_count = 0
    for pos in positions:
        if is_futures and pos.is_futures_candidate:
            futures_count += 1
            lines.append(
                f"期货合约: {pos.code}, 持仓: {pos.volume}, 可用: {pos.available_volume}, 成本价: {pos.open_price:.3f}"
            )
            continue
        suffix = " (非期货)" if is_futures and not pos.is_futures_candidate else ""
        lines.append(
            f"代码: {pos.code}, 持仓: {pos.volume}, 可用: {pos.available_volume}, 成本价: {pos.open_price:.3f}{suffix}"
        )

    if is_futures:
        if futures_count > 0:
            lines.append(f"共 {futures_count} 个期货合约持仓")
        else:
            lines.append("警告: 未检测到期货合约持仓，请确认账户类型正确")
    return lines
