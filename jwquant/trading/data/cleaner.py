"""
数据清洗

处理停牌数据、除权除息（前复权/后复权）、缺失值填充、异常值检测。
"""
from __future__ import annotations

import pandas as pd

from jwquant.common.config import Config


PRICE_COLUMNS = ["open", "high", "low", "close"]
EXACT_FACTOR_COLUMNS = {"interest", "allotPrice", "allotNum", "stockBonus", "stockGift"}


class PriceAdjuster:
    """基于原始行情和复权因子生成前/后复权价格。

    优先使用 XtQuant 文档中的精确复权公式；
    当因子字段不完整但包含 ``dr`` 时，回退为等比复权。
    """

    def __init__(self, price_digits: int | None = None, config: Config | None = None) -> None:
        cfg = config or Config()
        configured_digits = cfg.get("data.adjust.price_digits")
        if price_digits is None:
            price_digits = 3 if configured_digits is None else int(configured_digits)
        if int(price_digits) < 0:
            raise ValueError("price_digits must be >= 0")
        self.price_digits = int(price_digits)

    def adjust(self, bars: pd.DataFrame, factors: pd.DataFrame, adj: str | None = None) -> pd.DataFrame:
        normalized_adj = self._normalize_adj(adj)
        if normalized_adj == "none" or bars.empty:
            return bars.copy()
        if factors.empty:
            return bars.copy()

        quote = bars.copy().sort_values("dt").reset_index(drop=True)
        factor = factors.copy().sort_values("dt").reset_index(drop=True)

        if self._supports_absolute_factor(factor, normalized_adj):
            return self._apply_absolute_factor(quote, factor, normalized_adj)
        if self._supports_exact(factor):
            return self._apply_exact(quote, factor, normalized_adj)
        if "dr" in factor.columns:
            return self._apply_ratio(quote, factor, normalized_adj)
        raise ValueError("adjust factors do not contain required fields for qfq/hfq calculation")

    @staticmethod
    def _normalize_adj(adj: str | None) -> str:
        if adj is None:
            return "none"
        normalized = str(adj).strip().lower()
        if normalized in {"none", ""}:
            return "none"
        if normalized in {"qfq", "front"}:
            return "qfq"
        if normalized in {"hfq", "back"}:
            return "hfq"
        raise ValueError(f"unsupported adjust type: {adj}")

    @staticmethod
    def _supports_exact(factors: pd.DataFrame) -> bool:
        return EXACT_FACTOR_COLUMNS.issubset(set(factors.columns))

    @staticmethod
    def _supports_absolute_factor(factors: pd.DataFrame, adj: str) -> bool:
        required = "qfq_factor" if adj == "qfq" else "hfq_factor"
        return required in factors.columns and factors[required].notna().any()

    def _apply_absolute_factor(self, bars: pd.DataFrame, factors: pd.DataFrame, adj: str) -> pd.DataFrame:
        result = bars.copy()
        factor_column = "qfq_factor" if adj == "qfq" else "hfq_factor"
        factor_series = factors[["dt", factor_column]].copy().dropna(subset=[factor_column])
        factor_series["dt"] = pd.to_datetime(factor_series["dt"])
        factor_series = factor_series.sort_values("dt").drop_duplicates(subset=["dt"], keep="last")
        aligned = factor_series.set_index("dt")[factor_column].astype(float)
        aligned = aligned.reindex(pd.to_datetime(result["dt"]), method="ffill")
        if aligned.isna().any():
            aligned = aligned.bfill().fillna(1.0)

        for column in PRICE_COLUMNS:
            base_values = result[column].astype(float).values
            if adj == "qfq":
                result[column] = (base_values / aligned.values).round(self.price_digits)
            else:
                result[column] = (base_values * aligned.values).round(self.price_digits)
        return result

    def _apply_exact(self, bars: pd.DataFrame, factors: pd.DataFrame, adj: str) -> pd.DataFrame:
        result = bars.copy()
        factor_rows = factors.sort_values("dt").to_dict(orient="records")

        for column in PRICE_COLUMNS:
            adjusted_values: list[float] = []
            for _, row in bars.iterrows():
                value = float(row[column])
                bar_dt = pd.Timestamp(row["dt"])
                if adj == "qfq":
                    for factor in factor_rows:
                        factor_dt = pd.Timestamp(factor["dt"])
                        if factor_dt <= bar_dt:
                            continue
                        value = self._calc_front(value, factor)
                else:
                    for factor in reversed(factor_rows):
                        factor_dt = pd.Timestamp(factor["dt"])
                        if factor_dt > bar_dt:
                            continue
                        value = self._calc_back(value, factor)
                adjusted_values.append(round(value, self.price_digits))
            result[column] = adjusted_values
        return result

    def _apply_ratio(self, bars: pd.DataFrame, factors: pd.DataFrame, adj: str) -> pd.DataFrame:
        result = bars.copy()
        factor_series = factors.sort_values("dt")[["dt", "dr"]].copy()
        factor_series["dt"] = pd.to_datetime(factor_series["dt"])
        factor_series = factor_series.set_index("dt")["dr"].astype(float).cumprod()

        ratio = factor_series.reindex(pd.to_datetime(result["dt"]), method="ffill").fillna(1.0)
        if adj == "qfq":
            ratio = ratio / ratio.iloc[-1]

        for column in PRICE_COLUMNS:
            result[column] = (result[column].astype(float).values * ratio.values).round(self.price_digits)
        return result

    @staticmethod
    def _calc_front(value: float, factor: dict) -> float:
        return (
            (
                value
                - float(factor.get("interest", 0.0))
                + float(factor.get("allotPrice", 0.0)) * float(factor.get("allotNum", 0.0))
            )
            / (
                1.0
                + float(factor.get("allotNum", 0.0))
                + float(factor.get("stockBonus", 0.0))
                + float(factor.get("stockGift", 0.0))
            )
        )

    @staticmethod
    def _calc_back(value: float, factor: dict) -> float:
        return (
            value
            * (
                1.0
                + float(factor.get("stockGift", 0.0))
                + float(factor.get("stockBonus", 0.0))
                + float(factor.get("allotNum", 0.0))
            )
            + float(factor.get("interest", 0.0))
            - float(factor.get("allotNum", 0.0)) * float(factor.get("allotPrice", 0.0))
        )
