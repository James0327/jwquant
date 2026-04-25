# 单股票回测流程

这份文档描述的是**当前代码里真实存在的单股票回测执行链**，不是目标架构图。

适用场景：

- 回测单只股票
- 数据源配置为 XtQuant
- 本地存储为 `rocksdb/csv/sqlite/hdf5` 任一格式

对应主入口：

- [run_backtest.py](/Users/james/PycharmProjects/jwquant/scripts/run_backtest.py)

## 1. 一句话结论

当前单股票回测主线是：

**先本地读股票原始行情 -> 本地没数据时用 XtQuant 分页同步 -> DataFeed 按需动态复权 -> 策略发信号 -> 统一风控拦截 -> broker 模拟成交 -> recorder 记录 -> 输出回测结果。**

## 2. 前提说明

当前数据口径有两个关键点：

1. 股票底层始终存原始行情 `adj=none`
2. `qfq/hfq` 只在读取侧动态生成，不在下载时直接落复权价格

相关代码：

- [store.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/store.py)
- [feed.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/feed.py)
- [sync.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/sync.py)

## 3. 时序图

```text
[用户执行回测命令]
        |
        v
[scripts/run_backtest.py]
        |
        |-- 加载配置
        |     |- settings.common.toml
        |     |- settings.live.toml
        |     |- backtest.cost
        |     |- backtest.risk
        |
        |-- 创建策略实例
        |
        |-- 调 load_backtest_data()
                |
                v
         [DataFeed.get_bars()]
                |
                |-- 先读本地存储
                |     |
                |     v
                | [LocalDataStore]
                |     |- 股票底层存原始行情 none
                |     |- 复权因子单独存储
                |
                |-- 如果本地已有数据 --------------------+
                |                                        |
                |                                        v
                |                              [返回 bars 给回测]
                |
                |-- 如果本地没数据
                        |
                        v
                [sync_xtquant_data()/sync_market_data()]
                        |
                        |-- 计算增量起点 / 断点续传起点
                        |-- 按时间窗口分页下载
                        |     |- day / month / quarter / year
                        |     |- 默认 month
                        |-- 单个窗口支持重试
                        |
                        v
                [XtQuantDataSource.download_bars()]
                        |
                        |-- xtdata.download_history_data(...)
                        |-- xtdata.get_local_data(...)
                        |-- 标准化成 DataFrame
                        |
                        v
                [LocalDataStore.upsert_bars()]
                        |
                        |-- 股票额外下载并写入复权因子
                        v
                [重新用 DataFeed.get_bars() 读取]
                        |
                        |-- adj=none -> 直接返回原始行情
                        |-- adj=qfq/hfq -> 原始行情 + 因子动态复权
                        v
                [返回 bars 给回测]

        |
        v
[SimpleBacktester.run_backtest()]
        |
        |-- 按 dt 顺序推进 bar
        |
        |-- 每根 bar 调 strategy.on_bar(bar)
        |         |
        |         v
        |      [Signal]
        |
        |-- Signal -> Order
        |
        |-- 下单前统一风控
        |     |
        |     v
        | [PortfolioRiskManager.validate_order()]
        |     |- 单笔金额限制
        |     |- 单标的权重限制
        |     |- 总暴露限制
        |     |- ALLOW / ADJUST / BLOCK
        |
        |-- 若放行/裁单后继续
        |     |
        |     v
        | [SimBroker.execute_order()]
        |     |- 计算滑点
        |     |- 计算佣金
        |     |- 模拟撮合成交
        |     |- 更新 Portfolio
        |
        |-- 同一时间点再做 bar 风险检查
        |     |
        |     v
        | [PortfolioRiskManager.check_bar()]
        |     |- 固定止损
        |     |- 固定止盈
        |     |- 移动止损
        |     |- 最大回撤
        |     |- 生成 risk_signals
        |
        |-- risk_signals -> 退出订单 -> 风控 -> broker
        |
        |-- Recorder 记录
        |     |- 订单
        |     |- 成交
        |     |- 权益曲线
        |     |- 持仓快照
        |     |- 风险事件
        |
        v
[输出结果]
        |
        |- 终端打印统计
        |- 结构化 results
        |- 可选 HTML 报告
```

## 4. 关键步骤说明

### 4.1 脚本入口

[run_backtest.py](/Users/james/PycharmProjects/jwquant/scripts/run_backtest.py) 负责：

- 解析命令行参数
- 加载配置
- 创建策略实例
- 调用 `DataFeed` 取数
- 组装 `BacktestConfig`
- 调用包内回测引擎

### 4.2 数据读取优先级

单股票回测时，数据优先级是：

1. 本地存储
2. XtQuant 自动补数
3. 样例数据兜底

也就是说，当前回测**优先依赖本地数据，但不是只依赖本地数据**。

### 4.3 XtQuant 自动补数

当本地没有这只股票的数据时，会进入：

- [sync.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/sync.py)

当前同步策略：

- 支持增量下载
- 支持断点续传
- 支持按时间窗口分页
- 默认按月下载
- 单个时间窗口支持重试

### 4.4 复权处理

股票回测时：

- `--adj none`
  - 直接使用本地原始行情
- `--adj qfq`
  - 从本地原始行情 + 本地复权因子动态生成前复权
- `--adj hfq`
  - 从本地原始行情 + 本地复权因子动态生成后复权

这一步由 [feed.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/feed.py) 负责。

### 4.5 回测执行顺序

当前单股票回测在每个时间点的顺序已固定为：

1. 策略信号
2. bar 风险检查
3. 再平衡
4. 收盘记录

其中单股票场景通常不会体现组合再平衡的复杂性，但执行顺序和多标的是一致的。

### 4.6 风控与成交

订单不会直接成交，而是经过：

1. `Signal -> Order`
2. `PortfolioRiskManager.validate_order()`
3. `SimBroker.execute_order()`

风控可能的结果：

- `ALLOW`
- `ADJUST`
- `BLOCK`

只有放行或裁单后，订单才会进入 broker 模拟成交。

### 4.7 成本模型

当前单股票回测使用最小成本模型：

- 佣金 = 成交额 × `commission_rate`
- 滑点 = 按买卖方向对成交价做比例偏移

相关默认值来自：

- [settings.common.toml](/Users/james/PycharmProjects/jwquant/config/settings.common.toml) 的 `[backtest.cost]`

## 5. 关键代码入口

如果你要沿代码继续读，建议顺序是：

1. [run_backtest.py](/Users/james/PycharmProjects/jwquant/scripts/run_backtest.py)
2. [feed.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/feed.py)
3. [sync.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/sync.py)
4. [xtquant_src.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/sources/xtquant_src.py)
5. [engine.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/engine.py)
6. [risk.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/risk.py)
7. [broker.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/broker.py)

## 6. 当前边界

这条“单股票回测流程”文档描述的是**当前真实主链**，但仍有这些边界：

- 回测优先读本地，但缺数据时仍会尝试自动下载
- 当前不是盘口级撮合
- 当前不是完整实盘执行链
- 股票复权是读取时动态生成，不是下载时直接保存复权价格

## 7. 使用说明

当前单股票回测建议按下面顺序使用：

1. 先确认本地已配置 XtQuant，且 `config/settings.common.toml` + `config/settings.live.toml` 的数据源与本地存储路径可用
2. 先用 `scripts/download_data.py` 预下载目标股票的原始行情与复权因子
3. 再执行 `scripts/run_backtest.py` 做回测
4. 默认建议股票回测显式传 `--adj none`，先验证原始行情链路
5. 需要看动态复权结果时，再改为 `--adj qfq` 或 `--adj hfq`

常用命令模板：

```bash
python scripts/download_data.py \
  --code 000001.SZ \
  --market stock \
  --timeframe 1d \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --adj none
```

```bash
python scripts/run_backtest.py \
  --strategy single_ma \
  --code 000001.SZ \
  --market stock \
  --timeframe 1d \
  --adj none \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --capital 1000000 \
  --report-html outputs/backtest-single.html
```

补充说明：

- `--code` 当前脚本支持单代码，也支持逗号分隔多代码；本页聚焦单股场景
- `--adj` 只影响读取侧，不会改变 RocksDB 中已落库的原始行情
- 若本地没有数据，回测脚本会尝试自动走 XtQuant 补数；如果你希望流程更可控，建议先执行下载脚本

## 8. 鸿博股份回测示例

下面给一个单股示例。这里按常见证券代码写成 `002229.SZ`，但**请以你本地实际使用的证券代码为准**。

先下载：

```bash
python scripts/download_data.py \
  --code 002229.SZ \
  --market stock \
  --timeframe 1d \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --adj none
```

再回测：

```bash
python scripts/run_backtest.py \
  --strategy single_ma \
  --code 002229.SZ \
  --market stock \
  --timeframe 1d \
  --adj none \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --capital 1000000 \
  --commission-rate 0.0003 \
  --slippage 0.0005 \
  --report-html outputs/hongbo-single-backtest.html
```

如果你要检查“原始行情”和“动态前复权”差异，可以在同一时间段分别跑两次：

```bash
python scripts/run_backtest.py \
  --strategy single_ma \
  --code 002229.SZ \
  --market stock \
  --timeframe 1d \
  --adj qfq \
  --start 2024-01-01 \
  --end 2024-12-31
```
