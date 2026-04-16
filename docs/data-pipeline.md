# 数据链路说明

## 1. 设计原则

- 底层行情永远存原始数据 `adj=none`
- 股票复权信息单独存为复权因子
- 读取时按需动态生成 `qfq/hfq`
- 期货不走股票复权逻辑

## 2. 下载链路

入口：

- [scripts/download_data.py](/Users/james/PycharmProjects/jwquant/scripts/download_data.py)

核心同步逻辑：

- [jwquant/trading/data/sync.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/sync.py)

XtQuant 数据源：

- [jwquant/trading/data/sources/xtquant_src.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/sources/xtquant_src.py)

行为：

- 股票：
  - 下载原始 K 线
  - 下载复权因子
  - 两者分别增量落库
- 期货：
  - 下载原始 K 线
  - 不下载股票复权因子

## 3. 存储层

存储实现：

- [jwquant/trading/data/store.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/store.py)

默认按以下维度隔离：

- `market`
- `timeframe`

股票与期货底层分仓保存，不混存。

## 4. 读取与复权

统一读取入口：

- [jwquant/trading/data/feed.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/feed.py)

复权计算：

- [jwquant/trading/data/cleaner.py](/Users/james/PycharmProjects/jwquant/jwquant/trading/data/cleaner.py)

读取股票时支持：

- `adj="none"`
- `adj="qfq"`
- `adj="hfq"`

读取期货时建议固定：

- `adj="none"`

## 5. 回测链路

回测入口：

- [scripts/run_backtest.py](/Users/james/PycharmProjects/jwquant/scripts/run_backtest.py)

行为：

- 优先从本地 `DataFeed` 读取
- 本地无数据时自动尝试 XtQuant 下载
- 下载失败才回退样例数据

## 6. 检查脚本

复权因子与原始价格检查：

- [scripts/inspect_adjust_factors.py](/Users/james/PycharmProjects/jwquant/scripts/inspect_adjust_factors.py)
