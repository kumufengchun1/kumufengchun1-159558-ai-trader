# ATS V0.2.1 — Data & Feature Platform

159558 AI Trading System 的第二个可验收版本。本版本仍不发布交易建议，重点是把历史行情转化为**无未来数据泄漏、可审计、可重复生成**的特征数据。

## V0.2 已完成

- SQLite 行情数据库与幂等更新
- Yahoo → Twelve Data 供应商降级链
- A股目标交易日与海外前一交易日严格对齐
- 周末、美国/中国节假日错位处理
- Feature Store（特征仓库）
- 159558 自身滞后趋势、成交量、波动率因子
- SOX、SOXS、NVDA、TSM、ASML、VIX、NASDAQ、USDCNH、A50代理隔夜收益因子
- 原始收盘价与复权价审计
- 拆分、分红或异常跳变审核记录
- CI 自动测试
- 每日更新后自动重建 V0.2 特征

## 核心防泄漏规则

对 159558 的交易日 `T`：

- 海外因子只允许使用严格早于 `T` 的最后一个海外交易日；
- 159558 自身技术因子只允许使用 `T-1` 及更早的数据；
- 每个特征都保存来源资产和来源日期，可追溯检查。

例如 159558 在周一开盘前的信号，只会使用上周五或更早的美股收盘数据，不会使用周一尚未发生的海外行情。

## 数据表

- `daily_prices`：标准化日线
- `alignment_map`：目标日与来源日映射
- `feature_values`：版本化特征仓库
- `adjustment_audit`：复权和异常跳变审计
- `feature_runs`：每次特征生成记录
- `data_quality` / `provider_failures`：数据质量和供应商错误

## 本地运行

```bash
python -m pip install -r requirements-dev.txt
python -m scripts.update_market
python -m scripts.build_features
python -m scripts.report_data_quality
python -m scripts.report_feature_status
pytest
```

可选环境变量：

```text
TWELVE_API_KEY=你的 Twelve Data 密钥
ATS_DATABASE_PATH=data/market.db
```

## GitHub Actions

1. 推送代码后先确认 `CI` 成功。
2. 打开 `Actions → Daily market update → Run workflow`。
3. 工作流依次更新行情、生成复权审计、构建特征、输出质量报告并提交 `data/market.db`。

## 当前边界

- `A50_PROXY` 是免费指数代理，不等同于富时中国 A50 连续夜盘期货。
- V0.2 不训练模型、不计算胜率、不提供仓位建议。
- 数据供应商授权、稳定性和代码可用性仍需持续监控。

## 下一版本 V0.3

- 目标标签定义（收盘方向、开盘至收盘、收益区间）
- Walk-forward 滚动回测
- 逻辑回归基准模型
- 完整样本外指标、交易成本和最大回撤
- 决策日志初版

## V0.2.2 CI hotfix

- Wrapped all Python lines to the configured 100-character limit.
- Removed unused imports reported by Ruff.
- Local test result: 7 passed.

## V0.2.3 hotfix

Fixes the data-quality report crash caused by iterating over sqlite3.Row values as if they were column names. The report now uses explicit columns and the csv module, with a regression test.
