"""
运行策略回测
用法: python scripts/run_backtest.py --strategy turtle --code 000001.SZ
"""
import argparse
import sys
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import List, Optional

# 添加项目路径
sys.path.insert(0, '/Users/james/PycharmProjects/jwquant')

from jwquant.trading.strategy.registry import get_strategy_registry, create_registered_strategy
from jwquant.trading.strategy.base import BaseStrategy, StrategyManager
from jwquant.common.types import Bar, Signal, Asset, Position
from jwquant.common.config import load_config
from jwquant.trading.data.feed import DataFeed


class SimpleBacktester:
    """简易回测引擎"""
    
    def __init__(self, initial_capital: float = 1000000):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions: dict = {}
        self.trades: List[dict] = []
        self.equity_curve: List[float] = []
        self.dates: List[datetime] = []
        
        # 交易成本
        self.commission_rate = 0.0003  # 万分之三手续费
        self.slippage = 0.0001         # 万分之一滑点
        
    def execute_trade(self, signal: Signal, price: float) -> bool:
        """执行交易"""
        code = signal.code
        quantity = self.calculate_position_size(signal, price)
        
        if quantity <= 0:
            return False
            
        # 计算交易成本
        trade_value = quantity * price
        commission = trade_value * self.commission_rate
        total_cost = trade_value + commission
        
        if signal.signal_type.name == 'BUY':
            # 买入检查资金
            if total_cost > self.current_capital:
                print(f"资金不足: 需要 {total_cost:.2f}, 可用 {self.current_capital:.2f}")
                return False
                
            # 更新持仓
            if code in self.positions:
                # 加仓
                pos = self.positions[code]
                total_quantity = pos['quantity'] + quantity
                avg_price = (pos['quantity'] * pos['avg_price'] + quantity * price) / total_quantity
                self.positions[code] = {
                    'quantity': total_quantity,
                    'avg_price': avg_price
                }
            else:
                # 开仓
                self.positions[code] = {
                    'quantity': quantity,
                    'avg_price': price
                }
                
            # 扣除资金
            self.current_capital -= total_cost
            
        elif signal.signal_type.name == 'SELL':
            # 卖出检查持仓
            if code not in self.positions or self.positions[code]['quantity'] < quantity:
                print(f"持仓不足: 可卖 {self.positions.get(code, {}).get('quantity', 0)}, 欲卖 {quantity}")
                return False
                
            # 更新持仓
            pos = self.positions[code]
            remaining = pos['quantity'] - quantity
            
            if remaining <= 0:
                # 清仓
                del self.positions[code]
            else:
                # 减仓
                self.positions[code]['quantity'] = remaining
                
            # 增加资金（扣除成本）
            self.current_capital += trade_value - commission
            
            # 记录交易
            profit = (price - pos['avg_price']) * quantity - commission
            self.trades.append({
                'date': signal.dt,
                'code': code,
                'direction': 'SELL',
                'price': price,
                'quantity': quantity,
                'profit': profit,
                'commission': commission
            })
        
        # 记录买入交易
        if signal.signal_type.name == 'BUY':
            self.trades.append({
                'date': signal.dt,
                'code': code,
                'direction': 'BUY',
                'price': price,
                'quantity': quantity,
                'profit': 0,
                'commission': commission
            })
        
        return True
    
    def calculate_position_size(self, signal: Signal, price: float) -> int:
        """计算仓位大小"""
        # 简单的固定金额下单
        target_value = min(100000, self.current_capital * 0.1)  # 最多10万或可用资金的10%
        quantity = int(target_value / price / 100) * 100  # 整手交易
        return max(quantity, 100)  # 最少100股
    
    def calculate_equity(self, current_prices: dict) -> float:
        """计算当前权益"""
        position_value = 0
        for code, pos in self.positions.items():
            if code in current_prices:
                position_value += pos['quantity'] * current_prices[code]
        
        return self.current_capital + position_value
    
    def run_backtest(self, strategy: BaseStrategy, data: pd.DataFrame) -> dict:
        """运行回测"""
        print(f"开始回测策略: {strategy.name}")
        print(f"数据范围: {data['dt'].min()} 至 {data['dt'].max()}")
        print(f"初始资金: {self.initial_capital:,.2f}")
        
        # 初始化策略
        strategy.on_init()
        
        # 更新资产信息
        asset = Asset(cash=self.current_capital, total_asset=self.initial_capital)
        strategy.update_asset(asset)
        
        # 逐日回测
        for _, row in data.iterrows():
            # 创建Bar对象
            bar = Bar(
                code=row['code'],
                dt=row['dt'],
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=float(row['volume']),
                amount=float(row.get('amount', 0))
            )
            
            # 执行策略
            signal = strategy.on_bar(bar)
            
            # 执行交易信号
            if signal:
                success = self.execute_trade(signal, bar.close)
                if success:
                    print(f"{signal.dt.strftime('%Y-%m-%d')} {signal.code} "
                          f"{signal.signal_type.value} @{signal.price:.2f} "
                          f"[{signal.reason}]")
            
            # 更新每日权益
            current_prices = {bar.code: bar.close}
            equity = self.calculate_equity(current_prices)
            self.equity_curve.append(equity)
            self.dates.append(bar.dt)
        
        # 计算绩效指标
        results = self.calculate_performance()
        results['strategy_name'] = strategy.name
        results['total_trades'] = len(self.trades)
        results['final_equity'] = self.equity_curve[-1] if self.equity_curve else self.initial_capital
        
        return results
    
    def calculate_performance(self) -> dict:
        """计算绩效指标"""
        if not self.equity_curve:
            return {}
            
        equity_series = pd.Series(self.equity_curve)
        returns = equity_series.pct_change().dropna()
        
        # 基础指标
        total_return = (equity_series.iloc[-1] - self.initial_capital) / self.initial_capital
        annual_return = (1 + total_return) ** (252 / len(equity_series)) - 1
        
        # 风险指标
        volatility = returns.std() * np.sqrt(252)
        sharpe_ratio = annual_return / volatility if volatility > 0 else 0
        
        # 最大回撤
        rolling_max = equity_series.expanding().max()
        drawdown = (equity_series - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        # 胜率
        profitable_trades = [t for t in self.trades if t['direction'] == 'SELL' and t['profit'] > 0]
        win_rate = len(profitable_trades) / len([t for t in self.trades if t['direction'] == 'SELL']) if self.trades else 0
        
        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'total_commission': sum(t['commission'] for t in self.trades)
        }


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


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='策略回测工具')
    parser.add_argument('--strategy', '-s', required=True, help='策略名称')
    parser.add_argument('--code', '-c', default='000001.SZ', help='股票代码')
    parser.add_argument('--days', '-d', type=int, default=252, help='回测天数')
    parser.add_argument('--capital', type=float, default=1000000, help='初始资金')
    
    args = parser.parse_args()
    
    # 加载配置
    load_config()
    
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
    
    # 生成或加载数据
    data = generate_sample_data(args.code, args.days)
    
    # 运行回测
    backtester = SimpleBacktester(initial_capital=args.capital)
    results = backtester.run_backtest(strategy, data)
    
    # 输出结果
    print("\n" + "="*50)
    print("回测结果")
    print("="*50)
    print(f"策略名称: {results['strategy_name']}")
    print(f"回测期间: {data['dt'].min().strftime('%Y-%m-%d')} 至 {data['dt'].max().strftime('%Y-%m-%d')}")
    print(f"初始资金: {args.capital:,.2f}")
    print(f"最终权益: {results['final_equity']:,.2f}")
    print(f"总收益率: {results['total_return']*100:.2f}%")
    print(f"年化收益: {results['annual_return']*100:.2f}%")
    print(f"波动率: {results['volatility']*100:.2f}%")
    print(f"夏普比率: {results['sharpe_ratio']:.2f}")
    print(f"最大回撤: {results['max_drawdown']*100:.2f}%")
    print(f"胜率: {results['win_rate']*100:.1f}%")
    print(f"交易次数: {results['total_trades']}")
    print(f"总手续费: {results['total_commission']:,.2f}")


if __name__ == "__main__":
    main()