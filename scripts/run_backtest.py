"""
运行策略回测
用法: python scripts/run_backtest.py --strategy turtle --code 000001.SZ
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# 添加项目路径
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jwquant.trading.strategy.registry import get_strategy_registry, create_registered_strategy
from jwquant.common.config import Config, load_config
from jwquant.trading.backtest import (
    BacktestConfig,
    SimpleBacktester,
    build_backtest_report_output_path,
    resolve_unique_report_path,
    write_backtest_report_html,
)
from jwquant.trading.backtest.cost import BacktestCostConfig
from jwquant.trading.data.feed import DataFeed
from jwquant.trading.data.sources.xtquant_src import XtQuantDataSource
from jwquant.trading.data.store import LocalDataStore
from jwquant.trading.data.sync import sync_xtquant_data
from jwquant.trading.risk import RiskConfig


def generate_sample_data(code: str = "000001.SZ", days: int = 252) -> pd.DataFrame:
    """生成示例数据用于测试"""
    print(f"生成 {code} 的 {days} 天示例数据...")
    
    # 生成日期序列
    end_date = datetime.now()
    dates = pd.date_range(end=end_date, periods=days, freq='D')
    dates = dates[dates.weekday < 5]  # 只保留工作日
    
    # 生成价格序列（几何布朗运动）
    np.random.seed(42)
    returns = np.random.normal(0.0005, 0.02, len(dates))  # 日收益率
    prices = 100 * np.exp(np.cumsum(returns))  # 从100开始的价格
    
    # 生成OHLCV数据
    data = []
    for i, (date, close_price) in enumerate(zip(dates, prices)):
        # 生成开盘价（基于前一天收盘价）
        if i == 0:
            open_price = close_price * (1 + np.random.normal(0, 0.01))
        else:
            open_price = prices[i-1] * (1 + np.random.normal(0, 0.005))
            
        # 生成最高价和最低价
        high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, 0.01)))
        low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, 0.01)))
        
        # 确保高低价格顺序正确
        high_price = max(high_price, open_price, close_price)
        low_price = min(low_price, open_price, close_price)
        
        # 生成成交量
        volume = np.random.randint(1000000, 10000000)
        
        data.append({
            'code': code,
            'dt': date,
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'volume': volume
        })
    
    return pd.DataFrame(data)


def parse_codes(raw_codes: str) -> list[str]:
    codes = [code.strip() for code in str(raw_codes).split(",")]
    return [code for code in codes if code]


def parse_portfolio_weights(raw_weights: str | None, codes: list[str]) -> dict[str, float] | None:
    if raw_weights is None:
        return None

    raw_weights = str(raw_weights).strip()
    if not raw_weights:
        return None

    if raw_weights.lower() == "equal":
        if not codes:
            return None
        equal_weight = 1.0 / len(codes)
        return {code: equal_weight for code in codes}

    weights: dict[str, float] = {}
    for item in raw_weights.split(","):
        part = item.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"invalid portfolio weight: {part}")
        code, weight = part.split("=", 1)
        weights[code.strip()] = float(weight.strip())
    return weights or None


def load_backtest_risk_defaults() -> RiskConfig:
    config = Config()
    return RiskConfig.from_mapping(config.get("backtest.risk"))


def load_backtest_cost_defaults() -> BacktestCostConfig:
    """读取回测金额相关默认值。

    这层默认值只负责“金额参数从哪里来”，不改回测计算公式：
    - 佣金仍按成交额 * commission_rate
    - 滑点仍按成交方向对价格做比例偏移
    - 单笔金额上限仍先在 broker 层约束下单量
    """
    config = Config()
    return BacktestCostConfig.from_mapping(config.get("backtest.cost"))


def load_backtest_data(feed: DataFeed, args) -> pd.DataFrame:
    codes = parse_codes(args.code)

    if args.sample_data:
        return pd.concat([generate_sample_data(code, args.days) for code in codes], ignore_index=True)

    end = args.end or datetime.now().strftime("%Y-%m-%d")
    start = args.start
    if start is None:
        start = (pd.to_datetime(end) - timedelta(days=max(args.days * 2, args.days))).strftime("%Y-%m-%d")

    frames: list[pd.DataFrame] = []
    missing_codes: list[str] = []
    for code in codes:
        bars = feed.get_bars(
            code=code,
            start=start,
            end=end,
            timeframe=args.timeframe,
            market=args.market,
            adj=args.adj,
        )
        if bars.empty:
            missing_codes.append(code)
        else:
            frames.append(bars)

    if missing_codes:
        print(f"本地数据为空，尝试通过 XtQuant 自动下载: {', '.join(missing_codes)}")
        store = LocalDataStore()
        source = XtQuantDataSource()
        for code in missing_codes:
            try:
                sync_xtquant_data(
                    code=code,
                    start=start,
                    end=end,
                    market=args.market,
                    timeframe=args.timeframe,
                    store=store,
                    source=source,
                    incremental=True,
                )
                bars = feed.get_bars(
                    code=code,
                    start=start,
                    end=end,
                    timeframe=args.timeframe,
                    market=args.market,
                    adj=args.adj,
                )
                if not bars.empty:
                    frames.append(bars)
            except RuntimeError as exc:
                print(f"{code} 自动下载失败: {exc}")

    if not frames:
        print("回退到样例数据。")
        return pd.concat([generate_sample_data(code, args.days) for code in codes], ignore_index=True)

    return pd.concat(frames, ignore_index=True)


def main():
    """主函数"""
    load_config(extra=["config/strategies.toml"])
    # 风控默认值和金额默认值分开读取：
    # - risk 负责“是否允许下单/是否触发退出”
    # - cost 负责“成交会花多少钱/一笔最多按多少钱估量”
    risk_defaults = load_backtest_risk_defaults()
    cost_defaults = load_backtest_cost_defaults()

    parser = argparse.ArgumentParser(description='策略回测工具')
    parser.add_argument('--strategy', '-s', required=True, help='策略名称')
    parser.add_argument('--code', '-c', default='000001.SZ', help='股票代码')
    parser.add_argument('--market', default='stock', choices=['stock', 'futures'], help='市场类型')
    parser.add_argument('--timeframe', '-t', default='1d', help='周期，如 1d/1w/1m')
    parser.add_argument('--adj', default='none', help='复权方式：none/qfq/hfq，仅股票有效')
    parser.add_argument('--start', default=None, help='开始日期，优先用于本地数据读取')
    parser.add_argument('--end', default=None, help='结束日期，优先用于本地数据读取')
    parser.add_argument('--sample-data', action='store_true', help='强制使用样例数据，不读取本地存储')
    parser.add_argument('--days', '-d', type=int, default=252, help='回测天数')
    parser.add_argument('--capital', type=float, default=1000000, help='初始资金')
    parser.add_argument('--commission-rate', type=float, default=cost_defaults.commission_rate, help='佣金费率，按成交额比例收取')
    parser.add_argument('--slippage', type=float, default=cost_defaults.slippage, help='滑点比例，按成交方向对价格做比例偏移')
    parser.add_argument('--max-order-value', type=float, default=cost_defaults.max_order_value, help='单笔下单金额上限，broker 会先据此估算下单量')
    parser.add_argument('--portfolio-weights', default=None, help='组合目标权重，如 000001.SZ=0.6,600519.SH=0.4 或 equal')
    parser.add_argument('--rebalance-frequency', default='none', choices=['none', 'daily', 'weekly', 'monthly'], help='组合再平衡频率')
    parser.add_argument('--rebalance-tolerance', type=float, default=0.02, help='目标权重偏离容忍度')
    parser.add_argument('--risk-max-total-exposure', type=float, default=risk_defaults.max_total_exposure, help='组合总暴露上限')
    parser.add_argument('--risk-max-single-weight', type=float, default=risk_defaults.max_single_weight, help='单标的权重上限')
    parser.add_argument('--risk-max-futures-margin-ratio', type=float, default=risk_defaults.max_futures_margin_ratio, help='期货保证金占权益上限')
    parser.add_argument('--risk-max-holdings', type=int, default=risk_defaults.max_holdings, help='最大持仓标的数，0 表示关闭')
    parser.add_argument('--risk-max-order-amount', type=float, default=risk_defaults.max_order_amount, help='统一单笔下单金额上限，0 表示关闭')
    parser.add_argument('--stop-loss-pct', type=float, default=risk_defaults.stop_loss_pct, help='统一固定止损比例，0 表示关闭')
    parser.add_argument('--take-profit-pct', type=float, default=risk_defaults.take_profit_pct, help='统一固定止盈比例，0 表示关闭')
    parser.add_argument('--trailing-stop-pct', type=float, default=risk_defaults.trailing_stop_pct, help='统一移动止损比例，0 表示关闭')
    parser.add_argument('--max-drawdown-pct', type=float, default=risk_defaults.max_drawdown_pct, help='统一最大回撤止损比例，0 表示关闭')
    parser.add_argument('--buy-reject-threshold-pct', type=float, default=risk_defaults.buy_reject_threshold_pct, help='股票买入拦截阈值；相对昨收涨幅达到该比例后不再买入，0 表示关闭')
    parser.add_argument('--sell-reject-threshold-pct', type=float, default=risk_defaults.sell_reject_threshold_pct, help='股票卖出拦截阈值；相对昨收跌幅达到该比例后不再卖出，0 表示关闭')
    parser.add_argument('--limit-up-pct', type=float, default=risk_defaults.limit_up_pct, help='股票涨停阈值；相对昨收涨幅达到该比例后禁止买入')
    parser.add_argument('--limit-down-pct', type=float, default=risk_defaults.limit_down_pct, help='股票跌停阈值；相对昨收跌幅达到该比例后禁止卖出')
    parser.add_argument('--risk-conflict-policy', default=risk_defaults.conflict_policy, choices=['priority_first'], help='统一风控冲突仲裁策略')
    parser.add_argument('--report-html', default=None, help='输出 HTML 回测风险报告路径')
    parser.add_argument('--report-dir', default=None, help='HTML 回测报告输出目录；未传入时使用配置 backtest.report.dir')
    parser.add_argument('--futures-margin-rate', type=float, default=cost_defaults.futures_margin_rate, help='期货保证金率，用于估算占用保证金和可开仓手数')
    parser.add_argument('--futures-contract-multiplier', type=float, default=cost_defaults.futures_contract_multiplier, help='期货合约乘数，用于估算名义金额和盈亏')
    
    args = parser.parse_args()
    
    # 获取策略注册中心
    registry = get_strategy_registry()
    
    # 检查策略是否存在
    if args.strategy not in registry.list_strategies():
        print(f"错误: 策略 '{args.strategy}' 不存在")
        print(f"可用策略: {', '.join(registry.list_strategies())}")
        return
    
    # 创建策略实例
    strategy = create_registered_strategy(args.strategy)
    if not strategy:
        print(f"错误: 无法创建策略 '{args.strategy}'")
        return

    codes = parse_codes(args.code)
    portfolio_weights = parse_portfolio_weights(args.portfolio_weights, codes)
    
    feed = DataFeed()
    data = load_backtest_data(feed, args)

    # 把脚本参数显式落成 BacktestConfig，避免 broker / engine 再去隐式读配置。
    # 这样一来：
    # 1. CLI 覆盖优先级清晰
    # 2. 测试可以直接断言金额参数是否传到回测内核
    # 3. 佣金、滑点、保证金率等都能从同一个配置入口落地
    backtester = SimpleBacktester(
        BacktestConfig(
            initial_capital=args.capital,
            commission_rate=args.commission_rate,
            slippage=args.slippage,
            market=args.market,
            max_order_value=args.max_order_value,
            portfolio_weights=portfolio_weights,
            rebalance_frequency=args.rebalance_frequency,
            rebalance_tolerance=args.rebalance_tolerance,
            risk_max_total_exposure=args.risk_max_total_exposure,
            risk_max_single_weight=args.risk_max_single_weight,
            risk_max_futures_margin_ratio=args.risk_max_futures_margin_ratio,
            risk_max_holdings=args.risk_max_holdings,
            risk_max_order_amount=args.risk_max_order_amount,
            stop_loss_pct=args.stop_loss_pct,
            take_profit_pct=args.take_profit_pct,
            trailing_stop_pct=args.trailing_stop_pct,
            max_drawdown_pct=args.max_drawdown_pct,
            buy_reject_threshold_pct=args.buy_reject_threshold_pct,
            sell_reject_threshold_pct=args.sell_reject_threshold_pct,
            limit_up_pct=args.limit_up_pct,
            limit_down_pct=args.limit_down_pct,
            risk_conflict_policy=args.risk_conflict_policy,
            risk_rule_priorities=dict(risk_defaults.rule_priorities),
            futures_margin_rate=args.futures_margin_rate,
            futures_contract_multiplier=args.futures_contract_multiplier,
        )
    )
    results = backtester.run_backtest(strategy, data)
    
    # 输出结果
    print("\n" + "="*50)
    print("回测结果")
    print("="*50)
    print(f"策略名称: {results['strategy_name']}")
    print(f"标的数量: {data['code'].nunique()}")
    print(f"回测期间: {data['dt'].min().strftime('%Y-%m-%d')} 至 {data['dt'].max().strftime('%Y-%m-%d')}")
    print(f"初始资金: {args.capital:,.2f}")
    print(f"最终权益: {results['final_equity']:,.2f}")
    print(f"总收益率: {results['total_return']*100:.2f}%")
    print(f"年化收益: {results['annual_return']*100:.2f}%")
    print(f"波动率: {results['volatility']*100:.2f}%")
    print(f"夏普比率: {results['sharpe_ratio']:.2f}")
    print(f"最大回撤: {results['max_drawdown']*100:.2f}%")
    print(f"胜率: {results['win_rate']*100:.1f}%")
    print(f"盈亏因子: {results['profit_factor']:.2f}")
    print(f"平均单笔收益: {results['avg_trade_profit']:,.2f}")
    print(f"交易次数: {results['total_trades']}")
    print(f"订单次数: {results['total_orders']}")
    print(f"再平衡次数: {results['total_rebalances']}")
    print(f"风险事件数: {results['risk_event_count']}")
    print(f"风险分类统计: {results['report']['summary']['risk_by_category']}")
    print(f"风险来源统计: {results['report']['summary']['risk_by_source']}")
    print(f"风险动作统计: {results['report']['summary']['risk_by_action']}")
    print(f"总手续费: {results['total_commission']:,.2f}")

    report_start = data['dt'].min().strftime('%Y-%m-%d')
    report_end = data['dt'].max().strftime('%Y-%m-%d')
    if args.report_html:
        output_path = write_backtest_report_html(results, resolve_unique_report_path(args.report_html))
    else:
        config = Config()
        report_dir = args.report_dir or config.get("backtest.report.dir")
        output_path = write_backtest_report_html(
            results,
            build_backtest_report_output_path(
                output_dir=report_dir,
                strategy_name=args.strategy,
                start_date=report_start,
                end_date=report_end,
            ),
        )
    print(f"HTML 报告: {output_path}")
    order_status_counts = results["report"]["order_status_counts"]
    if order_status_counts:
        summary = ", ".join(f"{status}={count}" for status, count in sorted(order_status_counts.items()))
        print(f"订单状态: {summary}")


if __name__ == "__main__":
    main()
