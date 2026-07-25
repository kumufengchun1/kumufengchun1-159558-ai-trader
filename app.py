from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.auth import require_password
from src.config import DATA_DIR
from src.data import load_prices, load_status, save_uploaded_target, update_market_data
from src.features import build_dataset
from src.model import train_and_predict
from src.report import build_daily_text

st.set_page_config(page_title="159558 AI Trading System", page_icon="📈", layout="wide")
require_password()

st.title("159558 AI Trading System")
st.caption("云端日线完全体 · 海外半导体因子 + 风险偏好 + A股自身状态 · 仅用于研究")

with st.sidebar:
    st.header("系统控制")
    if st.button("立即更新全部行情", use_container_width=True):
        try:
            with st.spinner("正在更新 Yahoo Finance 行情并合并本地缓存..."):
                update_market_data()
            st.success("更新完成")
            st.rerun()
        except Exception as exc:
            st.error(f"更新失败：{exc}")

    st.markdown("**数据维护**")
    upload = st.file_uploader("导入159558 CSV（可选）", type=["csv"])
    if upload is not None and st.button("保存导入数据", use_container_width=True):
        try:
            count = save_uploaded_target(upload)
            st.success(f"已导入 {count} 行，点击上方按钮重新更新。")
        except Exception as exc:
            st.error(str(exc))

    st.info("自动任务在工作日运行。A50免费源可能缺失，系统会降级并明确显示，不会把旧数据伪装成当天数据。")

try:
    prices = load_prices(auto_update=False)
    dataset = build_dataset(prices)
    result = train_and_predict(dataset)
except Exception as exc:
    st.warning(f"正式多因子模型尚未就绪：{exc}")
    st.markdown("请先在 GitHub Actions 运行 **Update market data**，或点击左侧“立即更新全部行情”。")
    status = load_status()
    if not status.empty:
        st.dataframe(status, use_container_width=True, hide_index=True)
    st.stop()

latest = dataset.iloc[-1]
latest_date = pd.to_datetime(latest["date"]).date()

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("信号日期", str(latest_date))
m2.metric("量化评分", f"{result.score}/100")
m3.metric("方向判断", result.label)
m4.metric("上涨概率", f"{result.probability:.1%}")
m5.metric("模型健康度", f"{result.health_score}/100", result.health_label)

if result.score >= 72 and result.health_score >= 55:
    st.success(f"{result.action}｜参考仓位 {result.suggested_position}｜置信度 {result.confidence}")
elif result.score <= 40 or result.health_score < 45:
    st.error(f"{result.action}｜参考仓位 {result.suggested_position}｜置信度 {result.confidence}")
else:
    st.warning(f"{result.action}｜参考仓位 {result.suggested_position}｜置信度 {result.confidence}")

st.code(build_daily_text(result, latest_date), language=None)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "今日信号", "因子解释", "历史回测", "相似行情", "模型健康", "数据状态"
])

with tab1:
    c1, c2 = st.columns([1, 1])
    with c1:
        gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=result.score,
            title={"text": "今日量化评分"},
            gauge={"axis": {"range": [0, 100]}, "bar": {"thickness": 0.3}},
        ))
        gauge.update_layout(height=320, margin=dict(l=20, r=20, t=60, b=20))
        st.plotly_chart(gauge, use_container_width=True)
    with c2:
        st.subheader("决策摘要")
        st.write(f"**动作：** {result.action}")
        st.write(f"**参考仓位：** {result.suggested_position}")
        st.write(f"**模型置信度：** {result.confidence}")
        st.write(f"**可用因子：** {len(result.features)} 个")
        st.caption("仓位只是风险分级示例，不代表个性化投资建议。实盘前应先进行至少数月纸面跟踪。")

with tab2:
    view = result.contributions.copy()
    view["最新值"] = view["最新值"].map(lambda x: "缺失" if pd.isna(x) else f"{x:.2%}")
    view["贡献"] = view["贡献"].map(lambda x: f"{x:+.3f}")
    st.dataframe(view[["因子", "最新值", "影响", "贡献"]], use_container_width=True, hide_index=True)
    plot_df = result.contributions.head(12).sort_values("贡献")
    fig = px.bar(plot_df, x="贡献", y="因子", orientation="h", title="主要因子方向贡献")
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    metrics = result.metrics
    cols = st.columns(4)
    keys = list(metrics.keys())
    for i, key in enumerate(keys):
        value = metrics[key]
        if isinstance(value, float):
            shown = f"{value:.1%}" if key not in {"AUC", "Brier", "盈亏比"} else f"{value:.3f}"
        else:
            shown = str(value)
        cols[i % 4].metric(key, shown)

    hist = result.history.copy()
    hist["累计策略收益"] = (1 + hist["target_ret"].where(hist["pred_prob"] >= 0.58, 0)).cumprod() - 1
    hist["累计持有收益"] = (1 + hist["target_ret"]).cumprod() - 1
    fig = px.line(hist, x="date", y=["累计策略收益", "累计持有收益"], title="样本外滚动回测")
    st.plotly_chart(fig, use_container_width=True)

    prob_fig = px.line(hist, x="date", y="pred_prob", title="历史预测上涨概率")
    prob_fig.add_hline(y=0.5, line_dash="dash")
    prob_fig.add_hline(y=0.58, line_dash="dot")
    st.plotly_chart(prob_fig, use_container_width=True)
    st.download_button("下载样本外预测记录", hist.to_csv(index=False).encode("utf-8-sig"), "predictions.csv", "text/csv")

with tab4:
    similar = result.similar_days.copy()
    similar["日期"] = pd.to_datetime(similar["date"]).dt.date
    similar["相似距离"] = similar["distance"].map(lambda x: f"{x:.3f}")
    similar["当日收益"] = similar["target_ret"].map(lambda x: f"{x:.2%}")
    similar["结果"] = similar["target_up"].map({1: "上涨", 0: "下跌"})
    st.dataframe(similar[["日期", "相似距离", "当日收益", "结果"]], use_container_width=True, hide_index=True)
    if len(similar):
        st.metric("相似行情上涨率", f"{similar['target_up'].mean():.1%}")
        st.metric("相似行情平均收益", f"{similar['target_ret'].mean():.2%}")

with tab5:
    st.metric("健康度", f"{result.health_score}/100", result.health_label)
    health_df = pd.DataFrame([{"指标": k, "数值": v} for k, v in result.health_stats.items()])
    if not health_df.empty:
        health_df["数值"] = health_df["数值"].map(lambda x: f"{x:.3f}")
        st.dataframe(health_df, use_container_width=True, hide_index=True)
    st.markdown("健康度综合最近20日、60日及全样本的方向准确率与概率校准误差。低于45分时系统自动降低仓位建议。")

with tab6:
    status = load_status()
    if status.empty:
        st.info("尚未生成数据状态。")
    else:
        st.dataframe(status, use_container_width=True, hide_index=True)
    meta_path = DATA_DIR / "update_meta.json"
    if meta_path.exists():
        st.json(json.loads(meta_path.read_text(encoding="utf-8")))

st.divider()
st.caption("风险提示：历史回测、模型评分和相似行情均不能保证未来收益。该系统不构成证券投资建议，也不应替代止损、仓位管理与独立判断。")
