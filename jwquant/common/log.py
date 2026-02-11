"""
结构化日志

分级日志记录，支持：
- 控制台输出（人类可读格式）
- 按日滚动文件输出（可选 JSON 结构化格式）
- 分类日志器（交易/策略/智能体/系统）
- @log_elapsed 性能计时装饰器
- 运行时动态调整日志级别
"""
import functools
import json
import logging
import logging.handlers
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

_CONSOLE_FMT = "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"
_CONSOLE_DATEFMT = "%Y-%m-%d %H:%M:%S"


class JSONFormatter(logging.Formatter):
    """JSON 结构化日志格式器，适用于日志聚合系统（ELK / Splunk 等）。"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc)
                         .strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        # 将用户通过 extra 传入的字段一并输出
        for key in ("code", "order_id", "direction", "price", "volume",
                     "elapsed", "event_type"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        return json.dumps(log_entry, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Handler factories
# ---------------------------------------------------------------------------

def _make_console_handler(level: int) -> logging.StreamHandler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_CONSOLE_FMT, datefmt=_CONSOLE_DATEFMT))
    handler.setLevel(level)
    return handler


def _make_file_handler(
    name: str,
    log_dir: str | Path = "logs",
    json_format: bool = False,
    level: int = logging.DEBUG,
    backup_count: int = 30,
) -> logging.handlers.TimedRotatingFileHandler:
    """创建按日滚动的文件处理器。

    文件命名：logs/{name}.log，轮转后自动追加日期后缀。
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    filepath = log_path / f"{name}.log"

    handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(filepath),
        when="midnight",
        interval=1,
        backupCount=backup_count,
        encoding="utf-8",
    )
    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(_CONSOLE_FMT, datefmt=_CONSOLE_DATEFMT))
    handler.setLevel(level)
    return handler


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def get_logger(
    name: str,
    level: int = logging.INFO,
    enable_file: bool = False,
    json_format: bool = False,
    log_dir: str | Path = "logs",
) -> logging.Logger:
    """获取命名日志器。

    Args:
        name: 日志器名称（如 "jwquant.trade"）。
        level: 日志级别。
        enable_file: 是否启用文件输出（按日滚动）。
        json_format: 文件日志是否使用 JSON 格式。
        log_dir: 日志文件目录。

    Returns:
        配置好的 Logger 实例。
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.addHandler(_make_console_handler(level))

    if enable_file:
        # 使用最后一段名称作为文件名（如 "jwquant.trade" -> "trade"）
        file_name = name.rsplit(".", 1)[-1] if "." in name else name
        logger.addHandler(_make_file_handler(file_name, log_dir, json_format, level))

    return logger


# ---------------------------------------------------------------------------
# Category logger shortcuts
# ---------------------------------------------------------------------------

def _read_log_config() -> tuple[bool, bool, str]:
    """从 config 模块读取日志配置，失败时使用默认值。"""
    try:
        from jwquant.common import config
        enable_file = config.get_bool("log.enable_file", True)
        enable_json = config.get_bool("log.enable_json", False)
        log_dir = config.get_str("log.log_dir", "logs")
    except Exception:
        enable_file, enable_json, log_dir = True, False, "logs"
    return enable_file, enable_json, log_dir


def get_trade_logger() -> logging.Logger:
    """交易日志器 - 记录订单提交、成交、撤单。"""
    ef, ej, ld = _read_log_config()
    return get_logger("jwquant.trade", enable_file=ef, json_format=ej, log_dir=ld)


def get_strategy_logger() -> logging.Logger:
    """策略日志器 - 记录信号生成、仓位变化。"""
    ef, ej, ld = _read_log_config()
    return get_logger("jwquant.strategy", enable_file=ef, json_format=ej, log_dir=ld)


def get_agent_logger() -> logging.Logger:
    """智能体日志器 - 记录决策流程、工作流状态。"""
    ef, ej, ld = _read_log_config()
    return get_logger("jwquant.agent", enable_file=ef, json_format=ej, log_dir=ld)


def get_system_logger() -> logging.Logger:
    """系统日志器 - 记录启动、配置变更、异常。"""
    ef, ej, ld = _read_log_config()
    return get_logger("jwquant.system", enable_file=ef, json_format=ej, log_dir=ld)


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

def log_elapsed(logger: logging.Logger | None = None, level: int = logging.INFO):
    """装饰器：自动记录函数执行耗时。

    Usage::

        @log_elapsed()
        def heavy_computation():
            ...

        @log_elapsed(get_strategy_logger(), logging.DEBUG)
        def calc_indicators(df):
            ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            _logger = logger or get_logger("jwquant.perf")
            start = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                elapsed = time.perf_counter() - start
                _logger.log(level, "%s completed in %.3fs", fn.__name__, elapsed)
                return result
            except Exception:
                elapsed = time.perf_counter() - start
                _logger.error("%s failed after %.3fs", fn.__name__, elapsed, exc_info=True)
                raise
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Dynamic level adjustment
# ---------------------------------------------------------------------------

def set_log_level(name: str, level: int) -> None:
    """运行时动态调整指定日志器的级别。

    Args:
        name: 日志器名称（如 "jwquant.trade"）。
        level: 新的日志级别（如 logging.DEBUG）。
    """
    target = logging.getLogger(name)
    target.setLevel(level)
    for handler in target.handlers:
        handler.setLevel(level)
