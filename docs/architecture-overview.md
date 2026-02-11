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
│(res.app) │ │ 回测     │ │(execution)│ │ (risk)   │
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
│          │ │          │ │  行情数据(trading.data) + 外部采集(research.crawler)         │
│ RAG引擎   │ │ PDF解析   │ │  Tushare / Baostock / YFinance / XtQuant │
│ Prompt   │ │ 向量化    │ │  技术指标(trading.indicator) - Talib             │
│ Func Call│ │ 情感分析   │ │  本地数据库 CSV/HDF5                      │
└──────────┘ └──────────┘ └──────────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                      基础设施层 (common)                               │
│           配置管理 / 结构化日志 / 消息通知 / 任务调度                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 3. 领域驱动模块划分

采用领域驱动分层架构，按"交易域"和"投研域"两大业务领域划分，智能体层编排两个域的协作。

### 3.1 公共层 (common)

| 模块 | 包路径 | 职责 |
|------|--------|------|
| 数据类型 | `jwquant.common.types` | Bar/Signal/Order/Position 等共享数据结构 |
| 事件总线 | `jwquant.common.event` | 模块间发布/订阅解耦通信 |
| 配置管理 | `jwquant.common.config` | TOML 配置加载与读取 |
| 日志 | `jwquant.common.log` | 结构化分级日志 |

### 3.2 交易域 (trading)

| 模块 | 包路径 | 职责 |
|------|--------|------|
| 行情数据 | `jwquant.trading.data` | 多源数据获取(Tushare/Baostock/YFinance/XtQuant)、清洗、存储 |
| 技术指标 | `jwquant.trading.indicator` | Talib 封装、缠论指标、信号生成 |
| 策略 | `jwquant.trading.strategy` | 海龟/缠论/网格/轮动等经典策略 |
| 风控 | `jwquant.trading.risk` | 风控规则引擎、拦截器 |
| 交易执行 | `jwquant.trading.execution` | XtQuant 对接、订单管理、自动化交易闭环 |
| 回测 | `jwquant.trading.backtest` | Backtrader 引擎、QuantStats 绩效、归因分析 |

### 3.3 投研域 (research)

| 模块 | 包路径 | 职责 |
|------|--------|------|
| 外部采集 | `jwquant.research.crawler` | 新闻/舆情/研报文档采集 |
| NLP 处理 | `jwquant.research.nlp` | PDF 解析、文本向量化、向量数据库、情感分析 |
| 大模型 | `jwquant.research.llm` | LLM 接口、RAG 引擎、Prompt 工程 |
| 投研应用 | `jwquant.research.app` | 智能研报、投资晨会、舆情监控 |

### 3.4 跨域层

| 模块 | 包路径 | 职责 |
|------|--------|------|
| 智能体编排 | `jwquant.agent` | LangGraph 工作流、四大角色定义、多智能体协调 |
| 机器学习 | `jwquant.ml` | 因子挖掘、策略进化、强化学习 |
| MCP 协议 | `jwquant.mcp` | MCP 服务、Skill 注册 |
| 可视化 | `jwquant.dashboard` | Streamlit 看板 |

## 4. 两条核心链路

### 4.1 交易执行链路

```
行情数据 → 技术指标 → 策略信号 → 风控审核 → 下单执行 → 持仓管理 → 绩效归因
(trading.data) (trading.indicator) (trading.strategy) (trading.risk) (trading.execution) (trading.execution) (trading.backtest)
```

### 4.2 AI 投研链路

```
外部采集 → NLP处理 → 向量存储 → RAG检索 → 大模型生成 → AI应用(研报/晨会/舆情)
(research.crawler) (research.nlp) (research.nlp) (research.llm) (research.llm) (research.app)
```

### 4.3 智能体编排层（连接两条链路）

```
LangGraph 工作流编排
    │
    ├── 情报官 → 调用 research.crawler + research.nlp + research.app.monitor
    ├── 分析师 → 调用 trading.indicator + ml + research.app.report
    ├── 交易员 → 调用 trading.strategy + trading.execution
    └── 风控员 → 调用 trading.risk + trading.backtest
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
├── config/                      # 配置文件
│   ├── settings.toml                # 系统配置（券商/数据源/LLM/风控）
│   └── strategies.toml              # 策略参数配置
│
├── jwquant/                     # 源码主包
│   ├── __init__.py
│   │
│   ├── common/                  # ===== 公共层 =====
│   │   ├── types.py                 # 数据类型(Bar/Signal/Order/Position)
│   │   ├── event.py                 # 事件总线
│   │   ├── config.py                # 配置加载
│   │   └── log.py                   # 结构化日志
│   │
│   ├── trading/                 # ===== 交易域 =====
│   │   ├── data/                    # 行情数据
│   │   │   ├── feed.py                  # 统一数据接口
│   │   │   ├── cleaner.py               # 数据清洗
│   │   │   ├── store.py                 # 本地存储(CSV/HDF5)
│   │   │   └── sources/                 # 多数据源
│   │   │       ├── tushare_src.py
│   │   │       ├── baostock_src.py
│   │   │       └── xtquant_src.py
│   │   ├── indicator/               # 技术指标
│   │   │   ├── talib_wrap.py            # Talib 封装
│   │   │   ├── chanlun.py               # 缠论指标
│   │   │   └── signal.py               # 信号生成
│   │   ├── strategy/                # 策略
│   │   │   ├── base.py                  # 策略基类
│   │   │   ├── turtle.py                # 海龟交易法则
│   │   │   ├── chanlun.py               # 缠论量化
│   │   │   ├── grid.py                  # 网格交易
│   │   │   ├── rotation.py              # 轮动策略
│   │   │   └── registry.py              # 策略注册管理
│   │   ├── risk/                    # 风控
│   │   │   ├── rules.py                 # 风控规则引擎
│   │   │   └── interceptor.py           # 拦截器
│   │   ├── execution/               # 交易执行
│   │   │   ├── broker.py                # 券商接口(XtQuant)
│   │   │   ├── order.py                 # 订单管理
│   │   │   └── loop.py                  # 自动化交易闭环
│   │   └── backtest/                # 回测
│   │       ├── engine.py                # Backtrader 引擎
│   │       ├── stats.py                 # QuantStats 绩效
│   │       └── attribution.py           # 归因分析
│   │
│   ├── research/                # ===== 投研域 =====
│   │   ├── crawler/                 # 外部数据采集
│   │   │   ├── news.py                  # 新闻采集
│   │   │   ├── sentiment.py             # 舆情采集
│   │   │   └── report.py               # 研报采集
│   │   ├── nlp/                     # NLP 处理
│   │   │   ├── parser.py               # PDF 解析
│   │   │   ├── vectorizer.py            # 文本向量化
│   │   │   ├── vector_store.py          # 向量数据库
│   │   │   └── sentiment.py             # 情感分析
│   │   ├── llm/                     # 大模型
│   │   │   ├── client.py                # LLM 统一接口
│   │   │   ├── rag.py                   # RAG 引擎
│   │   │   └── prompt.py               # Prompt 模板
│   │   └── app/                     # 投研应用
│   │       ├── report.py                # 智能研报生成
│   │       ├── briefing.py              # 投资晨会
│   │       └── monitor.py              # 舆情监控
│   │
│   ├── agent/                   # ===== 智能体编排层 =====
│   │   ├── roles.py                 # 角色定义(情报官/分析师/交易员/风控员)
│   │   ├── graph.py                 # LangGraph 工作流引擎
│   │   └── workflow.py              # 工作流模板(晨会/交易/复盘)
│   │
│   ├── ml/                      # ===== 机器学习（跨域）=====
│   │   ├── factor.py                # 因子挖掘
│   │   ├── evolve.py                # 策略进化
│   │   └── rl.py                    # 强化学习
│   │
│   ├── mcp/                     # ===== MCP 协议 =====
│   │   ├── server.py                # MCP 服务端
│   │   └── skill.py                 # Skill 注册
│   │
│   └── dashboard/               # ===== 可视化 =====
│       └── app.py                   # Streamlit 入口
│
├── tests/                       # 测试
│   ├── trading/
│   │   └── test_xtquant_conn.py     # XtQuant 连接测试
│   ├── research/
│   └── agent/
│
├── scripts/                     # 脚本
│   ├── download_data.py             # 下载历史数据
│   └── run_backtest.py              # 运行回测
│
├── docs/                        # 文档
├── main.py                      # 入口
└── .gitignore
```
