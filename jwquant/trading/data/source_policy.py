"""数据源选择策略。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jwquant.common.config import Config


_TIMEFRAME_ALIASES = {
    "1d": "daily",
    "d": "daily",
    "day": "daily",
    "daily": "daily",
    "1w": "weekly",
    "w": "weekly",
    "week": "weekly",
    "weekly": "weekly",
    "1m": "monthly",
    "m": "monthly",
    "month": "monthly",
    "monthly": "monthly",
}

_DIRECT_ADJUST_SOURCE_ELIGIBILITY = {
    ("stock", "research", "none"): {"xtquant", "akshare", "tushare", "baostock"},
    # 当前仅限制 Baostock qfq/hfq；AkShare qfq/hfq 在 source policy 层不再额外限制。
    ("stock", "research", "qfq"): {"xtquant", "akshare", "tushare"},
    ("stock", "research", "hfq"): {"xtquant", "akshare", "tushare"},
    ("stock", "repair", "none"): {"xtquant", "akshare", "tushare", "baostock"},
    ("stock", "repair", "qfq"): {"xtquant", "akshare", "tushare"},
    ("stock", "repair", "hfq"): {"xtquant", "akshare", "tushare"},
    ("stock", "backtest", "none"): {"xtquant", "akshare", "tushare", "baostock"},
    ("stock", "backtest", "qfq"): {"xtquant", "akshare", "tushare"},
    ("stock", "backtest", "hfq"): {"xtquant", "akshare", "tushare"},
    ("stock", "reconciliation", "none"): {"xtquant", "akshare", "tushare", "baostock"},
    ("stock", "reconciliation", "qfq"): {"xtquant", "akshare", "tushare"},
    ("stock", "reconciliation", "hfq"): {"xtquant", "akshare", "tushare"},
}


@dataclass(frozen=True)
class SourcePolicy:
    """单场景数据源优先级策略。"""

    market: str
    use_case: str
    timeframe_group: str
    sources: tuple[str, ...]
    adj: str = "none"
    primary: str | None = None
    secondary: tuple[str, ...] = ()


def normalize_timeframe_group(timeframe: str) -> str:
    normalized = str(timeframe).strip().lower()
    if normalized in {"5m", "15m", "30m", "60m", "intraday"}:
        return "intraday"
    resolved = _TIMEFRAME_ALIASES.get(normalized)
    if resolved is None:
        raise ValueError(f"unsupported timeframe for source policy: {timeframe}")
    return resolved


def _normalize_source_sequence(value: Any, *, field_name: str) -> tuple[str, ...]:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ()
        return (stripped,)
    if isinstance(value, (list, tuple)):
        normalized = tuple(str(item).strip() for item in value if str(item).strip())
        return normalized
    raise TypeError(f"source policy field {field_name} must be a string or sequence: {value!r}")


def _normalize_adj(adj: str | None) -> str:
    normalized = "none" if adj is None else str(adj).strip().lower()
    if normalized in {"none", "qfq", "hfq"}:
        return normalized
    raise ValueError(f"unsupported adjust type for source policy: {adj}")


def _filter_sources_by_adjustment(*, market: str, use_case: str, adj: str, sources: tuple[str, ...]) -> tuple[str, ...]:
    allowed = _DIRECT_ADJUST_SOURCE_ELIGIBILITY.get((market, use_case, adj))
    if allowed is None:
        return sources
    return tuple(source for source in sources if source in allowed)


def load_source_policy(
    *,
    market: str,
    use_case: str,
    timeframe: str,
    adj: str | None = None,
    config: Config | None = None,
) -> SourcePolicy:
    """从配置读取 source policy。

    配置结构示例：

    [data.source_policy.stock.research]
    daily = ["akshare", "tushare", "baostock", "xtquant"]
    """
    cfg = config or Config()
    normalized_market = str(market).strip().lower()
    normalized_use_case = str(use_case).strip().lower()
    timeframe_group = normalize_timeframe_group(timeframe)
    normalized_adj = _normalize_adj(adj)
    key = f"data.source_policy.{market}.{use_case}"
    payload = cfg.get(key)
    if not isinstance(payload, dict):
        raise TypeError(f"source policy must be a mapping: {key}")

    sources = _normalize_source_sequence(payload.get(timeframe_group, ()), field_name=timeframe_group)
    sources = _filter_sources_by_adjustment(
        market=normalized_market,
        use_case=normalized_use_case,
        adj=normalized_adj,
        sources=sources,
    )
    primary = payload.get("primary")
    secondaries = _normalize_source_sequence(payload.get("secondary", ()), field_name="secondary")
    secondaries = _filter_sources_by_adjustment(
        market=normalized_market,
        use_case=normalized_use_case,
        adj=normalized_adj,
        sources=secondaries,
    )
    if primary is not None:
        primary = str(primary).strip() or None
        if primary and primary not in _filter_sources_by_adjustment(
            market=normalized_market,
            use_case=normalized_use_case,
            adj=normalized_adj,
            sources=(primary,),
        ):
            primary = None

    return SourcePolicy(
        market=normalized_market,
        use_case=normalized_use_case,
        timeframe_group=timeframe_group,
        sources=sources,
        adj=normalized_adj,
        primary=primary,
        secondary=secondaries,
    )


def choose_primary_source(
    *,
    market: str,
    use_case: str,
    timeframe: str,
    adj: str | None = None,
    config: Config | None = None,
) -> str | None:
    """获取当前场景下的首选 source。

    当前仅作为 policy 读取入口，不在这里做自动降级与健康检查。
    """
    policy = load_source_policy(market=market, use_case=use_case, timeframe=timeframe, adj=adj, config=config)
    if policy.primary:
        return policy.primary
    if policy.sources:
        return policy.sources[0]
    return None
