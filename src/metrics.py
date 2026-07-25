from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score


def backtest_metrics(history: pd.DataFrame, threshold: float = 0.58) -> dict[str, float | int]:
    h = history.dropna(subset=["target_up", "pred_prob", "target_ret"]).copy()
    if h.empty:
        return {}
    h["pred_up"] = (h["pred_prob"] >= 0.5).astype(int)
    h["signal"] = h["pred_prob"] >= threshold
    signal = h[h["signal"]]
    equity = (1 + signal["target_ret"].fillna(0)).cumprod() if not signal.empty else pd.Series(dtype=float)
    drawdown = equity / equity.cummax() - 1 if not equity.empty else pd.Series(dtype=float)
    wins = signal.loc[signal["target_ret"] > 0, "target_ret"]
    losses = signal.loc[signal["target_ret"] < 0, "target_ret"]
    payoff = float(wins.mean() / abs(losses.mean())) if len(wins) and len(losses) and losses.mean() != 0 else np.nan
    return {
        "样本外样本": int(len(h)),
        "方向准确率": float(accuracy_score(h["target_up"], h["pred_up"])),
        "AUC": float(roc_auc_score(h["target_up"], h["pred_prob"])) if h["target_up"].nunique() > 1 else np.nan,
        "Brier": float(brier_score_loss(h["target_up"], h["pred_prob"])),
        "强信号次数": int(len(signal)),
        "强信号胜率": float((signal["target_ret"] > 0).mean()) if len(signal) else np.nan,
        "强信号平均收益": float(signal["target_ret"].mean()) if len(signal) else np.nan,
        "盈亏比": payoff,
        "最大回撤": float(drawdown.min()) if len(drawdown) else np.nan,
    }


def model_health(history: pd.DataFrame) -> tuple[int, str, dict[str, float]]:
    h = history.dropna(subset=["target_up", "pred_prob"]).copy()
    if len(h) < 20:
        return 40, "数据不足", {}
    windows = {"20日": 20, "60日": 60, "全部": len(h)}
    stats: dict[str, float] = {}
    scores = []
    for name, n in windows.items():
        x = h.tail(n)
        acc = ((x["pred_prob"] >= 0.5).astype(int) == x["target_up"]).mean()
        brier = ((x["pred_prob"] - x["target_up"]) ** 2).mean()
        stats[f"{name}准确率"] = float(acc)
        stats[f"{name}Brier"] = float(brier)
        scores.append(np.clip((acc - 0.45) / 0.20, 0, 1) * 60 + np.clip((0.28 - brier) / 0.12, 0, 1) * 40)
    health = int(round(0.5 * scores[0] + 0.3 * scores[1] + 0.2 * scores[2]))
    label = "良好" if health >= 75 else "正常" if health >= 55 else "衰减" if health >= 35 else "失效警告"
    return health, label, stats
