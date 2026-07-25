from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ats.db.repository import Repository
from ats.features.engine import FEATURE_VERSION
from ats.labels import LABEL_NAME, LABEL_VERSION

MODEL_NAME = "logistic_regression"
MODEL_VERSION = "v0.3.0"


@dataclass(frozen=True)
class TrainingResult:
    run_id: int
    train_rows: int
    test_rows: int
    metrics: dict[str, float | None]
    feature_names: tuple[str, ...]


class BaselineTrainer:
    def __init__(self, repo: Repository, test_fraction: float = 0.25):
        if not 0.1 <= test_fraction <= 0.5:
            raise ValueError("test_fraction must be between 0.1 and 0.5")
        self.repo = repo
        self.test_fraction = test_fraction

    def train(self, target_symbol: str) -> TrainingResult:
        frame = self.repo.load_model_frame(
            target_symbol,
            FEATURE_VERSION,
            LABEL_NAME,
            LABEL_VERSION,
        )
        if frame.empty:
            raise ValueError("no joined feature and label rows")

        feature_names = tuple(
            column for column in frame.columns if column not in {"feature_date", "label"}
        )
        usable = frame.dropna(subset=["label"]).sort_values("feature_date").reset_index(drop=True)
        if len(usable) < 40:
            raise ValueError(f"at least 40 labeled rows are required, got {len(usable)}")

        split = max(20, int(len(usable) * (1.0 - self.test_fraction)))
        split = min(split, len(usable) - 10)
        train = usable.iloc[:split]
        test = usable.iloc[split:]
        x_train = train.loc[:, feature_names]
        x_test = test.loc[:, feature_names]
        y_train = (train["label"] > 0).astype(int)
        y_test = (test["label"] > 0).astype(int)
        if y_train.nunique() < 2:
            raise ValueError("training sample contains only one class")

        run_id = self.repo.start_model_run(
            target_symbol=target_symbol,
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
            feature_version=FEATURE_VERSION,
            label_version=LABEL_VERSION,
            train_start=str(train.iloc[0]["feature_date"]),
            train_end=str(train.iloc[-1]["feature_date"]),
            test_start=str(test.iloc[0]["feature_date"]),
            test_end=str(test.iloc[-1]["feature_date"]),
            train_rows=len(train),
            test_rows=len(test),
        )

        pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("classifier", LogisticRegression(max_iter=2000, random_state=42)),
            ]
        )
        try:
            pipeline.fit(x_train, y_train)
            probabilities = pipeline.predict_proba(x_test)[:, 1]
            predicted = (probabilities >= 0.5).astype(int)
            metrics = _metrics(y_test.to_numpy(), probabilities, predicted)
            self.repo.save_model_metrics(run_id, metrics, "holdout")
            self.repo.save_predictions(
                run_id,
                target_symbol,
                test["feature_date"].astype(str).tolist(),
                probabilities.tolist(),
                predicted.tolist(),
                y_test.astype(int).tolist(),
                test["label"].astype(float).tolist(),
                "holdout",
            )
            classifier = pipeline.named_steps["classifier"]
            coefficients = dict(zip(feature_names, classifier.coef_[0], strict=True))
            self.repo.save_model_coefficients(run_id, coefficients)
            self._write_journal(
                run_id,
                target_symbol,
                test,
                probabilities,
                test["label"].to_numpy(dtype=float),
            )
            self.repo.finish_model_run(run_id, "success", "chronological holdout complete")
        except Exception as exc:
            self.repo.finish_model_run(run_id, "failed", f"{type(exc).__name__}: {exc}")
            raise

        return TrainingResult(run_id, len(train), len(test), metrics, feature_names)

    def _write_journal(
        self,
        run_id: int,
        target_symbol: str,
        test: pd.DataFrame,
        probabilities: np.ndarray,
        returns: np.ndarray,
    ) -> None:
        generated_at = datetime.now(UTC).isoformat()
        rows = []
        for feature_date, probability, actual_return in zip(
            test["feature_date"], probabilities, returns, strict=True
        ):
            if probability >= 0.55:
                signal = "bullish"
            elif probability <= 0.45:
                signal = "bearish"
            else:
                signal = "neutral"
            confidence = abs(float(probability) - 0.5) * 2.0
            predicted_up = probability >= 0.5
            actual_up = actual_return > 0
            outcome = "correct" if predicted_up == actual_up else "incorrect"
            rows.append(
                (
                    target_symbol,
                    str(feature_date),
                    run_id,
                    float(probability),
                    signal,
                    confidence,
                    float(actual_return),
                    outcome,
                    generated_at,
                )
            )
        self.repo.save_decision_journal(rows)


def _metrics(
    actual: np.ndarray,
    probabilities: np.ndarray,
    predicted: np.ndarray,
) -> dict[str, float | None]:
    result: dict[str, float | None] = {
        "accuracy": float(accuracy_score(actual, predicted)),
        "brier_score": float(brier_score_loss(actual, probabilities)),
        "log_loss": float(log_loss(actual, probabilities, labels=[0, 1])),
        "positive_rate": float(actual.mean()),
    }
    result["roc_auc"] = (
        float(roc_auc_score(actual, probabilities)) if len(np.unique(actual)) == 2 else None
    )
    return result
