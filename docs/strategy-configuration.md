# JWQuant 策略参数说明

这份文档以 [strategies.toml](/Users/james/PycharmProjects/jwquant/config/strategies.toml) 为准，说明当前各策略参数的用途、取值语义和调参时需要注意的点。

## 1. 读取方式

当前大部分策略通过 [config.py](/Users/james/PycharmProjects/jwquant/jwquant/common/config.py) 的 `get_strategy_config(strategy_name, default)` 读取配置。

典型调用链：

- [single_ma.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/single_ma.py)
- [double_ma.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/double_ma.py)
- [three_ma_cross.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/three_ma_cross.py)
- [macd_base.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/macd_base.py)

优先级：

1. 策略类里的默认值
2. `config/strategies.toml`
3. 创建策略实例时传入的 `params`

也就是说，运行时显式传入的 `params` 优先级最高。

## 2. 指标公共配置

### `[indicators.macd]`

这组是 MACD 指标层面的公共参数模板。

- `fast_period`
  - MACD 快线周期
  - 常见值 12
- `slow_period`
  - MACD 慢线周期
  - 常见值 26
- `signal_period`
  - MACD 信号线周期
  - 常见值 9
- `divergence_window`
  - 背离识别时的局部窗口大小
  - 值越大，拐点识别越保守

注意：

- 当前 MACD 类策略多数直接读取各自 `strategies.*` 下的 MACD 参数
- 这组更适合作为公共指标模板或后续统一引用的基础配置

## 3. 海龟策略

### `[strategies.turtle]`

对应实现：

- [turtle.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/turtle.py)

- `entry_window`
  - 入场突破窗口
  - 值越大，信号越少、更偏中期趋势
- `exit_window`
  - 离场突破窗口
  - 值越小，离场越敏感
- `atr_period`
  - ATR 计算周期
  - 用于估算波动和风险单位
- `risk_ratio`
  - 单次风险比例
  - `0.01` 表示单次风险控制在账户权益的 1%

调参建议：

- 趋势更强的市场可保留较长 `entry_window`
- 若想更快止损，可适当减小 `exit_window`
- `risk_ratio` 不宜过大，否则单次波动对净值影响会放大

## 4. 网格策略

### `[strategies.grid]`

对应实现：

- [grid.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/grid.py)

- `grid_count`
  - 网格数量
  - 值越大，网格更密，交易次数通常更多
- `grid_spacing`
  - 网格间距
  - `0.02` 表示每格价格间距约 2%
- `base_amount`
  - 每格基础交易金额
  - 单位为账户计价货币

调参建议：

- 震荡更明显的品种，可适当增加 `grid_count`
- 波动较大时，过小的 `grid_spacing` 可能导致过度交易
- `base_amount` 应结合账户规模控制

## 5. 轮动策略

### `[strategies.rotation]`

对应实现：

- [rotation.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/rotation.py)

- `holding_count`
  - 目标持仓股票数量
  - `5` 表示每次持有 5 只
- `rebalance_days`
  - 调仓周期，按交易日计
  - `5` 表示大约每周调仓一次
- `market_cap_limit`
  - 市值上限，单位通常按“亿”
  - `50` 可理解为只考虑市值不超过 50 亿的标的

调参建议：

- `holding_count` 越大，组合越分散
- `rebalance_days` 越短，交易越频繁
- `market_cap_limit` 越小，组合越偏小盘风格

## 6. 缠论策略

### `[strategies.chanlun]`

对应实现：

- [chanlun.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/chanlun.py)

- `min_bi_length`
  - 最小笔长度
  - 值越大，结构识别越保守
- `zhongshu_count`
  - 中枢构成笔数
  - 值越大，结构确认要求越严格

调参建议：

- 想减少噪音，可适当提高 `min_bi_length`
- `zhongshu_count` 提高后，信号一般会更少但更严格

## 7. 单均线策略

### `[strategies.single_ma]`

对应实现：

- [single_ma.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/single_ma.py)

- `ma_period`
  - 均线周期
  - 值越短，反应越快但噪音更多
  - 值越长，信号更稳但滞后更明显
- `min_history`
  - 最小历史数据要求
  - 历史数据不足时，策略不会发出信号

调参建议：

- 日线常见可从 `15 ~ 30` 开始试
- `min_history` 通常应不小于主要指标周期

## 8. 双均线策略

### `[strategies.double_ma]`

对应实现：

- [double_ma.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/double_ma.py)

- `short_ma_period`
  - 短期均线周期
- `long_ma_period`
  - 长期均线周期
- `min_history`
  - 最小历史数据要求

常见理解：

- `short_ma_period < long_ma_period`
- 短均线上穿长均线通常对应买入信号
- 短均线越短，策略越敏感

调参建议：

- 常见起点：`5 / 10`、`10 / 30`
- `min_history` 应不小于长期均线周期，通常再多留一些缓冲

## 9. 三均线穿越策略

### `[strategies.three_ma_cross]`

对应实现：

- [three_ma_cross.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/three_ma_cross.py)

- `short_ma_period`
  - 短期均线周期
- `medium_ma_period`
  - 中期均线周期
- `long_ma_period`
  - 长期均线周期
- `min_history`
  - 最小历史数据要求

常见理解：

- 一般满足 `short < medium < long`
- 适合表达“强势突破同时站上多条均线”的逻辑

调参建议：

- 常见组合：`5 / 10 / 20`
- 想更灵敏可缩短三条均线，但假信号也会增加

## 10. MACD + KDJ 策略

### `[strategies.macd_kdj]`

对应实现：

- [macd_kdj.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/macd_kdj.py)

MACD 参数：

- `macd_fast`
- `macd_slow`
- `macd_signal`

KDJ 参数：

- `kdj_fastk`
- `kdj_slowk`
- `kdj_slowd`

策略参数：

- `min_history`
  - 最小历史数据要求
- `overbought_threshold`
  - 超买阈值
  - `80` 表示高于 80 视为较强超买区域

调参建议：

- `min_history` 应覆盖 MACD 和 KDJ 所需窗口
- `overbought_threshold` 越低，卖出/谨慎信号会越频繁

## 11. MACD 趋势信号策略

### `[strategies.macd_signal]`

对应实现：

- [macd_signal.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/macd_signal.py)
- [macd_base.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/macd_base.py)

- `macd_fast`
- `macd_slow`
- `macd_signal`
  - 这三项共同决定 MACD 指标灵敏度
- `min_history`
  - 最小历史数据要求
- `position_ratio`
  - 开仓资金使用比例
  - `0.9` 表示计划使用可用资金的 90%

调参建议：

- `position_ratio` 越高，单次开仓越激进
- 若想减小回撤，可降低 `position_ratio`

## 12. MACD 背离策略

### `[strategies.macd_divergence]`

对应实现：

- [macd_divergence.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/macd_divergence.py)
- [macd_base.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/macd_base.py)

- `macd_fast`
- `macd_slow`
- `macd_signal`
- `min_history`
- `position_ratio`

和 `macd_signal` 的差别主要在：

- `macd_signal` 更偏趋势确认
- `macd_divergence` 更偏反转/背离逻辑

## 13. 参数调整的一般原则

可以先按下面顺序理解：

1. 周期类参数
   - 决定信号灵敏度和滞后性
2. `min_history`
   - 决定策略开始发信号前需要积累多少历史
3. 仓位/金额类参数
   - 如 `risk_ratio`、`base_amount`、`position_ratio`
   - 决定单次交易激进程度
4. 阈值类参数
   - 如 `overbought_threshold`
   - 决定触发门槛高低

常见经验：

- 周期越短：信号越快、噪音越多
- 周期越长：信号越稳、滞后越大
- 仓位比例越高：收益弹性越大、回撤通常也越大
- 阈值越严格：信号越少

## 14. 相关入口

- 参数模板：
  - [strategies.toml](/Users/james/PycharmProjects/jwquant/config/strategies.toml)
- 配置读取：
  - [config.py](/Users/james/PycharmProjects/jwquant/jwquant/common/config.py)
- 策略注册中心：
  - [registry.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/strategy/registry.py)
