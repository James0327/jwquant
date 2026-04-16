# JWQuant 项目导图

这份文档描述的是仓库的当前代码现状，不是目标蓝图。

如果你只想先搞清楚“现在这个仓库到底能做什么、哪些地方已经写了、哪些地方还只是设计”，读这一份就够了。

如果你想直接看“当前整体做到哪一步了”，优先看：

- [progress-plan.md](/Users/james/PycharmProjects/jwquant/docs/progress-plan.md)
- [configuration.md](/Users/james/PycharmProjects/jwquant/docs/configuration.md)
- [strategy-configuration.md](/Users/james/PycharmProjects/jwquant/docs/strategy-configuration.md)
- [single-stock-backtest-flow.md](/Users/james/PycharmProjects/jwquant/docs/single-stock-backtest-flow.md)
- [multi-stock-backtest-flow.md](/Users/james/PycharmProjects/jwquant/docs/multi-stock-backtest-flow.md)

## 1. 一句话判断

这是一个“目标很大、当前实现集中在基础设施和策略实验”的量化交易仓库。

最成熟的部分是：

- 公共基础设施：配置、日志、事件、通知、共享类型
- 策略框架：策略基类、管理器、注册中心、多个策略实现
- 数据下载/本地存储/动态复权链路
- 最小可用回测引擎与统一风控链路
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
- `docs/configuration.md`：配置项说明与敏感项建议
- `docs/strategy-configuration.md`：策略参数说明与调参建议

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
| `jwquant.trading.data` | 数据获取/清洗/存储 | 已有本地存储、下载同步、动态复权主链 |
| `jwquant.trading.backtest` | 回测与绩效分析 | 已有最小正式化回测引擎、组合与风控接入、结构化/HTML 报告 |
| `jwquant.trading.execution` | 下单执行 | 已有执行前统一风控入口，真实执行闭环仍待补齐 |
| `jwquant.trading.risk` | 风控规则与拦截 | 已有统一协议、仓位/组合/止盈止损规则与回测接入 |
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

### `jwquant.trading.data`

当前已经不是占位目录。

关键文件：

- [jwquant/trading/data/store.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/store.py)
- [jwquant/trading/data/feed.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/feed.py)
- [jwquant/trading/data/sync.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/sync.py)
- [jwquant/trading/data/cleaner.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/cleaner.py)

当前已具备：

- 本地 `rocksdb/csv/sqlite/hdf5` 存储
- A 股 / 期货市场隔离存储
- XtQuant 下载与增量同步
- 股票原始行情 + 复权因子分离存储
- 读取侧动态 `none/qfq/hfq`

### `jwquant.trading.backtest`

当前已经不是“只有 docstring 的占位包”。

关键文件：

- [jwquant/trading/backtest/engine.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/engine.py)
- [jwquant/trading/backtest/risk.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/risk.py)
- [jwquant/trading/backtest/report.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/report.py)

当前已具备：

- 最小正式化回测引擎
- 多标的与组合推进
- 组合权重与再平衡
- 统一风控接入
- 结构化 report 和 HTML 报告导出

### `jwquant.trading.risk`

当前也已经是正式模块，不再是占位。

关键文件：

- [jwquant/trading/risk/context.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/risk/context.py)
- [jwquant/trading/risk/interceptor.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/risk/interceptor.py)
- [jwquant/trading/risk/position.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/risk/position.py)
- [jwquant/trading/risk/portfolio.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/risk/portfolio.py)
- [jwquant/trading/risk/stop.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/risk/stop.py)
- [jwquant/trading/risk/config.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/risk/config.py)

当前已具备：

- 统一风控协议层
- 下单前拦截
- 组合规则
- 统一止盈止损
- 风险配置与优先级仲裁

## 5. 脚本与主入口现状

### `main.py`

当前仍是 PyCharm 默认示例文件，不是项目真实入口。

### `scripts/run_backtest.py`

这是仓库里最接近“可跑业务流程”的脚本之一。当前它已经改为复用包内的 `jwquant.trading.backtest.engine.SimpleBacktester`。

这说明：

- 包内已经有最小正式化回测内核
- 回测、组合风控、报告导出已经接到主链
- 仍然不是完整的生产级撮合/执行系统

### `scripts/demo_*_strategy.py`

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

### 偏联调脚本

下列脚本依赖真实第三方环境，不应视为纯单元测试：

- `scripts/check_tushare_conn.py`
- `scripts/check_xtquant_conn.py`
- `scripts/check_xtquant_futures.py`

它们更适合作为手动联调入口，而不是默认 `pytest` 回归集合的一部分。

## 7. 代码成熟度判断

可以把仓库粗分成三层成熟度：

### A 级：当前可作为真实基础模块维护

- `jwquant.common.*`
- `jwquant.trading.strategy.*`
- `jwquant.trading.indicator.talib_wrap`

### B 级：已有最小可用闭环，但仍待继续增强

- `jwquant.trading.data`
- `jwquant.trading.backtest`
- `jwquant.trading.risk`
- `jwquant.trading.execution`
- `scripts/run_backtest.py`

### C 级：目前更像架构预留位

- `jwquant.agent`
- `jwquant.research.*`
- `jwquant.ml.*`
- `jwquant.mcp.*`
- `jwquant.dashboard.*`
