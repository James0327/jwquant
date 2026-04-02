"""
缠论量化策略
基于缠论指标分析结果，输出底分型与第三类买点信号。
"""
from typing import List, Optional

from jwquant.common.types import Bar, Signal, SignalType
from jwquant.trading.indicator.chanlun import (
    ChanBi,
    ChanBiDirection,
    ChanlunIndicator,
    Fractal,
    FractalType,
    ZhongShu,
)
from jwquant.trading.strategy.base import BaseStrategy


class ChanlunStrategy(BaseStrategy):
    """缠论策略实现"""
    
    def __init__(self, name: str = "chanlun", params: dict | None = None):
        super().__init__(name, params)
        
        # 缠论参数
        self.min_bi_length = params.get('min_bi_length', 5)        # 最小笔长度
        self.zhongshu_count = params.get('zhongshu_count', 3)      # 构成中枢的笔数
        self.confirm_bars = params.get('confirm_bars', 3)          # 确认K线数
        self.third_buy_threshold = params.get('third_buy_threshold', 0.02)  # 第三类买点阈值
        self.chanlun_indicator = ChanlunIndicator(
            min_bi_length=self.min_bi_length,
            zhongshu_count=self.zhongshu_count,
        )
        
        # 缠论结构存储
        self.fractals: List[Fractal] = []      # 分型列表
        self.chan_bis: List[ChanBi] = []       # 笔列表
        self.zhongshus: List[ZhongShu] = []    # 中枢列表
        self.last_signal: Optional[Signal] = None
        
    def on_init(self) -> None:
        """策略初始化"""
        super().on_init()
        print(f"缠论策略参数: 最小笔长={self.min_bi_length}, 中枢笔数={self.zhongshu_count}")
        print(f"确认K线数={self.confirm_bars}, 三买阈值={self.third_buy_threshold*100:.1f}%")
        
    def check_third_buy_point(self, current_bar: Bar) -> Optional[Signal]:
        """检查第三类买点"""
        if not self.zhongshus or not self.chan_bis:
            return None
            
        # 获取最后一个中枢
        latest_zhongshu = self.zhongshus[-1]
        
        # 检查是否有离开中枢的向下笔
        leaving_bi = None
        for bi in reversed(self.chan_bis):
            if (bi.direction == ChanBiDirection.DOWN and 
                bi.start_fractal.price > latest_zhongshu.high):
                leaving_bi = bi
                break
        
        if not leaving_bi:
            return None
            
        # 检查是否形成回调买点
        current_price = current_bar.close
        if (current_price > latest_zhongshu.high and 
            current_price < leaving_bi.start_fractal.price and
            (leaving_bi.start_fractal.price - current_price) / leaving_bi.start_fractal.price >= self.third_buy_threshold):
            
            signal = Signal(
                code=current_bar.code,
                dt=current_bar.dt,
                signal_type=SignalType.BUY,
                price=current_price,
                strength=0.9,
                reason=f"缠论第三类买点: 价格{current_price:.2f}回调至中枢上方"
            )
            
            return signal
        
        return None
    
    def check_bottom_fractal_signal(self, current_bar: Bar) -> Optional[Signal]:
        """检查底分型买入信号"""
        if not self.fractals:
            return None
            
        latest_fractal = self.fractals[-1]
        
        # 确认是底分型且已经确认
        if (latest_fractal.type == FractalType.BOTTOM and 
            len(self.history_bars) - 1 - latest_fractal.bar_index >= self.confirm_bars):
            
            # 检查是否创新低后反弹
            recent_bars = self.history_bars[max(0, latest_fractal.bar_index-5):latest_fractal.bar_index+1]
            if len(recent_bars) >= 3:
                min_price_before = min(bar.low for bar in recent_bars[:-1])
                if latest_fractal.price <= min_price_before * 1.01:  # 接近前期低点
                    
                    signal = Signal(
                        code=current_bar.code,
                        dt=current_bar.dt,
                        signal_type=SignalType.BUY,
                        price=current_bar.close,
                        strength=0.7,
                        reason=f"缠论底分型: 价格{latest_fractal.price:.2f}形成底部反转"
                    )
                    
                    return signal
        
        return None
    
    def on_bar(self, bar: Bar) -> Signal | None:
        """每根K线执行策略逻辑"""
        # 更新数据
        self.add_bar(bar)
        
        if len(self.history_bars) < 10:
            return None
            
        # 识别分型
        self.fractals = self.chanlun_indicator.find_valid_fractals(self.history_bars)
        
        # 构建笔
        self.chan_bis = self.chanlun_indicator.build_chan_bis(self.fractals)
        
        # 识别中枢
        self.zhongshus = self.chanlun_indicator.identify_zhongshu(self.chan_bis)
        
        # 检查第三类买点
        third_buy_signal = self.check_third_buy_point(bar)
        if third_buy_signal:
            return third_buy_signal
            
        # 检查底分型信号
        bottom_signal = self.check_bottom_fractal_signal(bar)
        if bottom_signal:
            return bottom_signal
            
        return None
    
    def get_chanlun_analysis(self) -> dict:
        """获取缠论分析结果"""
        return {
            'fractals_count': len(self.fractals),
            'bis_count': len(self.chan_bis),
            'zhongshus_count': len(self.zhongshus),
            'latest_fractal': self.fractals[-1] if self.fractals else None,
            'latest_bi': self.chan_bis[-1] if self.chan_bis else None,
            'latest_zhongshu': self.zhongshus[-1] if self.zhongshus else None
        }
    
    def on_stop(self) -> None:
        """策略停止"""
        self.fractals.clear()
        self.chan_bis.clear()
        self.zhongshus.clear()
        self.last_signal = None
        super().on_stop()


# 快捷创建函数
def create_chanlun_strategy(params: dict | None = None) -> ChanlunStrategy:
    """创建缠论策略实例"""
    default_params = {
        'min_bi_length': 5,
        'zhongshu_count': 3,
        'confirm_bars': 3,
        'third_buy_threshold': 0.02
    }
    
    if params:
        default_params.update(params)
        
    return ChanlunStrategy("chanlun", default_params)
