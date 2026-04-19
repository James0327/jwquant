"""
回测报告渲染。
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any


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


def render_backtest_report_html(results: dict[str, Any]) -> str:
    report = results.get("report", {})
    summary = report.get("summary", {})
    risk_events = report.get("risk_events", [])
    equity_records = report.get("equity_records", [])
    latest_positions = report.get("latest_positions", {})
    risk_by_category = report.get("risk_by_category", {})
    risk_by_source = report.get("risk_by_source", {})
    risk_by_action = report.get("risk_by_action", {})

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
    .json {{ white-space: pre-wrap; word-break: break-word; font-family: ui-monospace, SFMono-Regular, monospace; font-size: 12px; }}
    .empty {{ color: #7b8794; padding: 16px 0; }}
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


def write_backtest_report_html(results: dict[str, Any], output_path: str | Path) -> Path:
    path = resolve_unique_report_path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_backtest_report_html(results), encoding="utf-8")
    return path
