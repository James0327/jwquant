"""
缠论量化策略
笔/线段/中枢识别，底分型与第三类买点信号输出。
"""
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from jwquant.common.types import Bar, Signal, SignalType
from jwquant.trading.strategy.base import BaseStrategy


class FractalType(Enum):
    """分型类型"""
    TOP = "top"      # 顶分型
    BOTTOM = "bottom"  # 底分型
    NONE = "none"    # 无分型


class ChanBiDirection(Enum):
    """笔的方向"""
    UP = "up"      # 向上笔
    DOWN = "down"  # 向下笔


@dataclass
class Fractal:
    """分型结构"""
    type: FractalType
    bar_index: int
    price: float
    dt: object


@dataclass
class ChanBi:
    """缠论笔"""
    direction: ChanBiDirection
    start_fractal: Fractal
    end_fractal: Fractal
    start_index: int
    end_index: int


@dataclass
class ZhongShu:
    """中枢"""
    high: float
    low: float
    start_bi_index: int
    end_bi_index: int
    bi_count: int


class ChanlunStrategy(BaseStrategy):
    """缠论策略实现"""
    
    def __init__(self, name: str = "chanlun", params: dict | None = None):
        super().__init__(name, params)
        
        # 缠论参数
        self.min_bi_length = params.get('min_bi_length', 5)        # 最小笔长度
        self.zhongshu_count = params.get('zhongshu_count', 3)      # 构成中枢的笔数
        self.confirm_bars = params.get('confirm_bars', 3)          # 确认K线数
        self.third_buy_threshold = params.get('third_buy_threshold', 0.02)  # 第三类买点阈值
        
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
        
    def identify_fractal(self, bars: List[Bar]) -> Optional[Fractal]:
        """识别分型"""
        if len(bars) < 5:
            return None
            
        # 取中间的K线作为候选分型
        middle_idx = len(bars) - 3
        middle_bar = bars[middle_idx]
        
        # 获取前后各两根K线
        prev2_bar = bars[middle_idx - 2]
        prev1_bar = bars[middle_idx - 1]
        next1_bar = bars[middle_idx + 1]
        next2_bar = bars[middle_idx + 2]
        
        # 顶分型判断：中间K线最高价 > 前后K线最高价
        if (middle_bar.high > prev1_bar.high and 
            middle_bar.high > prev2_bar.high and
            middle_bar.high > next1_bar.high and
            middle_bar.high > next2_bar.high):
            
            # 确保是局部最高点
            if middle_bar.high >= max(prev1_bar.high, next1_bar.high):
                return Fractal(FractalType.TOP, middle_idx, middle_bar.high, middle_bar.dt)
        
        # 底分型判断：中间K线最低价 < 前后K线最低价
        elif (middle_bar.low < prev1_bar.low and 
              middle_bar.low < prev2_bar.low and
              middle_bar.low < next1_bar.low and
              middle_bar.low < next2_bar.low):
            
            # 确保是局部最低点
            if middle_bar.low <= min(prev1_bar.low, next1_bar.low):
                return Fractal(FractalType.BOTTOM, middle_idx, middle_bar.low, middle_bar.dt)
        
        return None
    
    def find_valid_fractals(self, bars: List[Bar]) -> List[Fractal]:
        """寻找有效的分型点"""
        fractals = []
        
        # 从第2根到倒数第2根K线寻找分型
        for i in range(2, len(bars) - 2):
            window = bars[i-2:i+3]  # 取5根K线窗口
            fractal = self.identify_fractal(window)
            if fractal:
                fractal.bar_index = i  # 更新实际索引
                fractals.append(fractal)
        
        # 过滤相邻的同类分型（保留更强的）
        filtered_fractals = []
        i = 0
        while i < len(fractals):
            current = fractals[i]
            filtered_fractals.append(current)
            
            # 跳过相邻的同类型分型
            j = i + 1
            while j < len(fractals) and fractals[j].type == current.type:
                j += 1
            i = j
        
        return filtered_fractals
    
    def build_chan_bis(self, fractals: List[Fractal]) -> List[ChanBi]:
        """构建缠论笔"""
        if len(fractals) < 2:
            return []
            
        bis = []
        i = 0
        
        while i < len(fractals) - 1:
            start_fractal = fractals[i]
            end_fractal = fractals[i + 1]
            
            # 检查笔的长度要求
            if abs(end_fractal.bar_index - start_fractal.bar_index) >= self.min_bi_length:
                # 确定笔的方向
                if end_fractal.type == FractalType.TOP:
                    direction = ChanBiDirection.UP
                else:
                    direction = ChanBiDirection.DOWN
                    
                bi = ChanBi(
                    direction=direction,
                    start_fractal=start_fractal,
                    end_fractal=end_fractal,
                    start_index=start_fractal.bar_index,
                    end_index=end_fractal.bar_index
                )
                bis.append(bi)
                i += 1
            else:
                i += 1
        
        return bis
    
    def identify_zhongshu(self, bis: List[ChanBi]) -> List[ZhongShu]:
        """识别中枢"""
        zhongshus = []
        
        if len(bis) < self.zhongshu_count:
            return zhongshus
            
        # 寻找连续同向的笔组合
        for i in range(len(bis) - self.zhongshu_count + 1):
            # 取连续的几笔
            candidate_bis = bis[i:i + self.zhongshu_count]
            
            # 检查是否满足中枢条件
            if self.is_valid_zhongshu(candidate_bis):
                # 计算中枢区间
                high = min(bi.end_fractal.price for bi in candidate_bis)
                low = max(bi.start_fractal.price for bi in candidate_bis)
                
                if high > low:  # 有效中枢
                    zhongshu = ZhongShu(
                        high=high,
                        low=low,
                        start_bi_index=i,
                        end_bi_index=i + self.zhongshu_count - 1,
                        bi_count=self.zhongshu_count
                    )
                    zhongshus.append(zhongshu)
        
        return zhongshus
    
    def is_valid_zhongshu(self, bis: List[ChanBi]) -> bool:
        """判断是否构成有效中枢"""
        if len(bis) < 3:
            return False
            
        # 检查是否交替上升下降
        directions = [bi.direction for bi in bis]
        for i in range(1, len(directions)):
            if directions[i] == directions[i-1]:
                return False  # 相邻笔方向相同，不符合中枢定义
        
        return True
    
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
        self.fractals = self.find_valid_fractals(self.history_bars)
        
        # 构建笔
        self.chan_bis = self.build_chan_bis(self.fractals)
        
        # 识别中枢
        self.zhongshus = self.identify_zhongshu(self.chan_bis)
        
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