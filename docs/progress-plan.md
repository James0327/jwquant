# 项目整体进度计划表

## 1. 说明

这份文档用于汇总当前仓库的整体推进状态，方便后续继续开发时快速定位：

- 哪些主线已经打通
- 哪些步骤已经完成
- 哪些能力已经有最小可用版本
- 哪些内容仍然是后续阶段

状态约定：

- `已完成`
- `进行中`
- `待开始`

---

## 2. 数据主线

| 步骤 | 内容 | 当前状态 | 说明 |
| --- | --- | --- | --- |
| D1 | 本地存储层落地 | 已完成 | 已支持 `csv / sqlite / rocksdb / hdf5`，默认使用 `rocksdb` |
| D2 | RocksDB 存储结构与索引 | 已完成 | 已按 `market + timeframe` 分仓，行情与复权因子分离存储 |
| D3 | 下载脚本接入本地存储 | 已完成 | `scripts/download_data.py` 已能下载并落库 |
| D4 | XtQuant 股票 / 期货下载链路 | 已完成 | A 股与期货都已支持，底层按市场隔离 |
| D5 | 增量下载 | 已完成 | 已支持本地最新时间后的增量同步 |
| D6 | 原始行情与复权因子分离 | 已完成 | 股票底层存 `none` 原始行情，复权因子单独存储 |
| D7 | 读取侧动态复权 | 已完成 | `DataFeed` 已支持 `none / qfq / hfq` 动态生成 |
| D8 | 回测入口接本地数据与自动同步 | 已完成 | 回测优先读本地，无数据时可自动同步 |
| D9 | 脚本与测试目录整理 | 已完成 | `scripts/` 与 `tests/` 已按用途重新整理，`pytest` 收集边界已固定 |

相关文档：

- [data-pipeline.md](/Users/james/PycharmProjects/jwquant/docs/data-pipeline.md)

---

## 3. 回测主线

| 步骤 | 内容 | 当前状态 | 说明 |
| --- | --- | --- | --- |
| B1 | 拆出最小 `Portfolio / Broker / MarketRules` | 已完成 | 引擎不再兼任全部职责 |
| B2 | 引入最小 `Order` 流程 | 已完成 | 已从 `signal -> 直接成交` 收敛为 `signal -> order -> broker` |
| B3 | 引入最小 `Recorder` | 已完成 | 订单、成交、权益、持仓快照记录已独立 |
| B4 | 细化股票 / 期货规则差异 | 已完成 | 股票 `T+1`、期货 `T+0` 已进入规则层 |
| B5 | 期货最小交易语义 | 已完成 | 已支持保证金、乘数、开平语义 |
| B6 | 收窄 `SimpleBacktester` 职责 | 已完成 | 主循环以编排为主 |
| B7 | 订单类型最小语义 | 已完成 | 已支持 `market / limit` |
| B8 | 结构化 report | 已完成 | 已支持结构化回测结果输出 |
| B9 | 多标的与组合能力 | 已完成 | 已支持多代码输入与按时间点聚合推进 |
| B10 | 组合权重、再平衡、统一风控 | 已完成 | 已支持静态配权、定时再平衡、统一风控接入 |
| B11 | 风控统计增强 | 已完成 | report 已补 `risk_by_type / risk_by_category / risk_by_source / risk_by_action` |
| B12 | HTML 报告导出 | 已完成 | `run_backtest.py --report-html ...` 可生成可视化 HTML 报告 |

相关文档：

- [backtest-design.md](/Users/james/PycharmProjects/jwquant/docs/backtest-design.md)

---

## 4. 风控主线

| 步骤 | 内容 | 当前状态 | 说明 |
| --- | --- | --- | --- |
| R1 | `RiskCheckContext / RiskDecision / BaseRiskRule` 协议层 | 已完成 | 最小协议与导出已落地 |
| R2 | `RiskInterceptor` 总入口 | 已完成 | 已支持 `order / bar / portfolio` 三阶段 |
| R3 | 单标的仓位规则 | 已完成 | 已支持单笔金额、单标的仓位、股票裸卖空、期货方向限制 |
| R4 | 组合级规则 | 已完成 | 已支持总暴露、持仓数、目标权重裁剪 |
| R5 | `backtest.risk` 收敛到 `trading.risk` | 已完成 | `PortfolioRiskManager` 已统一调用 `trading.risk` |
| R6 | 统一止盈止损 | 已完成 | 已支持固定止损、固定止盈、移动止损、最大回撤 |
| R7 | 回测引擎下单前风控接入 | 已完成 | 普通策略单与再平衡单都已统一校验 |
| R8 | 回测引擎 bar 风险检查接入 | 已完成 | 已统一消费 `risk_signals` 并转退出订单 |
| R9 | 风控测试与文档 | 已完成 | `tests/common`、`tests/trading` 和设计文档已补齐 |
| R10 | 风险配置外部化 | 已完成 | 已新增 `RiskConfig`，回测脚本默认读取 `[backtest.risk]` |
| R11 | 风险优先级与仲裁 | 已完成 | 规则已支持 `priority`，当前策略为 `priority_first` |
| R12 | 执行前风控入口 | 已完成 | 已新增 `ExecutionRiskGuard`，可用于真实下单前校验 |
| R13 | 期货组合风控增强 | 已完成 | 已补期货保证金占权益约束 `max_futures_margin_ratio` 的最小闭环 |

相关文档：

- [risk-design.md](/Users/james/PycharmProjects/jwquant/docs/risk-design.md)

---

## 5. 执行与报告主线

| 步骤 | 内容 | 当前状态 | 说明 |
| --- | --- | --- | --- |
| E1 | 执行层目录预留 | 已完成 | `trading.execution` 目录已存在 |
| E2 | 执行前统一风控入口 | 已完成 | 已新增 `ExecutionRiskGuard` |
| E3 | 风险报告结构化增强 | 已完成 | 回测报告已带分类、来源、动作统计 |
| E4 | 风险报告 HTML 可视化 | 已完成 | 已支持生成自包含 HTML 报告 |
| E5 | 真实券商执行闭环 | 待开始 | 当前仍未接入真实下单执行主链 |

---

## 6. 当前已完成的主线结论

目前已经可以认为完成的部分：

1. 数据下载、存储、读取、动态复权主链已打通
2. 回测引擎最小正式化已打通
3. 统一风控模块已从协议层一直接到回测主循环
4. 回测报告已支持结构化输出和 HTML 可视化
5. 执行前风控已经有可复用入口

---

## 7. 当前仍建议继续推进的方向

虽然主链已经比较完整，但下面这些仍然适合作为下一阶段重点：

1. 更完整的期货组合风控  
说明：当前已补最小保证金占比约束，但仍未覆盖逐日盯市、强平、今昨仓、多合约组合风险。

2. 动态权重生成与组合优化  
说明：当前目标权重仍以静态配置为主，不是策略内动态优化器。

3. 更细粒度撮合  
说明：当前仍是 bar 级最小撮合，不含盘口、部分成交、撤单队列等语义。

4. 真实执行主链  
说明：`ExecutionRiskGuard` 已有，但真实 broker / order / loop 还没有接成完整闭环。

5. 更完整报告体系  
说明：当前已支持 HTML 报告，但还没有图表交互、归因分析、参数对比和批量报告聚合。
