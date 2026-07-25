from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .config import MIN_TRAIN, RANDOM_STATE, RAW_FEATURES
from .metrics import backtest_metrics, model_health


@dataclass
class PredictionResult:
    probability: float
    score: int
    label: str
    action: str
    suggested_position: str
    confidence: str
    features: list[str]
    contributions: pd.DataFrame
    history: pd.DataFrame
    metrics: dict
    health_score: int
    health_label: str
    health_stats: dict
    similar_days: pd.DataFrame


def _models() -> dict[str, Pipeline]:
    return {
        "logistic": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(C=0.35, max_iter=3000, class_weight="balanced", random_state=RANDOM_STATE)),
        ]),
        "forest": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", RandomForestClassifier(
                n_estimators=300, max_depth=4, min_samples_leaf=10,
                class_weight="balanced_subsample", random_state=RANDOM_STATE, n_jobs=-1,
            )),
        ]),
        "boost": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", HistGradientBoostingClassifier(
                max_depth=2, learning_rate=0.035, max_iter=160,
                min_samples_leaf=15, l2_regularization=3.0, random_state=RANDOM_STATE,
            )),
        ]),
    }


def usable_features(df: pd.DataFrame) -> list[str]:
    return [c for c in RAW_FEATURES if c in df.columns and df[c].notna().sum() >= 60 and df[c].nunique(dropna=True) > 3]


def _ensemble_predict(models: dict[str, Pipeline], x: pd.DataFrame) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    weights = {"logistic": 0.50, "forest": 0.25, "boost": 0.25}
    parts = {name: model.predict_proba(x)[:, 1] for name, model in models.items()}
    pred = sum(weights[name] * values for name, values in parts.items())
    return pred, parts


def walk_forward(dataset: pd.DataFrame, features: list[str], retrain_every: int = 20) -> pd.DataFrame:
    df = dataset.dropna(subset=["target_ret", "target_up"]).reset_index(drop=True).copy()
    if len(df) < MIN_TRAIN + 30:
        raise ValueError(f"有效历史不足，需要至少 {MIN_TRAIN + 30} 个交易日")
    rows = []
    fitted = None
    for i in range(MIN_TRAIN, len(df)):
        if fitted is None or (i - MIN_TRAIN) % retrain_every == 0:
            train = df.iloc[:i]
            fitted = {name: clone(model).fit(train[features], train["target_up"].astype(int)) for name, model in _models().items()}
        x = df.iloc[[i]][features]
        pred, parts = _ensemble_predict(fitted, x)
        rows.append({
            "date": df.iloc[i]["date"],
            "target_ret": float(df.iloc[i]["target_ret"]),
            "target_up": int(df.iloc[i]["target_up"]),
            "pred_prob": float(pred[0]),
            **{f"p_{k}": float(v[0]) for k, v in parts.items()},
        })
    return pd.DataFrame(rows)


def _explain_logistic(model: Pipeline, latest: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    imp = model.named_steps["imputer"].transform(latest)
    z = model.named_steps["scale"].transform(imp)[0]
    coef = model.named_steps["model"].coef_[0]
    contribution = z * coef
    labels = {
        "SOX_r1": "SOX单日", "SOX_r3": "SOX三日", "NVDA_r1": "NVDA单日", "NVDA_r3": "NVDA三日",
        "TSM_r1": "TSM单日", "ASML_r1": "ASML单日", "SOXS_r1": "SOXS单日", "VIX_r1": "VIX单日",
        "NASDAQ_r1": "纳指单日", "USDCNH_r1": "离岸人民币", "A50_r1": "A50夜盘",
        "breadth_up": "半导体上涨广度", "semiconductor_mean": "半导体平均涨幅", "risk_on": "风险偏好",
        "cn_lag1": "159558前一日", "cn_lag3": "159558前三日", "cn_ma5_gap": "相对5日均线",
        "cn_ma20_gap": "相对20日均线", "cn_vol20": "20日波动率",
    }
    out = pd.DataFrame({
        "因子": [labels.get(x, x) for x in features],
        "字段": features,
        "最新值": latest.iloc[0].values,
        "贡献": contribution,
    })
    out["影响"] = np.select([out["贡献"] > 0.04, out["贡献"] < -0.04], ["利多", "利空"], default="中性")
    return out.reindex(out["贡献"].abs().sort_values(ascending=False).index)


def _similar_days(dataset: pd.DataFrame, features: list[str], latest: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    hist = dataset.dropna(subset=["target_ret"]).copy()
    med = hist[features].median()
    std = hist[features].std().replace(0, 1)
    z_hist = (hist[features].fillna(med) - med) / std
    z_latest = (latest[features].fillna(med) - med) / std
    dist = np.sqrt(((z_hist - z_latest.iloc[0]) ** 2).mean(axis=1))
    out = hist.assign(distance=dist).sort_values("distance").head(n + 1)
    out = out[out["date"] != latest.iloc[0]["date"]].head(n)
    return out[["date", "distance", "target_ret", "target_up"]]


def train_and_predict(dataset: pd.DataFrame) -> PredictionResult:
    features = usable_features(dataset)
    if len(features) < 5:
        raise ValueError("可用因子不足5个。请先运行云端行情更新。")
    clean = dataset.dropna(subset=["target_ret", "target_up"]).copy()
    history = walk_forward(clean, features)

    fitted = {name: model.fit(clean[features], clean["target_up"].astype(int)) for name, model in _models().items()}
    latest = dataset.iloc[[-1]].copy()
    probability_arr, parts = _ensemble_predict(fitted, latest[features])
    probability = float(probability_arr[0])
    score = int(round(probability * 100))

    spread = float(np.std([v[0] for v in parts.values()]))
    confidence = "高" if spread < 0.06 and abs(probability - 0.5) >= 0.15 else "中" if spread < 0.11 else "低"
    if score >= 72:
        label, action, position = "强偏多", "可考虑分批参与", "20%–35%"
    elif score >= 60:
        label, action, position = "偏多", "观察开盘确认", "10%–20%"
    elif score <= 28:
        label, action, position = "强偏空", "回避新增仓位", "0%"
    elif score <= 40:
        label, action, position = "偏空", "以防守为主", "0%–10%"
    else:
        label, action, position = "中性", "不交易或等待", "0%–10%"

    contributions = _explain_logistic(fitted["logistic"], latest[features], features)
    metrics = backtest_metrics(history)
    health_score, health_label, health_stats = model_health(history)
    similar = _similar_days(dataset, features, latest)

    if health_score < 45:
        action = "模型健康度偏低，暂停新增交易"
        position = "0%–10%"

    return PredictionResult(
        probability, score, label, action, position, confidence, features,
        contributions, history, metrics, health_score, health_label, health_stats, similar,
    )
