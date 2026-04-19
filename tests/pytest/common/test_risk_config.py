from __future__ import annotations

from jwquant.trading.risk import RiskConfig


def test_risk_config_from_mapping_loads_thresholds_and_priorities():
    config = RiskConfig.from_mapping(
        {
            "max_total_exposure": 0.8,
            "max_single_weight": 0.3,
            "max_futures_margin_ratio": 1.0,
            "max_holdings": 5,
            "max_order_amount": 200000,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.0,
            "trailing_stop_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "allow_futures_long": True,
            "allow_futures_short": True,
            "buy_reject_threshold_pct": 0.08,
            "sell_reject_threshold_pct": 0.07,
            "limit_up_pct": 0.1,
            "limit_down_pct": 0.1,
            "conflict_policy": "priority_first",
            "rule_priorities": {"max_total_exposure": 10},
        }
    )

    assert config.max_total_exposure == 0.8
    assert config.max_single_weight == 0.3
    assert config.max_holdings == 5
    assert config.max_order_amount == 200000.0
    assert config.stop_loss_pct == 0.05
    assert config.buy_reject_threshold_pct == 0.08
    assert config.sell_reject_threshold_pct == 0.07
    assert config.limit_up_pct == 0.1
    assert config.limit_down_pct == 0.1
    assert config.conflict_policy == "priority_first"
    assert config.rule_priorities == {"max_total_exposure": 10}
