"""
配置管理

统一加载和管理系统配置：券商参数、策略参数、风控阈值、LLM API Key 等。
支持 TOML 格式配置文件。
"""
import tomllib
from pathlib import Path
from typing import Any


_config: dict[str, Any] = {}


def load_config(config_path: str | Path = "config/settings.toml") -> dict[str, Any]:
    """加载配置文件"""
    global _config
    path = Path(config_path)
    if path.exists():
        with open(path, "rb") as f:
            _config = tomllib.load(f)
    return _config


def get(key: str, default: Any = None) -> Any:
    """获取配置项，支持点号分隔的路径（如 'broker.xtquant.path'）"""
    keys = key.split(".")
    value = _config
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k)
        else:
            return default
        if value is None:
            return default
    return value
