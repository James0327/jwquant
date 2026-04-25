"""
配置管理

统一加载和管理系统配置：券商参数、策略参数、风控阈值、LLM API Key 等。
支持 TOML 格式配置文件、多文件合并、敏感字段脱敏。
"""
import copy
import tomllib
from pathlib import Path
from typing import Any


_config: dict[str, Any] = {}

_SENSITIVE_KEYS = {"api_key", "token", "password", "secret", "account_id"}
_DEFAULT_CONFIG_DIR = "config"
_DEFAULT_CONFIG_PROFILE = "live"


class Config:
    """配置管理类，提供面向对象的配置访问接口。
    
    示例::
    
        config = Config()
        path = config.get("broker.xtquant.path")
        api_key = config.get("llm.api_key")
    """
    
    def __init__(self, profile: str | None = None, config_dir: str | Path = _DEFAULT_CONFIG_DIR):
        """初始化配置，如果尚未加载则自动加载。

        Args:
            profile: 配置环境名称。None 表示默认加载 live。
            config_dir: 分层配置目录，仅在首次自动加载时使用。
        """
        if not _config:
            load_config(profile=profile, config_dir=config_dir)
    
    def get(self, key: str) -> Any:
        """获取配置项，支持点号分隔的路径（如 'broker.xtquant.path'）。"""
        return get(key)
    
    def get_str(self, key: str) -> str:
        """获取字符串类型配置项。"""
        return get_str(key)
    
    def get_int(self, key: str) -> int:
        """获取整数类型配置项。"""
        return get_int(key)
    
    def get_float(self, key: str) -> float:
        """获取浮点数类型配置项。"""
        return get_float(key)
    
    def get_bool(self, key: str) -> bool:
        """获取布尔类型配置项。"""
        return get_bool(key)
    
    def get_all(self) -> dict[str, Any]:
        """返回完整配置字典。"""
        return get_all()
    
    def get_masked_config(self) -> dict[str, Any]:
        """返回脱敏后的配置字典副本。"""
        return get_masked_config()
    
    def reload(
        self,
        primary: str | Path | None = None,
        extra: list[str | Path] | None = None,
        profile: str | None = None,
        config_dir: str | Path = _DEFAULT_CONFIG_DIR,
    ) -> dict[str, Any]:
        """重新加载配置文件。
        
        Args:
            primary: 主配置文件路径。None 表示使用 profile 分层配置。
            extra: 额外配置文件列表
            profile: 配置环境名称，如 live/test。
            config_dir: 分层配置目录。
            
        Returns:
            加载后的配置字典
        """
        return reload_config(primary, extra, profile=profile, config_dir=config_dir)
    
    def validate(self) -> list[str]:
        """校验配置必填项和值范围。
        
        Returns:
            错误信息列表，空列表表示通过
        """
        return validate()


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


def _mask_value(key: str, value: Any) -> Any:
    """如果 key 属于敏感字段，返回脱敏后的值。"""
    if isinstance(value, dict):
        return {k: _mask_value(k, v) for k, v in value.items()}
    if key in _SENSITIVE_KEYS and isinstance(value, str) and value:
        return "***"
    return value


def _read_toml_file(path: Path) -> dict[str, Any]:
    """读取单个 TOML 配置文件。

    输入输出：
      - 输入：TOML 文件路径；
      - 输出：解析后的配置字典，不存在时返回空字典。

    设计原因：
      - 分层配置需要多次读取 common/profile/extra；
      - 统一封装可以保证缺失文件的处理口径一致。
    """
    if not path.exists():
        raise FileNotFoundError(f"config file does not exist: {path}")
    with open(path, "rb") as f:
        return tomllib.load(f)


def _resolve_profile(profile: str | None = None) -> str:
    """解析配置 profile。

    规则：
      - 调用方显式传入 profile 时使用该值；
      - 未传入时默认使用 live；
      - profile 不再从环境变量读取，避免命令行环境隐式改变交易配置。
    """
    resolved = str(profile or _DEFAULT_CONFIG_PROFILE).strip().lower()
    return resolved or _DEFAULT_CONFIG_PROFILE


def _resolve_config_dir(config_dir: str | Path = _DEFAULT_CONFIG_DIR) -> Path:
    """解析分层配置目录。

    输入输出：
      - 输入：调用方显式传入的配置目录，默认是项目内 config；
      - 输出：Path 对象，用于定位 settings.common.toml 和 settings.<profile>.toml。

    设计原因：
      - 配置目录不再从环境变量读取，避免测试、实盘或外部 shell 状态隐式改变加载路径；
      - 测试场景需要切换目录时，必须通过 config_dir 参数显式传入。
    """
    return Path(config_dir)


def _load_profile_config(
    profile: str | None = None,
    config_dir: str | Path = _DEFAULT_CONFIG_DIR,
) -> dict[str, Any]:
    """按 common + profile 的顺序加载分层配置。

    关键逻辑：
      1. 先加载 settings.common.toml，提供项目公共配置；
      2. 再加载 settings.<profile>.toml，覆盖实盘/测试差异项；
      3. 配置文件缺失直接抛错，避免静默使用错误环境。
    """
    config_dir = _resolve_config_dir(config_dir)
    resolved_profile = _resolve_profile(profile)
    common_path = config_dir / "settings.common.toml"
    profile_path = config_dir / f"settings.{resolved_profile}.toml"

    merged: dict[str, Any] = {}
    for path in (common_path, profile_path):
        merged = _deep_merge(merged, _read_toml_file(path))
    return merged


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config(
    primary: str | Path | None = None,
    extra: list[str | Path] | None = None,
    profile: str | None = None,
    config_dir: str | Path = _DEFAULT_CONFIG_DIR,
) -> dict[str, Any]:
    """加载配置文件并合并。

    Args:
        primary: 主配置文件路径。None 表示加载分层配置：
            settings.common.toml + settings.<profile>.toml。
        extra: 额外配置文件列表（如 strategies.toml），后加载的覆盖先加载的。
        profile: 配置环境名称。None 表示默认 live。
        config_dir: 分层配置目录，仅在 primary 为 None 时使用。

    Returns:
        合并后的完整配置字典。
    """
    global _config
    if primary is None:
        _config = _load_profile_config(profile, config_dir=config_dir)
    else:
        primary_path = Path(primary)
        _config = _read_toml_file(primary_path)

    for extra_path in (extra or []):
        p = Path(extra_path)
        _config = _deep_merge(_config, _read_toml_file(p))

    return _config


def _ensure_loaded() -> None:
    """在首次访问配置时自动加载默认配置文件。"""
    if not _config:
        load_config()


def _lookup(key: str, *, required: bool) -> Any:
    """按点号路径解析配置项。"""
    _ensure_loaded()
    keys = key.split(".")
    value = _config
    for k in keys:
        if not isinstance(value, dict) or k not in value:
            if required:
                raise KeyError(f"missing config key: {key}")
            return None
        value = value[k]
        if value is None:
            if required:
                raise KeyError(f"missing config key: {key}")
            return None
    return value


def get_strategy_config(strategy_name: str) -> dict:
    """获取指定策略的配置参数。"""
    strategies_config = get("strategies")
    if not isinstance(strategies_config, dict) or strategy_name not in strategies_config:
        raise KeyError(f"missing strategy config: strategies.{strategy_name}")
    strategy_config = strategies_config[strategy_name]
    if not isinstance(strategy_config, dict):
        raise TypeError(f"strategy config must be a mapping: strategies.{strategy_name}")
    return strategy_config


def get(key: str) -> Any:
    """获取配置项，支持点号分隔的路径（如 'broker.xtquant.path'）。"""
    return _lookup(key, required=True)


def get_str(key: str) -> str:
    """获取字符串类型配置项。"""
    value = get(key)
    return str(value)


def get_int(key: str) -> int:
    """获取整数类型配置项。"""
    value = get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        raise TypeError(f"config key {key} is not an int: {value!r}") from None


def get_float(key: str) -> float:
    """获取浮点数类型配置项。"""
    value = get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        raise TypeError(f"config key {key} is not a float: {value!r}") from None


def get_bool(key: str) -> bool:
    """获取布尔类型配置项。"""
    value = get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.lower()
        if normalized in ("true", "1", "yes"):
            return True
        if normalized in ("false", "0", "no"):
            return False
    raise TypeError(f"config key {key} is not a bool: {value!r}")


def get_all() -> dict[str, Any]:
    """返回完整配置字典（原始引用，勿直接修改）。"""
    return _config


def get_masked_config() -> dict[str, Any]:
    """返回脱敏后的配置字典副本，敏感字段显示为 '***'。"""
    return {k: _mask_value(k, v) for k, v in copy.deepcopy(_config).items()}


def validate() -> list[str]:
    """校验配置必填项和值范围，返回错误信息列表（空列表表示通过）。"""
    errors: list[str] = []
    _ensure_loaded()

    def maybe_get(key: str) -> Any:
        return _lookup(key, required=False)

    # 风控参数校验
    pct = maybe_get("risk.max_position_pct")
    if pct is not None and (not isinstance(pct, (int, float)) or not 0 < pct <= 1):
        errors.append(f"risk.max_position_pct must be in (0, 1], got {pct}")

    dd = maybe_get("risk.max_daily_drawdown")
    if dd is not None and (not isinstance(dd, (int, float)) or not 0 < dd <= 1):
        errors.append(f"risk.max_daily_drawdown must be in (0, 1], got {dd}")

    amount = maybe_get("risk.max_order_amount")
    if amount is not None and (not isinstance(amount, (int, float)) or amount <= 0):
        errors.append(f"risk.max_order_amount must be positive, got {amount}")

    # 券商路径校验（仅在有配置时校验）
    broker_path = maybe_get("broker.xtquant.path")
    if broker_path and not Path(broker_path).exists():
        errors.append(f"broker.xtquant.path does not exist: {broker_path}")

    return errors


def reload_config(
    primary: str | Path | None = None,
    extra: list[str | Path] | None = None,
    profile: str | None = None,
    config_dir: str | Path = _DEFAULT_CONFIG_DIR,
) -> dict[str, Any]:
    """重新加载配置文件（热重载）。"""
    return load_config(primary, extra, profile=profile, config_dir=config_dir)
