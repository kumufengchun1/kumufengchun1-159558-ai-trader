from __future__ import annotations
from dataclasses import dataclass
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, brier_score_loss
from app.config import settings

@dataclass
class Bundle:
    models: dict
    features: list[str]
    metrics: dict


def _models() -> dict:
    return {
        "logit": Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler()), ("model", LogisticRegression(max_iter=2000, C=0.5))]),
        "forest": Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", RandomForestClassifier(n_estimators=300, max_depth=4, min_samples_leaf=10, random_state=42, class_weight="balanced"))]),
        "hgb": Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200, l2_regularization=1.0, random_state=42))]),
    }

def train(df: pd.DataFrame) -> Bundle:
    data = df.dropna(subset=["target_up"]).copy()
    features = [c for c in data.columns if c not in {"trade_date", "target_up", "target_return"}]
    if len(data) < 120:
        raise ValueError("有效样本不足120条，暂不训练。")
    split = int(len(data) * 0.7)
    train_df, test_df = data.iloc[:split], data.iloc[split:]
    models = _models(); probs = []
    for m in models.values():
        m.fit(train_df[features], train_df["target_up"])
        probs.append(m.predict_proba(test_df[features])[:, 1])
    ensemble = np.mean(probs, axis=0)
    metrics = {
        "train_samples": len(train_df), "test_samples": len(test_df),
        "test_accuracy": float(accuracy_score(test_df["target_up"], ensemble >= 0.5)),
        "test_brier": float(brier_score_loss(test_df["target_up"], ensemble)),
    }
    for m in models.values():
        m.fit(data[features], data["target_up"])
    bundle = Bundle(models=models, features=features, metrics=metrics)
    joblib.dump(bundle, settings.model_path)
    return bundle

def load_bundle() -> Bundle:
    return joblib.load(settings.model_path)

def predict_row(bundle: Bundle, row: pd.DataFrame) -> tuple[float, dict]:
    ps = {name: float(m.predict_proba(row[bundle.features])[:, 1][0]) for name, m in bundle.models.items()}
    return float(np.mean(list(ps.values()))), ps
