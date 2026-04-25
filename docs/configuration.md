# JWQuant 配置说明

这份文档以 [settings.common.toml](/Users/james/PycharmProjects/jwquant/config/settings.common.toml)、[settings.live.toml](/Users/james/PycharmProjects/jwquant/config/settings.live.toml) 和 [settings.test.toml](/Users/james/PycharmProjects/jwquant/config/settings.test.toml) 为准，说明当前主要配置项的用途、取值语义和敏感项建议。

## 1. 读取方式

项目当前通过 [config.py](/Users/james/PycharmProjects/jwquant/jwquant/common/config.py) 加载配置。

支持两种加载方式：

- `Config()` 或 `load_config()` 默认加载 `config/settings.common.toml` + `config/settings.live.toml`
- `Config(profile="test")` 或 `load_config(profile="test")` 显式加载测试配置
- 测试需要临时目录时，通过 `config_dir` 参数显式传入

示例：

```python
from jwquant.common.config import Config, load_config

live_config = Config()
test_config = Config(profile="test")
load_config(profile="test", config_dir="/tmp/jwquant-config")
```

建议：

- 公用项放入 `settings.common.toml`
- 实盘差异项放入 `settings.live.toml`
- 测试差异项放入 `settings.test.toml`
- 真实账号、Token 等敏感值不要提交到公共仓库

## 2. 项目基础配置

### `[project]`

- `name`
  - 项目名称
- `version`
  - 项目版本号，用于标识当前配置与代码的大致对应关系

## 3. 券商连接配置

### `[broker.xtquant.stock]`

股票账户连接 QMT 所需配置。

- `account_type`
  - 固定为 `STOCK`
- `path`
  - 本机 QMT 股票账户目录，通常是 `userdata_mini`
  - 路径错误时通常无法连接终端
- `account_id`
  - 股票资金账号
  - 需与 `path` 指向的终端环境一致

### `[broker.xtquant.futures]`

期货账户连接 QMT 所需配置。

- `account_type`
  - 固定为 `FUTURE`
- `path`
  - 本机 QMT 期货账户目录
- `account_id`
  - 期货资金账号

敏感项建议：

- `account_id` 不建议直接提交真实值到公共仓库
- 生产或共享环境应使用本地私有配置文件维护真实值

## 4. 数据配置

### `[data.tushare]`

- `token`
  - Tushare Token
  - 留空表示当前不启用 Tushare 数据源
  - 建议仅写入本地私有配置文件，避免提交真实值

### `[data.akshare]`

- `enabled`
  - AkShare 数据源总开关
  - 当前主要用于股票历史研究、补数和对账场景
- `default_adjust`
  - AkShare 默认复权方式
  - 当前建议保持 `none`

当前建议：

- 不要把 `AkShare qfq/hfq` 作为统一回测复权主链来源
- `AkShare none` 可用于研究与补数

### `[data.source_policy.*]`

这组配置用于定义不同场景下的数据源优先级。

当前已经按以下维度组织：

- 市场：`stock / futures`
- 用途：`research / backtest / repair / reconciliation`
- 周期分组：`daily / weekly / monthly / intraday`

关键行为说明：

- `download_data.py`
  - 仍然是显式入口
  - 不会自动按 `source policy` 改写调用方指定的 `--source`
- `run_backtest.py`
  - 本地缺数据时会按 `source policy` 尝试补数
- `stock + backtest + qfq/hfq`
  - 当前会在 policy 层自动过滤掉 `AkShare`
  - 只允许支持统一复权主链的 source 参与候选

### `[data.store]`

本地行情和因子存储配置。

- `path`
  - 本地数据根目录
  - 行情、因子、rocksdb 等文件都会落在这个目录下
- `format`
  - 本地存储格式
  - 当前可选：`csv / sqlite / rocksdb / hdf5`

建议理解：

- `csv`
  - 便于直接查看和排查
- `sqlite`
  - 便于轻量查询
- `rocksdb`
  - 更适合较大规模 KV 存储
- `hdf5`
  - 适合本地分析和历史数据文件化

## 5. LLM 配置

### `[llm]`

- `provider`
  - 当前使用的模型提供方
  - 常见值：`openai / qwen / local`
- `api_key`
  - 对应 provider 的 API Key
  - 建议通过环境变量提供
- `model`
  - 默认模型名
  - 应填写该 provider 下真实可用的模型 id

## 6. 通用风险配置

### `[risk]`

这组配置更偏通用风控和策略侧默认限制。

- `max_position_pct`
  - 单票最大仓位占比
  - `0.2` 表示单只标的最多占账户权益 20%
  - `1.0` 表示最多占满账户权益
- `max_daily_drawdown`
  - 单日最大回撤比例
  - `0.05` 表示单日回撤达到 5% 触发限制
- `max_order_amount`
  - 单笔最大金额
  - 单位为账户计价货币
- `blacklist`
  - 黑名单关键词列表
  - 常用于过滤 `ST / *ST` 一类标的

## 7. 回测成本配置

### `[backtest.cost]`

这组配置控制回测里和金额直接相关的默认参数。

- `commission_rate`
  - 佣金费率
  - 当前回测口径：佣金 = 成交额 × `commission_rate`
  - `0.0003` 表示万分之三
- `slippage`
  - 滑点比例
  - 当前口径：买入上浮、卖出下浮
  - `0.0001` 表示万分之一
- `max_order_value`
  - broker 层估算单笔可下金额时的第一层上限
  - `0` 或负数表示关闭 broker 层这一额外限制
- `futures_margin_rate`
  - 期货保证金率
  - `0.12` 表示按合约名义金额的 12% 估算保证金
- `futures_contract_multiplier`
  - 期货合约乘数
  - 用于估算名义金额、保证金和盈亏

注意：

- 当前回测仍是最小成本模型
- 还没有单独引入印花税、最低佣金、分市场差异手续费

## 8. 回测风控配置

### `[backtest.risk]`

这组配置用于回测主链里的统一风控。

- `max_total_exposure`
  - 组合总暴露上限
  - `1.0` 表示总暴露最多等于账户权益
  - `0.8` 表示最多使用 80% 权益
  - `0` 或负数表示关闭
- `max_single_weight`
  - 单标的权重上限
  - `1.0` 表示单标的最多 100%
  - `0.3` 表示单标的最多 30%
  - `0` 或负数表示关闭
- `max_futures_margin_ratio`
  - 期货保证金占权益上限
  - `1.0` 表示最多占满权益
  - `0.5` 表示最多占 50%
- `max_holdings`
  - 最大持仓标的数
  - `0` 表示关闭
- `max_order_amount`
  - 统一单笔下单金额上限
  - 单位为账户计价货币
  - `0` 或负数表示关闭
- `stop_loss_pct`
  - 统一固定止损比例
  - `0.05` 表示亏损 5% 触发退出
- `take_profit_pct`
  - 统一固定止盈比例
  - `0.1` 表示盈利 10% 触发退出
- `trailing_stop_pct`
  - 统一移动止损比例
  - `0.08` 表示从持仓最高有利价回撤 8% 触发退出
- `max_drawdown_pct`
  - 统一最大回撤止损比例
  - `0.12` 表示组合从净值高点回撤 12% 触发退出
- `conflict_policy`
  - 风控规则冲突时的仲裁策略
  - 当前仅支持 `priority_first`

### `[backtest.risk.rule_priorities]`

这组配置控制规则优先级。

规则：

- 数字越小，优先级越高
- 当多条规则冲突时，会优先采用更高优先级规则

例如：

- `10` 会先于 `20`
- `20` 会先于 `50`

## 9. 执行前风控配置

### `[execution.risk]`

这组配置用于执行前统一校验。

- `max_total_exposure`
  - 执行前组合总暴露上限
- `max_single_weight`
  - 执行前单标的权重上限
- `max_futures_margin_ratio`
  - 执行前期货保证金占权益上限
- `max_holdings`
  - 执行前最大持仓标的数
- `max_order_amount`
  - 执行前统一单笔下单金额上限
- `allow_futures_long`
  - 是否允许期货开多
- `allow_futures_short`
  - 是否允许期货开空
- `conflict_policy`
  - 冲突仲裁策略，当前仅支持 `priority_first`

这组配置和回测风控配置相似，但目标不同：

- `backtest.risk` 作用于回测主链
- `execution.risk` 作用于真实执行前的统一风控入口

## 10. 日志配置

### `[log]`

- `level`
  - 日志级别
  - `DEBUG` 最详细
  - `INFO` 为常规运行
  - `WARNING / ERROR` 逐步收紧输出
- `enable_file`
  - 是否输出到文件
- `log_dir`
  - 日志目录
- `enable_json`
  - 是否使用 JSON 日志格式
  - `true` 更适合日志采集
  - `false` 更适合人工查看

## 11. 通知配置

### `[notification]`

- `enabled`
  - 通知总开关
- `channels`
  - 默认启用的通知渠道列表
- `rate_limit_enabled`
  - 是否开启速率限制
- `max_messages_per_minute`
  - 每分钟最大消息数

### `[notification.routing]`

定义不同级别消息默认发往哪些渠道。

例如：

- `INFO`
- `WARNING`
- `ERROR`
- `CRITICAL`

### `[notification.wechat]`

- `provider`
  - 当前支持的微信通知提供方，如 `serverchan / pushplus`
- `token`
  - 对应渠道 token
  - 建议通过环境变量或外部密钥管理提供

### `[notification.dingtalk]`

- `webhook`
  - 钉钉机器人地址
- `secret`
  - 签名密钥

建议：

- 不要把真实 `webhook` 和 `secret` 提交到公共仓库

### `[notification.email]`

- `smtp_server`
  - SMTP 服务地址
- `smtp_port`
  - SMTP 端口
  - `587` 常用于 TLS
  - `465` 常用于 SSL
- `username`
  - SMTP 用户名
- `password`
  - SMTP 密码或授权码
- `from_addr`
  - 发件人地址
- `to_addrs`
  - 收件人列表
- `use_tls`
  - 是否启用 TLS

## 12. 敏感项建议

下列字段建议优先通过环境变量提供，不要直接写入共享仓库配置：

- `broker.xtquant.stock.account_id`
- `broker.xtquant.futures.account_id`
- `data.tushare.token`
- `llm.api_key`
- `notification.wechat.token`
- `notification.dingtalk.webhook`
- `notification.dingtalk.secret`
- `notification.email.username`
- `notification.email.password`

## 13. 相关入口

配置加载实现：

- [config.py](/Users/james/PycharmProjects/jwquant/jwquant/common/config.py)

最常用配置消费入口：

- [run_backtest.py](/Users/james/PycharmProjects/jwquant/scripts/run_backtest.py)
- [risk.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/risk.py)
- [engine.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/engine.py)
