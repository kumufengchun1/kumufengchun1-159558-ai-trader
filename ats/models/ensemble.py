from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ats.db.repository import Repository
from ats.features.engine import FEATURE_VERSION
from ats.labels import LABEL_NAME, LABEL_VERSION

MODEL_NAME = "calibrated_ensemble"
MODEL_VERSION = "v0.5.0"


@dataclass(frozen=True)
class EnsembleResult:
    run_id: int
    train_rows: int
    calibration_rows: int
    test_rows: int
    metrics: dict[str, float | None]
    weights: dict[str, float]


@dataclass
class _FittedComponent:
    name: str
    estimator: Any
    calibrator: LogisticRegression | None
    calibration_brier: float

    def raw_probability(self, frame: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.estimator.predict_proba(frame)[:, 1], dtype=float)

    def probability(self, frame: pd.DataFrame) -> np.ndarray:
        raw = self.raw_probability(frame)
        if self.calibrator is None:
            return np.clip(raw, 1e-6, 1.0 - 1e-6)
        calibrated = self.calibrator.predict_proba(raw.reshape(-1, 1))[:, 1]
        return np.clip(calibrated, 1e-6, 1.0 - 1e-6)


class EnsembleTrainer:
    def __init__(self, repo: Repository, test_fraction: float = 0.25):
        if not 0.15 <= test_fraction <= 0.35:
            raise ValueError("test_fraction must be between 0.15 and 0.35")
        self.repo = repo
        self.test_fraction = test_fraction

    def train(self, target_symbol: str) -> EnsembleResult:
        frame = self.repo.load_model_frame(
            target_symbol,
            FEATURE_VERSION,
            LABEL_NAME,
            LABEL_VERSION,
        )
        if frame.empty:
            raise ValueError("no joined feature and label rows")

        usable = frame.dropna(subset=["label"]).sort_values("feature_date").reset_index(drop=True)
        if len(usable) < 80:
            raise ValueError(f"at least 80 labeled rows are required, got {len(usable)}")

        feature_names = tuple(
            column for column in usable.columns if column not in {"feature_date", "label"}
        )
        test_start = max(60, int(len(usable) * (1.0 - self.test_fraction)))
        test_start = min(test_start, len(usable) - 15)
        calibration_size = max(20, int(test_start * 0.2))
        fit_end = test_start - calibration_size
        if fit_end < 40:
            raise ValueError("not enough pre-test rows for temporal calibration")

        fit = usable.iloc[:fit_end]
        calibration = usable.iloc[fit_end:test_start]
        test = usable.iloc[test_start:]
        x_fit = fit.loc[:, feature_names]
        x_calibration = calibration.loc[:, feature_names]
        x_test = test.loc[:, feature_names]
        y_fit = (fit["label"] > 0).astype(int)
        y_calibration = (calibration["label"] > 0).astype(int)
        y_test = (test["label"] > 0).astype(int)
        if y_fit.nunique() < 2:
            raise ValueError("fit sample contains only one class")

        run_id = self.repo.start_model_run(
            target_symbol=target_symbol,
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
            feature_version=FEATURE_VERSION,
            label_version=LABEL_VERSION,
            train_start=str(fit.iloc[0]["feature_date"]),
            train_end=str(calibration.iloc[-1]["feature_date"]),
            test_start=str(test.iloc[0]["feature_date"]),
            test_end=str(test.iloc[-1]["feature_date"]),
            train_rows=len(fit) + len(calibration),
            test_rows=len(test),
        )

        try:
            components = self._fit_components(
                x_fit,
                y_fit,
                x_calibration,
                y_calibration,
            )
            weights = _component_weights(components)
            raw_matrix = np.column_stack(
                [component.raw_probability(x_test) for component in components]
            )
            calibrated_matrix = np.column_stack(
                [component.probability(x_test) for component in components]
            )
            weight_vector = np.asarray([weights[item.name] for item in components])
            probabilities = calibrated_matrix @ weight_vector
            agreement = np.clip(1.0 - 2.0 * calibrated_matrix.std(axis=1), 0.0, 1.0)
            confidence = np.abs(probabilities - 0.5) * 2.0
            positions = np.asarray(
                [
                    position_from_probability(probability, agreement_value)
                    for probability, agreement_value in zip(
                        probabilities,
                        agreement,
                        strict=True,
                    )
                ]
            )
            predicted = (probabilities >= 0.5).astype(int)
            metrics = _metrics(
                y_test.to_numpy(),
                probabilities,
                predicted,
                agreement,
                positions,
            )
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
            self.repo.save_ensemble_weights(
                run_id,
                {
                    item.name: (item.calibration_brier, weights[item.name])
                    for item in components
                },
            )
            self._save_component_predictions(
                run_id,
                test,
                components,
                raw_matrix,
                calibrated_matrix,
            )
            self._save_decisions(
                run_id,
                target_symbol,
                test,
                probabilities,
                agreement,
                confidence,
                positions,
            )
            self.repo.finish_model_run(
                run_id,
                "success",
                "temporal calibration and weighted ensemble complete",
            )
        except Exception as exc:
            self.repo.finish_model_run(run_id, "failed", f"{type(exc).__name__}: {exc}")
            raise

        return EnsembleResult(
            run_id=run_id,
            train_rows=len(fit),
            calibration_rows=len(calibration),
            test_rows=len(test),
            metrics=metrics,
            weights=weights,
        )

    def _fit_components(
        self,
        x_fit: pd.DataFrame,
        y_fit: pd.Series,
        x_calibration: pd.DataFrame,
        y_calibration: pd.Series,
    ) -> list[_FittedComponent]:
        estimators = {
            "logistic": Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="median")),
                    ("scaler", StandardScaler()),
                    (
                        "classifier",
                        LogisticRegression(max_iter=2000, random_state=42),
                    ),
                ]
            ),
            "extra_trees": Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="median")),
                    (
                        "classifier",
                        ExtraTreesClassifier(
                            n_estimators=250,
                            min_samples_leaf=5,
                            max_features="sqrt",
                            random_state=42,
                            n_jobs=-1,
                        ),
                    ),
                ]
            ),
            "hist_gradient_boosting": Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="median")),
                    (
                        "classifier",
                        HistGradientBoostingClassifier(
                            max_iter=150,
                            learning_rate=0.05,
                            max_leaf_nodes=15,
                            l2_regularization=1.0,
                            random_state=42,
                        ),
                    ),
                ]
            ),
        }
        fitted: list[_FittedComponent] = []
        for name, estimator in estimators.items():
            estimator.fit(x_fit, y_fit)
            raw = np.asarray(estimator.predict_proba(x_calibration)[:, 1], dtype=float)
            calibrator = _fit_sigmoid_calibrator(raw, y_calibration.to_numpy())
            if calibrator is None:
                calibrated = raw
            else:
                calibrated = calibrator.predict_proba(raw.reshape(-1, 1))[:, 1]
            brier = float(brier_score_loss(y_calibration, calibrated))
            fitted.append(_FittedComponent(name, estimator, calibrator, brier))
        return fitted

    def _save_component_predictions(
        self,
        run_id: int,
        test: pd.DataFrame,
        components: list[_FittedComponent],
        raw_matrix: np.ndarray,
        calibrated_matrix: np.ndarray,
    ) -> None:
        rows: list[tuple[str, str, float, float]] = []
        dates = test["feature_date"].astype(str).tolist()
        for component_index, component in enumerate(components):
            for row_index, prediction_date in enumerate(dates):
                rows.append(
                    (
                        prediction_date,
                        component.name,
                        float(raw_matrix[row_index, component_index]),
                        float(calibrated_matrix[row_index, component_index]),
                    )
                )
        self.repo.save_ensemble_component_predictions(run_id, rows)

    def _save_decisions(
        self,
        run_id: int,
        target_symbol: str,
        test: pd.DataFrame,
        probabilities: np.ndarray,
        agreement: np.ndarray,
        confidence: np.ndarray,
        positions: np.ndarray,
    ) -> None:
        rows = []
        journal_rows = []
        generated_at = datetime.now(UTC).isoformat()
        for date_value, probability, agree, conf, position, actual_return in zip(
            test["feature_date"],
            probabilities,
            agreement,
            confidence,
            positions,
            test["label"].to_numpy(dtype=float),
            strict=True,
        ):
            signal = signal_from_position(float(position), float(probability))
            predicted_up = probability >= 0.5
            actual_up = actual_return > 0
            outcome = "correct" if predicted_up == actual_up else "incorrect"
            rows.append(
                (
                    target_symbol,
                    str(date_value),
                    float(probability),
                    float(agree),
                    float(conf),
                    float(position),
                    signal,
                    float(actual_return),
                    outcome,
                )
            )
            journal_rows.append(
                (
                    target_symbol,
                    str(date_value),
                    run_id,
                    float(probability),
                    signal,
                    float(conf),
                    float(actual_return),
                    outcome,
                    generated_at,
                )
            )
        self.repo.save_ensemble_decisions(run_id, rows)
        self.repo.save_decision_journal(journal_rows)


def _fit_sigmoid_calibrator(
    probabilities: np.ndarray,
    actual: np.ndarray,
) -> LogisticRegression | None:
    if len(np.unique(actual)) < 2 or len(probabilities) < 10:
        return None
    calibrator = LogisticRegression(max_iter=1000, random_state=42)
    calibrator.fit(probabilities.reshape(-1, 1), actual)
    return calibrator


def _component_weights(components: list[_FittedComponent]) -> dict[str, float]:
    inverse = np.asarray([1.0 / max(item.calibration_brier, 1e-4) for item in components])
    normalized = inverse / inverse.sum()
    return {
        item.name: float(weight)
        for item, weight in zip(components, normalized, strict=True)
    }


def position_from_probability(probability: float, agreement: float) -> float:
    if probability < 0.52 or agreement < 0.50:
        return 0.0
    if probability < 0.57:
        position = 0.25
    elif probability < 0.62:
        position = 0.50
    else:
        position = 0.75
    if agreement < 0.65:
        return min(position, 0.25)
    if agreement < 0.80:
        return min(position, 0.50)
    return position


def signal_from_position(position: float, probability: float) -> str:
    if position == 0.0:
        return "watch" if probability >= 0.5 else "defensive"
    if position <= 0.25:
        return "small_long"
    if position <= 0.50:
        return "medium_long"
    return "strong_long"


def _metrics(
    actual: np.ndarray,
    probabilities: np.ndarray,
    predicted: np.ndarray,
    agreement: np.ndarray,
    positions: np.ndarray,
) -> dict[str, float | None]:
    result: dict[str, float | None] = {
        "accuracy": float(accuracy_score(actual, predicted)),
        "brier_score": float(brier_score_loss(actual, probabilities)),
        "log_loss": float(log_loss(actual, probabilities, labels=[0, 1])),
        "positive_rate": float(actual.mean()),
        "mean_agreement": float(agreement.mean()),
        "mean_confidence": float((np.abs(probabilities - 0.5) * 2.0).mean()),
        "mean_position": float(positions.mean()),
        "active_rate": float((positions > 0).mean()),
    }
    result["roc_auc"] = (
        float(roc_auc_score(actual, probabilities)) if len(np.unique(actual)) == 2 else None
    )
    return result
