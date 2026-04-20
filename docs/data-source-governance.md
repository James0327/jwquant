# 数据源治理设计

## 0. 整体执行计划

本治理文档同时承担原 `akshare-integration-plan` 的执行计划职责，后续关于 `AkShare` 接入的设计、排期、准入和实施顺序统一维护在本文档，不再拆分单独计划文档。

### 0.1 总目标

`AkShare` 接入不以“新增一个可下载历史行情的 source class”为目标，而以“将 AkShare 纳入统一数据治理框架”为目标。最终要求如下：

- 与 `XtQuant / Tushare / Baostock` 在架构层面平级
- 遵循统一数据契约，而不是各自返回“差不多”的字段
- 明确其在系统中的定位、优先级和使用边界
- 具备可校验、可对账、可准入、可扩展能力
- 不破坏现有“原始行情落库 + 读取侧动态复权”的长期方向

### 0.2 总体原则

- 治理先行，编码后置
- 优先定义契约、策略、准入标准，再进入具体实现
- 原则上不为单一数据源建立专属下载体系
- 原则上复用现有 `sync / store / feed` 主链
- 不默认信任外部数据源的复权口径，必须先校验
- 不把“能跑通下载”当作完成标准

### 0.3 实施阶段

#### 第一阶段：治理设计落地

目标：

- 定义正式数据源契约
- 定义源选择策略层
- 定义复权准入标准
- 明确 `AkShare` 的系统定位

交付物：

- 本文档

验收标准：

- 团队对数据源能力边界、优先级、准入规则有统一口径
- 后续 `AkShare` 接入实现有明确约束，不再靠临时判断推进

#### 第二阶段：能力模型与基础实现

目标：

- 在代码中落地“正式数据源契约”
- 新增 `AkShareDataSource`
- 将 `AkShare` 接入统一下载入口

建议实施项：

- 新增 `jwquant/trading/data/sources/akshare_src.py`
- 强化 `jwquant/trading/data/sync.py` 中对 source 能力的显式判断
- 在 `scripts/download_data.py` 中接入 `akshare`
- 在配置层引入 `data.akshare` 与 `data.source_policy`

验收标准：

- `AkShare` 与现有 source 使用同一主链
- 上层不再依赖 `hasattr()` 猜测能力
- 下载、落库、读取链路不出现 source 专属旁路

#### 第三阶段：数据质量与对账体系

目标：

- 建立统一 contract tests
- 建立源间 reconciliation tests
- 建立重跑稳定性与幂等性验证

建议实施项：

- 新增统一 source contract 测试
- 新增 `AkShare vs XtQuant / Baostock / Tushare` 对账脚本
- 形成差异报表输出

验收标准：

- 能回答“AkShare 数据是否可用于研究 / 回测 / 补数”
- 能定位差异是时间覆盖、价格口径还是成交量口径问题

#### 第四阶段：复权体系准入评估

目标：

- 评估 `AkShare` 的无复权、前复权、后复权语义
- 决定其是否进入统一复权体系

建议实施项：

- 评估 AkShare 原始行情语义是否稳定
- 评估 AkShare 前复权 / 后复权结果可重复性
- 评估是否能稳定拿到复权因子或等价信息
- 输出准入结论

验收标准：

- 对 AkShare 的复权可信度有明确结论
- 明确其是否支持进入“原始行情 + 复权因子 + 动态复权”统一体系

#### 第五阶段：运营化与默认策略收口

目标：

- 明确 `AkShare` 的默认使用场景
- 明确默认 source policy
- 补齐文档、配置与检查脚本

建议实施项：

- 更新用户文档和模块文档
- 更新默认配置
- 明确回测 / 研究 / 补数的默认优先级

验收标准：

- 新同事可直接判断何时该用 `AkShare`
- 配置、文档、测试和默认行为保持一致

### 0.4 里程碑与顺序

推荐顺序如下：

1. 完成第一阶段治理设计
2. 再进入契约代码化和 `AkShareDataSource` 实现
3. 再进入对账与质量体系
4. 最后做复权准入和默认策略收口

不建议跳过第一阶段直接编码。否则后续容易出现以下问题：

- 不同 source 的能力口径不一致
- 复权行为失控
- 回测和研究使用了不同语义的数据
- 未来新增 source 时继续复制分支逻辑

### 0.5 当前推荐定位

在完成复权准入评估并得到当前阶段结论后，`AkShare` 的推荐定位为：

- 股票历史行情研究源
- 非 QMT 环境下的补数源
- 源间对账参考源

暂不默认将其定义为：

- 实盘前核心主源
- 统一复权主源
- 期货数据主源

当前阶段的明确结论：

- `AkShare none`
  - 可用于研究、补数、价格对账
  - 与 `Baostock none` 在本次评估标的上 `OHLC` 价格完全一致
  - 但 `volume` / `amount` 口径不应默认视为完全等价
- `AkShare qfq/hfq`
  - 可作为外部前后复权参考口径
  - 在 `source policy` 层不再额外限制
  - 是否作为统一复权主链真值，仍需与“本地原始行情 + 因子动态复权”链路分开理解
- `Baostock qfq/hfq`
  - 属于源端直接返回的复权行情，不是系统本地基于复权因子计算所得
  - 已人工抽查发现其前复权口径与同花顺 App / AkShare 存在明显偏差
  - 不再作为 `research / reconciliation` 场景下的复权对账真值源
  - 当前仅保留在 `repair` 等非真值对账场景中作为兼容性候选源

### 0.6 关键决策点

以下决策需要在后续阶段明确，不建议在实现过程中临时决定：

#### 0.6.1 数据语义决策

- `AkShare` 的 `adj=none` 是否可视为系统定义下的原始行情
- 周线 / 月线是否应由上游直接提供，还是由日线聚合生成
- 成交量、成交额单位是否需要额外归一化

#### 0.6.2 复权决策

- 是否允许 `AkShare` 直接提供 `qfq/hfq` 结果用于研究
- 是否允许这些结果直接进入回测
- 是否支持 `download_adjust_factors()` 形式接入统一复权链路

#### 0.6.3 源策略决策

- 股票日线研究默认是否优先 `AkShare`
- 回测默认是否仍优先 `XtQuant`
- 当主源不可用时是否允许自动降级

### 0.7 后续实施清单

第一阶段结束后，建议按下面顺序进入代码实现：

1. 新增 source capability 结构
2. 将 `sync.py` 从隐式能力判断改为显式能力判断
3. 实现 `AkShareDataSource`
4. 接入 `download_data.py`
5. 增加配置与文档
6. 增加统一 contract tests
7. 增加源间对账脚本
8. 评估复权准入

### 0.8 非目标

本计划当前不包含以下目标：

- `AkShare` 实盘交易接口
- `AkShare` 期货全量接入
- `AkShare` 实时行情体系
- `AkShare` 财务、资金流、板块等扩展数据统一治理

这些能力可以在历史行情主链稳定后再评估是否纳入统一框架。

## 1. 背景

当前项目已经具备多个数据源：

- `XtQuant`
- `Tushare`
- `Baostock`

随着 `AkShare` 计划接入，数据模块需要从“多个 source 并存”升级为“统一治理的数据源体系”。

治理目标不是增加一个下载实现，而是解决以下长期问题：

- 不同 source 能力边界不清晰
- 上层通过 `hasattr()` 猜测能力，不够稳定
- 复权口径缺少统一准入标准
- 回测、研究、补数可能使用不同语义的数据
- 后续新增 source 时容易复制分支逻辑

## 2. 设计目标

本设计用于约束所有市场数据源，要求做到：

- 输入输出契约统一
- 数据能力显式化
- source 选择策略配置化
- 复权准入规则清晰化
- 数据质量校验可重复执行
- 新 source 接入时复用同一框架

## 3. 总体分层

建议继续沿用现有主链，并补齐治理层抽象：

1. source 层
2. sync 层
3. store 层
4. feed 层
5. governance 层

职责如下：

### 3.1 source 层

职责：

- 访问上游数据源
- 返回标准化后的 DataFrame
- 明确声明自己支持的能力

禁止：

- 自行决定落库策略
- 自行决定回测默认优先级
- 自行决定复权准入

### 3.2 sync 层

职责：

- 分段下载
- 增量续传
- 重试
- 落库编排
- 调用 source capability 判断支持范围

禁止：

- 依赖 source 特殊旁路逻辑
- 使用隐式 `hasattr()` 作为长期能力判断方式

### 3.3 store 层

职责：

- 统一持久化标准化后的 bars / factors
- 保证幂等与主键唯一

### 3.4 feed 层

职责：

- 提供统一读取接口
- 在股票场景按需做动态复权

### 3.5 governance 层

职责：

- 声明 source 能力契约
- 维护 source policy
- 维护 source 等级与准入状态
- 提供统一 contract / reconciliation 校验准则

## 4. 正式数据源契约

建议将现有轻量 `BarSource` 协议升级为“正式 source contract”。

### 4.1 必须满足的 bars 契约

任意支持历史 K 线的数据源，返回值必须满足：

- 返回类型：`pd.DataFrame`
- 字段至少包含：
  - `code`
  - `market`
  - `dt`
  - `open`
  - `high`
  - `low`
  - `close`
  - `volume`
- 可选字段：
  - `amount`
  - `open_interest`

标准要求：

- `dt` 必须可转为 `pd.Timestamp`
- `market` 必须为系统标准值，如 `stock / futures`
- `code` 必须回写为系统标准代码
- 返回结果必须按 `market + code + dt` 排序
- 不允许返回重复主键
- 不允许返回 `None`

### 4.2 因子契约

如 source 支持复权因子，返回值必须满足：

- 返回类型：`pd.DataFrame`
- 字段至少包含：
  - `code`
  - `market`
  - `dt`
  - `factor_data`

要求：

- `factor_data` 必须为可序列化结构
- 同一 `code + dt` 只允许一条有效记录

### 4.3 能力声明契约

建议为每个 source 提供显式能力描述，而不是只靠某个方法是否存在。

建议能力项至少包含：

- `source_name`
- `supported_markets`
- `supported_timeframes`
- `supports_adjusted_bars`
- `supports_adjust_factors`
- `supports_main_contract`
- `supports_incremental_safe`
- `data_grade`

建议 `data_grade` 先定义为：

- `A`
  - 可用于核心研究与回测
- `B`
  - 可用于研究、补数、对账
- `C`
  - 仅用于辅助参考

说明：

- `data_grade` 不是“数据源好坏”的主观评价，而是当前系统治理结论
- 等级可随着对账和复权评估结果调整

## 5. Source Policy 设计

建议新增统一 source policy 概念，用于约束不同场景的优先级，而不是把优先顺序写死在脚本里。

### 5.1 设计目标

- 将“谁是默认主源”从代码逻辑中抽离
- 支持按市场、周期、用途配置默认顺序
- 为未来自动降级和双源对账留出扩展点

### 5.2 维度建议

建议至少按以下维度组织：

- 市场：`stock / futures`
- 周期：`1d / 1w / 1m / intraday`
- 用途：`research / backtest / repair / reconciliation`

### 5.3 配置样例

推荐后续落成如下结构：

```toml
[data.source_policy.stock.research]
daily = ["akshare", "tushare", "baostock", "xtquant"]
weekly = ["akshare", "tushare", "baostock"]
monthly = ["akshare", "tushare", "baostock"]

[data.source_policy.stock.backtest]
daily = ["xtquant", "akshare", "tushare", "baostock"]

[data.source_policy.stock.repair]
daily = ["akshare", "tushare", "baostock"]

[data.source_policy.stock.reconciliation]
primary = "xtquant"
secondary = ["akshare", "tushare", "baostock"]

[data.source_policy.futures.backtest]
daily = ["xtquant"]
```

### 5.4 当前建议

在完成 `AkShare` 复权准入评估前，建议：

- 研究场景可优先尝试 `AkShare`
- 回测场景股票日线仍优先 `XtQuant`
- 期货场景仍仅 `XtQuant`

## 6. 复权治理与准入标准

复权治理是本阶段的核心。

系统长期原则应保持不变：

- 底层优先落原始行情
- 股票复权信息单独存储
- 读取时按需动态生成 `qfq / hfq`

### 6.1 准入目标

任何 source 若要进入统一复权体系，必须先回答以下问题：

1. 是否能稳定提供系统定义下的原始行情
2. 是否能提供稳定、可重现的复权结果
3. 是否能提供可独立校验的复权因子或等价信息
4. 同一时间区间重跑时结果是否稳定

### 6.2 准入门槛

建议复权准入至少满足以下要求：

- 无复权行情与主参考源高度一致
- 日期覆盖率达到既定阈值
- `OHLC` 差异可解释
- 复权结果可重复生成
- 若无因子，则需明确其仅能作为结果数据源，而不能进入统一因子链路

### 6.3 结果分类

建议将结论分为三类：

- `accepted`
  - 允许进入统一复权体系
- `limited`
  - 允许提供复权结果用于研究，但不进入统一复权主链
- `rejected`
  - 不允许进入统一复权主链

当前对 `AkShare` 的推荐状态更新为：

- `none`: `limited`
- `qfq`: `rejected`
- `hfq`: `rejected`

依据：

- `none` 口径在本次 `AkShare vs Baostock` 评估中价格一致，但量额不一致
- `qfq/hfq` 口径在本次评估中与参考源差异明显，不满足统一复权主链准入条件

## 7. 数据质量校验标准

建议将质量校验分成 3 类。

### 7.1 Source Contract 校验

目标：

- 检查 source 是否满足统一契约

必查项：

- 返回类型
- 字段完整性
- 主键唯一性
- 排序正确性
- 空值行为
- 不支持场景是否抛出明确异常

### 7.2 Reconciliation 校验

目标：

- 检查多个 source 之间的一致性

建议指标：

- row count
- distinct dt
- `open/high/low/close` exact match rate
- `volume/amount` diff rate
- missing dt
- 极端差异样本 Top N

### 7.3 Replay / Idempotency 校验

目标：

- 检查同一请求多次执行是否稳定

必查项：

- 重复下载是否重复落库
- 增量下载是否无漏数
- 同一窗口重跑结果是否一致

## 8. AkShare 的当前定位

在治理框架下，建议当前将 `AkShare` 定位为：

- 股票历史行情研究源
- 补数源
- 对账参考源

暂不建议直接定义为：

- 股票回测默认主源
- 统一复权主源
- 期货主源

这不是对 `AkShare` 能力的否定，而是为了避免在复权、单位、时间覆盖尚未完成评估前过早赋予核心地位。

当前默认策略建议如下：

- `download_data.py`
  - 保持显式入口，调用方自行指定 `--source`
  - 不做自动 source 选择
- `run_backtest.py`
  - 本地无数据时按 `source policy` 自动补数
  - `backtest + qfq/hfq` 当前仅额外排除 `Baostock`
  - `backtest + none` 允许 `XtQuant / AkShare / Tushare / Baostock`

## 9. 第一阶段落地项

第一阶段不直接做 `AkShareDataSource` 编码，而先落以下内容：

1. 形成本治理文档
2. 形成整体执行计划文档
3. 明确后续代码改造入口：
   - `source capability`
   - `source policy`
   - `adjust eligibility`
4. 统一团队口径

## 10. 第二阶段代码化建议

本设计稿确认后，建议下一步进入以下代码实现：

1. 引入 source capability 结构
2. 将 `sync.py` 的能力判断从隐式转为显式
3. 引入 source policy 配置读取逻辑
4. 再实现 `AkShareDataSource`
5. 再补统一 contract tests 和 reconciliation tests
