# JWQuant 模块详细设计

本文档采用领域驱动分层架构，按交易域/投研域/跨域层组织模块。

> 包路径统一为 `jwquant.<domain>.<module>.<file>`

---

## 1. 数据模块 (trading.data)

负责行情数据的获取、清洗和本地持久化，为策略和智能体提供统一的数据访问接口。

### 子模块

| 子模块 | 文件 | 功能描述 |
|--------|------|---------|
| 数据馈送 | `trading/data/feed.py` | 统一数据接口，向策略层和回测引擎提供标准化的 DataFrame 格式数据 |
| 数据清洗 | `trading/data/cleaner.py` | 处理停牌数据、除权除息（前复权/后复权）、缺失值填充、异常值检测 |
| 数据存储 | `trading/data/store.py` | 本地高质量行情数据库，支持 CSV、HDF5、SQLite 三种存储格式 |
| Tushare 源 | `trading/data/sources/tushare_src.py` | A 股日线/分钟线/财务数据 |
| Baostock 源 | `trading/data/sources/baostock_src.py` | A 股历史日线/周线(免费) |
| XtQuant 源 | `trading/data/sources/xtquant_src.py` | 实时行情，券商级数据 |

### 数据源对比

| 数据源 | 特点 | 适用场景 |
|--------|------|---------|
| Tushare | 数据全面，需 Token | A 股日线/分钟线/财务数据 |
| Baostock | 免费，无需注册 | A 股历史日线/周线 |
| YFinance | 全球市场 | 美股/港股/ETF |
| XtQuant | 实时行情，券商级 | 实盘交易时的实时数据 |

---

## 2. 技术指标模块 (trading.indicator)

封装常用技术分析指标，支持自定义指标扩展，将指标计算结果转化为交易信号。

### 子模块

| 子模块 | 文件 | 功能描述 |
|--------|------|---------|
| Talib 封装 | `trading/indicator/talib_wrap.py` | 封装 TA-Lib 库：SMA、EMA、MACD、RSI、ATR、KDJ、布林带等常用指标 |
| 缠论指标 | `trading/indicator/chanlun.py` | 缠论指标（笔/线段/中枢）、唐奇安通道、自定义组合指标 |
| 信号生成 | `trading/indicator/signal.py` | 根据指标计算结果生成标准化的买入/卖出/持有信号 |

### 支持的指标列表

- **趋势类**: SMA, EMA, MACD, 唐奇安通道
- **震荡类**: RSI, KDJ, 布林带, CCI
- **波动率**: ATR, 标准差
- **成交量**: OBV, 量比
- **缠论**: 分型, 笔, 线段, 中枢

---

## 3. 策略模块 (trading.strategy)

实现经典量化交易策略，提供策略基类和注册管理机制，支持多策略并行运行。

### 子模块

| 子模块 | 文件 | 功能描述 |
|--------|------|---------|
| 策略基类 | `trading/strategy/base.py` | 定义策略生命周期方法：`on_init()`, `on_bar()`, `on_tick()`, `on_order()`, `on_stop()` |
| 海龟策略 | `trading/strategy/turtle.py` | 海龟交易法则：唐奇安通道突破入场，ATR 动态止损与加仓，科学仓位管理 |
| 缠论策略 | `trading/strategy/chanlun.py` | 缠论量化：笔/线段/中枢数学定义与算法识别，底分型与第三类买点信号输出 |
| 网格策略 | `trading/strategy/grid.py` | 网格交易法：均值回归逻辑，自动在价格网格内低买高卖 |
| 轮动策略 | `trading/strategy/rotation.py` | 动量轮动：强者恒强的市场规律，小市值轮动选股 |
| 策略注册 | `trading/strategy/registry.py` | 策略统一注册、发现与管理，支持多策略同时运行 |

### 策略生命周期

```
on_init()      → 策略初始化，加载参数和指标
    │
on_bar(bar)    → 每根 K 线触发，执行策略逻辑
    │
on_tick(tick)  → 每个 Tick 触发（高频策略）
    │
on_order(order)→ 委托状态变更回调
    │
on_trade(trade)→ 成交回报回调
```

---

## 4. 机器学习模块 (ml)

将机器学习和强化学习技术应用于因子挖掘、策略进化和交易执行优化。跨域模块，同时服务交易域和投研域。

### 子模块

| 子模块 | 文件 | 功能描述 |
|--------|------|---------|
| 因子挖掘 | `ml/factor.py` | 将 Talib 技术指标作为特征(Feature)，次日涨跌作为标签(Label)，训练二分类预测模型，产出"上涨概率因子" |
| 策略进化 | `ml/evolve.py` | 设置目标函数（如夏普比率>1.5），AI 自动修改代码参数与逻辑，多轮"优胜劣汰"迭代 |
| 强化学习 | `ml/rl.py` | RL 模型优化挂单价格，实现智能拆单与择时，集成 Qlib 工具箱 |

### 因子挖掘流程

```
原始数据 → 特征工程(Talib指标) → 标签生成(次日涨跌) → 模型训练(XGBoost/LightGBM)
    → 产出"上涨概率因子" → 辅助策略买卖点判断
```

### 策略进化流程

```
初始策略代码 → 回测(Backtrader) → 评估(夏普/回撤) → AI分析不足
    → AI修改参数/逻辑 → 再次回测 → 循环迭代至达标
```

---

## 5. 回测模块 (trading.backtest)

提供策略历史验证能力，集成 QuantStats 绩效分析，支持归因分析帮助区分运气与策略收益。

### 子模块

| 子模块 | 文件 | 功能描述 |
|--------|------|---------|
| 回测引擎 | `trading/backtest/engine.py` | 封装 Backtrader 框架：数据投喂、策略加载、撮合模拟、结果输出 |
| 绩效分析 | `trading/backtest/stats.py` | 集成 QuantStats：年化收益率、夏普比率、最大回撤、胜率、Sortino 比率等 |
| 归因分析 | `trading/backtest/attribution.py` | 交割单归因：区分运气vs策略收益，识别盈利来源，优化策略参数 |

### 核心绩效指标

| 指标 | 说明 |
|------|------|
| 年化收益率 | 策略的年化回报 |
| 夏普比率 | 风险调整后收益（目标>1.5） |
| 最大回撤 | 最大净值回撤幅度 |
| 胜率 | 盈利交易占比 |
| 盈亏比 | 平均盈利/平均亏损 |
| Sortino 比率 | 仅考虑下行风险的夏普比率 |

---

## 6. 交易执行模块 (trading.execution)

对接实盘接口，管理订单全生命周期，实现从信号到下单的自动化交易闭环。

### 子模块

| 子模块 | 文件 | 功能描述 |
|--------|------|---------|
| 券商接口 | `trading/execution/broker.py` | 券商接口抽象层，封装 XtQuant SDK，支持连接/断开/重连 |
| 订单管理 | `trading/execution/order.py` | 委托管理：下单/撤单/改单，同步报单，处理异步回调，订单状态跟踪 |
| 交易闭环 | `trading/execution/loop.py` | 自动化交易闭环：信号触发 → 风控审核 → 下单执行 → 消息推送 |

### 自动化交易闭环流程

```
策略信号触发
    │
    ▼
风控审核 ──── 不通过 → 记录日志 + 通知
    │
    ▼ 通过
生成委托指令
    │
    ▼
提交至 XtQuant（模拟盘/实盘）
    │
    ▼
监听异步回调（成交/撤单/废单）
    │
    ▼
更新持仓 + 推送消息通知
```

---

## 7. 风控模块 (trading.risk)

为交易安全保驾护航，支持盘前风控检查和盘中实时监控，可配置风控规则。

### 子模块

| 子模块 | 文件 | 功能描述 |
|--------|------|---------|
| 规则引擎 | `trading/risk/rules.py` | 可配置的风控规则：资金上限、仓位限制、黑名单、最大回撤、熔断机制、频率限制 |
| 拦截器 | `trading/risk/interceptor.py` | 风控规则不通过时阻断下单，记录拦截原因，支持盘前检查和盘中监控 |

### 风控规则

| 规则类型 | 示例 |
|----------|------|
| 资金上限 | 单笔下单金额不超过总资产的 X% |
| 仓位限制 | 单只股票持仓不超过总资产的 Y% |
| 黑名单 | 禁止交易 ST/*ST/退市风险股 |
| 最大回撤 | 当日亏损达 Z% 时触发熔断，停止交易 |
| 频率限制 | 同一股票 N 分钟内不得重复下单 |

---

## 8. MCP 协议与 Skill 模块 (mcp)

将系统能力封装为标准化的工具(Skill)，通过 MCP 协议让大模型调用量化交易系统的各项功能。

### 子模块

| 子模块 | 文件 | 功能描述 |
|--------|------|---------|
| MCP 服务 | `mcp/server.py` | MCP 协议服务端：接收大模型的工具调用请求，路由至对应 Skill 执行 |
| Skill 注册 | `mcp/skill.py` | Skill 定义与注册中心：将数据能力、计算能力、交易能力封装为标准工具 |

### Skill 示例

| Skill 名称 | 功能 | 输入 | 输出 |
|------------|------|------|------|
| `query_stock_data` | 查询股票行情 | 股票代码, 时间范围 | K 线 DataFrame |
| `run_backtest` | 执行回测 | 策略名, 参数, 时间范围 | 绩效指标 |
| `place_order` | 下单 | 股票代码, 方向, 数量, 价格 | 订单状态 |
| `calc_indicator` | 计算指标 | 股票代码, 指标名, 参数 | 指标值序列 |
| `analyze_sentiment` | 舆情分析 | 关键词 | 情感评分 |

---

## 9. 大模型层 (research.llm)

提供大模型统一接口、RAG 检索增强生成、Prompt 工程能力。属于投研域。

### 子模块

| 子模块 | 文件 | 功能描述 |
|--------|------|---------|
| LLM 接口 | `research/llm/client.py` | 大模型统一接口，支持 OpenAI、通义千问、本地部署模型的切换 |
| RAG 引擎 | `research/llm/rag.py` | 检索增强生成：向量数据库检索相关文档 → 上下文注入 → LLM 生成回答 |
| Prompt 引擎 | `research/llm/prompt.py` | Prompt 模板管理：研报生成/绩效分析/晨报撰写/舆情总结等场景模板 |

### RAG 投研系统架构

```
用户提问（如"分析贵州茅台基本面"）
    │
    ▼
向量检索：从财报/研报向量库中检索相关文档片段
    │
    ▼
上下文构建：将检索结果 + 用户提问组合为 Prompt
    │
    ▼
LLM 生成：大模型基于上下文生成专业分析报告
```

---

## 10. 智能体编排模块 (agent)

基于 LangGraph 实现多智能体协作的工作流编排，是系统的"大脑"。跨域层，编排交易域与投研域的协作。

### 子模块

| 子模块 | 文件 | 功能描述 |
|--------|------|---------|
| 角色定义 | `agent/roles.py` | 定义四大角色：情报官、分析师、交易员、风控员，各自的职责和可调用的工具 |
| LangGraph 引擎 | `agent/graph.py` | LangGraph 工作流核心：定义 Node(员工)、Edge(流程)、State(状态) |
| 工作流模板 | `agent/workflow.py` | 预置工作流：投资晨会、交易决策、风险预警、绩效复盘 |

### 角色职责

| 角色 | 职责 | 调用的模块 |
|------|------|-----------|
| 情报官 | 收集市场信息、监控舆情、追踪新闻热点 | `research.crawler`, `research.nlp` |
| 分析师 | 技术分析、基本面分析、生成研报、因子挖掘 | `trading.indicator`, `ml`, `research.app` |
| 交易员 | 执行交易策略、管理订单、跟踪持仓 | `trading.strategy`, `trading.execution` |
| 风控员 | 审核交易指令、监控风险指标、执行熔断 | `trading.risk`, `trading.backtest` |

### 投资晨会工作流

```
情报官：采集隔夜新闻 + 舆情分析 + 市场情绪评估
    │
    ▼
分析师：结合行情数据 + 技术指标 + 基本面，产出分析观点
    │
    ▼
交易员：根据分析结果，制定当日交易计划
    │
    ▼
风控员：审核交易计划，评估风险敞口
    │
    ▼
输出：每日投资晨报
```

---

## 11. 外部数据采集模块 (research.crawler)

采集新闻、舆情、研报等非行情类外部数据。属于投研域。

### 子模块

| 子模块 | 文件 | 功能描述 |
|--------|------|---------|
| 新闻采集 | `research/crawler/news.py` | 对接新闻接口（财联社等），采集财经新闻、公告、政策信息 |
| 舆情采集 | `research/crawler/sentiment.py` | 采集股吧、雪球、东财社区等平台的股票讨论和舆情数据 |
| 研报采集 | `research/crawler/report.py` | 采集券商研报、财报 PDF 文档 |

---

## 12. NLP 数据处理模块 (research.nlp)

对非结构化文本进行解析、向量化和语义分析，为 RAG 和舆情监控提供数据基础。属于投研域。

### 子模块

| 子模块 | 文件 | 功能描述 |
|--------|------|---------|
| PDF 解析 | `research/nlp/parser.py` | PDF/Word 文档解析，提取结构化文本与表格数据 |
| 文本向量化 | `research/nlp/vectorizer.py` | 文本 Embedding，将文档转为向量表示，支持多种 Embedding 模型 |
| 向量数据库 | `research/nlp/vector_store.py` | 向量数据库管理（FAISS/Chroma），文档向量的存储、索引与检索 |
| 情感分析 | `research/nlp/sentiment.py` | NLP 情绪分析：贪婪/恐慌指数、关键词（"资产重组"等）捕捉与量化打分 |

---

## 13. AI 应用层 (research.app)

面向用户的智能应用，将 LLM 能力与量化数据结合，产出实用的投研工具。属于投研域。

### 子模块

| 子模块 | 文件 | 功能描述 |
|--------|------|---------|
| 智能研报 | `research/app/report.py` | 基于国泰君安研报"五步法"，结合 RAG 数据生成基本面分析报告 |
| 投资晨会 | `research/app/briefing.py` | 每日自动生成投资晨报：隔夜新闻、市场情绪、技术面分析、交易计划 |
| 舆情监控 | `research/app/monitor.py` | 实时舆情监控系统：关键词追踪、情绪异动预警、利好/利空推送 |

### 研报"五步法"

1. **行业分析** — 行业景气度、政策环境、竞争格局
2. **公司分析** — 商业模式、核心竞争力、管理层
3. **财务分析** — 营收/利润/现金流、ROE、资产负债率
4. **估值分析** — PE/PB/DCF 估值、与同行对比
5. **投资建议** — 目标价、评级、风险提示

---

## 14. 可视化控制台 (dashboard)

基于 Streamlit 构建 Web UI 看板，将智能体工作状态和交易数据可视化展示。

### 子模块

| 子模块 | 文件 | 功能描述 |
|--------|------|---------|
| 主框架 | `dashboard/app.py` | Streamlit 应用入口，页面路由与布局 |
| 智能体看板 | `dashboard/pages/agent_monitor.py` | 展示各智能体角色的运行状态、决策过程、消息流 |
| 交易看板 | `dashboard/pages/trade_dashboard.py` | 持仓分布、盈亏曲线、订单状态、成交记录 |
| 策略看板 | `dashboard/pages/strategy_dashboard.py` | 回测结果、绩效曲线、信号标记、策略对比 |

---

## 15. 调度与事件模块 (common.event)

管理系统的定时任务和事件驱动机制，确保各模块按时序协调工作。事件总线位于公共层。

### 子模块

| 子模块 | 文件 | 功能描述 |
|--------|------|---------|
| 事件总线 | `common/event.py` | 模块间发布/订阅解耦通信：行情事件、信号事件、成交事件、风控事件 |
| 定时任务 | `scripts/scheduler.py` | 盘前(数据更新/晨报生成)、盘中(策略执行/监控)、盘后(清算/复盘) |
| 复盘调度 | `scripts/run_evolution.py` | 定期触发绩效复盘、归因分析和策略参数自动调优 |

### 每日任务时间线

```
08:30  盘前准备：数据更新、晨报生成、风控规则加载
09:15  开盘就绪：策略初始化、账户同步
09:30  盘中运行：策略执行、信号监控、风控实时检查
11:30  午间休市：中场复盘、舆情更新
13:00  午后开盘：继续策略执行
15:00  收盘处理：持仓同步、盈亏计算
15:30  盘后分析：绩效统计、归因分析、交易日报生成
20:00  晚间任务：隔夜新闻监控、次日策略预调整
```

---

## 16. 基础设施 (common)

提供配置管理、日志记录、事件通信和消息通知等基础能力，支撑整个系统运行。位于公共层，全部使用 Python 标准库实现，零外部依赖。

### 子模块

| 子模块 | 文件 | 功能描述 |
|--------|------|---------|
| 数据类型 | `common/types.py` | 共享数据结构：Bar、Tick、Signal、Order、Trade、Position、Asset、RiskEvent、StrategyMeta |
| 配置管理 | `common/config.py` | 多文件合并(settings+strategies)、环境变量覆盖(JWQUANT_前缀)、敏感字段脱敏、配置校验、类型化 getter |
| 结构化日志 | `common/log.py` | 按日滚动文件、JSON 结构化格式、分类日志器(交易/策略/智能体/系统)、@log_elapsed 性能装饰器、动态级别调整 |
| 事件总线 | `common/event.py` | 发布/订阅解耦通信、EventType 事件常量、处理器优先级、条件过滤订阅、事件日志 |
| 消息通知 | `common/notifier.py` | 微信(Server酱/PushPlus) + 钉钉(Webhook签名) + 邮件(SMTP/TLS)、分级路由、速率限制、消息模板、失败重试 |

### 配置管理特性

| 特性 | 说明 |
|------|------|
| 多文件合并 | `load_config(primary, extra=[...])` 深度合并多个 TOML 文件，后者覆盖前者 |
| 环境变量覆盖 | `JWQUANT_BROKER_XTQUANT_PATH` → `broker.xtquant.path`，自动类型推断 |
| 敏感字段脱敏 | `get_masked_config()` 自动将 api_key/token/password 等显示为 `***` |
| 配置校验 | `validate()` 检查风控参数范围、券商路径存在性，返回错误列表 |
| 类型化 getter | `get_str()` / `get_int()` / `get_float()` / `get_bool()` 类型安全访问 |
| 热重载 | `reload_config()` 运行时重新读取配置文件 |

### 日志系统特性

| 特性 | 说明 |
|------|------|
| 文件滚动 | `TimedRotatingFileHandler` 每日午夜自动切换，保留 30 天 |
| JSON 格式 | `JSONFormatter` 输出 `{"ts", "level", "logger", "msg", ...}` 兼容 ELK/Splunk |
| 分类日志器 | `get_trade_logger()` / `get_strategy_logger()` / `get_agent_logger()` / `get_system_logger()` |
| 性能计时 | `@log_elapsed()` 装饰器自动记录函数执行耗时 |
| 动态级别 | `set_log_level(name, level)` 运行时切换 DEBUG/INFO/WARN 无需重启 |

### 事件总线特性

| 特性 | 说明 |
|------|------|
| 事件常量 | `EventType.BAR` / `EventType.ORDER_FILLED` / `EventType.RISK_VIOLATION` 等标准化常量 |
| 优先级 | 100=风控拦截器、50=策略处理器、0=日志通知，高优先级先执行 |
| 条件过滤 | `subscribe_filtered(event, handler, filter_fn)` 仅处理满足条件的事件 |
| 事件日志 | publish 时自动记录事件类型和数据摘要 |
| 安全执行 | handler 异常不影响后续处理器，错误自动记录 |

### 通知系统特性

| 特性 | 说明 |
|------|------|
| 微信通知 | Server酱 (`sctapi.ftqq.com`) 或 PushPlus (`pushplus.plus`)，Markdown 格式 |
| 钉钉通知 | Webhook 机器人 + 可选 HMAC-SHA256 签名验证 |
| 邮件通知 | SMTP + STARTTLS，支持多收件人 |
| 分级路由 | INFO→微信、WARNING→微信+钉钉、ERROR/CRITICAL→全渠道 |
| 速率限制 | 滑动窗口计数器，默认 10 条/分钟 |
| 消息模板 | 预置 `order_filled` / `risk_alert` / `daily_briefing` / `system_error` 模板 |
| 失败重试 | 指数退避重试 3 次（1s → 2s → 4s） |
