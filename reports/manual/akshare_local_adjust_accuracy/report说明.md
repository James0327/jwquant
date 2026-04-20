# AkShare 本地复权验证报告说明

## 1. 验证目的

本目录用于验证以下结论是否成立：

- 使用 `AkShare` 下载的 `none` 原始行情
- 再结合 `AkShare` 下载的复权因子
- 由本地代码计算得到的 `qfq`

是否能够与 `AkShare` 直接返回的 `adj=qfq` 数据保持一致。

本次验证标的与区间：

- 标的：`601006.SH`，大秦铁路
- 区间：`2022-01-01 ~ 2025-12-31`
- 周期：`1d`

## 2. 当前结论

本次验证的当前结论是：

- 本地 `none + 因子 -> qfq` 计算链路已跑通
- `DataFeed` 读取侧与本地计算结果一致
- 与 `AkShare` 直下 `qfq` 相比，不存在超出容差的真正差异
- 之前看到的小数位不一致，主要来自展示精度差异：
  - 本地计算原始结果保留 4 位小数
  - `AkShare` 直下价格通常按 2 位小数展示

当前采用的“真正差异”判断标准：

- 四个价格字段 `open/high/low/close`
- 任一字段绝对差值 `> 0.005`
- 才认定为真正差异

## 3. 文件说明

### `raw_none_bars.csv`

含义：

- `AkShare` 下载的无复权原始日线
- 是本地复权计算的输入行情

### `adjust_factors.csv`

含义：

- `AkShare` 下载的复权因子表
- 当前包含 `qfq_factor` 和 `hfq_factor`
- 本次报告主要使用其中的 `qfq_factor`

### `calculated_qfq_bars.csv`

含义：

- 本地基于 `raw_none_bars.csv + adjust_factors.csv` 计算得到的 `qfq`
- 保留较高计算精度，便于排查

特点：

- 价格字段通常保留到 4 位小数

### `calculated_qfq_bars_2dp.csv`

含义：

- 将本地计算的 `qfq` 价格统一四舍五入到 2 位小数后的版本
- 用于与 `AkShare` 直下 `qfq` 做人工逐行对照

### `direct_qfq_bars.csv`

含义：

- `AkShare` 直接下载的 `adj=qfq` 日线
- 作为外部参考结果

### `feed_qfq_bars.csv`

含义：

- 通过项目里的 `DataFeed.get_bars(adj="qfq")` 读取到的结果
- 代表系统内部实际给策略、回测使用的复权读取结果

特点：

- 当前导出时已统一按 2 位小数输出
- 便于和 `direct_qfq_bars.csv` 直接人工比对

### `comparison_qfq.csv`

含义：

- 完整的逐日对账明细表
- 同时包含：
  - 无复权原始价格
  - 本地计算价格
  - `AkShare` 直下价格
  - `DataFeed` 输出价格
  - 各类差值字段

用途：

- 用于精细排查差异来源
- 是最完整的一张分析表

### `diff_qfq.csv`

含义：

- 只保留真正有差异的数据行
- 当前“真正差异”的标准为：任一价格字段绝对差值大于 `0.005`

说明：

- 如果该文件为空，说明当前没有超出容差的实质差异

### `missing_dates_qfq.csv`

含义：

- 用于记录日期集合不一致的情况
- 如果为空，说明本地计算、直下数据、DataFeed 输出三者日期对齐

### `store/`

含义：

- 本次手工验证的本地存储目录
- 当前格式为 `sqlite`
- 保留原始下载结果和因子，便于继续排查

## 4. 字段说明

以下字段主要出现在 `comparison_qfq.csv` 中。

### 公共字段

#### `dt`

含义：

- 交易日期

### 原始无复权字段

#### `raw_open`
#### `raw_high`
#### `raw_low`
#### `raw_close`

含义：

- `AkShare none` 原始日线价格

### 本地计算字段

#### `calc_open`
#### `calc_high`
#### `calc_low`
#### `calc_close`

含义：

- 本地依据 `none + qfq_factor` 计算得到的 qfq 价格
- 保留较高精度，主要用于技术排查

### 直下参考字段

#### `direct_open`
#### `direct_high`
#### `direct_low`
#### `direct_close`

含义：

- `AkShare` 直接返回的 `adj=qfq` 价格

### DataFeed 读取字段

#### `feed_open`
#### `feed_high`
#### `feed_low`
#### `feed_close`

含义：

- 通过系统 `DataFeed` 读取到的 qfq 价格

### 原始精度差值字段

#### `diff_open`
#### `diff_high`
#### `diff_low`
#### `diff_close`

计算方式：

- `calc - direct`

含义：

- 本地计算结果与 `AkShare` 直下结果的价格差

#### `feed_diff_open`
#### `feed_diff_high`
#### `feed_diff_low`
#### `feed_diff_close`

计算方式：

- `feed - direct`

含义：

- `DataFeed` 输出与 `AkShare` 直下结果的价格差

### 2 位小数对齐字段

#### `calc_open_2dp`
#### `calc_high_2dp`
#### `calc_low_2dp`
#### `calc_close_2dp`

含义：

- 本地计算价格四舍五入到 2 位小数后的结果

#### `feed_open_2dp`
#### `feed_high_2dp`
#### `feed_low_2dp`
#### `feed_close_2dp`

含义：

- `DataFeed` 结果四舍五入到 2 位小数后的结果

#### `direct_open_2dp`
#### `direct_high_2dp`
#### `direct_low_2dp`
#### `direct_close_2dp`

含义：

- `AkShare` 直下价格按 2 位小数口径展示后的结果

#### `round_diff_open`
#### `round_diff_high`
#### `round_diff_low`
#### `round_diff_close`

计算方式：

- `calc_2dp - direct_2dp`

含义：

- 在统一到 2 位小数后，本地计算与直下结果是否还存在显示差异

### 判定字段

#### `within_direct_tolerance`

含义：

- 本行四个价格字段是否全部落在容差范围内

当前规则：

- `abs(diff_open/high/low/close) <= 0.005`

#### `has_diff`

含义：

- 原始精度下是否存在任意非零差值

说明：

- 该字段会把 0.0004、0.0048 这类舍入差也记为“有差值”
- 它更适合技术排查
- 不等同于“存在真正业务差异”

#### `max_abs_diff`

含义：

- 当前行四个价格字段中的最大绝对差值

用途：

- 便于快速定位偏差最大的日期

## 5. 关于小数位不一致

这次排查确认过：

- 小数位不一致主要不是算法错误
- 而是展示精度不一致

具体表现：

- 本地计算结果的小数位由配置项控制
- 当前配置项为 `data.adjust.price_digits`
- 当前默认值为 `3`
- `AkShare` 直下 `qfq` 常见展示口径保留到 2 位小数

因此：

- `calculated_qfq_bars.csv` 更适合技术排查
- `calculated_qfq_bars_2dp.csv` 更适合人工逐行核对

如果你要人工对比，优先看这三份：

- `calculated_qfq_bars_2dp.csv`
- `direct_qfq_bars.csv`
- `feed_qfq_bars.csv`

如需调整本地复权结果保留位数，可修改配置：

```toml
[data.adjust]
price_digits = 4
```

也可通过环境变量覆盖：

```bash
export JWQUANT_DATA__ADJUST__PRICE_DIGITS=4
```

## 6. 推荐查看顺序

推荐按以下顺序查看：

1. `report说明.md`
2. `raw_none_bars.csv`
3. `adjust_factors.csv`
4. `calculated_qfq_bars_2dp.csv`
5. `direct_qfq_bars.csv`
6. `feed_qfq_bars.csv`
7. `comparison_qfq.csv`
8. `diff_qfq.csv`
9. `missing_dates_qfq.csv`
