"""
缠论指标

分型、笔、中枢的识别与分析逻辑。
"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from jwquant.common.types import Bar


class FractalType(Enum):
    """分型类型"""
    TOP = "top"
    BOTTOM = "bottom"
    NONE = "none"


class ChanBiDirection(Enum):
    """笔的方向"""
    UP = "up"
    DOWN = "down"


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


class ChanlunIndicator:
    """缠论结构识别器"""

    def __init__(self, min_bi_length: int = 5, zhongshu_count: int = 3):
        self.min_bi_length = min_bi_length
        self.zhongshu_count = zhongshu_count

    def identify_fractal(self, bars: List[Bar]) -> Optional[Fractal]:
        """识别分型"""
        if len(bars) < 5:
            return None

        middle_idx = len(bars) - 3
        middle_bar = bars[middle_idx]

        prev2_bar = bars[middle_idx - 2]
        prev1_bar = bars[middle_idx - 1]
        next1_bar = bars[middle_idx + 1]
        next2_bar = bars[middle_idx + 2]

        if (
            middle_bar.high > prev1_bar.high
            and middle_bar.high > prev2_bar.high
            and middle_bar.high > next1_bar.high
            and middle_bar.high > next2_bar.high
        ):
            if middle_bar.high >= max(prev1_bar.high, next1_bar.high):
                return Fractal(FractalType.TOP, middle_idx, middle_bar.high, middle_bar.dt)

        if (
            middle_bar.low < prev1_bar.low
            and middle_bar.low < prev2_bar.low
            and middle_bar.low < next1_bar.low
            and middle_bar.low < next2_bar.low
        ):
            if middle_bar.low <= min(prev1_bar.low, next1_bar.low):
                return Fractal(FractalType.BOTTOM, middle_idx, middle_bar.low, middle_bar.dt)

        return None

    def find_valid_fractals(self, bars: List[Bar]) -> List[Fractal]:
        """寻找有效分型"""
        fractals: List[Fractal] = []

        for i in range(2, len(bars) - 2):
            window = bars[i - 2:i + 3]
            fractal = self.identify_fractal(window)
            if fractal:
                fractal.bar_index = i
                fractals.append(fractal)

        filtered_fractals: List[Fractal] = []
        i = 0
        while i < len(fractals):
            current = fractals[i]
            filtered_fractals.append(current)

            j = i + 1
            while j < len(fractals) and fractals[j].type == current.type:
                j += 1
            i = j

        return filtered_fractals

    def build_chan_bis(self, fractals: List[Fractal]) -> List[ChanBi]:
        """构建缠论笔"""
        if len(fractals) < 2:
            return []

        bis: List[ChanBi] = []
        i = 0

        while i < len(fractals) - 1:
            start_fractal = fractals[i]
            end_fractal = fractals[i + 1]

            if abs(end_fractal.bar_index - start_fractal.bar_index) >= self.min_bi_length:
                direction = ChanBiDirection.UP if end_fractal.type == FractalType.TOP else ChanBiDirection.DOWN
                bis.append(
                    ChanBi(
                        direction=direction,
                        start_fractal=start_fractal,
                        end_fractal=end_fractal,
                        start_index=start_fractal.bar_index,
                        end_index=end_fractal.bar_index,
                    )
                )
            i += 1

        return bis

    def identify_zhongshu(self, bis: List[ChanBi]) -> List[ZhongShu]:
        """识别中枢"""
        zhongshus: List[ZhongShu] = []
        if len(bis) < self.zhongshu_count:
            return zhongshus

        for i in range(len(bis) - self.zhongshu_count + 1):
            candidate_bis = bis[i:i + self.zhongshu_count]
            if self.is_valid_zhongshu(candidate_bis):
                high = min(bi.end_fractal.price for bi in candidate_bis)
                low = max(bi.start_fractal.price for bi in candidate_bis)
                if high > low:
                    zhongshus.append(
                        ZhongShu(
                            high=high,
                            low=low,
                            start_bi_index=i,
                            end_bi_index=i + self.zhongshu_count - 1,
                            bi_count=self.zhongshu_count,
                        )
                    )

        return zhongshus

    @staticmethod
    def is_valid_zhongshu(bis: List[ChanBi]) -> bool:
        """判断是否构成有效中枢"""
        if len(bis) < 3:
            return False

        directions = [bi.direction for bi in bis]
        for i in range(1, len(directions)):
            if directions[i] == directions[i - 1]:
                return False

        return True


__all__ = [
    "ChanBi",
    "ChanBiDirection",
    "ChanlunIndicator",
    "Fractal",
    "FractalType",
    "ZhongShu",
]
