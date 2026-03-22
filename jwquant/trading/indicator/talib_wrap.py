"""
Talib 指标封装
封装 TA-Lib 库常用指标：SMA、EMA、MACD、RSI、ATR、KDJ、布林带等。
"""
import numpy as np
import pandas as pd
try:
    import talib
except ImportError:
    talib = None
    print("Warning: TA-Lib not installed. Please install with: pip install TA-Lib")

from typing import Union


class TechnicalIndicators:
    """技术指标计算器"""
    
    @staticmethod
    def sma(data: Union[pd.Series, np.ndarray], period: int) -> np.ndarray:
        """简单移动平均线 (Simple Moving Average)"""
        if talib:
            return talib.SMA(np.array(data), timeperiod=period)
        else:
            # 手动实现
            return pd.Series(data).rolling(window=period).mean().values
    
    @staticmethod
    def ema(data: Union[pd.Series, np.ndarray], period: int) -> np.ndarray:
        """指数移动平均线 (Exponential Moving Average)"""
        if talib:
            return talib.EMA(np.array(data), timeperiod=period)
        else:
            # 手动实现
            return pd.Series(data).ewm(span=period).mean().values
    
    @staticmethod
    def macd(data: Union[pd.Series, np.ndarray], fast_period: int = 12, 
             slow_period: int = 26, signal_period: int = 9):
        """MACD指标"""
        if talib:
            macd_line, signal_line, hist = talib.MACD(
                np.array(data), 
                fastperiod=fast_period, 
                slowperiod=slow_period, 
                signalperiod=signal_period
            )
            return macd_line, signal_line, hist
        else:
            # 手动实现
            ema_fast = pd.Series(data).ewm(span=fast_period).mean()
            ema_slow = pd.Series(data).ewm(span=slow_period).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=signal_period).mean()
            hist = macd_line - signal_line
            return macd_line.values, signal_line.values, hist.values
    
    @staticmethod
    def rsi(data: Union[pd.Series, np.ndarray], period: int = 14) -> np.ndarray:
        """相对强弱指数 (Relative Strength Index)"""
        if talib:
            return talib.RSI(np.array(data), timeperiod=period)
        else:
            # 手动实现
            delta = pd.Series(data).diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.values
    
    @staticmethod
    def atr(high: Union[pd.Series, np.ndarray], low: Union[pd.Series, np.ndarray], 
            close: Union[pd.Series, np.ndarray], period: int = 14) -> np.ndarray:
        """平均真实波幅 (Average True Range)"""
        if talib:
            return talib.ATR(np.array(high), np.array(low), np.array(close), timeperiod=period)
        else:
            # 手动实现
            df = pd.DataFrame({
                'high': high,
                'low': low,
                'close': close
            })
            tr0 = df['high'] - df['low']
            tr1 = abs(df['high'] - df['close'].shift())
            tr2 = abs(df['low'] - df['close'].shift())
            tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean()
            return atr.values
    
    @staticmethod
    def bollinger_bands(data: Union[pd.Series, np.ndarray], period: int = 20, 
                       nbdev_up: int = 2, nbdev_dn: int = 2):
        """布林带 (Bollinger Bands)"""
        if talib:
            upper, middle, lower = talib.BBANDS(
                np.array(data), 
                timeperiod=period, 
                nbdevup=nbdev_up, 
                nbdevdn=nbdev_dn
            )
            return upper, middle, lower
        else:
            # 手动实现
            series = pd.Series(data)
            middle = series.rolling(window=period).mean()
            std = series.rolling(window=period).std()
            upper = middle + (std * nbdev_up)
            lower = middle - (std * nbdev_dn)
            return upper.values, middle.values, lower.values
    
    @staticmethod
    def kdj(high: Union[pd.Series, np.ndarray], low: Union[pd.Series, np.ndarray], 
            close: Union[pd.Series, np.ndarray], fastk_period: int = 9, 
            slowk_period: int = 3, slowd_period: int = 3):
        """KDJ随机指标"""
        if talib:
            k, d = talib.STOCH(
                np.array(high), np.array(low), np.array(close),
                fastk_period=fastk_period,
                slowk_period=slowk_period,
                slowk_matype=0,
                slowd_period=slowd_period,
                slowd_matype=0
            )
            j = 3 * k - 2 * d
            return k, d, j
        else:
            # 手动实现
            df = pd.DataFrame({
                'high': high,
                'low': low,
                'close': close
            })
            
            # 计算RSV
            low_min = df['low'].rolling(window=fastk_period).min()
            high_max = df['high'].rolling(window=fastk_period).max()
            rsv = (df['close'] - low_min) / (high_max - low_min) * 100
            
            # 计算K值
            k = rsv.ewm(alpha=1/slowk_period).mean()
            # 计算D值
            d = k.ewm(alpha=1/slowd_period).mean()
            # 计算J值
            j = 3 * k - 2 * d
            
            return k.values, d.values, j.values
    
    @staticmethod
    def donchian_channel(high: Union[pd.Series, np.ndarray], 
                        low: Union[pd.Series, np.ndarray], 
                        period: int = 20):
        """唐奇安通道 (Donchian Channel)"""
        df = pd.DataFrame({
            'high': high,
            'low': low
        })
        
        upper = df['high'].rolling(window=period).max()
        lower = df['low'].rolling(window=period).min()
        middle = (upper + lower) / 2
        
        return upper.values, middle.values, lower.values
    
    @staticmethod
    def adx(high: Union[pd.Series, np.ndarray], low: Union[pd.Series, np.ndarray], 
            close: Union[pd.Series, np.ndarray], period: int = 14) -> np.ndarray:
        """平均趋向指数 (Average Directional Index)"""
        if talib:
            return talib.ADX(np.array(high), np.array(low), np.array(close), timeperiod=period)
        else:
            # 简化手动实现
            df = pd.DataFrame({
                'high': high,
                'low': low,
                'close': close
            })
            
            # 计算+DM和-DM
            up_move = df['high'].diff()
            down_move = -df['low'].diff()
            
            # 计算真实波幅
            tr = TechnicalIndicators.atr(high, low, close, period)
            
            # 计算+DI和-DI
            plus_di = 100 * (up_move.rolling(period).mean() / pd.Series(tr).rolling(period).mean())
            minus_di = 100 * (down_move.rolling(period).mean() / pd.Series(tr).rolling(period).mean())
            
            # 计算ADX
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
            adx = dx.rolling(period).mean()
            
            return adx.values


# 便捷函数
def calculate_indicators(df: pd.DataFrame, indicators: list) -> pd.DataFrame:
    """批量计算多个技术指标
    
    Args:
        df: 包含OHLCV数据的DataFrame
        indicators: 指标配置列表，如 [('sma', 20), ('ema', 12), ('rsi', 14)]
    
    Returns:
        添加了指标列的新DataFrame
    """
    result_df = df.copy()
    ti = TechnicalIndicators()
    
    for indicator in indicators:
        if isinstance(indicator, tuple):
            name, param = indicator[0], indicator[1:]
        else:
            name, param = indicator, ()
            
        if name == 'sma':
            period = param[0] if param else 20
            result_df[f'sma_{period}'] = ti.sma(df['close'], period)
        elif name == 'ema':
            period = param[0] if param else 12
            result_df[f'ema_{period}'] = ti.ema(df['close'], period)
        elif name == 'rsi':
            period = param[0] if param else 14
            result_df[f'rsi_{period}'] = ti.rsi(df['close'], period)
        elif name == 'macd':
            fast, slow, signal = param if len(param) >= 3 else (12, 26, 9)
            macd_line, signal_line, hist = ti.macd(df['close'], fast, slow, signal)
            result_df['macd'] = macd_line
            result_df['macd_signal'] = signal_line
            result_df['macd_hist'] = hist
        elif name == 'bollinger':
            period, nbdev = param[:2] if len(param) >= 2 else (20, 2)
            upper, middle, lower = ti.bollinger_bands(df['close'], period, nbdev, nbdev)
            result_df['bb_upper'] = upper
            result_df['bb_middle'] = middle
            result_df['bb_lower'] = lower
        elif name == 'kdj':
            k, d, j = ti.kdj(df['high'], df['low'], df['close'])
            result_df['k'] = k
            result_df['d'] = d
            result_df['j'] = j
    
    return result_df