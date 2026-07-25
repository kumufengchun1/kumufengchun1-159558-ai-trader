# 159558 AI Trading System

这是一个低成本云端日线交易研究系统。它每天更新 159558、SOX、NVDA、TSM、ASML、SOXS、VIX、纳指、离岸人民币和富时中国 A50 的日线数据，按中国交易日对齐上一可用海外收盘，使用滚动样本外回测生成上涨概率、评分、因子解释、相似行情和模型健康度。

> 仅用于研究，不构成投资建议。不要把历史胜率视为未来承诺。

## 核心能力

- 手机与电脑浏览器访问
- GitHub Actions 工作日自动更新
- 逻辑回归、随机森林、梯度提升三模型投票
- 严格按时间顺序滚动训练，避免随机切分导致未来信息泄漏
- 今日评分、参考仓位、置信度和主要原因
- 样本外回测、最大回撤、盈亏比、概率校准
- 最近20日/60日模型健康度及失效警告
- 免费源缺失时使用缓存并明确标记
- 可选访问密码
- 可导入 159558 CSV 作为备用数据

## 一、上传到 GitHub

推荐使用 GitHub Desktop，隐藏目录 `.github` 和 `.streamlit` 会自动上传。

1. 在 GitHub 创建仓库 `159558-ai-trader`。
2. 使用 GitHub Desktop 克隆仓库。
3. 将本项目目录中的全部文件复制到本地仓库根目录。
4. Commit，然后 Push。

也可使用命令行：

```bash
git clone https://github.com/kumufengchun1/159558-ai-trader.git
cd 159558-ai-trader
# 把本项目文件复制到这里
git add .
git commit -m "Initial complete system"
git push
```

## 二、首次更新数据

仓库页面进入：

`Actions → Update market data → Run workflow`

然后进入：

`Settings → Actions → General → Workflow permissions → Read and write permissions`

首次运行后，`data/market_prices.parquet` 和数据状态文件会被提交到仓库。

## 三、部署 Streamlit

1. 登录 Streamlit Community Cloud。
2. Create app。
3. Repository 选择 `kumufengchun1/159558-ai-trader`。
4. Branch 选择 `main`。
5. Main file path 填 `app.py`。
6. Python 选择 3.12。
7. 点击 Deploy。

如果需要密码，在 Streamlit 的 Advanced settings → Secrets 中填写：

```toml
APP_PASSWORD = "你的访问密码"
```

不要将真实密码或 API Key 上传到 GitHub。Streamlit 官方建议把 secrets 放在部署平台设置中，而不是提交到仓库。

## 四、数据口径

- 预测目标：159558 当日收盘相对前一交易日是否上涨。
- 海外因子：使用 159558 交易日前最近一个可用海外收盘。
- A50：免费 Yahoo 别名可能发生变化；系统会依次尝试多个别名并显示实际使用结果。
- 159558：内置用户历史数据作为种子；Yahoo 成功时会用新数据覆盖同日期缓存。
- 拆股与复权：Yahoo 下载使用自动复权；用户导入数据应尽量使用前复权或一致口径。

## 五、建议的实盘验证流程

1. 先连续纸面记录至少 60 个交易日。
2. 不只看胜率，同时看平均收益、最大回撤、盈亏比和信号次数。
3. 健康度低于 45 时暂停使用。
4. 强信号也不建议满仓；系统给出的仓位仅是风险分级示例。
5. 每月检查数据缺失和因子漂移。

## 本地运行

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python update.py
streamlit run app.py
```

## 项目结构

```text
app.py                       Web 主程序
update.py                    行情更新入口
src/config.py                资产与模型配置
src/data.py                  下载、缓存与导入
src/features.py              时区对齐与因子生成
src/model.py                 三模型投票与滚动回测
src/metrics.py               回测指标与模型健康度
src/report.py                每日文字摘要
.github/workflows/           自动更新任务
.streamlit/                  页面配置和 secrets 示例
data/                        缓存与用户历史种子
```
