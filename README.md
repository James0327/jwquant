# JWQuant

JWQuant 是一个以 Python 编写的量化交易项目，目标是把传统量化策略、公共基础设施和 AI/Agent 能力放到同一个代码库里。就当前仓库状态而言，已经有较完整实现的部分主要集中在：

- `jwquant.common`：公共数据结构、配置、日志、事件总线、通知
- `jwquant.trading.strategy`：策略基类、策略注册中心、8 个示例/实验性策略
- `tests/common`：针对公共模块的单元测试，覆盖度较好

其余很多目录已经完成了分层和命名设计，但代码仍处于占位或早期骨架阶段，比如 `trading.data`、`trading.backtest`、`trading.execution`、`research`、`mcp`、`dashboard`。

## 先看哪里

如果你是第一次接手这个仓库，建议按这个顺序阅读：

1. [docs/project-map.md](/Users/james/PycharmProjects/jwquant/docs/project-map.md)
2. [docs/ai-code-map.md](/Users/james/PycharmProjects/jwquant/docs/ai-code-map.md)
3. [jwquant/common/config.py](/Users/james/PycharmProjects/jwquant/jwquant/common/config.py)
4. [jwquant/common/types.py](/Users/james/PycharmProjects/jwquant/jwquant/common/types.py)
5. [jwquant/trading/strategy/base.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/base.py)
6. [jwquant/trading/strategy/registry.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/registry.py)
7. 任选一个具体策略实现，例如 [jwquant/trading/strategy/single_ma.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/single_ma.py)

## 仓库结构

```text
jwquant/
├── config/                  # TOML 配置
├── docs/                    # 文档
├── jwquant/                 # 主源码包
│   ├── common/              # 当前最成熟的基础设施层
│   ├── trading/             # 交易相关模块，策略实现最完整
│   ├── agent/               # 角色定义较完整，工作流实现仍是骨架
│   ├── research/            # 投研与 LLM 方向，目前多为占位文件
│   ├── ml/                  # 机器学习方向，目前多为占位文件
│   ├── mcp/                 # MCP 方向，目前多为占位文件
│   └── dashboard/           # Streamlit 入口占位
├── scripts/                 # 演示脚本与简易回测脚本
└── tests/                   # 测试与外部连接验证脚本
```

## 当前实现状态

### 已有较真实代码的区域

- `jwquant.common.types`
- `jwquant.common.config`
- `jwquant.common.log`
- `jwquant.common.event`
- `jwquant.common.notifier`
- `jwquant.trading.indicator.talib_wrap`
- `jwquant.trading.strategy.*`
- `scripts/test_*_strategy.py`
- `scripts/run_backtest.py`

### 主要是接口说明或规划骨架的区域

- `jwquant.trading.data.*`
- `jwquant.trading.backtest.*`
- `jwquant.trading.execution.*`
- `jwquant.trading.risk.*`
- `jwquant.research.*`
- `jwquant.ml.*`
- `jwquant.mcp.*`
- `jwquant.dashboard.app`
- `jwquant.agent.graph`
- `jwquant.agent.workflow`

## 配置

核心配置文件：

- [config/settings.toml](/Users/james/PycharmProjects/jwquant/config/settings.toml)
- [config/strategies.toml](/Users/james/PycharmProjects/jwquant/config/strategies.toml)

配置加载入口在 [jwquant/common/config.py](/Users/james/PycharmProjects/jwquant/jwquant/common/config.py)，支持：

- 多 TOML 文件合并
- `JWQUANT_` 前缀环境变量覆盖
- 基础类型转换
- 敏感字段脱敏
- 部分配置校验

## 测试现状

仓库当前测试可以粗分为两类：

- 可稳定离线运行的单元测试：例如 `tests/common/test_common.py`
- 偏联调/演示性质的测试：例如 `tests/trading/test_tushare_conn.py`、`tests/trading/test_xtquant_conn.py`

已核对的本地结果：

- `pytest tests/common/test_common.py`：通过
- `pytest tests/test_strategies.py`：存在 5 个失败，说明策略测试与当前实现已有偏差

## 关于旧文档

仓库里原有两份文档更接近“目标架构/理想设计”，不是对当前代码状态的精确描述：

- [docs/architecture-overview.md](/Users/james/PycharmProjects/jwquant/docs/architecture-overview.md)
- [docs/module-design.md](/Users/james/PycharmProjects/jwquant/docs/module-design.md)

建议把它们当作规划文档阅读，把下面两份当作当前项目导读：

- [docs/project-map.md](/Users/james/PycharmProjects/jwquant/docs/project-map.md)
- [docs/ai-code-map.md](/Users/james/PycharmProjects/jwquant/docs/ai-code-map.md)
