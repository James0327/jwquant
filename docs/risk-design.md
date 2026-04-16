# 风控模块设计

## 1. 目标

`trading.risk` 的目标不是只服务某一个回测脚本，而是提供一套可复用的统一风控层，供以下场景共同使用：

- 回测前/回测中下单拦截
- 组合权重裁剪与再平衡约束
- 策略统一止盈止损
- 未来模拟盘/实盘下单前风控

设计原则：

1. 风控模块负责判断、裁剪、拦截、产出事件，不负责撮合成交
2. 风控模块不直接替代策略，但可以在策略信号之后追加统一约束
3. 回测、模拟、实盘尽量共用同一套规则协议
4. 先做最小闭环，再逐步补完整规则

---

## 2. 当前现状

当前仓库已经有两部分与风控相关的实现，但还没有形成正式统一模块：

- 策略内自带的仓位控制、止盈止损
  - 例如 [turtle.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/turtle.py) 中的 `risk_ratio`、`stop_loss_price`
- 回测层内部最小组合风控
  - 例如 [risk.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/risk.py)
  - 已支持：
    - 单标的权重上限
    - 组合总暴露上限
    - 目标权重裁剪
    - 风险事件记录

当前 [rules.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/risk/rules.py) 仍是占位说明，还没有成为正式模块入口。

---

## 3. 设计边界

`trading.risk` 应该负责：

- 仓位限制
- 组合暴露限制
- 再平衡目标权重裁剪
- 黑名单/白名单规则
- 最大回撤/熔断
- 固定止损/止盈
- 移动止损
- 风险事件标准化输出

`trading.risk` 不应该负责：

- 撮合成交
- 账户记账
- 手续费计算
- 行情驱动主循环
- 策略 alpha 逻辑

一句话说，风控模块负责“能不能下、该不该裁、是否该强制退”，不负责“怎么成交”。

---

## 4. 建议模块结构

建议目录结构：

```text
jwquant/trading/risk/
├── __init__.py
├── context.py        # 风控判断上下文
├── rules.py          # 风控规则协议和基础规则
├── interceptor.py    # 统一拦截入口
├── position.py       # 单标的仓位规则
├── portfolio.py      # 组合级规则
└── stop.py           # 止盈止损规则
```

### 4.1 `context.py`

定义统一风控判断输入。

建议对象：

- `RiskCheckContext`
  - `dt`
  - `market`
  - `code`
  - `bar_price`
  - `order`
  - `asset`
  - `position`
  - `portfolio_positions`
  - `portfolio_equity`
  - `latest_prices`

作用：

- 统一规则输入
- 避免每条规则自己拼参数
- 后续回测和实盘共用

### 4.2 `rules.py`

定义规则协议和统一返回结果。

建议对象：

- `BaseRiskRule`
- `RiskDecision`
  - `allowed`
  - `adjusted_order`
  - `events`

规则动作建议统一为三类：

- `ALLOW`
- `ADJUST`
- `BLOCK`

### 4.3 `position.py`

单标的规则。

第一批建议放：

- 最大单笔下单金额
- 最大单标的仓位比例
- 股票最小交易单位限制
- 禁止裸卖空
- 期货开仓方向限制

### 4.4 `portfolio.py`

组合级规则。

第一批建议放：

- 最大总暴露
- 最大单标的权重
- 最大持仓标的数
- 组合目标权重裁剪
- 再平衡前后暴露校验

### 4.5 `stop.py`

统一止盈止损规则。

第一批建议放：

- 固定止损
- 固定止盈
- 移动止损
- 组合最大回撤止损

注意：

- 这一层不直接成交
- 这一层只产出风险事件和建议动作
- 真正卖出仍走回测/执行主链

### 4.6 `interceptor.py`

统一入口。

建议职责：

- 顺序执行规则
- 聚合风险事件
- 给出最终决策
- 向上层返回：
  - 允许
  - 裁剪后允许
  - 拒绝

---

## 5. 与回测的结合方式

建议接两处。

### 5.1 下单前拦截

接入点：

- [engine.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/engine.py)
- [broker.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/broker.py)

流程：

```text
Signal -> Order -> RiskInterceptor -> Broker -> Portfolio
```

这一层主要负责：

- 仓位限制
- 组合暴露限制
- 黑名单
- 再平衡订单约束

### 5.2 Bar 驱动风险检查

接入点：

- 回测主循环每个时间点推进后

流程：

```text
Bar -> Strategy.on_bar -> RiskInterceptor.check_bar -> 补充风险信号 -> Broker
```

当前回测实现里，同一时间点的实际执行顺序已经固定为：

```text
策略信号 -> bar 风险检查 -> 再平衡 -> 收盘记录
```

这一层主要负责：

- 固定止损
- 固定止盈
- 移动止损
- 组合回撤熔断

---

## 6. 与策略层的关系

当前策略里已经存在一部分仓位控制和止盈止损逻辑，例如：

- [turtle.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/turtle.py)
- [grid.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/grid.py)
- [single_ma.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/single_ma.py)

建议关系如下：

1. 策略层仍然允许保留专属规则
2. 风控层负责统一约束和通用能力
3. 两者并存时，按这个顺序：
   1. 策略先产出原始信号
   2. 风控层做下单前检查
   3. 风控层按 bar 追加统一止盈止损信号

这样做的好处：

- 不打断现有策略
- 可以逐步把重复风控逻辑收敛到 `trading.risk`
- 未来更容易复用到实盘执行层

---

## 7. 与组合权重、再平衡、统一风控的关系

当前组合相关能力已经在回测层最小落地：

- 静态目标权重
- 定时再平衡
- 单标的权重上限
- 组合总暴露上限

这部分后续应从 [backtest/risk.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/risk.py) 逐步收敛到 `trading.risk`，避免长期形成两套风控实现。

建议演进方向：

1. 先把协议层统一
2. 再迁移现有组合风控逻辑
3. 再补统一止盈止损
4. 最后扩到更完整的期货组合风控

---

## 8. 进度计划表

说明：

- 本表用于跟踪 `trading.risk` 正式化进度
- 每次完成一轮编码后，都要同步更新这里
- 状态约定：
  - `已完成`
  - `进行中`
  - `待开始`

| 步骤 | 内容 | 当前状态 | 说明 |
| --- | --- | --- | --- |
| 1 | 建立 `RiskCheckContext / RiskDecision / BaseRiskRule` 基础协议 | 已完成 | 已落地最小协议层、基础导出和定向测试，后续规则和拦截器可在此基础上扩展 |
| 2 | 实现 `RiskInterceptor` 总入口 | 已完成 | 已补 `check_order / check_bar / check_portfolio` 三类入口，规则可按阶段分发执行，并有定向测试覆盖 |
| 3 | 接入单标的仓位控制规则 | 已完成 | 已补最大单笔金额、最大单标的仓位比例、股票裸卖空限制和期货开仓方向限制，并有定向测试覆盖 |
| 4 | 接入组合级风险规则 | 已完成 | 已补最大总暴露、最大持仓数、目标权重裁剪规则，并支持通过上下文更新回写裁剪后的目标权重 |
| 5 | 将现有 `backtest.risk` 逻辑迁移/收敛到 `trading.risk` | 已完成 | `PortfolioRiskManager` 已保留兼容接口，内部统一改为调用 `trading.risk` 规则与上下文；股票回测下单已支持 `ADJUST` 后继续执行裁剪单，期货订单也已纳入统一暴露校验 |
| 6 | 实现统一止盈止损规则 | 已完成 | 已落地 `stop.py`，支持固定止损、固定止盈、移动止损、最大回撤止损；统一通过 `metadata[\"risk_signals\"]` 产出退出信号，运行时状态统一收敛到 `metadata[\"risk_state\"]`，并已在回测主循环中消费 |
| 7 | 在回测引擎中接入下单前风控拦截 | 已完成 | 普通策略单和再平衡单都在 `engine._submit_order()` 中经过统一 `PortfolioRiskManager.validate_order()` 校验，`ALLOW/ADJUST/BLOCK` 都已进入主链 |
| 8 | 在回测引擎中接入 bar 驱动风险检查 | 已完成 | 回测主循环按时间点调用 `PortfolioRiskManager.check_bar()`，统一消费 `risk_signals` 并生成退出订单，已支持固定止损、固定止盈、移动止损和最大回撤 |
| 9 | 补测试与文档 | 已完成 | 已补 `tests/common` 规则单测、`tests/trading` 回测集成测试、`PortfolioRiskManager` 定向测试，并同步更新设计文档与进度表 |

补充约定：

- 风险事件统一带 `category / source`
- `risk_signals` 继续作为退出信号输出通道
- `risk_state` 作为 bar 风险规则的运行时状态容器
- 规则执行顺序按 `priority` 从小到大仲裁，当前冲突策略为 `priority_first`
- 已提供执行前风控入口，可在真实下单前复用统一规则

---

## 9. 后续增强已落地

本轮额外补齐了原先列为“可后置”的几项能力：

1. 风险配置外部化
- 已新增 `RiskConfig`
- 回测脚本默认会读取 `[backtest.risk]`
- 执行前风控入口默认会读取统一风控配置对象

2. 风险优先级与仲裁
- `BaseRiskRule` 已支持 `priority`
- `RiskInterceptor` 已按优先级排序执行规则
- 当前仲裁策略固定为 `priority_first`

3. 实盘执行前风控接入
- 已新增 `ExecutionRiskGuard`
- 支持在执行层对订单做统一下单前校验
- 当前仍是执行前校验入口，不直接负责真实下单

4. 风险报告增强
- 回测 report 已新增：
  - `risk_by_type`
  - `risk_by_category`
  - `risk_by_source`
  - `risk_by_action`
