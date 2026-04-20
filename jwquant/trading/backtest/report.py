"""
回测报告渲染。
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _sanitize_filename_part(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return "unknown"
    text = text.replace(" ", "_")
    return re.sub(r'[\\/:*?"<>|]+', "_", text)


def _normalize_report_date(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return "unknown"

    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if match:
        return match.group(0).replace("-", "")

    match = re.search(r"\d{8}", text)
    if match:
        return match.group(0)

    return _sanitize_filename_part(text)


def build_backtest_report_filename(strategy_name: Any, start_date: Any, end_date: Any) -> str:
    strategy_label = _sanitize_filename_part(strategy_name)
    start_label = _normalize_report_date(start_date)
    end_label = _normalize_report_date(end_date)
    return f"{strategy_label}_{start_label}_{end_label}.html"


def resolve_unique_report_path(output_path: str | Path) -> Path:
    path = Path(output_path)
    if not path.exists():
        return path

    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem}（{counter}）{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def build_backtest_report_output_path(
    output_dir: str | Path,
    strategy_name: Any,
    start_date: Any,
    end_date: Any,
) -> Path:
    filename = build_backtest_report_filename(strategy_name, start_date, end_date)
    return resolve_unique_report_path(Path(output_dir) / filename)


def _build_equity_svg(equity_records: list[dict[str, Any]]) -> str:
    if not equity_records:
        return "<div class='empty'>无权益曲线数据</div>"
    values = [float(item["equity"]) for item in equity_records]
    if len(values) == 1:
        values = [values[0], values[0]]
    min_v = min(values)
    max_v = max(values)
    span = max(max_v - min_v, 1e-9)
    width = 860
    height = 260
    points = []
    for index, value in enumerate(values):
        x = 20 + (width - 40) * index / (len(values) - 1)
        y = 20 + (height - 40) * (1 - (value - min_v) / span)
        points.append(f"{x:.2f},{y:.2f}")
    polyline = " ".join(points)
    return (
        f"<svg viewBox='0 0 {width} {height}' class='equity-chart'>"
        f"<polyline fill='none' stroke='#0f766e' stroke-width='3' points='{polyline}' />"
        "</svg>"
    )


def _normalize_chart_mode(chart_mode: str | None) -> str:
    normalized = str(chart_mode or "simple").strip().lower()
    if normalized not in {"simple", "full"}:
        return "simple"
    return normalized


def _select_chart_dataset(report: dict[str, Any]) -> tuple[pd.DataFrame, str | None, str]:
    market_data = pd.DataFrame(report.get("market_data", []))
    if market_data.empty:
        return pd.DataFrame(), None, "无价格数据"

    market_data = market_data.copy()
    market_data["dt"] = pd.to_datetime(market_data["dt"])
    market_data = market_data.sort_values(["dt", "code"]).reset_index(drop=True)
    unique_codes = [str(code) for code in market_data["code"].dropna().astype(str).unique().tolist()]
    if not unique_codes:
        return pd.DataFrame(), None, "无价格数据"

    chart_code = unique_codes[0]
    note = f"展示标的: {chart_code}"
    if len(unique_codes) > 1:
        note = f"多标的场景当前仅展示首个标的: {chart_code}"

    code_data = market_data[market_data["code"].astype(str) == chart_code].copy()
    return code_data.reset_index(drop=True), chart_code, note


def _build_trade_marker_map(trade_records: list[dict[str, Any]], chart_code: str | None) -> dict[pd.Timestamp, list[dict[str, Any]]]:
    if chart_code is None:
        return {}
    marker_map: dict[pd.Timestamp, list[dict[str, Any]]] = {}
    for trade in trade_records:
        if str(trade.get("code", "")) != chart_code:
            continue
        trade_dt = trade.get("date") or trade.get("dt")
        if trade_dt is None:
            continue
        dt = pd.Timestamp(trade_dt)
        marker_map.setdefault(dt, []).append(trade)
    return marker_map


def _build_signal_marker_records(signal_records: list[dict[str, Any]], chart_code: str | None) -> list[dict[str, Any]]:
    if chart_code is None:
        return []
    markers: list[dict[str, Any]] = []
    for record in signal_records:
        if str(record.get("code", "")) != chart_code:
            continue
        signal_dt = record.get("signal_dt")
        signal_price = record.get("signal_price")
        if signal_dt is None or signal_price is None:
            continue
        markers.append(
            {
                "dt": pd.Timestamp(signal_dt),
                "price": float(signal_price),
                "signal_type": str(record.get("signal_type", "")),
                "status": str(record.get("status", "")).lower(),
                "reason_detail": str(record.get("reason_detail", "")),
                "reason_source": str(record.get("reason_source", "")),
            }
        )
    return markers


def _build_holding_intervals(trade_records: list[dict[str, Any]], chart_code: str | None) -> list[dict[str, Any]]:
    if chart_code is None:
        return []
    code_trades = [
        trade for trade in trade_records
        if str(trade.get("code", "")) == chart_code
    ]
    code_trades = sorted(
        code_trades,
        key=lambda item: pd.Timestamp(item.get("date") or item.get("dt")),
    )
    intervals: list[dict[str, Any]] = []
    open_trade: dict[str, Any] | None = None
    for trade in code_trades:
        offset = str(trade.get("offset", ""))
        if offset == "open_long" and open_trade is None:
            open_trade = trade
        elif offset == "close_long" and open_trade is not None:
            intervals.append(
                {
                    "start_dt": pd.Timestamp(open_trade.get("date") or open_trade.get("dt")),
                    "end_dt": pd.Timestamp(trade.get("date") or trade.get("dt")),
                }
            )
            open_trade = None
    if open_trade is not None:
        intervals.append(
            {
                "start_dt": pd.Timestamp(open_trade.get("date") or open_trade.get("dt")),
                "end_dt": None,
            }
        )
    return intervals


def _build_position_line_svg(position_records: list[dict[str, Any]], chart_code: str | None) -> str:
    if chart_code is None:
        return "<div class='empty'>无仓位变化数据</div>"
    df = pd.DataFrame(position_records)
    if df.empty:
        return "<div class='empty'>无仓位变化数据</div>"
    df = df[df["code"].astype(str) == chart_code].copy()
    if df.empty:
        return "<div class='empty'>无仓位变化数据</div>"
    df["dt"] = pd.to_datetime(df["dt"])
    df = df.sort_values("dt").drop_duplicates(subset=["dt"], keep="last").reset_index(drop=True)
    width = max(860, len(df) * 6 + 40)
    height = 160
    values = df["quantity"].astype(float).tolist()
    min_v = min(values)
    max_v = max(values)
    span = max(max_v - min_v, 1.0)
    points: list[str] = []
    for index, value in enumerate(values):
        x = 20 + (width - 40) * index / max(len(values) - 1, 1)
        y = 20 + (height - 40) * (1 - (value - min_v) / span)
        points.append(f"{x:.2f},{y:.2f}")
    return (
        f"<div class='chart-scroll'><svg viewBox='0 0 {width} {height}' class='position-chart'>"
        f"<polyline fill='none' stroke='#0f766e' stroke-width='2.5' points='{' '.join(points)}' />"
        "</svg></div>"
    )


def _signal_marker_style(signal: dict[str, Any]) -> tuple[str, str]:
    signal_type = str(signal["signal_type"]).lower()
    status = str(signal["status"]).lower()
    reason_source = str(signal.get("reason_source", "")).lower()
    if status == "filled":
        color = "#2563eb"
    elif reason_source == "stock_price_guard":
        color = "#f59e0b"
    elif reason_source == "no_next_bar":
        color = "#6b7280"
    else:
        color = "#8b5cf6"
    label = "SB" if signal_type == "buy" else "SS"
    return color, label


def _build_simple_price_svg(
    price_data: pd.DataFrame,
    trade_records: list[dict[str, Any]],
    signal_records: list[dict[str, Any]],
    chart_code: str | None,
) -> str:
    if price_data.empty:
        return "<div class='empty'>无价格图数据</div>"

    width = max(860, len(price_data) * 6 + 40)
    height = 320
    closes = price_data["close"].astype(float).tolist()
    min_v = min(closes)
    max_v = max(closes)
    span = max(max_v - min_v, 1e-9)
    points: list[str] = []
    x_positions: dict[pd.Timestamp, float] = {}
    for index, row in price_data.iterrows():
        x = 20 + (width - 40) * index / max(len(price_data) - 1, 1)
        y = 20 + (height - 40) * (1 - (float(row["close"]) - min_v) / span)
        dt = pd.Timestamp(row["dt"])
        x_positions[dt] = x
        points.append(f"{x:.2f},{y:.2f}")

    marker_map = _build_trade_marker_map(trade_records, chart_code)
    signal_markers = _build_signal_marker_records(signal_records, chart_code)
    marker_svg: list[str] = []
    holding_svg: list[str] = []
    holding_intervals = _build_holding_intervals(trade_records, chart_code)
    for interval in holding_intervals:
        start_dt = interval["start_dt"]
        end_dt = interval["end_dt"] or price_data["dt"].iloc[-1]
        if start_dt not in x_positions or pd.Timestamp(end_dt) not in x_positions:
            continue
        x1 = x_positions[start_dt]
        x2 = x_positions[pd.Timestamp(end_dt)]
        width_rect = max(x2 - x1, 2.0)
        holding_svg.append(
            f"<rect x='{x1:.2f}' y='20' width='{width_rect:.2f}' height='{height - 40:.2f}' fill='rgba(37,99,235,0.08)' />"
        )
    for dt, trades in marker_map.items():
        if dt not in x_positions:
            continue
        for trade in trades:
            price = float(trade.get("price", 0.0))
            y = 20 + (height - 40) * (1 - (price - min_v) / span)
            direction = str(trade.get("direction", "")).lower()
            color = "#16a34a" if direction == "buy" else "#dc2626"
            label = "B" if direction == "buy" else "S"
            marker_svg.append(
                f"<g><title>{html.escape(f'成交 {label}: 日期={dt}, 价格={price:.4f}, 数量={trade.get("quantity", "")}, offset={trade.get("offset", "")}')}</title>"
                f"<circle cx='{x_positions[dt]:.2f}' cy='{y:.2f}' r='5' fill='{color}' />"
                f"<text x='{x_positions[dt]:.2f}' y='{y - 10:.2f}' text-anchor='middle' class='marker-label'>{label}</text></g>"
            )

    for signal in signal_markers:
        dt = signal["dt"]
        if dt not in x_positions:
            continue
        price = float(signal["price"])
        y = 20 + (height - 40) * (1 - (price - min_v) / span)
        color, label = _signal_marker_style(signal)
        reason_detail = signal["reason_detail"]
        signal_status = str(signal["status"])
        marker_svg.append(
            f"<g><title>{html.escape(f'信号 {label}: 日期={dt}, 价格={price:.4f}, 状态={signal_status}, 原因={reason_detail}')}</title>"
            f"<line x1='{x_positions[dt] - 4:.2f}' y1='{y - 4:.2f}' x2='{x_positions[dt] + 4:.2f}' y2='{y + 4:.2f}' stroke='{color}' stroke-width='2' />"
            f"<line x1='{x_positions[dt] - 4:.2f}' y1='{y + 4:.2f}' x2='{x_positions[dt] + 4:.2f}' y2='{y - 4:.2f}' stroke='{color}' stroke-width='2' />"
            f"<text x='{x_positions[dt]:.2f}' y='{y - 10:.2f}' text-anchor='middle' class='marker-label'>{label}</text></g>"
        )

    return (
        f"<div class='chart-scroll'><svg viewBox='0 0 {width} {height}' class='price-chart'>"
        f"{''.join(holding_svg)}"
        f"<polyline fill='none' stroke='#2563eb' stroke-width='2.5' points='{' '.join(points)}' />"
        f"{''.join(marker_svg)}"
        "</svg></div>"
    )


def _build_full_candlestick_svg(
    price_data: pd.DataFrame,
    trade_records: list[dict[str, Any]],
    signal_records: list[dict[str, Any]],
    chart_code: str | None,
) -> str:
    if price_data.empty:
        return "<div class='empty'>无价格图数据</div>"

    width = max(860, len(price_data) * 8 + 40)
    height = 360
    high_max = float(price_data["high"].astype(float).max())
    low_min = float(price_data["low"].astype(float).min())
    span = max(high_max - low_min, 1e-9)
    candle_width = 4
    x_positions: dict[pd.Timestamp, float] = {}
    candle_svg: list[str] = []
    holding_svg: list[str] = []

    for index, row in price_data.iterrows():
        x = 20 + (width - 40) * index / max(len(price_data) - 1, 1)
        dt = pd.Timestamp(row["dt"])
        x_positions[dt] = x
        open_price = float(row["open"])
        high_price = float(row["high"])
        low_price = float(row["low"])
        close_price = float(row["close"])
        open_y = 20 + (height - 40) * (1 - (open_price - low_min) / span)
        high_y = 20 + (height - 40) * (1 - (high_price - low_min) / span)
        low_y = 20 + (height - 40) * (1 - (low_price - low_min) / span)
        close_y = 20 + (height - 40) * (1 - (close_price - low_min) / span)
        color = "#16a34a" if close_price >= open_price else "#dc2626"
        body_top = min(open_y, close_y)
        body_height = max(abs(close_y - open_y), 1.2)
        candle_svg.append(
            f"<line x1='{x:.2f}' y1='{high_y:.2f}' x2='{x:.2f}' y2='{low_y:.2f}' stroke='{color}' stroke-width='1.2' />"
            f"<rect x='{x - candle_width / 2:.2f}' y='{body_top:.2f}' width='{candle_width:.2f}' height='{body_height:.2f}' fill='{color}' />"
        )

    holding_intervals = _build_holding_intervals(trade_records, chart_code)
    for interval in holding_intervals:
        start_dt = interval["start_dt"]
        end_dt = interval["end_dt"] or price_data["dt"].iloc[-1]
        if start_dt not in x_positions or pd.Timestamp(end_dt) not in x_positions:
            continue
        x1 = x_positions[start_dt]
        x2 = x_positions[pd.Timestamp(end_dt)]
        width_rect = max(x2 - x1, 2.0)
        holding_svg.append(
            f"<rect x='{x1:.2f}' y='20' width='{width_rect:.2f}' height='{height - 40:.2f}' fill='rgba(37,99,235,0.08)' />"
        )

    marker_map = _build_trade_marker_map(trade_records, chart_code)
    marker_svg: list[str] = []
    for dt, trades in marker_map.items():
        if dt not in x_positions:
            continue
        x = x_positions[dt]
        for trade in trades:
            price = float(trade.get("price", 0.0))
            y = 20 + (height - 40) * (1 - (price - low_min) / span)
            direction = str(trade.get("direction", "")).lower()
            color = "#16a34a" if direction == "buy" else "#dc2626"
            if direction == "buy":
                points = f"{x - 5:.2f},{y + 8:.2f} {x + 5:.2f},{y + 8:.2f} {x:.2f},{y - 2:.2f}"
                label_y = y - 8
                label = "B"
            else:
                points = f"{x - 5:.2f},{y - 8:.2f} {x + 5:.2f},{y - 8:.2f} {x:.2f},{y + 2:.2f}"
                label_y = y + 18
                label = "S"
            marker_svg.append(
                f"<g><title>{html.escape(f'成交 {label}: 日期={dt}, 价格={price:.4f}, 数量={trade.get("quantity", "")}, offset={trade.get("offset", "")}')}</title>"
                f"<polygon points='{points}' fill='{color}' />"
                f"<text x='{x:.2f}' y='{label_y:.2f}' text-anchor='middle' class='marker-label'>{label}</text></g>"
            )

    for signal in _build_signal_marker_records(signal_records, chart_code):
        dt = signal["dt"]
        if dt not in x_positions:
            continue
        x = x_positions[dt]
        price = float(signal["price"])
        y = 20 + (height - 40) * (1 - (price - low_min) / span)
        color, label = _signal_marker_style(signal)
        reason_detail = signal["reason_detail"]
        signal_status = str(signal["status"])
        marker_svg.append(
            f"<g><title>{html.escape(f'信号 {label}: 日期={dt}, 价格={price:.4f}, 状态={signal_status}, 原因={reason_detail}')}</title>"
            f"<line x1='{x - 4:.2f}' y1='{y - 4:.2f}' x2='{x + 4:.2f}' y2='{y + 4:.2f}' stroke='{color}' stroke-width='2' />"
            f"<line x1='{x - 4:.2f}' y1='{y + 4:.2f}' x2='{x + 4:.2f}' y2='{y - 4:.2f}' stroke='{color}' stroke-width='2' />"
            f"<text x='{x:.2f}' y='{y - 10:.2f}' text-anchor='middle' class='marker-label'>{label}</text></g>"
        )

    return (
        f"<div class='chart-scroll'><svg viewBox='0 0 {width} {height}' class='price-chart'>"
        f"{''.join(holding_svg)}"
        f"{''.join(candle_svg)}"
        f"{''.join(marker_svg)}"
        "</svg></div>"
    )


def _build_price_chart_html(report: dict[str, Any], chart_mode: str) -> tuple[str, str]:
    price_data, chart_code, chart_note = _select_chart_dataset(report)
    trade_records = report.get("trade_records", [])
    signal_records = report.get("signal_records", [])
    if price_data.empty:
        return "<div class='empty'>当前报告没有可用价格数据</div>", chart_note
    if chart_mode == "full":
        return _build_full_candlestick_svg(price_data, trade_records, signal_records, chart_code), chart_note
    return _build_simple_price_svg(price_data, trade_records, signal_records, chart_code), chart_note


def _build_position_chart_html(report: dict[str, Any]) -> tuple[str, str]:
    _, chart_code, chart_note = _select_chart_dataset(report)
    return _build_position_line_svg(report.get("position_records", []), chart_code), chart_note


def render_backtest_report_html(results: dict[str, Any], chart_mode: str = "simple") -> str:
    report = results.get("report", {})
    summary = report.get("summary", {})
    risk_events = report.get("risk_events", [])
    equity_records = report.get("equity_records", [])
    latest_positions = report.get("latest_positions", {})
    risk_by_category = report.get("risk_by_category", {})
    risk_by_source = report.get("risk_by_source", {})
    risk_by_action = report.get("risk_by_action", {})
    normalized_chart_mode = _normalize_chart_mode(chart_mode)
    price_chart_html, price_chart_note = _build_price_chart_html(report, normalized_chart_mode)
    position_chart_html, _ = _build_position_chart_html(report)

    summary_rows = "".join(
        f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>"
        for key, value in summary.items()
    )
    risk_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(event.get('dt', '')))}</td>"
        f"<td>{html.escape(str(event.get('risk_type', '')))}</td>"
        f"<td>{html.escape(str(event.get('category', '')))}</td>"
        f"<td>{html.escape(str(event.get('source', '')))}</td>"
        f"<td>{html.escape(str(event.get('code', '')))}</td>"
        f"<td>{html.escape(str(event.get('action_taken', '')))}</td>"
        f"<td>{html.escape(str(event.get('message', '')))}</td>"
        "</tr>"
        for event in risk_events
    ) or "<tr><td colspan='7'>无风险事件</td></tr>"
    position_rows = "".join(
        "<tr>"
        f"<td>{html.escape(code)}</td>"
        f"<td>{html.escape(str(snapshot.get('quantity', '')))}</td>"
        f"<td>{html.escape(str(snapshot.get('avg_price', '')))}</td>"
        f"<td>{html.escape(str(snapshot.get('sellable_quantity', '')))}</td>"
        f"<td>{html.escape(str(snapshot.get('margin', '')))}</td>"
        "</tr>"
        for code, snapshot in latest_positions.items()
    ) or "<tr><td colspan='5'>无持仓</td></tr>"
    execution_timing = html.escape(str(summary.get("execution_timing", "")))
    execution_price_model = html.escape(str(summary.get("execution_price_model", "")))
    rejected_orders = html.escape(str(summary.get("rejected_orders", 0)))
    price_guard_blocked_orders = html.escape(str(summary.get("price_guard_blocked_orders", 0)))
    price_chart_note = html.escape(str(price_chart_note))
    chart_mode_label = "完整K线图" if normalized_chart_mode == "full" else "简化折线图"
    chart_legend = (
        "图例说明: "
        "B=买入成交点，"
        "S=卖出成交点，"
        "SB=买入信号点，"
        "SS=卖出信号点，"
        "橙色信号=价格阈值/涨跌停拦截，"
        "灰色信号=无下一根Bar未执行，"
        "紫色信号=其他原因未成交，"
        "浅蓝色背景=持仓区间。"
        "鼠标悬停标记可查看日期、价格、数量、offset 与未成交原因。"
    )
    chart_legend = html.escape(chart_legend)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>JWQuant 回测风险报告</title>
  <style>
    body {{ font-family: 'PingFang SC', 'Noto Sans SC', sans-serif; margin: 24px; color: #102a43; background: #f8fbff; }}
    h1, h2 {{ margin: 0 0 12px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; margin-bottom: 24px; }}
    .card {{ background: white; border: 1px solid #d9e2ec; border-radius: 14px; padding: 18px; box-shadow: 0 8px 30px rgba(15, 23, 42, 0.06); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid #e5edf5; padding: 8px 10px; text-align: left; vertical-align: top; }}
    .metric-list {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }}
    .metric {{ background: #f3f7fb; border-radius: 10px; padding: 12px; }}
    .metric .label {{ font-size: 12px; color: #627d98; }}
    .metric .value {{ font-size: 20px; font-weight: 700; margin-top: 4px; }}
    .equity-chart {{ width: 100%; height: auto; background: linear-gradient(180deg, #ffffff 0%, #eef8f7 100%); border-radius: 10px; }}
    .price-chart {{ width: 100%; height: auto; background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%); border-radius: 10px; }}
    .position-chart {{ width: 100%; height: auto; background: linear-gradient(180deg, #ffffff 0%, #f5fbf9 100%); border-radius: 10px; }}
    .json {{ white-space: pre-wrap; word-break: break-word; font-family: ui-monospace, SFMono-Regular, monospace; font-size: 12px; }}
    .empty {{ color: #7b8794; padding: 16px 0; }}
    .chart-scroll {{ overflow-x: auto; padding-bottom: 6px; }}
    .chart-note {{ color: #627d98; font-size: 12px; margin-bottom: 10px; }}
    .chart-legend {{ color: #486581; font-size: 12px; margin: 8px 0 12px; line-height: 1.6; }}
    .marker-label {{ fill: #334e68; font-size: 10px; font-weight: 700; }}
  </style>
</head>
<body>
  <h1>JWQuant 回测风险报告</h1>
  <div class="grid">
    <section class="card">
      <h2>摘要</h2>
      <table>{summary_rows}</table>
    </section>
    <section class="card">
      <h2>撮合口径</h2>
      <div class="metric-list">
        <div class="metric"><div class="label">撮合时机</div><div class="json">{execution_timing}</div></div>
        <div class="metric"><div class="label">成交价格模型</div><div class="json">{execution_price_model}</div></div>
        <div class="metric"><div class="label">拒单数</div><div class="value">{rejected_orders}</div></div>
        <div class="metric"><div class="label">价格拦截数</div><div class="value">{price_guard_blocked_orders}</div></div>
      </div>
    </section>
    <section class="card">
      <h2>风险统计</h2>
      <div class="metric-list">
        <div class="metric"><div class="label">按分类</div><div class="json">{html.escape(_json(risk_by_category))}</div></div>
        <div class="metric"><div class="label">按来源</div><div class="json">{html.escape(_json(risk_by_source))}</div></div>
        <div class="metric"><div class="label">按动作</div><div class="json">{html.escape(_json(risk_by_action))}</div></div>
      </div>
    </section>
  </div>
  <section class="card">
    <h2>权益曲线</h2>
    {_build_equity_svg(equity_records)}
  </section>
  <section class="card">
    <h2>价格图与买卖点</h2>
    <div class="chart-note">图表模式: {chart_mode_label} | {price_chart_note}</div>
    <div class="chart-legend">{chart_legend}</div>
    {price_chart_html}
  </section>
  <section class="card">
    <h2>仓位变化折线</h2>
    <div class="chart-note">{price_chart_note}</div>
    {position_chart_html}
  </section>
  <div class="grid">
    <section class="card">
      <h2>风险事件</h2>
      <table>
        <thead><tr><th>时间</th><th>类型</th><th>分类</th><th>来源</th><th>代码</th><th>动作</th><th>说明</th></tr></thead>
        <tbody>{risk_rows}</tbody>
      </table>
    </section>
    <section class="card">
      <h2>最新持仓</h2>
      <table>
        <thead><tr><th>代码</th><th>数量</th><th>均价</th><th>可卖</th><th>保证金</th></tr></thead>
        <tbody>{position_rows}</tbody>
      </table>
    </section>
  </div>
</body>
</html>"""


def write_backtest_report_html(results: dict[str, Any], output_path: str | Path, chart_mode: str = "simple") -> Path:
    path = resolve_unique_report_path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_backtest_report_html(results, chart_mode=chart_mode), encoding="utf-8")
    return path
