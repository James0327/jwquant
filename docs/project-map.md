# JWQuant 项目导图

这份文档描述的是仓库的当前代码现状，不是目标蓝图。

如果你只想先搞清楚“现在这个仓库到底能做什么、哪些地方已经写了、哪些地方还只是设计”，读这一份就够了。

## 1. 一句话判断

这是一个“目标很大、当前实现集中在基础设施和策略实验”的量化交易仓库。

最成熟的部分是：

- 公共基础设施：配置、日志、事件、通知、共享类型
- 策略框架：策略基类、管理器、注册中心、多个策略实现
- 一部分演示脚本和单元测试

较多模块仍处于：

- 目录结构已规划
- 文件命名已确定
- 顶层 docstring 已写
- 具体业务实现尚未补齐

## 2. 顶层目录说明

### `config/`

项目配置，采用 TOML。

- `settings.toml`：系统总配置，含券商、数据源、LLM、日志、通知、风控
- `strategies.toml`：策略参数模板

### `jwquant/`

主源码包。按领域拆分，但“完成度不均衡”。

### `tests/`

测试目录，既有单元测试，也有依赖外部服务的联调脚本。

### `scripts/`

辅助脚本目录，包含：

- 简易回测脚本
- 多个策略的独立演示脚本
- 一些总结性 Markdown 文件

### `docs/`

文档目录。旧文档偏蓝图，新文档偏现状。

## 3. 包级别地图

| 包 | 作用 | 当前状态 |
| --- | --- | --- |
| `jwquant.common` | 通用基础设施 | 已实现较完整 |
| `jwquant.trading.strategy` | 策略抽象与具体策略 | 已实现较完整 |
| `jwquant.trading.indicator` | 技术指标封装 | 部分实现 |
| `jwquant.agent` | Agent 角色和流程编排 | 角色定义完整，执行流未落地 |
| `jwquant.trading.data` | 数据获取/清洗/存储 | 大多占位 |
| `jwquant.trading.backtest` | 回测与绩效分析 | 包内基本占位，脚本里有简易回测器 |
| `jwquant.trading.execution` | 下单执行 | 占位 |
| `jwquant.trading.risk` | 风控规则与拦截 | 占位 |
| `jwquant.research` | 投研、NLP、LLM | 目录齐全，代码多为占位 |
| `jwquant.ml` | 机器学习/RL | 占位 |
| `jwquant.mcp` | MCP 能力封装 | 占位 |
| `jwquant.dashboard` | Streamlit UI | 占位 |

## 4. 当前最值得读的代码

### `jwquant.common`

这是仓库里最像“可复用工程基础层”的部分。

关键文件：

- [jwquant/common/types.py](/Users/james/PycharmProjects/jwquant/jwquant/common/types.py)
- [jwquant/common/config.py](/Users/james/PycharmProjects/jwquant/jwquant/common/config.py)
- [jwquant/common/log.py](/Users/james/PycharmProjects/jwquant/jwquant/common/log.py)
- [jwquant/common/event.py](/Users/james/PycharmProjects/jwquant/jwquant/common/event.py)
- [jwquant/common/notifier.py](/Users/james/PycharmProjects/jwquant/jwquant/common/notifier.py)

这层解决的问题：

- 系统内共享的数据结构怎么统一表达
- 配置如何加载、合并、覆盖、校验
- 日志如何分层输出
- 模块之间如何通过发布订阅解耦
- 如何向微信、钉钉、邮件推送消息

### `jwquant.trading.strategy`

这是仓库里第二个最成熟的区域。

关键文件：

- [jwquant/trading/strategy/base.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/base.py)
- [jwquant/trading/strategy/registry.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/registry.py)
- [jwquant/trading/strategy/single_ma.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/single_ma.py)
- [jwquant/trading/strategy/double_ma.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/double_ma.py)
- [jwquant/trading/strategy/three_ma_cross.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/three_ma_cross.py)
- [jwquant/trading/strategy/macd_kdj.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/macd_kdj.py)
- [jwquant/trading/strategy/turtle.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/turtle.py)
- [jwquant/trading/strategy/grid.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/grid.py)
- [jwquant/trading/strategy/rotation.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/rotation.py)
- [jwquant/trading/strategy/chanlun.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/chanlun.py)

这层当前已经具备：

- 统一的策略抽象 `BaseStrategy`
- 一个可管理多策略的 `StrategyManager`
- 一个可注册/创建策略实例的 `StrategyRegistry`
- 多个偏教学/实验性质的策略实现

### `jwquant.trading.indicator`

当前真正可用的是 [jwquant/trading/indicator/talib_wrap.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/indicator/talib_wrap.py)。

它提供：

- SMA / EMA
- MACD
- RSI
- ATR
- Bollinger Bands
- KDJ
- 唐奇安通道
- ADX

而 `indicator.signal`、`indicator.chanlun` 目前还是占位。

### `jwquant.agent`

当前只有 [jwquant/agent/roles.py](/Users/james/PycharmProjects/jwquant/jwquant/agent/roles.py) 内容比较完整。

它主要是“角色设计说明”而不是“已可运行的 agent 系统”。其中定义了：

- 情报官
- 分析师
- 交易员
- 风控员

`graph.py` 和 `workflow.py` 目前仍是骨架说明。

## 5. 脚本与主入口现状

### `main.py`

当前仍是 PyCharm 默认示例文件，不是项目真实入口。

### `scripts/run_backtest.py`

这是仓库里最接近“可跑业务流程”的脚本之一。它没有使用 `jwquant.trading.backtest.engine`，而是自己定义了一个 `SimpleBacktester`。

这说明：

- 包内正式回测模块还没补齐
- 但作者已经在脚本层做了可运行验证

### `scripts/test_*_strategy.py`

这些脚本更像“策略行为演示”而不是正式测试框架的一部分，适合：

- 快速理解单个策略
- 看信号生成逻辑
- 用模拟数据走通一遍处理流程

## 6. 测试现状

### 通过情况

`tests/common/test_common.py` 覆盖了 `common` 层主要模块，本地已验证通过。

### 需谨慎看待的测试

`tests/test_strategies.py` 当前和实现存在偏差，已发现的明显问题包括：

- 直接实例化抽象类 `BaseStrategy`
- 部分对 `GridStrategy` 的预期与实现不一致
- 策略注册信息断言与当前返回结构不一致

### 偏联调脚本的测试

下列测试依赖真实第三方环境，不应视为纯单元测试：

- `tests/trading/test_tushare_conn.py`
- `tests/trading/test_xtquant_conn.py`
- `tests/trading/test_xtquant_futures.py`

而且其中部分代码和当前 `common.config` 实现并不完全匹配，例如 `test_xtquant_conn.py` 仍引用了不存在的 `Config` 类。

## 7. 代码成熟度判断

可以把仓库粗分成三层成熟度：

### A 级：当前可作为真实基础模块维护

- `jwquant.common.*`
- `jwquant.trading.strategy.*`
- `jwquant.trading.indicator.talib_wrap`

### B 级：有设计、有命名、有目录，但还需要补主实现

- `jwquant.agent`
- `scripts/run_backtest.py`

### C 级：目前更像架构预留位

- `jwquant.trading.data.*`
- `jwquant.trading.backtest.*`
- `jwquant.trading.execution.*`
- `jwquant.trading.risk.*`
- `jwquant.research.*`
- `jwquant.ml.*`
- `jwquant.mcp.*`
- `jwquant.dashboard.*`

## 8. 后续维护建议

如果后面要继续推进这个项目，建议优先补齐这几个方向：

1. 先把 `main.py` 替换成真实入口
2. 为 `trading.data` 和 `trading.backtest` 补上最小可用实现
3. 把 `tests/test_strategies.py` 修到和当前代码一致
4. 统一 `tests/trading/*` 的配置读取方式，移除旧接口引用
5. 给蓝图文档加上“规划态”标签，避免误读
