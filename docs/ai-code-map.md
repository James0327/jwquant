# JWQuant AI 代码地图

这份文档专门给 AI 助手和后续自动化工具使用，目标是降低误判成本。

核心原则只有一条：

不要把旧文档里的目标架构，当成当前已经落地的代码实现。

## 1. 仓库判断结论

### 真实情况

- 项目处于“架构先行、实现分布不均”的阶段
- `common` 和 `strategy` 是最可靠的代码区域
- 大量 `research`、`execution`、`backtest`、`mcp` 文件只有 docstring
- `main.py` 不是业务入口

### 读取优先级

当你需要理解项目时，优先读代码，不要优先读旧文档。

建议顺序：

1. `README.md`
2. `docs/project-map.md`
3. `docs/progress-plan.md`
4. `docs/configuration.md`
5. `jwquant/common/*.py`
6. `jwquant/trading/strategy/*.py`
7. `jwquant/trading/data/*.py`
8. `jwquant/trading/backtest/*.py`
9. `jwquant/trading/risk/*.py`
10. `tests/common/*.py` 与 `tests/trading/*.py`
11. 最后再参考 `docs/architecture-overview.md` 和 `docs/module-design.md`

## 2. 可信入口

### 共享模型层

- [jwquant/common/types.py](/Users/james/PycharmProjects/jwquant/jwquant/common/types.py)

这里定义了仓库里最核心的数据结构：

- `Bar`
- `Tick`
- `Signal`
- `Order`
- `Trade`
- `Position`
- `Asset`
- `RiskEvent`
- `StrategyMeta`

如果你要补交易链路，通常应该复用这套类型，而不是再定义一套。

### 配置入口

- [jwquant/common/config.py](/Users/james/PycharmProjects/jwquant/jwquant/common/config.py)

关键能力：

- `load_config(primary, extra)`
- `get("a.b.c")`
- `get_strategy_config(strategy_name)`
- `validate()`
- 环境变量覆盖规则：`JWQUANT_SECTION__SUBSECTION__KEY`

注意：

- 当前已经有 `Config` 类
- 也保留了函数式接口 `load_config / get / get_*`
- 新风控默认值现在也会通过配置读取

### 策略系统入口

- [jwquant/trading/strategy/base.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/base.py)
- [jwquant/trading/strategy/registry.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/registry.py)

真实主线是：

`Bar` -> `BaseStrategy.add_bar()` -> `BaseStrategy.on_bar()` -> `Signal`

与之配套的管理对象：

- `StrategyManager`：管理已实例化策略，负责逐 bar 驱动
- `StrategyRegistry`：注册策略类、工厂函数和元信息

## 3. 具体策略索引

当前注册中心内置了这些策略：

| 策略名 | 文件 | 说明 |
| --- | --- | --- |
| `turtle` | `jwquant/trading/strategy/turtle.py` | 趋势跟踪 |
| `grid` | `jwquant/trading/strategy/grid.py` | 网格交易 |
| `rotation` | `jwquant/trading/strategy/rotation.py` | 轮动 |
| `chanlun` | `jwquant/trading/strategy/chanlun.py` | 缠论 |
| `single_ma` | `jwquant/trading/strategy/single_ma.py` | 单均线交叉 |
| `double_ma` | `jwquant/trading/strategy/double_ma.py` | 双均线交叉 |
| `three_ma_cross` | `jwquant/trading/strategy/three_ma_cross.py` | 一阳穿三线 |
| `macd_kdj` | `jwquant/trading/strategy/macd_kdj.py` | MACD + KDJ |

这些策略共同特点：

- 都继承 `BaseStrategy`
- 大多依赖 `history_bars`
- 多数参数来自 `config/strategies.toml`
- 更偏研究/教学用途，不是成熟实盘策略框架

## 4. 当前已可直接复用的主链

### 数据主链

- [jwquant/trading/data/store.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/store.py)
- [jwquant/trading/data/feed.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/feed.py)
- [jwquant/trading/data/sync.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/sync.py)

已具备：

- 本地存储
- 增量下载
- 股票动态复权
- A 股 / 期货市场隔离

### 回测主链

- [jwquant/trading/backtest/engine.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/engine.py)
- [jwquant/trading/backtest/risk.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/risk.py)
- [jwquant/trading/backtest/report.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/report.py)
- [scripts/run_backtest.py](/Users/james/PycharmProjects/jwquant/scripts/run_backtest.py)

已具备：

- 最小正式化回测
- 多标的推进
- 再平衡
- 统一风控
- 结构化 report
- HTML 报告导出

### 风控主链

- [jwquant/trading/risk/context.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/risk/context.py)
- [jwquant/trading/risk/interceptor.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/risk/interceptor.py)
- [jwquant/trading/risk/position.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/risk/position.py)
- [jwquant/trading/risk/portfolio.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/risk/portfolio.py)
- [jwquant/trading/risk/stop.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/risk/stop.py)
- [jwquant/trading/risk/config.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/risk/config.py)

已具备：

- 协议层
- 仓位规则
- 组合规则
- 止盈止损
- 优先级执行
- 执行前风控入口

## 5. 哪些文件不要高估

以下文件目前仍然主要是模块说明或预留位：

- `jwquant/research/**/*`
- `jwquant/ml/*`
- `jwquant/mcp/*`
- `jwquant/dashboard/app.py`
- `jwquant/agent/graph.py`
- `jwquant/agent/workflow.py`

如果你要修改这些区域，先假设“需要从零补实现”，而不是“只需小修”。

## 5. 哪些文档要降权

下列文档更像愿景或设计稿：

- [docs/architecture-overview.md](/Users/james/PycharmProjects/jwquant/docs/architecture-overview.md)
- [docs/module-design.md](/Users/james/PycharmProjects/jwquant/docs/module-design.md)

使用方式建议：

- 用它们理解作者想把项目做成什么样
- 不要用它们判断某模块是否真的已经可运行

仍需谨慎看待但不再属于“纯占位”的区域：

- `jwquant/trading/data/*`
- `jwquant/trading/backtest/*`
- `jwquant/trading/risk/*`
- `jwquant/trading/execution/*`

这些模块已经有最小闭环，但不应误判为完整生产级实现。

## 6. 脚本与包实现的关系

### `scripts/run_backtest.py`

这是当前正式回测脚本入口。它已经开始复用包内的最小回测引擎，而不是把回测逻辑完全堆在脚本内。

结论：

- 包内 `jwquant.trading.backtest.engine` 已有最小正式化实现
- 已接入统一风控和报告导出
- 但仍不能把它视为完整的正式撮合/执行框架

### `scripts/demo_*_strategy.py`

这些脚本适合作为：

- 策略行为示例
- 手工调试入口
- 新增策略时的参考模板

不适合作为：

- 稳定的 CI 测试基线
- 严格的回归测试标准

## 7. 测试可信度地图

### 高可信

- [tests/common/test_common.py](/Users/james/PycharmProjects/jwquant/tests/common/test_common.py)

说明：

- 覆盖了 `types/config/log/event/notifier`
- 本地可通过
- 能用于理解公共模块 API

### 中可信

- [tests/test_strategies.py](/Users/james/PycharmProjects/jwquant/tests/test_strategies.py)

说明：

- 能帮助理解预期行为
- 但当前已和实现发生漂移
- 不能直接把测试断言当成真实规范

已知漂移点：

- 抽象类实例化错误
- 部分网格预期不匹配
- 注册中心返回字段预期不匹配

### 低可信或强环境依赖的手动脚本

- [check_tushare_conn.py](/Users/james/PycharmProjects/jwquant/scripts/check_tushare_conn.py)
- [check_xtquant_conn.py](/Users/james/PycharmProjects/jwquant/scripts/check_xtquant_conn.py)
- [check_xtquant_futures.py](/Users/james/PycharmProjects/jwquant/scripts/check_xtquant_futures.py)

说明：

- 依赖真实服务或本地交易环境
- 不是纯离线单元测试
- 存在旧接口引用和硬编码配置

## 8. 给 AI 的修改建议

### 如果要做小改动

优先选这些区域：

- `jwquant.common`
- `jwquant.trading.strategy`
- `jwquant.trading.indicator.talib_wrap`
- `tests/common`

### 如果要补系统能力

建议从这条线开始：

1. 先看 `docs/progress-plan.md`
2. 再看 `docs/backtest-design.md` 和 `docs/risk-design.md`
3. 沿现有主链补增强能力，而不是重起一套新实现

### 如果要做 Agent 或 LLM 功能

先确认是要：

- 补“真实实现”
- 还是整理“架构设计”

因为当前 `agent/research/llm/mcp` 里大部分文件还只是名字和 docstring。

## 9. 防误判清单

在回答或改代码前，最好先检查这几件事：

- 这个文件是不是已经从占位演进成最小闭环
- 这个测试是不是依赖外部服务
- 这个模块是不是只在文档里存在、代码里没有
- 这个“入口”是不是其实只是演示脚本
- 这个接口是不是旧版本遗留，而不是当前真实入口
