"""
轮动策略
动量效应，强者恒强，小市值轮动选股。
"""
from typing import List, Dict, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from jwquant.common.types import Bar, Signal, SignalType
from jwquant.trading.strategy.base import BaseStrategy


class RotationStrategy(BaseStrategy):
    """轮动策略实现"""
    
    def __init__(self, name: str = "rotation", params: dict | None = None):
        super().__init__(name, params)
        
        # 策略参数
        self.holding_count = params.get('holding_count', 5)      # 持仓股票数量
        self.rebalance_days = params.get('rebalance_days', 5)    # 调仓周期(交易日)
        self.market_cap_limit = params.get('market_cap_limit', 50)  # 市值上限(亿)
        self.lookback_period = params.get('lookback_period', 20)    # 回看周期
        self.min_volume = params.get('min_volume', 1000000)         # 最小成交量
        
        # 策略状态
        self.target_stocks: List[str] = []      # 目标持仓股票
        self.current_holdings: List[str] = []   # 当前持仓股票
        self.last_rebalance_date: Optional[datetime] = None
        self.price_data: Dict[str, List[Bar]] = {}  # 各股票价格数据
        self.performance_data: Dict[str, float] = {}  # 各股票表现数据
        
    def on_init(self) -> None:
        """策略初始化"""
        super().on_init()
        print(f"轮动策略参数: 持仓数={self.holding_count}, 调仓周期={self.rebalance_days}天")
        print(f"回看周期={self.lookback_period}, 市值上限={self.market_cap_limit}亿")
        
    def add_stock_data(self, bar: Bar) -> None:
        """添加股票数据"""
        if bar.code not in self.price_data:
            self.price_data[bar.code] = []
        
        self.price_data[bar.code].append(bar)
        
        # 保持合理的历史数据长度
        max_length = self.lookback_period * 2
        if len(self.price_data[bar.code]) > max_length:
            self.price_data[bar.code] = self.price_data[bar.code][-max_length:]
    
    def calculate_momentum(self, stock_code: str) -> float:
        """计算股票动量"""
        if stock_code not in self.price_data:
            return 0.0
            
        bars = self.price_data[stock_code]
        if len(bars) < self.lookback_period:
            return 0.0
            
        # 计算价格变化率
        current_price = bars[-1].close
        lookback_price = bars[-self.lookback_period].close
        
        if lookback_price == 0:
            return 0.0
            
        momentum = (current_price - lookback_price) / lookback_price
        return momentum
    
    def calculate_volatility(self, stock_code: str) -> float:
        """计算股票波动率"""
        if stock_code not in self.price_data:
            return 0.0
            
        bars = self.price_data[stock_code]
        if len(bars) < 10:
            return 0.0
            
        # 计算收益率序列
        returns = []
        for i in range(1, len(bars)):
            if bars[i-1].close != 0:
                ret = (bars[i].close - bars[i-1].close) / bars[i-1].close
                returns.append(ret)
        
        if not returns:
            return 0.0
            
        # 计算年化波动率
        volatility = np.std(returns) * np.sqrt(252)  # 年化
        return volatility
    
    def screen_stocks(self) -> List[str]:
        """股票筛选"""
        candidates = []
        
        # 收集所有有足够数据的股票
        for stock_code in self.price_data.keys():
            bars = self.price_data[stock_code]
            if len(bars) >= self.lookback_period:
                # 基本面筛选（这里简化处理）
                avg_volume = np.mean([bar.volume for bar in bars[-10:]])
                
                # 简化的市值估算（假设股价*流通股本）
                current_price = bars[-1].close
                estimated_market_cap = current_price * 10000  # 假设1万股
                
                # 筛选条件
                if (avg_volume >= self.min_volume and 
                    estimated_market_cap <= self.market_cap_limit * 100000000):  # 转换为元
                    
                    momentum = self.calculate_momentum(stock_code)
                    volatility = self.calculate_volatility(stock_code)
                    
                    # 风险调整后收益
                    if volatility > 0:
                        risk_adjusted_return = momentum / volatility
                    else:
                        risk_adjusted_return = momentum
                        
                    candidates.append({
                        'code': stock_code,
                        'momentum': momentum,
                        'volatility': volatility,
                        'risk_return': risk_adjusted_return,
                        'price': current_price
                    })
        
        # 按风险调整后收益排序
        candidates.sort(key=lambda x: x['risk_return'], reverse=True)
        
        # 返回前N只股票
        selected = [item['code'] for item in candidates[:self.holding_count * 2]]  # 多选一些用于进一步筛选
        return selected[:self.holding_count]
    
    def should_rebalance(self, current_date: datetime) -> bool:
        """判断是否需要调仓"""
        if not self.last_rebalance_date:
            return True
            
        # 计算交易日间隔
        days_diff = (current_date - self.last_rebalance_date).days
        return days_diff >= self.rebalance_days
    
    def generate_rebalance_signals(self, current_date: datetime) -> List[Signal]:
        """生成调仓信号"""
        signals = []
        
        # 筛选目标股票
        new_targets = self.screen_stocks()
        
        # 卖出不在目标中的股票
        for stock in self.current_holdings:
            if stock not in new_targets:
                # 查找该股票的最新价格数据
                if stock in self.price_data and self.price_data[stock]:
                    latest_bar = self.price_data[stock][-1]
                    signal = Signal(
                        code=stock,
                        dt=current_date,
                        signal_type=SignalType.SELL,
                        price=latest_bar.close,
                        strength=0.9,
                        reason=f"轮动调仓: 卖出{stock}"
                    )
                    signals.append(signal)
        
        # 买入新增的目标股票
        for stock in new_targets:
            if stock not in self.current_holdings:
                # 查找该股票的最新价格数据
                if stock in self.price_data and self.price_data[stock]:
                    latest_bar = self.price_data[stock][-1]
                    signal = Signal(
                        code=stock,
                        dt=current_date,
                        signal_type=SignalType.BUY,
                        price=latest_bar.close,
                        strength=0.9,
                        reason=f"轮动调仓: 买入{stock}"
                    )
                    signals.append(signal)
        
        # 更新持仓状态
        if signals:
            self.current_holdings = new_targets
            self.last_rebalance_date = current_date
            print(f"调仓完成: {len(signals)}个信号，当前持仓: {self.current_holdings}")
        
        return signals
    
    def on_bar(self, bar: Bar) -> Signal | None:
        """每根K线执行策略逻辑"""
        # 更新数据
        self.add_bar(bar)
        self.add_stock_data(bar)
        
        # 检查是否需要调仓
        if self.should_rebalance(bar.dt):
            signals = self.generate_rebalance_signals(bar.dt)
            # 返回第一个信号（如果有）
            return signals[0] if signals else None
        
        return None
    
    def get_portfolio_info(self) -> dict:
        """获取组合信息"""
        info = {
            'target_stocks': self.target_stocks,
            'current_holdings': self.current_holdings,
            'last_rebalance': self.last_rebalance_date,
            'stock_count': len(self.current_holdings),
            'performance_ranking': []
        }
        
        # 添加各股票的表现排名
        for stock_code in self.price_data.keys():
            if len(self.price_data[stock_code]) >= self.lookback_period:
                momentum = self.calculate_momentum(stock_code)
                volatility = self.calculate_volatility(stock_code)
                info['performance_ranking'].append({
                    'code': stock_code,
                    'momentum': momentum,
                    'volatility': volatility
                })
        
        # 按动量排序
        info['performance_ranking'].sort(key=lambda x: x['momentum'], reverse=True)
        
        return info
    
    def on_stop(self) -> None:
        """策略停止"""
        self.target_stocks.clear()
        self.current_holdings.clear()
        self.price_data.clear()
        self.performance_data.clear()
        self.last_rebalance_date = None
        super().on_stop()


# 快捷创建函数
def create_rotation_strategy(params: dict | None = None) -> RotationStrategy:
    """创建轮动策略实例"""
    default_params = {
        'holding_count': 5,
        'rebalance_days': 5,
        'market_cap_limit': 50,      # 50亿
        'lookback_period': 20,
        'min_volume': 1000000
    }
    
    if params:
        default_params.update(params)
        
    return RotationStrategy("rotation", default_params)