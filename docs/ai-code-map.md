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
3. `jwquant/common/*.py`
4. `jwquant/trading/strategy/*.py`
5. `tests/common/test_common.py`
6. `scripts/run_backtest.py`
7. 最后再参考 `docs/architecture-overview.md` 和 `docs/module-design.md`

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

- 当前没有 `Config` 类
- 如果代码里还在 `from jwquant.common.config import Config`，那是旧接口残留

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

## 4. 哪些文件不要高估

以下文件目前基本只有模块说明，几乎没有业务实现：

- `jwquant/trading/data/feed.py`
- `jwquant/trading/data/store.py`
- `jwquant/trading/data/cleaner.py`
- `jwquant/trading/data/sources/*.py`
- `jwquant/trading/backtest/*.py`
- `jwquant/trading/execution/*.py`
- `jwquant/trading/risk/*.py`
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

## 6. 脚本与包实现的关系

### `scripts/run_backtest.py`

这是一个重要信号文件，因为它说明作者在“正式包实现未完成”的情况下，已经用脚本走通了一个最小回测流程。

结论：

- 如果要补 `jwquant.trading.backtest.engine`，可以参考这里的 `SimpleBacktester`
- 但不能反过来说“包内回测引擎已经实现”

### `scripts/test_*_strategy.py`

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

### 低可信或强环境依赖

- [tests/trading/test_tushare_conn.py](/Users/james/PycharmProjects/jwquant/tests/trading/test_tushare_conn.py)
- [tests/trading/test_xtquant_conn.py](/Users/james/PycharmProjects/jwquant/tests/trading/test_xtquant_conn.py)
- [tests/trading/test_xtquant_futures.py](/Users/james/PycharmProjects/jwquant/tests/trading/test_xtquant_futures.py)

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

1. 定义清晰的包内入口
2. 补 `trading.data.feed`
3. 补 `trading.backtest.engine`
4. 再让 `scripts/run_backtest.py` 复用包内实现

### 如果要做 Agent 或 LLM 功能

先确认是要：

- 补“真实实现”
- 还是整理“架构设计”

因为当前 `agent/research/llm/mcp` 里大部分文件还只是名字和 docstring。

## 9. 防误判清单

在回答或改代码前，最好先检查这几件事：

- 这个文件是不是只有 5 行左右 docstring
- 这个测试是不是依赖外部服务
- 这个模块是不是只在文档里存在、代码里没有
- 这个“入口”是不是其实只是演示脚本
- 这个接口是不是旧版本遗留，例如 `Config` 类
