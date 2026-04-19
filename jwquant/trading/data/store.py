"""
本地数据存储

提供面向 DataFrame 的本地行情存储能力，当前内置支持：
- CSV：便于直接检查文件内容
- SQLite：便于按条件查询和增量更新
- RocksDB：便于高性能 KV 存取（基于 rocksdict）
- HDF5：与现有配置默认值保持兼容（依赖 pandas 的 HDF5 支持）

说明：
- 所有存储格式都统一使用 ``code/market/dt/open/high/low/close/volume/amount/open_interest`` 列。
- 写入时会自动标准化时间列、排序并按 ``market + code + dt`` 去重。
- 目前不强制依赖 RocksDB；如后续需要可在此基础上扩展。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Literal

import pandas as pd
from rocksdict import Rdict

from jwquant.common.config import get


StoreFormat = Literal["csv", "sqlite", "rocksdb", "hdf5"]

REQUIRED_COLUMNS = ["code", "market", "dt", "open", "high", "low", "close", "volume"]
ALL_COLUMNS = REQUIRED_COLUMNS + ["amount", "open_interest"]
FACTOR_COLUMNS = ["code", "market", "dt", "factor_data"]


class LocalDataStore:
    """本地行情存储。

    以 ``code`` 和 ``timeframe`` 作为逻辑分区键，向上提供统一的
    ``save/upsert/load`` 接口，屏蔽底层文件格式差异。
    """

    def __init__(
        self,
        base_path: str | Path | None = None,
        fmt: str | None = None,
    ) -> None:
        self.base_path = Path(base_path or get("data.store.path")).expanduser()
        self.fmt: StoreFormat = self._normalize_format(fmt or get("data.store.format"))
        self.base_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _normalize_format(fmt: str) -> StoreFormat:
        normalized = str(fmt).strip().lower()
        if normalized not in {"csv", "sqlite", "rocksdb", "hdf5"}:
            raise ValueError(f"unsupported data store format: {fmt}")
        return normalized  # type: ignore[return-value]

    @staticmethod
    def _sanitize_code(code: str) -> str:
        return code.replace("/", "_").replace("\\", "_")

    @staticmethod
    def _normalize_timeframe(timeframe: str) -> str:
        return timeframe.strip().lower().replace("/", "_")

    @staticmethod
    def _normalize_bars(
        bars: pd.DataFrame,
        default_code: str | None = None,
        default_market: str | None = None,
    ) -> pd.DataFrame:
        if bars.empty:
            return pd.DataFrame(columns=ALL_COLUMNS)

        df = bars.copy()
        if "datetime" in df.columns and "dt" not in df.columns:
            df = df.rename(columns={"datetime": "dt"})
        if "ts_code" in df.columns and "code" not in df.columns:
            df = df.rename(columns={"ts_code": "code"})

        if "code" not in df.columns:
            if not default_code:
                raise ValueError("bars must contain column 'code' or provide default_code")
            df["code"] = default_code

        if "market" not in df.columns:
            if not default_market:
                raise ValueError("bars must contain column 'market' or provide default_market")
            df["market"] = default_market

        missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
        if missing:
            raise ValueError(f"bars missing required columns: {missing}")

        if "amount" not in df.columns:
            df["amount"] = 0.0
        if "open_interest" not in df.columns:
            df["open_interest"] = 0.0

        df = df[ALL_COLUMNS].copy()
        df["dt"] = pd.to_datetime(df["dt"])
        df["market"] = df["market"].astype(str).str.lower()
        df = df.sort_values(["market", "code", "dt"]).drop_duplicates(
            subset=["market", "code", "dt"], keep="last"
        )
        return df.reset_index(drop=True)

    @staticmethod
    def _normalize_market(market: str) -> str:
        normalized = str(market).strip().lower()
        if not normalized:
            raise ValueError("market must not be empty")
        return normalized

    def _csv_path(self, code: str, timeframe: str, market: str) -> Path:
        return (
            self.base_path
            / "csv"
            / self._normalize_market(market)
            / self._normalize_timeframe(timeframe)
            / f"{self._sanitize_code(code)}.csv"
        )

    def _hdf5_path(self, timeframe: str, market: str) -> Path:
        return self.base_path / "hdf5" / self._normalize_market(market) / f"{self._normalize_timeframe(timeframe)}.h5"

    def _sqlite_path(self, market: str) -> Path:
        return self.base_path / "sqlite" / self._normalize_market(market) / "market_data.sqlite3"

    def _rocksdb_path(self, timeframe: str, market: str) -> Path:
        return self.base_path / "rocksdb" / self._normalize_market(market) / self._normalize_timeframe(timeframe)

    def _hdf5_key(self, code: str) -> str:
        return f"bars/{self._sanitize_code(code)}"

    def _hdf5_factor_key(self, code: str) -> str:
        return f"factors/{self._sanitize_code(code)}"

    def _rocksdb_data_key(self, code: str, dt: pd.Timestamp) -> str:
        return f"bar:{code}:{pd.Timestamp(dt).isoformat()}"

    def _rocksdb_codes_key(self) -> str:
        return "__codes__"

    def _rocksdb_code_index_key(self, code: str) -> str:
        return f"__code_keys__:{code}"

    def _rocksdb_factor_codes_key(self) -> str:
        return "__factor_codes__"

    def _rocksdb_factor_index_key(self, code: str) -> str:
        return f"__factor_keys__:{code}"

    def _rocksdb_factor_data_key(self, code: str, dt: pd.Timestamp) -> str:
        return f"factor:{code}:{pd.Timestamp(dt).isoformat()}"

    def _open_rocksdb(self, timeframe: str, market: str) -> Rdict:
        path = self._rocksdb_path(timeframe, market)
        path.parent.mkdir(parents=True, exist_ok=True)
        return Rdict(str(path))

    def _init_sqlite(self, market: str) -> None:
        db_path = self._sqlite_path(market)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bars (
                    code TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    dt TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    amount REAL NOT NULL DEFAULT 0,
                    open_interest REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY (code, timeframe, dt)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_bars_lookup ON bars (code, timeframe, dt)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS adjust_factors (
                    code TEXT NOT NULL,
                    dt TEXT NOT NULL,
                    factor_data TEXT NOT NULL,
                    PRIMARY KEY (code, dt)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_factors_lookup ON adjust_factors (code, dt)"
            )

    @staticmethod
    def _normalize_factors(
        factors: pd.DataFrame,
        default_code: str | None = None,
        default_market: str | None = None,
    ) -> pd.DataFrame:
        if factors.empty:
            return pd.DataFrame(columns=FACTOR_COLUMNS)

        df = factors.copy()
        if "datetime" in df.columns and "dt" not in df.columns:
            df = df.rename(columns={"datetime": "dt"})

        if "code" not in df.columns:
            if not default_code:
                raise ValueError("factors must contain column 'code' or provide default_code")
            df["code"] = default_code
        if "market" not in df.columns:
            if not default_market:
                raise ValueError("factors must contain column 'market' or provide default_market")
            df["market"] = default_market

        if "dt" not in df.columns:
            if df.index.name or not isinstance(df.index, pd.RangeIndex):
                df = df.reset_index().rename(columns={df.index.name or "index": "dt"})
            else:
                raise ValueError("factors must contain column 'dt' or datetime-like index")

        extra_cols = [col for col in df.columns if col not in {"code", "market", "dt", "factor_data"}]
        if "factor_data" not in df.columns:
            df["factor_data"] = df[extra_cols].to_dict(orient="records")
        else:
            df["factor_data"] = df["factor_data"].apply(
                lambda value: value if isinstance(value, dict) else {"value": value}
            )

        normalized = df[FACTOR_COLUMNS].copy()
        normalized["dt"] = pd.to_datetime(normalized["dt"])
        normalized["market"] = normalized["market"].astype(str).str.lower()
        normalized = normalized.sort_values(["market", "code", "dt"]).drop_duplicates(
            subset=["market", "code", "dt"], keep="last"
        )
        return normalized.reset_index(drop=True)

    def save_adjust_factors(self, code: str, factors: pd.DataFrame, market: str = "stock") -> int:
        normalized_market = self._normalize_market(market)
        df = self._normalize_factors(factors, default_code=code, default_market=normalized_market)
        if self.fmt == "csv":
            return self._save_factors_csv(code, normalized_market, df)
        if self.fmt == "sqlite":
            self._init_sqlite(normalized_market)
            return self._save_factors_sqlite(code, normalized_market, df, replace=True)
        if self.fmt == "rocksdb":
            return self._save_factors_rocksdb(code, normalized_market, df, replace=True)
        return self._save_factors_hdf5(code, normalized_market, df)

    def upsert_adjust_factors(self, code: str, factors: pd.DataFrame, market: str = "stock") -> int:
        normalized_market = self._normalize_market(market)
        df = self._normalize_factors(factors, default_code=code, default_market=normalized_market)
        if self.fmt == "csv":
            return self._upsert_factors_csv(code, normalized_market, df)
        if self.fmt == "sqlite":
            self._init_sqlite(normalized_market)
            return self._save_factors_sqlite(code, normalized_market, df, replace=False)
        if self.fmt == "rocksdb":
            return self._save_factors_rocksdb(code, normalized_market, df, replace=False)
        return self._upsert_factors_hdf5(code, normalized_market, df)

    def load_adjust_factors(
        self,
        code: str,
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
        market: str = "stock",
    ) -> pd.DataFrame:
        normalized_market = self._normalize_market(market)
        if self.fmt == "csv":
            df = self._load_factors_csv(code, normalized_market)
        elif self.fmt == "sqlite":
            df = self._load_factors_sqlite(code, normalized_market, start, end)
        elif self.fmt == "rocksdb":
            df = self._load_factors_rocksdb(code, normalized_market)
        else:
            df = self._load_factors_hdf5(code, normalized_market)

        if df.empty:
            return pd.DataFrame(columns=["code", "market", "dt"])
        if self.fmt != "sqlite":
            df = self._filter_by_date(df, start, end)
        return self._expand_factor_data(df.reset_index(drop=True))

    def get_latest_factor_dt(self, code: str, market: str = "stock") -> pd.Timestamp | None:
        normalized_market = self._normalize_market(market)
        if self.fmt == "csv":
            return self._get_latest_factor_dt_csv(code, normalized_market)
        if self.fmt == "sqlite":
            return self._get_latest_factor_dt_sqlite(code, normalized_market)
        if self.fmt == "rocksdb":
            return self._get_latest_factor_dt_rocksdb(code, normalized_market)
        return self._get_latest_factor_dt_hdf5(code, normalized_market)

    @staticmethod
    def _expand_factor_data(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=["code", "market", "dt"])
        expanded = pd.json_normalize(df["factor_data"])
        result = pd.concat([df[["code", "market", "dt"]].reset_index(drop=True), expanded.reset_index(drop=True)], axis=1)
        return result

    def save_bars(self, code: str, bars: pd.DataFrame, timeframe: str = "1d", market: str = "stock") -> int:
        """覆盖保存指定标的的 K 线数据。"""
        normalized_market = self._normalize_market(market)
        df = self._normalize_bars(bars, default_code=code, default_market=normalized_market)
        if self.fmt == "csv":
            return self._save_csv(code, timeframe, normalized_market, df)
        if self.fmt == "sqlite":
            self._init_sqlite(normalized_market)
            return self._save_sqlite(code, timeframe, normalized_market, df, replace=True)
        if self.fmt == "rocksdb":
            return self._save_rocksdb(code, timeframe, normalized_market, df, replace=True)
        return self._save_hdf5(code, timeframe, normalized_market, df)

    def upsert_bars(self, code: str, bars: pd.DataFrame, timeframe: str = "1d", market: str = "stock") -> int:
        """增量写入，按 ``code + dt`` 去重更新。"""
        normalized_market = self._normalize_market(market)
        df = self._normalize_bars(bars, default_code=code, default_market=normalized_market)
        if self.fmt == "csv":
            return self._upsert_csv(code, timeframe, normalized_market, df)
        if self.fmt == "sqlite":
            self._init_sqlite(normalized_market)
            return self._save_sqlite(code, timeframe, normalized_market, df, replace=False)
        if self.fmt == "rocksdb":
            return self._save_rocksdb(code, timeframe, normalized_market, df, replace=False)
        return self._upsert_hdf5(code, timeframe, normalized_market, df)

    def load_bars(
        self,
        code: str,
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
        timeframe: str = "1d",
        market: str = "stock",
    ) -> pd.DataFrame:
        """按代码和时间范围读取 K 线数据。"""
        normalized_market = self._normalize_market(market)
        if self.fmt == "csv":
            df = self._load_csv(code, timeframe, normalized_market)
        elif self.fmt == "sqlite":
            df = self._load_sqlite(code, timeframe, normalized_market, start, end)
        elif self.fmt == "rocksdb":
            df = self._load_rocksdb(code, timeframe, normalized_market)
        else:
            df = self._load_hdf5(code, timeframe, normalized_market)

        if df.empty:
            return pd.DataFrame(columns=ALL_COLUMNS)

        if self.fmt not in {"sqlite"}:
            df = self._filter_by_date(df, start, end)

        return df.reset_index(drop=True)

    def has_data(self, code: str, timeframe: str = "1d", market: str = "stock") -> bool:
        """判断本地是否已有对应行情。"""
        return not self.load_bars(code, timeframe=timeframe, market=market).empty

    def get_latest_dt(
        self,
        code: str,
        timeframe: str = "1d",
        market: str = "stock",
    ) -> pd.Timestamp | None:
        """获取本地已有数据的最新时间。"""
        normalized_market = self._normalize_market(market)
        if self.fmt == "csv":
            return self._get_latest_dt_csv(code, timeframe, normalized_market)
        if self.fmt == "sqlite":
            return self._get_latest_dt_sqlite(code, timeframe, normalized_market)
        if self.fmt == "rocksdb":
            return self._get_latest_dt_rocksdb(code, timeframe, normalized_market)
        return self._get_latest_dt_hdf5(code, timeframe, normalized_market)

    def list_codes(self, timeframe: str = "1d", market: str = "stock") -> list[str]:
        """列出指定周期下已有数据的标的代码。"""
        normalized_timeframe = self._normalize_timeframe(timeframe)
        normalized_market = self._normalize_market(market)
        if self.fmt == "csv":
            root = self.base_path / "csv" / normalized_market / normalized_timeframe
            if not root.exists():
                return []
            return sorted(path.stem for path in root.glob("*.csv"))

        if self.fmt == "sqlite":
            db_path = self._sqlite_path(normalized_market)
            if not db_path.exists():
                return []
            with sqlite3.connect(db_path) as conn:
                rows = conn.execute(
                    "SELECT DISTINCT code FROM bars ORDER BY code",
                ).fetchall()
            return [row[0] for row in rows]

        if self.fmt == "rocksdb":
            db = self._open_rocksdb(timeframe, normalized_market)
            try:
                return sorted(db.get(self._rocksdb_codes_key(), []))
            finally:
                db.close()

        path = self._hdf5_path(timeframe, normalized_market)
        if not path.exists():
            return []
        with pd.HDFStore(path, mode="r") as store:
            return sorted(key.split("/")[-1] for key in store.keys())

    @staticmethod
    def _filter_by_date(
        df: pd.DataFrame,
        start: str | pd.Timestamp | None,
        end: str | pd.Timestamp | None,
    ) -> pd.DataFrame:
        result = df.copy()
        if start is not None:
            result = result[result["dt"] >= pd.to_datetime(start)]
        if end is not None:
            result = result[result["dt"] <= pd.to_datetime(end)]
        return result.sort_values(["market", "code", "dt"])

    def _save_csv(self, code: str, timeframe: str, market: str, df: pd.DataFrame) -> int:
        path = self._csv_path(code, timeframe, market)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
        return len(df)

    def _upsert_csv(self, code: str, timeframe: str, market: str, df: pd.DataFrame) -> int:
        existing = self._load_csv(code, timeframe, market)
        merged = df if existing.empty else pd.concat([existing, df], ignore_index=True)
        normalized = self._normalize_bars(merged, default_code=code, default_market=market)
        return self._save_csv(code, timeframe, market, normalized)

    def _load_csv(self, code: str, timeframe: str, market: str) -> pd.DataFrame:
        path = self._csv_path(code, timeframe, market)
        if not path.exists():
            return pd.DataFrame(columns=ALL_COLUMNS)
        df = pd.read_csv(path, parse_dates=["dt"])
        return self._normalize_bars(df, default_code=code, default_market=market)

    def _get_latest_dt_csv(self, code: str, timeframe: str, market: str) -> pd.Timestamp | None:
        path = self._csv_path(code, timeframe, market)
        if not path.exists():
            return None
        df = pd.read_csv(path, usecols=["dt"], parse_dates=["dt"])
        if df.empty:
            return None
        return pd.Timestamp(df["dt"].max())

    def _factor_csv_path(self, code: str, market: str) -> Path:
        return self.base_path / "csv" / self._normalize_market(market) / "factors" / f"{self._sanitize_code(code)}.csv"

    def _save_factors_csv(self, code: str, market: str, df: pd.DataFrame) -> int:
        path = self._factor_csv_path(code, market)
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = df.copy()
        serialized["factor_data"] = serialized["factor_data"].apply(json.dumps)
        serialized.to_csv(path, index=False)
        return len(serialized)

    def _upsert_factors_csv(self, code: str, market: str, df: pd.DataFrame) -> int:
        existing = self._load_factors_csv(code, market)
        merged = df if existing.empty else pd.concat([existing, df], ignore_index=True)
        normalized = self._normalize_factors(merged, default_code=code, default_market=market)
        return self._save_factors_csv(code, market, normalized)

    def _load_factors_csv(self, code: str, market: str) -> pd.DataFrame:
        path = self._factor_csv_path(code, market)
        if not path.exists():
            return pd.DataFrame(columns=FACTOR_COLUMNS)
        df = pd.read_csv(path, parse_dates=["dt"])
        df["factor_data"] = df["factor_data"].apply(json.loads)
        return self._normalize_factors(df, default_code=code, default_market=market)

    def _get_latest_factor_dt_csv(self, code: str, market: str) -> pd.Timestamp | None:
        path = self._factor_csv_path(code, market)
        if not path.exists():
            return None
        df = pd.read_csv(path, usecols=["dt"], parse_dates=["dt"])
        if df.empty:
            return None
        return pd.Timestamp(df["dt"].max())

    def _save_sqlite(self, code: str, timeframe: str, market: str, df: pd.DataFrame, replace: bool) -> int:
        normalized_timeframe = self._normalize_timeframe(timeframe)
        rows = [
            (
                row.code,
                normalized_timeframe,
                row.dt.isoformat(),
                float(row.open),
                float(row.high),
                float(row.low),
                float(row.close),
                float(row.volume),
                float(row.amount),
                float(row.open_interest),
            )
            for row in df.itertuples(index=False)
        ]
        with sqlite3.connect(self._sqlite_path(market)) as conn:
            if replace:
                conn.execute(
                    "DELETE FROM bars WHERE code = ? AND timeframe = ?",
                    (code, normalized_timeframe),
                )
            conn.executemany(
                """
                INSERT INTO bars (
                    code, timeframe, dt, open, high, low, close, volume, amount, open_interest
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code, timeframe, dt) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume,
                    amount = excluded.amount,
                    open_interest = excluded.open_interest
                """,
                rows,
            )
        return len(df)

    def _load_sqlite(
        self,
        code: str,
        timeframe: str,
        market: str,
        start: str | pd.Timestamp | None,
        end: str | pd.Timestamp | None,
    ) -> pd.DataFrame:
        sql = """
            SELECT code, ? as market, dt, open, high, low, close, volume, amount, open_interest
            FROM bars
            WHERE code = ? AND timeframe = ?
        """
        params: list[object] = [market, code, self._normalize_timeframe(timeframe)]

        if start is not None:
            sql += " AND dt >= ?"
            params.append(pd.to_datetime(start).isoformat())
        if end is not None:
            sql += " AND dt <= ?"
            params.append(pd.to_datetime(end).isoformat())

        sql += " ORDER BY dt"
        with sqlite3.connect(self._sqlite_path(market)) as conn:
            df = pd.read_sql_query(sql, conn, params=params, parse_dates=["dt"])
        if df.empty:
            return pd.DataFrame(columns=ALL_COLUMNS)
        return self._normalize_bars(df, default_code=code, default_market=market)

    def _get_latest_dt_sqlite(self, code: str, timeframe: str, market: str) -> pd.Timestamp | None:
        db_path = self._sqlite_path(market)
        if not db_path.exists():
            return None
        sql = "SELECT MAX(dt) AS latest_dt FROM bars WHERE code = ? AND timeframe = ?"
        params = (code, self._normalize_timeframe(timeframe))
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(sql, params).fetchone()
        if not row or not row[0]:
            return None
        return pd.Timestamp(row[0])

    def _save_factors_sqlite(self, code: str, market: str, df: pd.DataFrame, replace: bool) -> int:
        rows = [
            (
                row.code,
                row.dt.isoformat(),
                json.dumps(row.factor_data, ensure_ascii=True),
            )
            for row in df.itertuples(index=False)
        ]
        with sqlite3.connect(self._sqlite_path(market)) as conn:
            if replace:
                conn.execute("DELETE FROM adjust_factors WHERE code = ?", (code,))
            conn.executemany(
                """
                INSERT INTO adjust_factors (code, dt, factor_data)
                VALUES (?, ?, ?)
                ON CONFLICT(code, dt) DO UPDATE SET
                    factor_data = excluded.factor_data
                """,
                rows,
            )
        return len(rows)

    def _load_factors_sqlite(
        self,
        code: str,
        market: str,
        start: str | pd.Timestamp | None,
        end: str | pd.Timestamp | None,
    ) -> pd.DataFrame:
        sql = "SELECT code, ? as market, dt, factor_data FROM adjust_factors WHERE code = ?"
        params: list[object] = [market, code]
        if start is not None:
            sql += " AND dt >= ?"
            params.append(pd.to_datetime(start).isoformat())
        if end is not None:
            sql += " AND dt <= ?"
            params.append(pd.to_datetime(end).isoformat())
        sql += " ORDER BY dt"
        with sqlite3.connect(self._sqlite_path(market)) as conn:
            df = pd.read_sql_query(sql, conn, params=params, parse_dates=["dt"])
        if df.empty:
            return pd.DataFrame(columns=FACTOR_COLUMNS)
        df["factor_data"] = df["factor_data"].apply(json.loads)
        return self._normalize_factors(df, default_code=code, default_market=market)

    def _get_latest_factor_dt_sqlite(self, code: str, market: str) -> pd.Timestamp | None:
        db_path = self._sqlite_path(market)
        if not db_path.exists():
            return None
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT MAX(dt) FROM adjust_factors WHERE code = ?", (code,)).fetchone()
        if not row or not row[0]:
            return None
        return pd.Timestamp(row[0])

    def _save_hdf5(self, code: str, timeframe: str, market: str, df: pd.DataFrame) -> int:
        path = self._hdf5_path(timeframe, market)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            df.to_hdf(path, key=self._hdf5_key(code), mode="a", format="table", index=False)
        except ImportError as exc:
            raise RuntimeError("hdf5 storage requires pytables support") from exc
        return len(df)

    def _upsert_hdf5(self, code: str, timeframe: str, market: str, df: pd.DataFrame) -> int:
        existing = self._load_hdf5(code, timeframe, market)
        merged = df if existing.empty else pd.concat([existing, df], ignore_index=True)
        normalized = self._normalize_bars(merged, default_code=code, default_market=market)
        return self._save_hdf5(code, timeframe, market, normalized)

    def _load_hdf5(self, code: str, timeframe: str, market: str) -> pd.DataFrame:
        path = self._hdf5_path(timeframe, market)
        if not path.exists():
            return pd.DataFrame(columns=ALL_COLUMNS)
        try:
            df = pd.read_hdf(path, key=self._hdf5_key(code))
        except (KeyError, FileNotFoundError):
            return pd.DataFrame(columns=ALL_COLUMNS)
        except ImportError as exc:
            raise RuntimeError("hdf5 storage requires pytables support") from exc
        return self._normalize_bars(df, default_code=code, default_market=market)

    def _get_latest_dt_hdf5(self, code: str, timeframe: str, market: str) -> pd.Timestamp | None:
        df = self._load_hdf5(code, timeframe, market)
        if df.empty:
            return None
        return pd.Timestamp(df["dt"].max())

    def _save_factors_hdf5(self, code: str, market: str, df: pd.DataFrame) -> int:
        path = self.base_path / "hdf5" / self._normalize_market(market) / "factors.h5"
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = df.copy()
        serialized["factor_data"] = serialized["factor_data"].apply(json.dumps)
        try:
            serialized.to_hdf(path, key=self._hdf5_factor_key(code), mode="a", format="table", index=False)
        except ImportError as exc:
            raise RuntimeError("hdf5 storage requires pytables support") from exc
        return len(serialized)

    def _upsert_factors_hdf5(self, code: str, market: str, df: pd.DataFrame) -> int:
        existing = self._load_factors_hdf5(code, market)
        merged = df if existing.empty else pd.concat([existing, df], ignore_index=True)
        normalized = self._normalize_factors(merged, default_code=code, default_market=market)
        return self._save_factors_hdf5(code, market, normalized)

    def _load_factors_hdf5(self, code: str, market: str) -> pd.DataFrame:
        path = self.base_path / "hdf5" / self._normalize_market(market) / "factors.h5"
        if not path.exists():
            return pd.DataFrame(columns=FACTOR_COLUMNS)
        try:
            df = pd.read_hdf(path, key=self._hdf5_factor_key(code))
        except (KeyError, FileNotFoundError):
            return pd.DataFrame(columns=FACTOR_COLUMNS)
        except ImportError as exc:
            raise RuntimeError("hdf5 storage requires pytables support") from exc
        df["factor_data"] = df["factor_data"].apply(json.loads)
        return self._normalize_factors(df, default_code=code, default_market=market)

    def _get_latest_factor_dt_hdf5(self, code: str, market: str) -> pd.Timestamp | None:
        df = self._load_factors_hdf5(code, market)
        if df.empty:
            return None
        return pd.Timestamp(df["dt"].max())

    def _save_rocksdb(self, code: str, timeframe: str, market: str, df: pd.DataFrame, replace: bool) -> int:
        db = self._open_rocksdb(timeframe, market)
        try:
            if replace:
                self._delete_rocksdb_code(db, code)

            code_keys = set(db.get(self._rocksdb_code_index_key(code), []))
            for row in df.itertuples(index=False):
                key = self._rocksdb_data_key(row.code, row.dt)
                db[key] = {
                    "code": row.code,
                    "dt": pd.Timestamp(row.dt).isoformat(),
                    "open": float(row.open),
                    "high": float(row.high),
                    "low": float(row.low),
                    "close": float(row.close),
                    "volume": float(row.volume),
                    "amount": float(row.amount),
                    "market": str(row.market),
                    "open_interest": float(row.open_interest),
                }
                code_keys.add(key)

            existing_codes = set(db.get(self._rocksdb_codes_key(), []))
            existing_codes.add(code)
            db[self._rocksdb_codes_key()] = sorted(existing_codes)
            db[self._rocksdb_code_index_key(code)] = sorted(code_keys)
        finally:
            db.close()
        return len(df)

    def _load_rocksdb(self, code: str, timeframe: str, market: str) -> pd.DataFrame:
        path = self._rocksdb_path(timeframe, market)
        if not path.exists():
            return pd.DataFrame(columns=ALL_COLUMNS)

        db = self._open_rocksdb(timeframe, market)
        try:
            keys = db.get(self._rocksdb_code_index_key(code), [])
            rows = [db[key] for key in keys if key in db]
        finally:
            db.close()

        if not rows:
            return pd.DataFrame(columns=ALL_COLUMNS)
        return self._normalize_bars(pd.DataFrame(rows), default_code=code, default_market=market)

    def _get_latest_dt_rocksdb(self, code: str, timeframe: str, market: str) -> pd.Timestamp | None:
        path = self._rocksdb_path(timeframe, market)
        if not path.exists():
            return None
        db = self._open_rocksdb(timeframe, market)
        try:
            keys = db.get(self._rocksdb_code_index_key(code), [])
        finally:
            db.close()
        if not keys:
            return None
        prefix = f"bar:{code}:"
        latest = max(pd.Timestamp(key[len(prefix):]) for key in keys)
        return latest

    def _save_factors_rocksdb(self, code: str, market: str, df: pd.DataFrame, replace: bool) -> int:
        db = self._open_rocksdb("factors", market)
        try:
            if replace:
                self._delete_factor_code(db, code)
            factor_keys = set(db.get(self._rocksdb_factor_index_key(code), []))
            for row in df.itertuples(index=False):
                key = self._rocksdb_factor_data_key(row.code, row.dt)
                db[key] = {
                    "code": row.code,
                    "market": str(row.market),
                    "dt": pd.Timestamp(row.dt).isoformat(),
                    "factor_data": row.factor_data,
                }
                factor_keys.add(key)
            codes = set(db.get(self._rocksdb_factor_codes_key(), []))
            codes.add(code)
            db[self._rocksdb_factor_codes_key()] = sorted(codes)
            db[self._rocksdb_factor_index_key(code)] = sorted(factor_keys)
        finally:
            db.close()
        return len(df)

    def _load_factors_rocksdb(self, code: str, market: str) -> pd.DataFrame:
        path = self._rocksdb_path("factors", market)
        if not path.exists():
            return pd.DataFrame(columns=FACTOR_COLUMNS)
        db = self._open_rocksdb("factors", market)
        try:
            keys = db.get(self._rocksdb_factor_index_key(code), [])
            rows = [db[key] for key in keys if key in db]
        finally:
            db.close()
        if not rows:
            return pd.DataFrame(columns=FACTOR_COLUMNS)
        return self._normalize_factors(pd.DataFrame(rows), default_code=code, default_market=market)

    def _get_latest_factor_dt_rocksdb(self, code: str, market: str) -> pd.Timestamp | None:
        path = self._rocksdb_path("factors", market)
        if not path.exists():
            return None
        db = self._open_rocksdb("factors", market)
        try:
            keys = db.get(self._rocksdb_factor_index_key(code), [])
        finally:
            db.close()
        if not keys:
            return None
        prefix = f"factor:{code}:"
        return max(pd.Timestamp(key[len(prefix):]) for key in keys)

    def _delete_rocksdb_code(self, db: Rdict, code: str) -> None:
        keys_to_delete = list(db.get(self._rocksdb_code_index_key(code), []))
        for key in keys_to_delete:
            if key in db:
                del db[key]

        if keys_to_delete:
            if self._rocksdb_code_index_key(code) in db:
                del db[self._rocksdb_code_index_key(code)]
            codes = set(db.get(self._rocksdb_codes_key(), []))
            if code in codes:
                codes.remove(code)
                db[self._rocksdb_codes_key()] = sorted(codes)

    def _delete_factor_code(self, db: Rdict, code: str) -> None:
        keys_to_delete = list(db.get(self._rocksdb_factor_index_key(code), []))
        for key in keys_to_delete:
            if key in db:
                del db[key]
        if keys_to_delete:
            if self._rocksdb_factor_index_key(code) in db:
                del db[self._rocksdb_factor_index_key(code)]
            codes = set(db.get(self._rocksdb_factor_codes_key(), []))
            if code in codes:
                codes.remove(code)
                db[self._rocksdb_factor_codes_key()] = sorted(codes)
