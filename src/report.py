from __future__ import annotations

import pandas as pd


def build_daily_text(result, latest_date) -> str:
    top = result.contributions.head(5)
    reasons = "；".join(f"{r['因子']}：{r['影响']}" for _, r in top.iterrows())
    return (
        f"159558 日线信号（{latest_date}）\n"
        f"评分：{result.score}/100，方向：{result.label}，上涨概率：{result.probability:.1%}\n"
        f"建议：{result.action}，参考仓位：{result.suggested_position}，置信度：{result.confidence}\n"
        f"模型健康度：{result.health_score}/100（{result.health_label}）\n"
        f"主要原因：{reasons}\n"
        "仅用于研究，不构成投资建议。"
    )
