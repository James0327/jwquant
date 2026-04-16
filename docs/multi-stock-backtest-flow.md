# 多股票组合回测流程

这份文档描述的是**当前代码里真实存在的多股票组合回测执行链**，不是目标组合投资平台蓝图。

适用场景：

- 回测多只股票
- 使用 `scripts/run_backtest.py`
- 代码通过逗号分隔形式传入，如 `000001.SZ,600519.SH`
- 数据源优先本地，缺失时走 XtQuant 自动补数

对应主入口：

- [run_backtest.py](/Users/james/PycharmProjects/jwquant/scripts/run_backtest.py)

## 1. 一句话结论

当前多股票组合回测主线是：

**逐只股票从本地或 XtQuant 补齐数据 -> 合并成统一时间轴 -> 引擎按时间点分组推进 -> 同一时间点内逐标的执行策略信号 -> bar 风险检查 -> 再平衡 -> 记录组合权益与风险事件 -> 输出结果。**

## 2. 前提说明

当前多股票组合回测复用了单股数据链和单股成交链，但在引擎层额外补了：

- 多代码数据加载
- 同一时间点聚合推进
- 组合权重
- 再平衡
- 组合统一风控

相关代码：

- [run_backtest.py](/Users/james/PycharmProjects/jwquant/scripts/run_backtest.py)
- [feed.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/feed.py)
- [engine.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/engine.py)
- [risk.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/risk.py)

## 3. 时序图

```text
[用户执行组合回测命令]
        |
        v
[scripts/run_backtest.py]
        |
        |-- 解析参数
        |     |- --code 逗号分隔多代码
        |     |- --portfolio-weights
        |     |- --rebalance-frequency
        |     |- --rebalance-tolerance
        |     |- --risk-*
        |
        |-- parse_codes()
        |     -> ["000001.SZ", "600519.SH", ...]
        |
        |-- parse_portfolio_weights()
        |     |- 显式权重，如 code=0.6,code=0.4
        |     |- 或 equal 自动等权
        |
        |-- load_backtest_data()
                |
                |-- 对每个 code 调 DataFeed.get_bars()
                |     |
                |     |-- 本地有数据 -> 直接返回
                |     |-- 本地没数据 -> sync_xtquant_data() 自动补数
                |
                |-- 汇总多只股票 bars
                |-- concat 成一个 DataFrame
                v
        [组合历史行情 DataFrame]

        |
        v
[SimpleBacktester.run_backtest()]
        |
        |-- _prepare_data()
        |     |- 按 dt, code 稳定排序
        |
        |-- 按 dt 分组推进
        |     |
        |     |-- 同一时间点内逐行遍历每个 code
        |     |     |
        |     |     |-- _build_bar()
        |     |     |-- strategy.on_bar(bar)
        |     |     |-- Signal -> Order
        |     |     |-- validate_order()
        |     |     |-- broker.execute_order()
        |     |     |-- 更新 latest_prices
        |     |
        |     |-- 同一时间点策略信号处理完后
        |     |     |
        |     |     |-- check_bar()
        |     |     |     |- 固定止损
        |     |     |     |- 固定止盈
        |     |     |     |- 移动止损
        |     |     |     |- 最大回撤
        |     |     |
        |     |     |-- _apply_rebalance_if_needed()
        |     |     |     |- 判断 daily/weekly/monthly
        |     |     |     |- 解析目标权重
        |     |     |     |- adjust_target_weights()
        |     |     |     |- 生成再平衡订单
        |     |     |     |- 再经过统一风控 -> broker
        |     |     |
        |     |     |-- _record_bar_state()
        |     |           |- 记录组合权益
        |     |           |- 记录当前持仓快照
        |     |           |- 记录风险事件
        |
        v
[输出组合回测结果]
        |
        |- 组合权益统计
        |- 订单统计
        |- 再平衡次数
        |- 风险事件数
        |- 结构化 report
        |- 可选 HTML 报告
```

## 4. 关键步骤说明

### 4.1 多代码输入

脚本通过：

- `parse_codes()`

把：

```text
000001.SZ,600519.SH,300750.SZ
```

解析成代码列表。

### 4.2 多代码数据加载

[run_backtest.py](/Users/james/PycharmProjects/jwquant/scripts/run_backtest.py) 的 `load_backtest_data()` 会：

1. 逐只股票调用 `DataFeed.get_bars()`
2. 哪只股票本地没数据，就只为那只股票自动补数
3. 把所有股票 bars 合并

所以当前不是“先整组合一次下载”，而是：

**按 code 独立补齐，再统一合并。**

### 4.3 组合数据时间轴

[engine.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/engine.py) 当前会：

1. 先按 `dt, code` 排序
2. 再按 `dt` 分组推进

这意味着：

- 同一时间点的多个股票会被视为同一批次
- 组合权益按“时间点”记录一次
- 不是每根 bar 都单独记一次组合净值

### 4.4 同一时间点内的处理顺序

当前固定顺序是：

1. 策略信号
2. bar 风险检查
3. 再平衡
4. 收盘记录

这对组合回测尤其重要，因为：

- 如果顺序改了
- 再平衡订单、止损退出和最终权益都会变

### 4.5 组合权重

当前支持两种方式：

1. 显式权重
   - 如 `000001.SZ=0.6,600519.SH=0.4`
2. `equal`
   - 自动对当前代码列表等权

权重最终会进入：

- [engine.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/engine.py)
- [risk.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/risk.py)

### 4.6 再平衡

当前支持：

- `none`
- `daily`
- `weekly`
- `monthly`

再平衡流程是：

1. 判断当前时间点是否命中再平衡周期
2. 解析目标权重
3. 统一风控裁剪目标权重
4. 生成再平衡订单
5. 再平衡订单也要走风控和 broker

### 4.7 组合风控

多股票场景下，统一风控会更明显地起作用。

当前主要包括：

- 单标的权重限制
- 组合总暴露限制
- 最大持仓标的数
- 单笔金额限制
- 统一止损/止盈/回撤规则

也就是说：

**策略订单和再平衡订单都不是直接成交，而是先经过组合风控。**

### 4.8 组合权益记录

当前 recorder 记录的是：

- 权益曲线
- 订单
- 成交
- 持仓快照
- 风险事件

在多股票场景下，组合权益依赖 `latest_prices` 统一估值，而不是只看当前处理中的单只股票。

## 5. 单股与组合的核心差异

相对单股票回测，多股票组合回测新增了 4 个关键机制：

1. 多代码加载与合并
2. 同一时间点聚合推进
3. 目标权重与再平衡
4. 组合级统一风控

单股票回测主要更像：

- 一条标的 + 一条信号链

组合回测则变成：

- 多条标的信号链
- 一个共享资金池
- 一套共享组合风控
- 一条组合权益曲线

## 6. 关键代码入口

如果你要沿代码继续读，建议顺序是：

1. [run_backtest.py](/Users/james/PycharmProjects/jwquant/scripts/run_backtest.py)
2. [feed.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/feed.py)
3. [engine.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/engine.py)
4. [risk.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/risk.py)
5. [broker.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/broker.py)
6. [recorder.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/backtest/recorder.py)

## 7. 当前边界

这条“多股票组合回测流程”文档描述的是**当前真实主链**，但仍有这些边界：

- 目标权重当前更偏静态配置，不是策略内动态优化器
- 组合风控当前是最小闭环，不是完整组合投资平台
- 当前不是高频撮合，也不是盘口级成交模拟
- 期货组合风控还未完全和股票组合一样成熟

## 8. 使用说明

当前多股票组合回测建议按下面顺序使用：

1. 先为组合里的每个标的准备本地数据，股票建议统一下载 `adj=none` 原始行情
2. 用 `--code code1,code2,...` 传入组合标的列表
3. 用 `--portfolio-weights` 指定权重；如果只想快速试跑，可先用 `equal`
4. 用 `--rebalance-frequency` 控制再平衡频率
5. 组合风控阈值优先用脚本参数显式传入，避免和配置默认值混淆

常用命令模板：

```bash
python scripts/run_backtest.py \
  --strategy double_ma \
  --code 000001.SZ,600519.SH \
  --market stock \
  --timeframe 1d \
  --adj none \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --capital 1000000 \
  --portfolio-weights equal \
  --rebalance-frequency monthly \
  --report-html outputs/backtest-portfolio.html
```

补充说明：

- 当前组合数据是“逐 code 取数后再合并”，不是先把组合当成一个下载任务整体拉取
- `--portfolio-weights equal` 会按当前传入代码列表做等权
- 显式权重之和建议不超过 `1.0`；若超过，仍可能被统一风控裁剪

## 9. 鸿博股份 + 国投丰乐回测示例

这里给一个双标的组合示例：

- 鸿博股份示例按常见证券代码写成 `002229.SZ`
- “国投丰乐”这个名称目前没有在仓库里找到可验证的证券代码，因此下面命令用 `SECOND_CODE` 占位

你只需要把 `SECOND_CODE` 替换成你本地实际要回测的那只证券代码即可。

先下载两只标的的原始行情：

```bash
python scripts/download_data.py \
  --code 002229.SZ \
  --market stock \
  --timeframe 1d \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --adj none
```

```bash
python scripts/download_data.py \
  --code SECOND_CODE \
  --market stock \
  --timeframe 1d \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --adj none
```

再执行组合回测：

```bash
python scripts/run_backtest.py \
  --strategy double_ma \
  --code 002229.SZ,SECOND_CODE \
  --market stock \
  --timeframe 1d \
  --adj none \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --capital 1000000 \
  --portfolio-weights 002229.SZ=0.5,SECOND_CODE=0.5 \
  --rebalance-frequency monthly \
  --rebalance-tolerance 0.02 \
  --risk-max-total-exposure 1.0 \
  --risk-max-single-weight 0.6 \
  --report-html outputs/hongbo-second-portfolio-backtest.html
```

如果你只是想先验证组合主链是否通，可以先改成等权：

```bash
python scripts/run_backtest.py \
  --strategy double_ma \
  --code 002229.SZ,SECOND_CODE \
  --market stock \
  --timeframe 1d \
  --adj none \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --portfolio-weights equal \
  --rebalance-frequency monthly
```
