from __future__ import annotations

from jwquant.common import config
from scripts.download_data import build_parser, build_source
from jwquant.trading.data.sources.akshare_src import AkShareDataSource


def test_build_source_should_support_akshare() -> None:
    source = build_source("akshare")
    assert isinstance(source, AkShareDataSource)


def test_build_parser_should_accept_akshare_source() -> None:
    config.load_config(profile="live")
    parser = build_parser()
    args = parser.parse_args(["--code", "601006.SH", "--start", "2025-01-01", "--source", "akshare"])

    assert args.source == "akshare"
