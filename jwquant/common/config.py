"""
配置管理

统一加载和管理系统配置：券商参数、策略参数、风控阈值、LLM API Key 等。
支持 TOML 格式配置文件、多文件合并、环境变量覆盖、敏感字段脱敏。
"""
import copy
import os
import tomllib
from pathlib import Path
from typing import Any


_config: dict[str, Any] = {}

_SENSITIVE_KEYS = {"api_key", "token", "password", "secret", "account_id"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    """递归深度合并两个字典，override 覆盖 base 的叶子节点。"""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _coerce_type(value: str) -> Any:
    """将环境变量字符串转换为合适的 Python 类型。"""
    if value.lower() in ("true", "1", "yes"):
        return True
    if value.lower() in ("false", "0", "no"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def _apply_env_overrides(config: dict) -> None:
    """扫描 JWQUANT_ 前缀的环境变量并覆盖配置项。

    环境变量格式：JWQUANT_SECTION__SUBSECTION__KEY=value
    映射规则：双下划线 ``__`` 作为层级分隔符，单下划线保留为键名的一部分。

    示例::

        JWQUANT_LLM__API_KEY=sk-xxx        → config["llm"]["api_key"]
        JWQUANT_BROKER__XTQUANT__PATH=/tmp  → config["broker"]["xtquant"]["path"]
        JWQUANT_RISK__MAX_POSITION_PCT=0.15 → config["risk"]["max_position_pct"]
    """
    prefix = "JWQUANT_"
    for env_key, env_val in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        # 双下划线分隔层级，单下划线保留
        parts = env_key[len(prefix):].lower().split("__")
        node = config
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = _coerce_type(env_val)


def _mask_value(key: str, value: Any) -> Any:
    """如果 key 属于敏感字段，返回脱敏后的值。"""
    if isinstance(value, dict):
        return {k: _mask_value(k, v) for k, v in value.items()}
    if key in _SENSITIVE_KEYS and isinstance(value, str) and value:
        return "***"
    return value


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config(
    primary: str | Path = "config/settings.toml",
    extra: list[str | Path] | None = None,
) -> dict[str, Any]:
    """加载配置文件并合并，最后应用环境变量覆盖。

    Args:
        primary: 主配置文件路径。
        extra: 额外配置文件列表（如 strategies.toml），后加载的覆盖先加载的。

    Returns:
        合并后的完整配置字典。
    """
    global _config
    path = Path(primary)
    if path.exists():
        with open(path, "rb") as f:
            _config = tomllib.load(f)
    else:
        _config = {}

    for extra_path in (extra or []):
        p = Path(extra_path)
        if p.exists():
            with open(p, "rb") as f:
                _config = _deep_merge(_config, tomllib.load(f))

    _apply_env_overrides(_config)
    return _config


def get(key: str, default: Any = None) -> Any:
    """获取配置项，支持点号分隔的路径（如 'broker.xtquant.path'）。"""
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


def get_str(key: str, default: str = "") -> str:
    """获取字符串类型配置项。"""
    value = get(key, default)
    return str(value) if value is not None else default


def get_int(key: str, default: int = 0) -> int:
    """获取整数类型配置项。"""
    value = get(key, default)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_float(key: str, default: float = 0.0) -> float:
    """获取浮点数类型配置项。"""
    value = get(key, default)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_bool(key: str, default: bool = False) -> bool:
    """获取布尔类型配置项。"""
    value = get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return default


def get_all() -> dict[str, Any]:
    """返回完整配置字典（原始引用，勿直接修改）。"""
    return _config


def get_masked_config() -> dict[str, Any]:
    """返回脱敏后的配置字典副本，敏感字段显示为 '***'。"""
    return {k: _mask_value(k, v) for k, v in copy.deepcopy(_config).items()}


def validate() -> list[str]:
    """校验配置必填项和值范围，返回错误信息列表（空列表表示通过）。"""
    errors: list[str] = []

    # 风控参数校验
    pct = get("risk.max_position_pct")
    if pct is not None and (not isinstance(pct, (int, float)) or not 0 < pct <= 1):
        errors.append(f"risk.max_position_pct must be in (0, 1], got {pct}")

    dd = get("risk.max_daily_drawdown")
    if dd is not None and (not isinstance(dd, (int, float)) or not 0 < dd <= 1):
        errors.append(f"risk.max_daily_drawdown must be in (0, 1], got {dd}")

    amount = get("risk.max_order_amount")
    if amount is not None and (not isinstance(amount, (int, float)) or amount <= 0):
        errors.append(f"risk.max_order_amount must be positive, got {amount}")

    # 券商路径校验（仅在有配置时校验）
    broker_path = get("broker.xtquant.path")
    if broker_path and not Path(broker_path).exists():
        errors.append(f"broker.xtquant.path does not exist: {broker_path}")

    return errors


def reload_config(
    primary: str | Path = "config/settings.toml",
    extra: list[str | Path] | None = None,
) -> dict[str, Any]:
    """重新加载配置文件（热重载）。"""
    return load_config(primary, extra)
