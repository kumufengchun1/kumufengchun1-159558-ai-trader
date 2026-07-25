# ATS 数据字典 V0.2

## daily_prices

| 字段 | 类型 | 说明 |
|---|---|---|
| asset_symbol | TEXT | ATS 内部资产代码 |
| trading_date | ISO date | 资产所属市场的交易日期 |
| open/high/low/close | REAL | 未复权日线价格 |
| adj_close | REAL nullable | 数据源提供的复权收盘价 |
| volume | REAL nullable | 成交量；指数和外汇可能为空 |
| provider | TEXT | 实际采用的数据供应商 |
| fetched_at | ISO datetime UTC | 获取时间 |
| is_cached | INTEGER | 是否来自缓存 |

## alignment_map

| 字段 | 类型 | 说明 |
|---|---|---|
| target_symbol | TEXT | 预测标的，当前为 159558 |
| target_date | ISO date | 计划生成信号的 A 股交易日 |
| source_symbol | TEXT | 海外或跨市场来源资产 |
| source_date | ISO date nullable | 严格早于 target_date 的最近来源交易日 |
| lag_calendar_days | INTEGER | 两个日期的自然日间隔 |
| alignment_rule | TEXT | 对齐算法版本说明 |

## feature_values

| 字段 | 类型 | 说明 |
|---|---|---|
| target_symbol | TEXT | 目标资产 |
| feature_date | ISO date | 特征可用于预测的目标日期 |
| feature_name | TEXT | 稳定、唯一的特征名 |
| value | REAL nullable | 特征值；缺失必须保留为空，不前向伪造 |
| source_symbol | TEXT nullable | 特征来源资产 |
| source_date | ISO date nullable | 特征最后使用的数据日期 |
| feature_version | TEXT | 特征定义版本，当前 v0.2.0 |
| generated_at | ISO datetime UTC | 生成时间 |

## V0.2 特征

| 特征名 | 定义 |
|---|---|
| TARGET_RETURN_1D_LAG1 | 159558 截至前一交易日的一日复权收益 |
| TARGET_CLOSE_VS_SMA5_LAG1 | 前一日复权收盘相对五日均线偏离 |
| TARGET_VOLATILITY_5D_LAG1 | 截至前一日的五日收益总体标准差 |
| TARGET_VOLUME_RATIO_5D_LAG1 | 前一日成交量 / 截至前一日五日均量 |
| `{SOURCE}_RETURN_1D` | 对齐后的来源资产一日复权收益 |

## adjustment_audit

`close_to_adj_ratio` 的明显变化、原始价格极端跳变但复权收益较平稳时，会标记为 `review`。该表只提供审计证据，不自动猜测拆分比例。
