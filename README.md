# 159558 AI Trading System

一个低成本、手机可访问的日线量化决策系统。系统自动更新 159558、SOX、SOXS、NVDA、TSM、ASML、VIX、纳指、离岸人民币与 A50 数据，训练三模型集成并生成每日评分。

> 仅用于研究和决策辅助，不构成任何投资建议。概率、胜率与仓位建议都可能失效。

## 1. 上传到 GitHub

推荐使用 GitHub Desktop，把本目录全部复制到仓库根目录后 Commit 和 Push。必须保留 `.github/workflows/daily-update.yml`。

## 2. 第一次运行

打开仓库的 **Actions** 标签，左侧选择 **Daily market update**，点击右侧 **Run workflow**。如果看不到：

1. 确认 `.github/workflows/daily-update.yml` 已经上传到 `main` 分支；
2. 打开 `Settings → Actions → General`，允许 Actions；
3. 在 `Workflow permissions` 选择 `Read and write permissions`。

成功后会生成：

- `data/market.db`
- `models/ensemble.joblib`

## 3. 部署到 Render

1. 登录 Render，选择 **New → Blueprint**；
2. 连接 GitHub 仓库；
3. Render 会读取 `render.yaml`；
4. 在环境变量中设置 `APP_PASSWORD`（可选）和 `TWELVE_API_KEY`（可选）；
5. 部署完成后即可通过手机浏览器访问。

注意：免费实例可能休眠，首次打开需要等待几十秒。仓库里的 SQLite 数据库由 GitHub Actions 持续更新，Render 自动部署最新提交。

## 4. 本地运行

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python scripts/update_and_train.py
uvicorn app.main:app --reload
```

打开 `http://127.0.0.1:8000`。

## 模型口径

- 海外市场因子只使用中国交易日开盘前已经可知的数据；
- 按时间先后 70%/30% 切分，禁止随机打乱；
- 三模型：逻辑回归、随机森林、直方图梯度提升；
- 最终概率为三模型平均值；
- 数据缺失由训练集的中位数填补，不把旧值伪装成当天值；
- 参考仓位受到模型健康度约束。

## 已知限制

- 免费数据源可能延迟、缺失或修订；A50 免费行情尤其不稳定；
- Yahoo Finance 数据不属于交易所授权实时行情；
- 当前模型是日线方向模型，不适用于盘中追涨杀跌；
- 初期样本量有限，必须持续记录真实预测表现。
