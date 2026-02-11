# JWQuant AI 量化交易系统 - 架构总览

## 1. 项目简介

JWQuant 是一个 AI 驱动的量化交易系统，融合了传统量化策略与大模型智能体技术，覆盖从数据采集、策略研发、回测验证、风控审核到实盘交易的完整闭环。

系统以"多智能体协作"为核心理念，定义了 **情报官、分析师、交易员、风控员** 四大角色，通过 LangGraph 编排实现自动化的投资决策工作流。

## 2. 系统架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        可视化控制台 (dashboard)                       │
│                 Streamlit Web UI / 智能体状态看板                      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                     智能体编排层 (agent)                              │
│          LangGraph 工作流 / 角色定义 / 多智能体协调                     │
│     ┌──────────┬──────────┬──────────┬──────────┐                  │
│     │ 情报官    │ 分析师    │ 交易员    │ 风控员    │                  │
│     └──────────┴──────────┴──────────┴──────────┘                  │
└──────┬───────────┬───────────┬───────────┬──────────────────────────┘
       │           │           │           │
┌──────▼───┐ ┌─────▼────┐ ┌───▼──────┐ ┌──▼───────┐
│ AI 投研   │ │ 策略 &    │ │ 交易执行  │ │ 风控模块  │
│ (ai_app) │ │ 回测     │ │(execution)│ │ (risk)   │
│          │ │(strategy │ │          │ │          │
│ 研报生成  │ │ backtest)│ │ XtQuant  │ │ 拦截规则  │
│ 晨会报告  │ │ ML因子   │ │ 自动闭环  │ │ 熔断机制  │
│ 舆情监控  │ │ 归因分析  │ │ 订单管理  │ │ 黑名单   │
└──────┬───┘ └─────┬────┘ └───┬──────┘ └──┬───────┘
       │           │           │           │
┌──────▼───────────▼───────────▼───────────▼──────────────────────────┐
│                      MCP 协议 & Skill 层                             │
│            Skill 注册 / MCP Server / Tool 封装                       │
└──────┬───────────┬───────────┬──────────────────────────────────────┘
       │           │           │
┌──────▼───┐ ┌─────▼────┐ ┌───▼──────────────────────────────────────┐
│ 大模型层  │ │ NLP 处理  │ │              数据层                       │
│ (llm)    │ │ (nlp)    │ │                                          │
│          │ │          │ │  行情数据(data) + 外部采集(crawler)         │
│ RAG引擎   │ │ PDF解析   │ │  Tushare / Baostock / YFinance / XtQuant │
│ Prompt   │ │ 向量化    │ │  技术指标(indicators) - Talib             │
│ Func Call│ │ 情感分析   │ │  本地数据库 CSV/HDF5                      │
└──────────┘ └──────────┘ └──────────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                      基础设施层 (infra)                               │
│           配置管理 / 结构化日志 / 消息通知 / 任务调度                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 3. 模块全景（17个模块）

| # | 模块 | 包名 | 职责 |
|---|------|------|------|
| 1 | 数据模块 | `data` | 多源行情数据获取、清洗、本地存储 |
| 2 | 技术指标模块 | `indicators` | Talib 指标封装、自定义指标、信号生成 |
| 3 | 策略模块 | `strategy` | 海龟/缠论/网格/轮动等经典策略实现 |
| 4 | 机器学习模块 | `ml` | 因子挖掘、论文复现、策略进化、强化学习、Qlib |
| 5 | 回测模块 | `backtest` | Backtrader 引擎、QuantStats 绩效、归因分析 |
| 6 | 交易执行模块 | `execution` | XtQuant 实盘对接、订单管理、自动化交易闭环 |
| 7 | 风控模块 | `risk` | 盘前/盘中风控、拦截逻辑、熔断机制 |
| 8 | 账户模块 | `account` | QMT 连接管理、资产查询、多账户支持 |
| 9 | MCP 协议与 Skill | `mcp_skill` | Skill 注册、MCP 服务、工具封装 |
| 10 | 大模型层 | `llm` | LLM 接口、RAG 引擎、Prompt 工程、Function Call |
| 11 | 智能体编排 | `agent` | LangGraph 工作流、角色定义、多智能体协调 |
| 12 | 外部数据采集 | `crawler` | 新闻/舆情/研报文档采集 |
| 13 | NLP 数据处理 | `nlp` | PDF 解析、文本向量化、向量数据库、情感分析 |
| 14 | AI 应用层 | `ai_app` | 智能研报、投资晨会、舆情监控 |
| 15 | 可视化控制台 | `dashboard` | Streamlit 看板、智能体/交易/策略可视化 |
| 16 | 调度模块 | `scheduler` | 定时任务、事件总线、定期复盘调度 |
| 17 | 基础设施 | `infra` | 配置管理、结构化日志、消息通知 |

## 4. 两条核心链路

### 4.1 交易执行链路

```
行情数据 → 技术指标 → 策略信号 → 风控审核 → 下单执行 → 持仓管理 → 绩效归因
 (data)  (indicators) (strategy)   (risk)   (execution)  (account)  (backtest)
```

### 4.2 AI 投研链路

```
外部采集 → NLP处理 → 向量存储 → RAG检索 → 大模型生成 → AI应用(研报/晨会/舆情)
(crawler)   (nlp)    (nlp)     (llm)      (llm)        (ai_app)
```

### 4.3 智能体编排层（连接两条链路）

```
LangGraph 工作流编排
    │
    ├── 情报官 → 调用 crawler + nlp + sentiment_monitor
    ├── 分析师 → 调用 indicators + ml + report_generator
    ├── 交易员 → 调用 strategy + execution + trade_loop
    └── 风控员 → 调用 risk + interceptor + realtime_monitor
```

## 5. 技术栈

| 类别 | 工具/框架 |
|------|----------|
| 语言 | Python 3.10+ |
| 数据源 | Tushare, Baostock, YFinance, XtQuant |
| 回测引擎 | Backtrader |
| 技术指标 | TA-Lib |
| 绩效分析 | QuantStats |
| 智能体编排 | LangGraph |
| 机器学习 | scikit-learn, Qlib (Microsoft) |
| 强化学习 | Stable-Baselines3 / 自定义 RL |
| 大模型 | OpenAI API / 通义千问 / 本地模型 |
| RAG/向量数据库 | FAISS / Chroma + Embedding |
| MCP 协议 | MCP SDK |
| 可视化 | Streamlit |
| 实盘接口 | XtQuant / QMT (迅投) |
| 消息通知 | 微信/钉钉/邮件 |

## 6. 目录结构

```
jwquant/
├── com/jw/
│   ├── data/                # 1. 数据模块
│   │   ├── market_data.py       # 多源行情获取
│   │   ├── data_cleaner.py      # 数据清洗(停牌/复权/缺失值)
│   │   ├── data_store.py        # 本地数据库(CSV/HDF5)
│   │   └── data_feed.py         # 统一数据接口
│   │
│   ├── indicators/          # 2. 技术指标
│   │   ├── talib_wrapper.py     # Talib 指标封装
│   │   ├── custom_indicators.py # 自定义指标(缠论/唐奇安)
│   │   └── signal_generator.py  # 信号生成
│   │
│   ├── strategy/            # 3. 策略模块
│   │   ├── base_strategy.py     # 策略基类
│   │   ├── turtle_strategy.py   # 海龟交易法则
│   │   ├── chanlun_strategy.py  # 缠论量化
│   │   ├── grid_strategy.py     # 网格交易
│   │   ├── rotation_strategy.py # 轮动策略
│   │   └── strategy_registry.py # 策略注册管理
│   │
│   ├── ml/                  # 4. 机器学习
│   │   ├── factor_mining.py     # 因子挖掘
│   │   ├── paper_replicator.py  # 论文复现
│   │   ├── strategy_evolver.py  # 策略自我进化
│   │   ├── rl_trader.py         # 强化学习交易
│   │   └── qlib_integration.py  # Qlib 集成
│   │
│   ├── backtest/            # 5. 回测模块
│   │   ├── backtrader_engine.py # Backtrader 引擎
│   │   ├── performance.py       # QuantStats 绩效
│   │   ├── report.py            # 回测报告
│   │   └── attribution.py       # 归因分析
│   │
│   ├── execution/           # 6. 交易执行
│   │   ├── broker.py            # 券商接口抽象
│   │   ├── order_manager.py     # 委托管理
│   │   ├── trade_router.py      # 交易路由
│   │   ├── position_manager.py  # 持仓管理
│   │   └── trade_loop.py        # 自动化交易闭环
│   │
│   ├── risk/                # 7. 风控模块
│   │   ├── pre_trade_check.py   # 盘前风控
│   │   ├── realtime_monitor.py  # 盘中监控
│   │   ├── interceptor.py       # 拦截逻辑
│   │   └── risk_rules.py        # 风控规则引擎
│   │
│   ├── account/             # 8. 账户模块
│   │   ├── account_manager.py   # 连接管理
│   │   ├── asset_query.py       # 资产查询
│   │   └── multi_account.py     # 多账户管理
│   │
│   ├── mcp_skill/           # 9. MCP 协议与 Skill
│   │   ├── skill_registry.py    # Skill 注册
│   │   ├── mcp_server.py        # MCP 协议服务
│   │   └── tool_wrapper.py      # 工具封装
│   │
│   ├── llm/                 # 10. 大模型层
│   │   ├── llm_client.py        # LLM 统一接口
│   │   ├── prompt_engine.py     # Prompt 模板管理
│   │   ├── rag_engine.py        # RAG 投研系统
│   │   └── function_call.py     # Function Call
│   │
│   ├── agent/               # 11. 智能体编排
│   │   ├── agent_roles.py       # 角色定义
│   │   ├── langgraph_engine.py  # LangGraph 工作流
│   │   ├── workflow.py          # 工作流模板
│   │   └── orchestrator.py      # 多智能体协调
│   │
│   ├── crawler/             # 12. 外部数据采集
│   │   ├── news_crawler.py      # 新闻采集
│   │   ├── sentiment_crawler.py # 舆情采集
│   │   └── report_crawler.py    # 研报采集
│   │
│   ├── nlp/                 # 13. NLP 处理
│   │   ├── pdf_parser.py        # PDF 解析
│   │   ├── text_vectorizer.py   # 文本向量化
│   │   ├── vector_store.py      # 向量数据库
│   │   └── sentiment_analyzer.py # 情感分析
│   │
│   ├── ai_app/              # 14. AI 应用层
│   │   ├── report_generator.py      # 智能研报生成
│   │   ├── morning_briefing.py      # 投资晨会
│   │   ├── sentiment_monitor.py     # 舆情监控
│   │   └── performance_reporter.py  # 绩效报告
│   │
│   ├── dashboard/           # 15. 可视化控制台
│   │   ├── streamlit_app.py     # Streamlit 主框架
│   │   ├── agent_monitor.py     # 智能体状态看板
│   │   ├── trade_dashboard.py   # 交易看板
│   │   └── strategy_dashboard.py # 策略看板
│   │
│   ├── scheduler/           # 16. 调度模块
│   │   ├── task_scheduler.py        # 定时任务
│   │   ├── event_bus.py             # 事件总线
│   │   └── evolution_scheduler.py   # 复盘调度
│   │
│   ├── infra/               # 17. 基础设施
│   │   ├── config.py            # 配置管理
│   │   ├── logger.py            # 结构化日志
│   │   └── notifier.py          # 消息通知
│   │
│   └── xtquant/             # 现有 XtQuant 对接
│       └── xtquant_test.py
│
├── docs/                    # 文档目录
├── tests/                   # 测试目录
└── main.py                  # 入口
```
