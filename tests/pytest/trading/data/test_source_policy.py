from __future__ import annotations

from pathlib import Path

from jwquant.common import config
from jwquant.common.config import Config
from jwquant.trading.data.source_policy import choose_primary_source, load_source_policy, normalize_timeframe_group


def _write_toml(tmp: Path, name: str, content: str) -> Path:
    path = tmp / name
    path.write_text(content, encoding="utf-8")
    return path


def test_normalize_timeframe_group() -> None:
    assert normalize_timeframe_group("1d") == "daily"
    assert normalize_timeframe_group("1w") == "weekly"
    assert normalize_timeframe_group("1m") == "monthly"
    assert normalize_timeframe_group("5m") == "intraday"


def test_load_source_policy_should_read_sequence_from_config(tmp_path) -> None:
    cfg_file = _write_toml(
        tmp_path,
        "source_policy.toml",
        """
[data.source_policy.stock.research]
daily = ["akshare", "tushare", "baostock"]
weekly = ["akshare", "tushare"]
monthly = ["akshare"]
intraday = ["xtquant"]
""",
    )
    config.load_config(cfg_file)

    policy = load_source_policy(market="stock", use_case="research", timeframe="1d", config=Config())

    assert policy.market == "stock"
    assert policy.use_case == "research"
    assert policy.timeframe_group == "daily"
    assert policy.sources == ("akshare", "tushare", "baostock")
    assert policy.adj == "none"
    assert policy.primary is None
    assert policy.secondary == ()


def test_choose_primary_source_should_prefer_primary_field(tmp_path) -> None:
    cfg_file = _write_toml(
        tmp_path,
        "source_policy_primary.toml",
        """
[data.source_policy.stock.reconciliation]
primary = "xtquant"
secondary = ["akshare", "tushare"]
daily = ["xtquant", "akshare", "tushare"]
""",
    )
    config.load_config(cfg_file)

    chosen = choose_primary_source(
        market="stock",
        use_case="reconciliation",
        timeframe="1d",
        config=Config(),
    )

    assert chosen == "xtquant"


def test_choose_primary_source_should_fallback_to_first_sequence_item(tmp_path) -> None:
    cfg_file = _write_toml(
        tmp_path,
        "source_policy_fallback.toml",
        """
[data.source_policy.stock.backtest]
daily = ["xtquant", "akshare", "tushare"]
""",
    )
    config.load_config(cfg_file)

    chosen = choose_primary_source(
        market="stock",
        use_case="backtest",
        timeframe="1d",
        config=Config(),
    )

    assert chosen == "xtquant"


def test_load_source_policy_should_filter_out_baostock_for_stock_research_qfq(tmp_path) -> None:
    cfg_file = _write_toml(
        tmp_path,
        "source_policy_adjust.toml",
        """
[data.source_policy.stock.research]
daily = ["akshare", "tushare", "baostock", "xtquant"]
""",
    )
    config.load_config(cfg_file)

    policy = load_source_policy(
        market="stock",
        use_case="research",
        timeframe="1d",
        adj="qfq",
        config=Config(),
    )

    assert policy.adj == "qfq"
    assert policy.sources == ("akshare", "tushare", "xtquant")


def test_choose_primary_source_should_skip_baostock_when_research_qfq_requested(tmp_path) -> None:
    cfg_file = _write_toml(
        tmp_path,
        "source_policy_adjust_primary.toml",
        """
[data.source_policy.stock.research]
daily = ["baostock", "akshare", "tushare"]
""",
    )
    config.load_config(cfg_file)

    chosen = choose_primary_source(
        market="stock",
        use_case="research",
        timeframe="1d",
        adj="qfq",
        config=Config(),
    )

    assert chosen == "akshare"


def test_choose_primary_source_should_allow_akshare_for_backtest_qfq(tmp_path) -> None:
    cfg_file = _write_toml(
        tmp_path,
        "source_policy_backtest_adjust.toml",
        """
[data.source_policy.stock.backtest]
daily = ["akshare", "tushare", "baostock", "xtquant"]
""",
    )
    config.load_config(cfg_file)

    chosen = choose_primary_source(
        market="stock",
        use_case="backtest",
        timeframe="1d",
        adj="qfq",
        config=Config(),
    )

    assert chosen == "akshare"


def test_load_source_policy_should_filter_out_only_baostock_for_backtest_hfq(tmp_path) -> None:
    cfg_file = _write_toml(
        tmp_path,
        "source_policy_backtest_adjust_hfq.toml",
        """
[data.source_policy.stock.backtest]
daily = ["xtquant", "akshare", "tushare", "baostock"]
""",
    )
    config.load_config(cfg_file)

    policy = load_source_policy(
        market="stock",
        use_case="backtest",
        timeframe="1d",
        adj="hfq",
        config=Config(),
    )

    assert policy.sources == ("xtquant", "akshare", "tushare")


def test_load_source_policy_should_clear_primary_when_baostock_is_not_adjust_eligible(tmp_path) -> None:
    cfg_file = _write_toml(
        tmp_path,
        "source_policy_primary_adjust.toml",
        """
[data.source_policy.stock.reconciliation]
primary = "baostock"
secondary = ["baostock", "akshare", "tushare"]
daily = ["baostock", "akshare", "tushare"]
""",
    )
    config.load_config(cfg_file)

    policy = load_source_policy(
        market="stock",
        use_case="reconciliation",
        timeframe="1d",
        adj="hfq",
        config=Config(),
    )

    assert policy.primary is None
    assert policy.secondary == ("akshare", "tushare")
    assert policy.sources == ("akshare", "tushare")


def test_load_source_policy_should_filter_out_baostock_for_reconciliation_hfq(tmp_path) -> None:
    cfg_file = _write_toml(
        tmp_path,
        "source_policy_reconciliation_hfq.toml",
        """
[data.source_policy.stock.reconciliation]
primary = "baostock"
secondary = ["baostock", "akshare", "tushare", "xtquant"]
daily = ["baostock", "akshare", "tushare", "xtquant"]
""",
    )
    config.load_config(cfg_file)

    policy = load_source_policy(
        market="stock",
        use_case="reconciliation",
        timeframe="1d",
        adj="hfq",
        config=Config(),
    )

    assert policy.primary is None
    assert policy.secondary == ("akshare", "tushare", "xtquant")
    assert policy.sources == ("akshare", "tushare", "xtquant")
