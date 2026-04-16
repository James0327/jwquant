# 回测模块现状与演进设计

## 1. 当前现状

仓库当前已经具备一套“最小可用”的回测链路，但还不是完整的正式回测框架。

已落地能力：

- 包内已有最小回测实现：
  - [engine.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/engine.py)
  - [stats.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/stats.py)
- 脚本入口：
  - [run_backtest.py](/Users/james/PycharmProjects/jwquant/scripts/run_backtest.py)
- 数据入口：
  - [feed.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/feed.py)

当前回测模型特点：

- 单账户
- 单策略
- 按 Bar 顺序驱动
- `signal -> order -> broker` 的最小订单流程
- 已接入统一下单前风控与 bar 驱动风险检查
- 使用固定金额和整手规则估算仓位
- 只统计基础绩效指标

当前代码里已经补上的最小正式化改进：

- `BacktestConfig.slippage` 已接入成交价格
- 股票 `100` 整手规则已从引擎中抽到 `StockMarketRules`
- 账户、撮合、市场规则已拆出最小模块：
  - `portfolio.py`
  - `broker.py`
  - `market_rules.py`
- 订单流已从 `signal -> 直接成交` 改成 `signal -> order -> broker`
- 记录职责已从引擎中拆出最小模块：
  - `recorder.py`
  - 记录订单、成交、权益曲线、日期、持仓快照
- 市场规则已进一步拉开股票与期货差异：
  - 股票买入仓位当日不可卖，次日结转后可卖
  - 期货保留 `T+0` 可卖语义
- 期货最小交易语义已补上：
  - 保证金占用
  - 合约乘数
  - `open_long / close_long / open_short / close_short`
  - `Asset.frozen_cash` 已能反映期货保证金占用
- 引擎职责已进一步收窄：
  - 数据准备
  - `Bar` 构建
  - 交易日结转
  - 信号执行
  - 收盘记录
  - 结果组装
  已拆成独立私有步骤，`run_backtest()` 主要保留流程编排
- 订单类型已补最小语义：
  - 默认 `market`
  - 支持 `limit`
  - 当 bar 内未满足限价条件时，订单标记为 `CANCELLED`
- 回测报告已补基础结构化输出：
  - 权益记录
  - 订单状态统计
  - 最新持仓快照
  - 基础统计项扩展到 `profit_factor / avg_trade_profit / avg_win_profit / avg_loss_profit`
- 多标的最小组合能力已补上：
  - 同一时间点支持多标的 bar 顺序推进
  - 组合权益按时间点聚合记录
  - 脚本支持逗号分隔多代码输入
- 组合层已补最小静态配权与再平衡能力：
  - 支持配置目标权重
  - 支持 `daily / weekly / monthly` 再平衡
  - 未配置显式权重时，可按当前标的自动等权
- 统一组合风控已补最小闭环：
  - 支持单标的权重上限
  - 支持组合总暴露上限
  - 风控事件会进入结构化 report
  - 风控事件当前已带 `category / source`
  - 普通策略订单与再平衡订单都会经过统一风控校验
- 风控配置与报告能力已继续增强：
  - 回测脚本默认可读取 `[backtest.risk]` 配置
  - 统一风控当前按规则 `priority` 执行，冲突策略为 `priority_first`
  - report 已新增 `risk_by_type / risk_by_category / risk_by_source / risk_by_action`
- 同一时间点内当前执行顺序已固定为：
  - 策略信号
  - bar 风险检查
  - 再平衡
  - 收盘记录

当前仍然存在但尚未完全解决的点：

- `market`、`timeframe`、`adj` 已在脚本入口存在，但订单类型仍是最小模型，暂不含 `stop / stop-limit / partial fill`
- 当前期货回测仍未覆盖逐日盯市、强平、多合约组合和更完整手续费模型
- 第 6 步虽然已完成“编排化”，但还没有把信号适配、订单工厂、结果汇总器进一步独立成专门模块
- 当前报表仍是终端文本 + 结构化 dict，尚未提供图表、HTML、持仓归因等更完整展示
- 当前组合能力仍是最小实现：
  - 目标权重主要面向静态配置，不是策略内动态优化器
  - 再平衡当前按 `daily / weekly / monthly` 粒度触发
  - 统一风控当前主要覆盖股票组合暴露约束，期货组合风控仍待继续细化
- 更完整的统一风控模块设计，已单独整理到：
  - [risk-design.md](/Users/james/PycharmProjects/jwquant/docs/risk-design.md)

## 2. 当前边界

当前实现明确**不是**这些能力：

- 不是 Backtrader 封装
- 不是完整的多资产组合优化与风控平台
- 不是盘口级撮合
- 不是完整期货逐日盯市/强平引擎
- 不是参数优化平台
- 不是订单簿/委托状态驱动模型
- 不是完整的股票/期货统一正式撮合器
- 不是“传了 `--market futures` 就具备期货交易语义”的完整期货回测

当前更适合作为：

- 策略开发早期验证
- 本地数据链路联调
- 简单收益/回撤检查
- 股票策略的快速原型验证

## 3. 现有模块职责

### `trading.backtest.engine`

负责：

- 驱动回测主循环
- 调用策略 `on_bar(bar)`
- 执行最小成交逻辑
- 维护现金、持仓、权益曲线

当前已实现对象：

- `BacktestConfig`
- `SimpleBacktester`
- `Portfolio`
- `SimBroker`
- `BacktestRecorder`
- `StockMarketRules`
- `FuturesMarketRules`

### `trading.backtest.stats`

负责：

- 总收益率
- 年化收益
- 波动率
- 夏普比率
- 最大回撤
- 胜率
- 总手续费

### `scripts/run_backtest.py`

负责：

- 解析命令行参数
- 读取本地行情
- 本地无数据时触发 XtQuant 自动同步
- 调用包内回测引擎
- 输出结果

## 4. 下一阶段建议

当前 1-10 步基础回测与统一风控已经打通，下一阶段更适合继续补这些能力：

- 动态权重生成与组合优化
- 更完整的期货组合风控
- 分钟级更细粒度撮合
- 主连换月回测
- 参数优化
- walk-forward
- 报表与可视化

## 5. 设计原则

1. 数据读取统一走 `DataFeed`
2. 策略接口先保持 `on_bar(bar)` 不变
3. 先保留当前最小引擎，再逐步拆分职责
4. 股票与期货规则不要混写
5. 先写单测，再扩引擎能力

## 6. 当前最值得先补的缺口

按优先级建议是：

1. 后续增强动态权重生成、组合优化与更完整期货组合风控
2. 后续增强更细粒度撮合与更完整报表输出

## 7. 推荐落地顺序

建议按这个顺序推进，风险最小：

1. 后续增强动态权重生成、组合优化与更完整期货组合风控
2. 后续增强更细粒度撮合与更完整报表输出

这样做的好处是：

- 不会一次性重写回测主流程
- 现有 `run_backtest.py` 可以持续可用
- 每一步都可以单独补测试
- 后面股票 T+1、期货保证金、多资产组合都更容易接进去

## 8. 进度计划表

说明：

- 本表用于跟踪回测模块推进状态
- 每次完成一轮编码后，都要同步更新这里
- 状态约定：
  - `已完成`
  - `进行中`
  - `待开始`

| 步骤 | 内容 | 当前状态 | 说明 |
| --- | --- | --- | --- |
| 1 | 拆出最小 `Portfolio / Broker / MarketRules`，让引擎不再兼任全部职责 | 已完成 | 已落地到 `portfolio.py`、`broker.py`、`market_rules.py`，并接入 `engine.py` |
| 2 | 引入最小 `Order`，把流程改成 `signal -> order -> broker` | 已完成 | 已补订单创建、订单状态、拒单路径和相关测试 |
| 3 | 引入最小 `Recorder`，拆出订单、成交、权益曲线、日期、持仓快照记录 | 已完成 | 已落地到 `recorder.py`，记录层不再直接依赖 `Portfolio` 内部结构，引擎通过兼容属性继续暴露原有访问方式 |
| 4 | 细化 `MarketRules`，继续拉开股票与期货规则差异 | 已完成 | 已补股票 `T+1` 可卖数量结转和期货 `T+0` 可卖语义，相关差异已进入规则层与测试 |
| 5 | 为期货补保证金、乘数、开平语义 | 已完成 | 已支持期货保证金占用、合约乘数、开多/平多/开空/平空的最小闭环，`Asset.frozen_cash` 也已反映保证金占用，并补相关测试 |
| 6 | 收窄 `SimpleBacktester` 职责，只保留流程编排 | 已完成 | 数据准备、Bar 构建、交易日结转、信号执行、收盘记录、结果组装已拆成独立私有步骤，主循环以编排为主 |
| 7 | 为订单补类型语义，如 `market / limit` | 已完成 | 已支持默认市价单与最小限价单语义，未满足条件的限价单会在当 bar 内取消，并补相关测试 |
| 8 | 扩展记录与报表输出 | 已完成 | 已补结构化 report、权益记录、订单状态统计和更完整的基础绩效指标，并接入脚本输出 |
| 9 | 增强多标的与组合能力 | 已完成 | 已支持多标的输入、按时间点聚合推进和组合权益记录，脚本可直接接受逗号分隔多代码 |
| 10 | 补组合权重、再平衡与统一风控 | 已完成 | 已支持静态目标权重、定时再平衡、组合总暴露/单标的权重限制，并将风险事件写入 report 与脚本输出 |
