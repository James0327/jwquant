"""
XtQuant 账户诊断展示辅助。

这一层只负责把账户查询结果格式化为适合终端展示的文本，
不承担连接、查询或状态管理。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from jwquant.common.log import get_logger
from jwquant.trading.execution.broker import (
    XtQuantAssetSnapshot,
    XtQuantOrderSnapshot,
    XtQuantPositionSnapshot,
    XtQuantPositionStatisticsSnapshot,
    XtQuantTradeSnapshot,
)

logger = get_logger("jwquant.xtquant.diagnostics")


def format_account_asset_lines(
    asset: XtQuantAssetSnapshot | None,
    account_type: str = "",
    is_futures: bool = False,
) -> list[str]:
    """格式化资产信息。

    展示策略：
      - 期货账户保留当前已对齐的摘要式输出；
      - 股票账户改为“账号总览”表格，字段顺序对齐客户端页面。
    """
    prefix = "期货账户资产信息" if is_futures else "股票账户总览"
    lines = [f"\n--- {prefix}" + (f" (账户类型: {account_type})" if account_type else "") + " ---"]
    if asset is None:
        lines.append("无法获取资产信息")
        return lines
    if not is_futures:
        lines.extend(_format_stock_asset_overview_lines(asset))
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
    position_statistics: list[XtQuantPositionStatisticsSnapshot] | None = None,
    asset: XtQuantAssetSnapshot | None = None,
) -> list[str]:
    """格式化持仓信息。

    期货账户下同时输出两层视图：
      1. 持仓统计：仅期货账户使用专用统计接口，保证与交易终端口径一致
      2. 持仓明细：展示底层返回的原始持仓记录，便于定位多空分拆或重复记录

    设计原因：
      - 股票与期货账户的持仓查询口径不同，必须分开处理；
      - 期货“持仓统计”不能从“持仓明细”简单汇总得到；
      - 终端界面通常同时存在“持仓统计 / 持仓明细”两个视图。
    """
    prefix = "期货账户持仓信息" if is_futures else "账户持仓信息"
    lines = [f"\n--- {prefix}" + (f" (账户类型: {account_type})" if is_futures and account_type else "") + " ---"]
    if is_futures:
        futures_positions = [pos for pos in positions if pos.is_futures_candidate]
        non_futures_positions = [pos for pos in positions if not pos.is_futures_candidate]
        has_statistics = bool(position_statistics)
        has_futures_positions = bool(futures_positions)

        if has_statistics or has_futures_positions:
            logger.info(
                "format futures diagnostics positions: total=%s, futures=%s, non_futures=%s, statistics=%s",
                len(positions),
                len(futures_positions),
                len(non_futures_positions),
                len(position_statistics or []),
            )
            statistics_rows = _build_futures_position_statistics_rows(position_statistics or [])
            lines.append("持仓统计:")
            if position_statistics:
                for line in _format_futures_position_summary_table_lines(statistics_rows):
                    lines.append(line)
            else:
                lines.append("当前无持仓统计或无法获取持仓统计信息")
            lines.append("持仓明细:")
            if has_futures_positions:
                for line in _format_futures_position_detail_table_lines(
                    _build_futures_position_detail_rows(futures_positions, statistics_rows=statistics_rows)
                ):
                    lines.append(line)
            else:
                lines.append("当前无持仓明细或无法获取持仓明细信息")
            lines.append(
                f"共 {len(futures_positions)} 条期货持仓明细，{len(position_statistics or [])} 条期货持仓统计"
            )
        else:
            lines.append("警告: 未检测到期货合约持仓，请确认账户类型正确")

        for pos in non_futures_positions:
            lines.append(
                f"代码: {pos.code}, 持仓: {pos.volume}, 可用: {pos.available_volume}, 成本价: {pos.open_price:.3f} (非期货)"
            )
        return lines

    if not positions:
        lines.append("当前无持仓或无法获取持仓信息")
        return lines

    lines.extend(_format_stock_position_table_lines(positions, asset))
    return lines


def format_account_trade_lines(
    trades: list[XtQuantTradeSnapshot],
    account_type: str = "",
    is_futures: bool = False,
) -> list[str]:
    """格式化成交记录。

    输出策略：
      - 股票与期货都展示成交记录；
      - 期货账户按终端截图字段输出额外的“期货公司/账号名称”列；
      - 若无成交，则明确提示为空，避免误以为查询失败。
    """
    prefix = "期货账户成交记录" if is_futures else "账户成交记录"
    lines = [f"\n--- {prefix}" + (f" (账户类型: {account_type})" if is_futures and account_type else "") + " ---"]
    if not trades:
        lines.append("当前无成交记录或无法获取成交信息")
        return lines
    if not is_futures:
        lines.extend(_format_stock_trade_table_lines(trades))
        return lines

    headers = [
        ("成交时间", 10, "text"),
        ("品种名称", 8, "text"),
        ("合约代码", 10, "text"),
        ("买卖方向", 8, "text"),
        ("开平", 4, "text"),
        ("成交均价", 10, "price"),
        ("成交量", 8, "num"),
        ("成交额", 10, "num"),
        ("委托号", 10, "text"),
        ("成交编号", 10, "text"),
        ("账号", 12, "text"),
    ]
    if is_futures:
        headers.extend([("期货公司", 10, "text"), ("账号名称", 10, "text")])

    rows: list[list[str]] = []
    for trade in trades:
        native = trade.native_trade
        values = [
            _format_xt_time(trade.traded_time),
            str(_get_native_attr(native, "instrument_name", default="")),
            _normalize_contract_code_for_terminal(trade.code),
            _resolve_trade_side(trade),
            _resolve_offset_flag_text(trade.offset_flag, is_futures=is_futures),
            _format_futures_trade_price(trade.traded_price) if is_futures else _format_price_or_integer(trade.traded_price),
            _format_futures_quantity(trade.traded_volume) if is_futures else _format_number(trade.traded_volume),
            _format_futures_trade_amount(trade.traded_amount) if is_futures else _format_number(trade.traded_amount),
            str(trade.order_id or ""),
            trade.traded_id,
            trade.account_id,
        ]
        if is_futures:
            values.extend(
                [
                    str(_get_native_attr(native, "futures_company", "broker_name", "company_name", default="")),
                    str(_get_native_attr(native, "account_name", "fund_name", "customer_name", default="")),
                ]
            )
        rows.append(values)
    lines.extend(_format_table(headers, rows, drop_empty_titles={"期货公司", "账号名称"} if is_futures else None))
    return lines


def format_account_order_lines(
    orders: list[XtQuantOrderSnapshot],
    account_type: str = "",
    is_futures: bool = False,
) -> list[str]:
    """格式化委托记录。"""
    prefix = "期货账户委托记录" if is_futures else "账户委托记录"
    lines = [f"\n--- {prefix}" + (f" (账户类型: {account_type})" if is_futures and account_type else "") + " ---"]
    if not orders:
        lines.append("当前无委托记录或无法获取委托信息")
        return lines
    if not is_futures:
        lines.extend(_format_stock_order_table_lines(orders))
        return lines

    headers = [
        ("委托时间", 10, "text"),
        ("品种名称", 8, "text"),
        ("合约代码", 10, "text"),
        ("委托状态", 8, "text"),
        ("买卖方向", 8, "text"),
        ("开平", 4, "text"),
        ("限价", 8, "price"),
        ("委托量", 8, "num"),
        ("成交数量", 8, "num"),
        ("成交均价", 8, "price"),
        ("投保", 4, "text"),
        ("委托号", 10, "text"),
        ("状态信息", 10, "text"),
        ("账号", 12, "text"),
    ]
    if is_futures:
        headers.extend([("期货公司", 10, "text"), ("账号名称", 10, "text")])

    rows: list[list[str]] = []
    for order in orders:
        native = order.native_order
        values = [
            _format_xt_time(order.order_time),
            str(_get_native_attr(native, "instrument_name", default="")),
            _normalize_contract_code_for_terminal(order.code),
            _resolve_order_status_text(order.order_status),
            _resolve_order_side(order),
            _resolve_offset_flag_text(order.offset_flag, is_futures=is_futures),
            _format_futures_order_price(order.price) if is_futures else _format_price_or_integer(order.price),
            _format_futures_quantity(order.order_volume) if is_futures else _format_number(order.order_volume),
            _format_futures_quantity(order.traded_volume) if is_futures else _format_number(order.traded_volume),
            _format_futures_order_price(order.traded_price) if is_futures else _format_price_or_integer(order.traded_price),
            _resolve_hedge_flag(native) if is_futures else "",
            str(order.order_id or ""),
            order.status_msg,
            order.account_id,
        ]
        if is_futures:
            values.extend(
                [
                    str(_get_native_attr(native, "futures_company", "broker_name", "company_name", default="")),
                    str(_get_native_attr(native, "account_name", "fund_name", "customer_name", default="")),
                ]
            )
        rows.append(values)
    lines.extend(_format_table(headers, rows, drop_empty_titles={"期货公司", "账号名称"} if is_futures else None))
    return lines


def _format_stock_position_table_lines(
    positions: list[XtQuantPositionSnapshot],
    asset: XtQuantAssetSnapshot | None,
) -> list[str]:
    """按股票客户端持仓页格式输出表格。

    设计原则：
      - 股票持仓与期货持仓字段口径不同，必须独立表头；
      - 优先使用 XtPosition 原始字段，避免混入期货概念；
      - 对无法从当前接口稳定获得的列，保留空白，避免虚构数据。
    """
    headers = [
        ("资金账号", 12, "text"),
        ("证券代码", 10, "text"),
        ("证券名称", 10, "text"),
        ("当前拥股", 10, "num"),
        ("可用数量", 10, "num"),
        ("在途股份", 10, "num"),
        ("冻结数量", 10, "num"),
        ("市值", 10, "num"),
        ("最新价", 8, "price"),
        ("成本价", 8, "price"),
        ("盈亏", 10, "num"),
        ("盈亏比例", 10, "num"),
        ("昨夜拥股", 10, "num"),
        ("账号名称", 10, "text"),
        ("证券公司", 12, "text"),
        ("到期日", 10, "text"),
    ]
    rows: list[list[str]] = []
    for pos in positions:
        native = pos.native_position
        market_value = _coerce_float(_get_native_attr(native, "market_value"), 0.0)
        profit_ratio = _coerce_float(_get_native_attr(native, "profit_rate"), 0.0)
        floating_profit = _coerce_float(_get_native_attr(native, "float_profit"), 0.0)
        values = [
            str(_get_native_attr(native, "account_id", default="") or (asset.account_id if asset else "")),
            _normalize_stock_code_for_terminal(pos.code),
            str(_get_native_attr(native, "instrument_name", "stock_name", default="")),
            _format_number(_coerce_float(_get_native_attr(native, "volume"), pos.volume)),
            _format_number(_coerce_float(_get_native_attr(native, "can_use_volume"), pos.available_volume)),
            _format_number(_coerce_float(_get_native_attr(native, "on_road_volume"), 0.0)),
            _format_number(_coerce_float(_get_native_attr(native, "frozen_volume"), 0.0)),
            _format_number(market_value),
            _format_price(_coerce_float(_get_native_attr(native, "last_price"), 0.0)),
            _format_price(_coerce_float(_get_native_attr(native, "avg_price", "open_price"), pos.open_price)),
            _format_number(floating_profit),
            _format_number(profit_ratio * 100.0),
            _format_number(_coerce_float(_get_native_attr(native, "yesterday_volume"), 0.0)),
            str(_get_native_attr(native, "account_name", default="")),
            str(_get_native_attr(native, "broker_name", default="")),
            str(_get_native_attr(native, "expire_date", default="")),
        ]
        rows.append(values)
    lines = _format_table(headers, rows)
    return lines


def _format_stock_asset_overview_lines(asset: XtQuantAssetSnapshot) -> list[str]:
    """按股票客户端“账号资金”页签红框字段输出账户总览。

    字段来源说明：
      - 只展示截图红框内的资金字段，不输出左侧登录状态、账号状态、更新时间、操作列；
      - 核心金额优先使用标准化快照字段，保证查询字段缺失时仍能展示稳定结果；
      - 证券公司、账号名称当前接口不稳定返回，股票总览中不展示这两个字段。
    """
    native = asset.native_asset
    native_attrs = sorted(name for name in dir(native) if not name.startswith("_")) if native is not None else []
    logger.debug(
        "format stock asset diagnostics: account_id=%s, native_fields=%s",
        asset.account_id,
        native_attrs,
    )

    headers = [
        ("总资产", 10, "num"),
        ("冻结金额", 10, "num"),
        ("当前余额", 10, "num"),
        ("可用金额", 10, "num"),
        ("可取金额", 10, "num"),
        ("总市值", 10, "num"),
        ("盈亏", 10, "num"),
        ("股票市值", 10, "num"),
        ("基金市值", 10, "num"),
        ("资金账号", 12, "text"),
    ]
    row = [
        _format_money(asset.total_asset),
        _format_money(asset.frozen_cash),
        _format_money(_coerce_float(_get_native_attr(native, "current_balance", "balance"), asset.cash)),
        _format_money(asset.cash),
        _format_money(_coerce_float(_get_native_attr(native, "fetch_balance", "enable_balance"), asset.cash)),
        _format_money(asset.market_value),
        _format_money(_coerce_float(_get_native_attr(native, "profit", "float_profit"), 0.0)),
        _format_money(_coerce_float(_get_native_attr(native, "stock_market_value"), asset.market_value)),
        _format_money(_coerce_float(_get_native_attr(native, "fund_market_value"), 0.0)),
        asset.account_id,
    ]
    return _format_table(headers, [row])


def _format_stock_trade_table_lines(trades: list[XtQuantTradeSnapshot]) -> list[str]:
    """按股票客户端成交页签输出表格。"""
    headers = [
        ("成交时间", 10, "text"),
        ("资金账号", 12, "text"),
        ("证券代码", 10, "text"),
        ("证券名称", 10, "text"),
        ("买卖标记", 8, "text"),
        ("成交价格", 10, "price"),
        ("成交数量", 10, "num"),
        ("成交金额", 10, "num"),
        ("成交编号", 10, "text"),
        ("合同编号", 12, "text"),
        ("账号名称", 10, "text"),
        ("投资备注", 10, "text"),
        ("策略名称", 10, "text"),
    ]
    rows: list[list[str]] = []
    for trade in trades:
        native = trade.native_trade
        rows.append(
            [
                _format_xt_time(trade.traded_time),
                trade.account_id,
                _normalize_stock_code_for_terminal(trade.code),
                str(_get_native_attr(native, "instrument_name", "stock_name", default="")),
                _resolve_stock_side(trade.offset_flag, trade.direction),
                _format_price_or_integer(trade.traded_price),
                _format_number(trade.traded_volume),
                _format_number(trade.traded_amount),
                trade.traded_id,
                str(_get_native_attr(native, "order_sysid", default="")),
                str(_get_native_attr(native, "account_name", default="")),
                str(_get_native_attr(native, "order_remark", default="")),
                str(_get_native_attr(native, "strategy_name", default="")),
            ]
        )
    return _format_table(headers, rows)


def _format_stock_order_table_lines(orders: list[XtQuantOrderSnapshot]) -> list[str]:
    """按股票客户端委托页签输出表格。"""
    headers = [
        ("资金账号", 12, "text"),
        ("委托时间", 10, "text"),
        ("证券代码", 10, "text"),
        ("证券名称", 10, "text"),
        ("买卖标记", 8, "text"),
        ("委托状态", 8, "text"),
        ("委托量", 10, "num"),
        ("成交数量", 10, "num"),
        ("已撤数量", 10, "num"),
        ("委托价格", 10, "price"),
        ("成交均价", 10, "price"),
        ("冻结金额", 10, "num"),
        ("合同编号", 12, "text"),
        ("废单原因", 10, "text"),
        ("投资备注", 10, "text"),
        ("策略名称", 10, "text"),
    ]
    rows: list[list[str]] = []
    for order in orders:
        native = order.native_order
        rows.append(
            [
                order.account_id,
                _format_xt_time(order.order_time),
                _normalize_stock_code_for_terminal(order.code),
                str(_get_native_attr(native, "instrument_name", "stock_name", default="")),
                _resolve_stock_side(order.offset_flag, order.direction),
                _resolve_order_status_text(order.order_status),
                _format_number(order.order_volume),
                _format_number(order.traded_volume),
                _format_number(_resolve_stock_canceled_volume(order)),
                _format_price_or_integer(order.price),
                _format_price_or_integer(order.traded_price),
                _format_number(_coerce_float(_get_native_attr(native, "frozen_cash"), 0.0)),
                str(_get_native_attr(native, "order_sysid", default="")),
                _resolve_stock_reject_reason(order),
                str(_get_native_attr(native, "order_remark", default="")),
                str(_get_native_attr(native, "strategy_name", default="")),
            ]
        )
    return _format_table(headers, rows)


@dataclass(slots=True)
class FuturesPositionDisplayRow:
    """期货持仓终端展示行。

    字段设计直接对齐终端截图中的列，目标是让诊断输出和柜台页面
    使用同一套业务语义，减少“字段看起来对不上”的理解成本。
    """
    product_name: str
    contract_code: str
    direction: str
    volume: float
    today_volume: float
    close_volume: float
    floating_pnl: float
    position_pnl: float
    last_price: float
    open_price: float
    position_cost: float
    open_cost: float
    previous_settlement_price: float
    market_value: float
    account_id: str
    today_flag: str = ""
    occupied_margin: float = 0.0
    hedge_flag: str = ""
    futures_company: str = ""
    account_name: str = ""


def _build_futures_position_statistics_rows(
    statistics: list[XtQuantPositionStatisticsSnapshot],
) -> list[FuturesPositionDisplayRow]:
    """构造“持仓统计”表格行。

    数据源要求：
      - 仅接收 XtQuant 专用的期货持仓统计对象；
      - 严禁用持仓明细做手工汇总，避免股票/期货口径混乱。
    """
    rows: list[FuturesPositionDisplayRow] = []
    for item in statistics:
        native = item.native_statistics
        rows.append(
            FuturesPositionDisplayRow(
                product_name=_resolve_futures_product_name(native, contract_code=item.instrument_id),
                contract_code=str(_get_native_attr(native, "instrument_id", default=item.instrument_id)),
                direction=_resolve_statistics_direction(item),
                volume=_coerce_float(_get_native_attr(native, "position"), 0.0),
                today_volume=_coerce_float(_get_native_attr(native, "today_position"), 0.0),
                close_volume=_coerce_float(_get_native_attr(native, "can_close_vol"), 0.0),
                floating_pnl=_coerce_float(_get_native_attr(native, "float_profit"), 0.0),
                position_pnl=_coerce_float(_get_native_attr(native, "position_profit"), 0.0),
                last_price=_coerce_float(_get_native_attr(native, "last_price"), 0.0),
                open_price=_coerce_float(_get_native_attr(native, "open_price"), 0.0),
                position_cost=_coerce_float(_get_native_attr(native, "position_cost"), 0.0),
                open_cost=_coerce_float(_get_native_attr(native, "open_cost"), 0.0),
                previous_settlement_price=0.0,
                market_value=_coerce_float(_get_native_attr(native, "instrument_value"), 0.0),
                account_id=str(_get_native_attr(native, "account_id", default="")),
                today_flag="是" if _coerce_float(_get_native_attr(native, "today_position"), 0.0) > 0 else "",
                occupied_margin=_coerce_float(_get_native_attr(native, "used_margin"), 0.0),
                hedge_flag=_resolve_hedge_flag(native),
                futures_company="",
                account_name="",
            )
        )
    return rows


def _build_futures_position_detail_rows(
    positions: list[XtQuantPositionSnapshot],
    statistics_rows: list[FuturesPositionDisplayRow] | None = None,
) -> list[FuturesPositionDisplayRow]:
    """构造“持仓明细”表格行。

    回退策略：
      - 明细原始对象里有时拿不到品种名称；
      - 若统计表已拿到同一合约代码的品种名称，则复用统计结果补齐明细展示；
      - 该回退仅用于终端展示，不改变底层查询数据。
    """
    statistics_name_map = {
        _normalize_contract_code_for_terminal(row.contract_code): row.product_name
        for row in (statistics_rows or [])
        if row.product_name
    }
    return [_build_futures_position_row(pos, statistics_name_map=statistics_name_map) for pos in positions]


def _build_futures_position_row(
    pos: XtQuantPositionSnapshot,
    statistics_name_map: dict[str, str] | None = None,
) -> FuturesPositionDisplayRow:
    """把单条原始持仓转换为终端表格行。

    字段提取策略：
      - 优先从 `native_position` 读取柜台原始字段，最大程度贴近图片内容；
      - 若原始字段缺失，再回退到快照中已有的标准化字段；
      - 所有数值字段统一做安全转换，避免因为字段缺失导致展示中断。
    """
    native = pos.native_position
    volume = _coerce_float(_get_native_attr(native, "volume"), pos.volume)
    last_price = _coerce_float(_get_native_attr(native, "last_price"), 0.0)
    open_price = _coerce_float(_get_native_attr(native, "open_price"), pos.open_price)
    avg_price = _coerce_float(_get_native_attr(native, "avg_price"), 0.0)
    market_value = _coerce_float(_get_native_attr(native, "market_value"), 0.0)
    direction_sign = 1.0 if _resolve_position_direction(pos) == "多" else -1.0
    contract_multiplier = _infer_futures_contract_multiplier(
        market_value=market_value,
        last_price=last_price,
        volume=volume,
    )
    raw_float_profit = _coerce_float(_get_native_attr(native, "float_profit"), 0.0)
    raw_position_profit = _coerce_float(_get_native_attr(native, "position_profit"), 0.0)
    raw_position_cost = _coerce_float(_get_native_attr(native, "position_cost"), 0.0)
    raw_open_cost = _coerce_float(_get_native_attr(native, "open_cost"), 0.0)
    raw_previous_settlement_price = _coerce_float(_get_native_attr(native, "pre_settle_price"), 0.0)

    derived_float_profit = raw_float_profit
    if abs(derived_float_profit) <= 1e-12 and contract_multiplier > 0 and volume > 0 and last_price > 0 and open_price > 0:
        derived_float_profit = (last_price - open_price) * contract_multiplier * volume * direction_sign

    derived_position_cost = raw_position_cost
    if abs(derived_position_cost) <= 1e-12 and contract_multiplier > 0 and volume > 0:
        cost_price = avg_price if avg_price > 0 else open_price
        if cost_price > 0:
            derived_position_cost = cost_price * contract_multiplier * volume

    derived_open_cost = raw_open_cost
    if abs(derived_open_cost) <= 1e-12 and contract_multiplier > 0 and volume > 0 and open_price > 0:
        derived_open_cost = open_price * contract_multiplier * volume

    derived_previous_settlement_price = raw_previous_settlement_price
    if (
        abs(derived_previous_settlement_price) <= 1e-12
        and abs(raw_position_profit) > 1e-12
        and contract_multiplier > 0
        and volume > 0
        and last_price > 0
    ):
        derived_previous_settlement_price = last_price - raw_position_profit / (contract_multiplier * volume * direction_sign)

    product_name = _resolve_futures_product_name(native, contract_code=pos.code)
    if not product_name and statistics_name_map:
        product_name = statistics_name_map.get(_normalize_contract_code_for_terminal(pos.code), "")
        if product_name:
            logger.info("fill futures detail product name from statistics: contract_code=%s, product_name=%s", pos.code, product_name)

    row = FuturesPositionDisplayRow(
        product_name=product_name,
        contract_code=pos.code,
        direction=_resolve_position_direction(pos),
        volume=volume,
        today_volume=_coerce_float(_get_native_attr(native, "today_volume"), 0.0),
        close_volume=_coerce_float(_get_native_attr(native, "close_volume"), 0.0),
        floating_pnl=derived_float_profit,
        position_pnl=raw_position_profit,
        last_price=last_price,
        open_price=open_price,
        position_cost=derived_position_cost,
        open_cost=derived_open_cost,
        previous_settlement_price=derived_previous_settlement_price,
        market_value=market_value,
        account_id=str(_get_native_attr(native, "account_id", default="")),
        today_flag=_resolve_today_flag(native),
        occupied_margin=_coerce_float(_get_native_attr(native, "margin", "used_margin", "occupy_margin"), 0.0),
        hedge_flag=str(_get_native_attr(native, "hedge_flag", default="")),
        futures_company="",
        account_name="",
    )
    return row


def _resolve_futures_product_name(native: Any, contract_code: str = "") -> str:
    """统一解析期货品种名称。

    背景：
      - 期货“持仓统计”和“持仓明细”的原始对象字段名并不完全一致；
      - 若两处分别手写字段别名，容易出现统计有值、明细为空的情况。

    处理策略：
      - 优先兼容 QMT 期货常见字段名；
      - 若最终仍为空，则记录一条带合约代码的告警，方便继续补字段映射。
    """
    product_name = str(
        _get_native_attr(
            native,
            "ft_product_name",
            "product_name",
            "instrument_name",
            default="",
        )
    ).strip()
    if product_name:
        return product_name
    logger.warning("resolve futures product name failed: contract_code=%s", contract_code)
    return ""


def _format_futures_position_table_lines(rows: list[FuturesPositionDisplayRow]) -> list[str]:
    """兼容旧调用，默认按明细表头输出。"""
    return _format_futures_position_detail_table_lines(rows)


def _format_futures_position_summary_table_lines(rows: list[FuturesPositionDisplayRow]) -> list[str]:
    """格式化“持仓合计”表格。

    表头直接对齐终端“持仓合计”页签，不复用明细表头，避免两张表语义混淆。
    """
    headers = [
        ("品种名称", 8, "text"),
        ("合约代码", 10, "text"),
        ("多空", 4, "text"),
        ("持仓量", 8, "num"),
        ("今仓", 4, "text"),
        ("开仓价", 10, "price"),
        ("浮动盈亏", 10, "num"),
        ("市值", 10, "num"),
        ("占用保证金", 12, "num"),
        ("投保", 4, "text"),
        ("账号", 12, "text"),
        ("期货公司", 10, "text"),
        ("账号名称", 10, "text"),
    ]
    rows_data: list[list[str]] = []
    for row in rows:
        values = [
            row.product_name,
            _normalize_contract_code_for_terminal(row.contract_code),
            row.direction,
            _format_futures_quantity(row.volume),
            row.today_flag,
            _format_price_or_integer(row.open_price),
            _format_futures_summary_amount(row.floating_pnl),
            _format_futures_summary_amount(row.market_value),
            _format_futures_summary_amount(row.occupied_margin),
            row.hedge_flag,
            row.account_id,
            row.futures_company,
            row.account_name,
        ]
        rows_data.append(values)
    return _format_table(headers, rows_data, drop_empty_titles={"期货公司", "账号名称"})


def _format_futures_position_detail_table_lines(rows: list[FuturesPositionDisplayRow]) -> list[str]:
    """格式化“持仓明细”表格。"""
    headers = [
        ("品种名称", 8, "text"),
        ("合约代码", 10, "text"),
        ("多空", 4, "text"),
        ("持仓量", 8, "num"),
        ("平仓量", 8, "num"),
        ("浮动盈亏", 10, "num"),
        ("持仓盈亏", 10, "num"),
        ("最新价", 10, "price"),
        ("开仓价", 10, "price"),
        ("持仓成本", 10, "num"),
        ("开仓成本", 10, "num"),
        ("昨结算", 10, "price"),
        ("市值", 10, "num"),
        ("账号", 12, "text"),
    ]
    rows_data: list[list[str]] = []
    for row in rows:
        values = [
            row.product_name,
            _normalize_contract_code_for_terminal(row.contract_code),
            row.direction,
            _format_futures_quantity(row.volume),
            _format_futures_quantity(row.close_volume),
            _format_futures_detail_amount(row.floating_pnl),
            _format_futures_detail_amount(row.position_pnl),
            _format_price(row.last_price),
            _format_futures_cost_price(row.open_price),
            _format_futures_detail_amount(row.position_cost),
            _format_futures_detail_amount(row.open_cost),
            _format_price(row.previous_settlement_price),
            _format_futures_detail_amount(row.market_value),
            row.account_id,
        ]
        rows_data.append(values)
    return _format_table(headers, rows_data)


def _format_table_row(values: list[str], headers: list[tuple[str, int, str]]) -> str:
    columns: list[str] = []
    for value, (_title, width, kind) in zip(values, headers):
        text = str(value)
        if kind == "text":
            columns.append(text.ljust(width))
        else:
            columns.append(text.rjust(width))
    return " | ".join(columns)


def _format_key_value_lines(items: list[tuple[str, Any]], columns: int = 3) -> list[str]:
    """把资产类字段格式化为稳定的多列键值对。

    输入是已经按业务优先级排序的 `(字段名, 展示值)` 列表，输出是终端文本行。
    这样做的原因是股票账号总览字段多、部分字段由柜台按账户类型决定是否返回；
    多列键值对能避免宽表在窄终端折行后出现表头和值错位。
    """
    normalized_items = [(title, str(value)) for title, value in items]
    if not normalized_items:
        return []

    title_width = max(len(title) for title, _value in normalized_items)
    cell_texts = [f"{title.ljust(title_width)}: {value}" for title, value in normalized_items]
    cell_width = max(len(text) for text in cell_texts) + 2
    row_size = max(int(columns), 1)

    lines: list[str] = []
    for start in range(0, len(cell_texts), row_size):
        row = cell_texts[start : start + row_size]
        lines.append("".join(text.ljust(cell_width) for text in row).rstrip())
    return lines


def _format_table(
    headers: list[tuple[str, int, str]],
    rows: list[list[str]],
    drop_empty_titles: set[str] | None = None,
) -> list[str]:
    """按内容自动扩宽表格列，并在需要时移除整列为空的列。

    设计说明：
      - 终端展示宽度应以真实内容为准，而不是固定宽度常量；
      - 对于“期货公司/账号名称”这类可选列，如果整列都为空，直接移除，
        避免展示大量空白列影响阅读。
    """
    visible_indexes: list[int] = []
    for index, (title, _width, _kind) in enumerate(headers):
        if drop_empty_titles and title in drop_empty_titles:
            if all(not str(row[index] if index < len(row) else "").strip() for row in rows):
                continue
        visible_indexes.append(index)

    visible_headers: list[tuple[str, int, str]] = []
    for index in visible_indexes:
        title, _width, kind = headers[index]
        auto_width = len(title)
        for row in rows:
            if index < len(row):
                auto_width = max(auto_width, len(str(row[index])))
        visible_headers.append((title, auto_width, kind))

    lines = [_format_table_row([headers[index][0] for index in visible_indexes], visible_headers)]
    for row in rows:
        lines.append(
            _format_table_row(
                [str(row[index]) if index < len(row) else "" for index in visible_indexes],
                visible_headers,
            )
        )
    return lines


def _resolve_position_direction(pos: XtQuantPositionSnapshot) -> str:
    native = pos.native_position
    raw_value = _get_native_attr(native, "direction")
    mapping = {
        1: "多",
        2: "空",
        48: "多",
        49: "空",
        "1": "多",
        "2": "空",
        "BUY": "多",
        "SELL": "空",
        "LONG": "多",
        "SHORT": "空",
        "多": "多",
        "空": "空",
    }
    if raw_value in mapping:
        return mapping[raw_value]
    normalized = str(raw_value or "").strip().upper()
    if normalized in mapping:
        return mapping[normalized]
    return "多" if pos.volume >= 0 else "空"


def _resolve_statistics_direction(item: XtQuantPositionStatisticsSnapshot) -> str:
    raw_value = item.direction
    mapping = {
        48: "多",
        49: "空",
        1: "多",
        2: "空",
        "48": "多",
        "49": "空",
        "1": "多",
        "2": "空",
        "LONG": "多",
        "SHORT": "空",
        "多": "多",
        "空": "空",
    }
    if raw_value in mapping:
        return mapping[raw_value]
    normalized = str(raw_value or "").strip().upper()
    return mapping.get(normalized, "")


def _resolve_hedge_flag(native: Any) -> str:
    raw_value = _get_native_attr(native, "hedge_flag")
    mapping = {
        0: "投机",
        1: "套利",
        2: "套保",
        49: "投机",
        50: "套利",
        51: "套保",
        "0": "投机",
        "1": "套利",
        "2": "套保",
        "49": "投机",
        "50": "套利",
        "51": "套保",
        "SPECULATION": "投机",
        "ARBITRAGE": "套利",
        "HEDGE": "套保",
        "投机": "投机",
        "套利": "套利",
        "套保": "套保",
    }
    if raw_value in mapping:
        return mapping[raw_value]
    normalized = str(raw_value or "").strip().upper()
    return mapping.get(normalized, str(raw_value or ""))


def _resolve_trade_side(trade: XtQuantTradeSnapshot) -> str:
    mapping = {
        23: "买入",
        24: "卖出",
        "23": "买入",
        "24": "卖出",
        "BUY": "买入",
        "SELL": "卖出",
    }
    native = trade.native_trade
    raw_value = _get_native_attr(native, "order_type", default=None)
    if raw_value in mapping:
        return mapping[raw_value]
    normalized = str(raw_value or "").strip().upper()
    return mapping.get(normalized, "")


def _resolve_stock_side(offset_flag: Any, direction: Any) -> str:
    """解析股票成交/委托的买卖标记。

    设计说明：
      - 股票买卖优先使用官方字段 `offset_flag`；
      - 若柜台未返回该字段，再退回 `direction`，避免页面完全空白。
    """
    mapping = {
        23: "买入",
        24: "卖出",
        "23": "买入",
        "24": "卖出",
        "BUY": "买入",
        "SELL": "卖出",
        "买入": "买入",
        "卖出": "卖出",
    }
    if offset_flag in mapping:
        return mapping[offset_flag]
    normalized_offset = str(offset_flag or "").strip().upper()
    if normalized_offset in mapping:
        return mapping[normalized_offset]
    if direction in mapping:
        return mapping[direction]
    normalized_direction = str(direction or "").strip().upper()
    return mapping.get(normalized_direction, "")


def _resolve_order_side(order: XtQuantOrderSnapshot) -> str:
    mapping = {
        23: "买入",
        24: "卖出",
        "23": "买入",
        "24": "卖出",
        "BUY": "买入",
        "SELL": "卖出",
    }
    native = order.native_order
    raw_value = _get_native_attr(native, "order_type", default=None)
    if raw_value in mapping:
        return mapping[raw_value]
    normalized = str(raw_value or "").strip().upper()
    return mapping.get(normalized, "")


def _resolve_offset_flag_text(raw_value: Any, *, is_futures: bool) -> str:
    if not is_futures:
        return ""
    mapping = {
        48: "开仓",
        49: "平仓",
        50: "强平",
        51: "平今",
        52: "平昨",
        "48": "开仓",
        "49": "平仓",
        "50": "强平",
        "51": "平今",
        "52": "平昨",
        "OPEN": "开仓",
        "CLOSE": "平仓",
        "FORCECLOSE": "强平",
        "CLOSETODAY": "平今",
        "CLOSEYESTERDAY": "平昨",
        "开仓": "开仓",
        "平仓": "平仓",
        "强平": "强平",
        "平今": "平今",
        "平昨": "平昨",
    }
    if raw_value in mapping:
        return mapping[raw_value]
    normalized = str(raw_value or "").strip().upper()
    return mapping.get(normalized, str(raw_value or ""))


def _resolve_order_status_text(raw_value: Any) -> str:
    mapping = {
        48: "未报",
        49: "待报",
        50: "已报",
        51: "已报待撤",
        52: "部成待撤",
        53: "部撤",
        54: "已撤",
        55: "部成",
        56: "已成",
        57: "废单",
        "48": "未报",
        "49": "待报",
        "50": "已报",
        "51": "已报待撤",
        "52": "部成待撤",
        "53": "部撤",
        "54": "已撤",
        "55": "部成",
        "56": "已成",
        "57": "废单",
    }
    if raw_value in mapping:
        return mapping[raw_value]
    return str(raw_value or "")


def _format_xt_time(value: Any) -> str:
    """把柜台时间格式统一成 QMT 页面常见的 `HH:MM:SS`。

    兼容输入：
      - `20260423220344` 这类完整日期时间
      - `220344` / `022344` 这类纯时间数字
      - `2026-04-23 22:03:44` 这类带分隔符字符串
      - Unix 秒 / 毫秒时间戳

    设计目标：
      - 终端输出只保留时分秒，尽量贴近 QMT 列表页显示；
      - 输入格式不可靠时优先做稳妥归一化，而不是原样打印长时间串。
    """
    if value is None:
        return ""

    if isinstance(value, datetime):
        return value.strftime("%H:%M:%S")

    text = str(value).strip()
    if not text:
        return ""

    # 先处理标准日期时间字符串，如 2026-04-23 22:03:44
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).strftime("%H:%M:%S")
        except ValueError:
            continue

    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return text

    # 处理 unix 时间戳（秒 / 毫秒）
    if len(digits) in {10, 13}:
        try:
            timestamp = int(digits)
            if len(digits) == 13:
                timestamp = timestamp / 1000
            return datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
        except (OSError, OverflowError, ValueError):
            pass

    # 处理 YYYYMMDDHHMMSS / YYYYMMDDHHMMSSmmm
    if len(digits) >= 14:
        return f"{digits[8:10]}:{digits[10:12]}:{digits[12:14]}"

    # 处理 HHMMSS / HMMSS 等纯时间数字，只取最后 6 位并左补零
    if len(digits) <= 6:
        padded = digits.zfill(6)
        return f"{padded[0:2]}:{padded[2:4]}:{padded[4:6]}"

    # 兜底：对更长但不足 14 位的数字串，仍取最后 6 位做时间展示
    tail = digits[-6:].zfill(6)
    return f"{tail[0:2]}:{tail[2:4]}:{tail[4:6]}"


def _format_xt_date(value: Any) -> str:
    """把柜台日期字段统一成 `YYYYMMDD`。

    股票总览页截图展示的是纯日期，因此这里不复用时分秒格式。
    """
    if value is None:
        return ""
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) >= 8:
        return digits[:8]
    return str(value)


def _resolve_today_flag(native: Any) -> str:
    raw_value = _get_native_attr(native, "today_flag", "is_today_position", "today_position_flag")
    mapping = {
        True: "是",
        False: "",
        1: "是",
        0: "",
        "1": "是",
        "0": "",
        "Y": "是",
        "N": "",
        "YES": "是",
        "NO": "",
        "是": "是",
        "否": "",
    }
    if raw_value in mapping:
        return mapping[raw_value]
    normalized = str(raw_value or "").strip().upper()
    return mapping.get(normalized, "")


def _resolve_stock_canceled_volume(order: XtQuantOrderSnapshot) -> float:
    """计算股票委托的已撤数量。

    规则：
      - 仅在已撤/部撤/废单这类结束状态下计算剩余未成交量；
      - 其余状态返回 0，避免把未完成委托误显示成已撤。
    """
    canceled_statuses = {53, 54, 57, "53", "54", "57"}
    if order.order_status not in canceled_statuses:
        return 0.0
    return max(float(order.order_volume or 0.0) - float(order.traded_volume or 0.0), 0.0)


def _resolve_stock_reject_reason(order: XtQuantOrderSnapshot) -> str:
    """提取股票委托的废单原因。

    只在废单状态下展示 `status_msg`，其余状态保持空白，贴近客户端表头语义。
    """
    if str(order.order_status) != "57":
        return ""
    return order.status_msg


def _normalize_contract_code_for_terminal(code: str) -> str:
    normalized = str(code or "").strip().upper()
    if "." not in normalized:
        return normalized
    symbol, _exchange = normalized.split(".", 1)
    return symbol


def _normalize_stock_code_for_terminal(code: str) -> str:
    normalized = str(code or "").strip().upper()
    if "." not in normalized:
        return normalized
    symbol, _exchange = normalized.split(".", 1)
    return symbol


def _infer_futures_contract_multiplier(*, market_value: float, last_price: float, volume: float) -> float:
    if abs(market_value) <= 1e-12 or abs(last_price) <= 1e-12 or abs(volume) <= 1e-12:
        return 0.0
    return abs(market_value) / (abs(last_price) * abs(volume))


def _resolve_stock_market_text(code: str) -> str:
    normalized = str(code or "").strip().upper()
    if normalized.endswith(".SZ"):
        return "深A"
    if normalized.endswith(".SH"):
        return "沪A"
    if normalized.endswith(".BJ"):
        return "北A"
    return ""


def _get_native_attr(native: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if native is not None and hasattr(native, name):
            value = getattr(native, name)
            if value is not None:
                return value
    return default


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _format_number(value: float) -> str:
    return f"{value:.1f}"


def _format_money(value: float) -> str:
    return f"{value:.2f}"


def _format_price(value: float) -> str:
    return f"{value:.3f}"


def _format_price_or_integer(value: float) -> str:
    if float(value).is_integer():
        return f"{value:.0f}"
    return f"{value:.3f}"


def _format_futures_quantity(value: float) -> str:
    if float(value).is_integer():
        return f"{value:.0f}"
    return f"{value:.3f}"


def _format_futures_summary_amount(value: float) -> str:
    return f"{value:.2f}"


def _format_futures_detail_amount(value: float) -> str:
    return f"{value:.1f}"


def _format_futures_cost_price(value: float) -> str:
    return f"{value:.1f}"


def _format_futures_trade_price(value: float) -> str:
    if float(value).is_integer():
        return f"{value:.0f}"
    return f"{value:.3f}"


def _format_futures_trade_amount(value: float) -> str:
    if float(value).is_integer():
        return f"{value:.0f}"
    return f"{value:.2f}"


def _format_futures_order_price(value: float) -> str:
    if abs(float(value)) <= 1e-12:
        return "0"
    if float(value).is_integer():
        return f"{value:.0f}"
    return f"{value:.3f}"
