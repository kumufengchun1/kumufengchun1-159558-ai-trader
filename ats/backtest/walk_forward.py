from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ats.db.repository import Repository
from ats.features.engine import FEATURE_VERSION
from ats.labels import LABEL_NAME, LABEL_VERSION
from ats.models.baseline import MODEL_NAME, MODEL_VERSION

STRATEGY_NAME = "logistic_long_cash"
STRATEGY_VERSION = "v0.4.0"
TRADING_DAYS = 252


@dataclass(frozen=True)
class BacktestResult:
    run_id: int
    rows: int
    retrains: int
    strategy_metrics: dict[str, float | None]
    benchmark_metrics: dict[str, float | None]


class WalkForwardBacktester:
    def __init__(
        self,
        repo: Repository,
        min_train_rows: int = 120,
        rebalance_rows: int = 20,
        entry_probability: float = 0.55,
        transaction_cost_bps: float = 3.0,
        slippage_bps: float = 2.0,
    ):
        if min_train_rows < 40:
            raise ValueError("min_train_rows must be at least 40")
        if rebalance_rows < 1:
            raise ValueError("rebalance_rows must be positive")
        if not 0.5 <= entry_probability <= 0.9:
            raise ValueError("entry_probability must be between 0.5 and 0.9")
        self.repo = repo
        self.min_train_rows = min_train_rows
        self.rebalance_rows = rebalance_rows
        self.entry_probability = entry_probability
        self.transaction_cost_bps = transaction_cost_bps
        self.slippage_bps = slippage_bps

    def run(self, target_symbol: str) -> BacktestResult:
        frame = self.repo.load_model_frame(
            target_symbol,
            FEATURE_VERSION,
            LABEL_NAME,
            LABEL_VERSION,
        )
        usable = frame.dropna(subset=["label"]).sort_values("feature_date").reset_index(drop=True)
        if len(usable) <= self.min_train_rows:
            raise ValueError(
                f"more than {self.min_train_rows} labeled rows are required, got {len(usable)}"
            )
        feature_names = [
            column for column in usable.columns if column not in {"feature_date", "label"}
        ]
        run_id = self.repo.start_backtest_run(
            target_symbol=target_symbol,
            strategy_name=STRATEGY_NAME,
            strategy_version=STRATEGY_VERSION,
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
            feature_version=FEATURE_VERSION,
            label_version=LABEL_VERSION,
            start_date=str(usable.iloc[self.min_train_rows]["feature_date"]),
            end_date=str(usable.iloc[-1]["feature_date"]),
            min_train_rows=self.min_train_rows,
            rebalance_rows=self.rebalance_rows,
            transaction_cost_bps=self.transaction_cost_bps,
            slippage_bps=self.slippage_bps,
        )
        try:
            probabilities, windows = self._predict(usable, feature_names)
            daily = self._simulate(usable.iloc[self.min_train_rows :], probabilities, windows)
            strategy_metrics = performance_metrics(daily["net_return"].to_numpy())
            benchmark_metrics = performance_metrics(daily["benchmark_return"].to_numpy())
            strategy_metrics.update(
                {
                    "exposure": float(daily["position"].mean()),
                    "turnover": float(daily["turnover"].sum()),
                    "trades": float((daily["turnover"] > 0).sum()),
                    "win_rate_in_market": _win_rate(daily),
                }
            )
            self.repo.save_backtest_daily(run_id, _database_rows(daily))
            self.repo.save_backtest_metrics(run_id, strategy_metrics, "strategy")
            self.repo.save_backtest_metrics(run_id, benchmark_metrics, "benchmark")
            self.repo.finish_backtest_run(run_id, "success", "expanding walk-forward complete")
        except Exception as exc:
            self.repo.finish_backtest_run(run_id, "failed", f"{type(exc).__name__}: {exc}")
            raise
        return BacktestResult(
            run_id=run_id,
            rows=len(daily),
            retrains=len(set(daily["train_end"])),
            strategy_metrics=strategy_metrics,
            benchmark_metrics=benchmark_metrics,
        )

    def _predict(
        self,
        frame: pd.DataFrame,
        feature_names: list[str],
    ) -> tuple[np.ndarray, list[tuple[str, str]]]:
        probabilities: list[float] = []
        windows: list[tuple[str, str]] = []
        for start in range(self.min_train_rows, len(frame), self.rebalance_rows):
            stop = min(start + self.rebalance_rows, len(frame))
            train = frame.iloc[:start]
            test = frame.iloc[start:stop]
            y_train = (train["label"] > 0).astype(int)
            if y_train.nunique() < 2:
                raise ValueError("walk-forward training sample contains only one class")
            model = _pipeline()
            model.fit(train[feature_names], y_train)
            block = model.predict_proba(test[feature_names])[:, 1]
            probabilities.extend(float(value) for value in block)
            window = (
                str(train.iloc[0]["feature_date"]),
                str(train.iloc[-1]["feature_date"]),
            )
            windows.extend([window] * len(test))
        return np.asarray(probabilities), windows

    def _simulate(
        self,
        test: pd.DataFrame,
        probabilities: np.ndarray,
        windows: list[tuple[str, str]],
    ) -> pd.DataFrame:
        daily = pd.DataFrame(
            {
                "trading_date": test["feature_date"].astype(str).to_numpy(),
                "probability_up": probabilities,
                "benchmark_return": test["label"].astype(float).to_numpy(),
                "train_start": [window[0] for window in windows],
                "train_end": [window[1] for window in windows],
            }
        )
        daily["position"] = (daily["probability_up"] >= self.entry_probability).astype(float)
        daily["prior_position"] = daily["position"].shift(1, fill_value=0.0)
        daily["turnover"] = (daily["position"] - daily["prior_position"]).abs()
        daily["gross_return"] = daily["position"] * daily["benchmark_return"]
        one_way_cost = (self.transaction_cost_bps + self.slippage_bps) / 10_000.0
        daily["transaction_cost"] = daily["turnover"] * one_way_cost
        daily["net_return"] = daily["gross_return"] - daily["transaction_cost"]
        daily["strategy_equity"] = (1.0 + daily["net_return"]).cumprod()
        daily["benchmark_equity"] = (1.0 + daily["benchmark_return"]).cumprod()
        return daily


def _pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(max_iter=2000, random_state=42)),
        ]
    )


def performance_metrics(returns: np.ndarray) -> dict[str, float | None]:
    if len(returns) == 0:
        raise ValueError("returns must not be empty")
    equity = np.cumprod(1.0 + returns)
    total_return = float(equity[-1] - 1.0)
    years = len(returns) / TRADING_DAYS
    cagr = float(equity[-1] ** (1.0 / years) - 1.0) if years > 0 else None
    annual_volatility = float(np.std(returns, ddof=1) * np.sqrt(TRADING_DAYS))
    mean = float(np.mean(returns))
    std = float(np.std(returns, ddof=1))
    sharpe = float(mean / std * np.sqrt(TRADING_DAYS)) if std > 0 else None
    running_max = np.maximum.accumulate(equity)
    max_drawdown = float(np.min(equity / running_max - 1.0))
    return {
        "total_return": total_return,
        "cagr": cagr,
        "annual_volatility": annual_volatility,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "positive_day_rate": float(np.mean(returns > 0)),
    }


def _win_rate(daily: pd.DataFrame) -> float | None:
    active = daily.loc[daily["position"] > 0, "net_return"]
    return float((active > 0).mean()) if len(active) else None


def _database_rows(daily: pd.DataFrame) -> list[tuple]:
    columns = [
        "trading_date",
        "probability_up",
        "position",
        "prior_position",
        "turnover",
        "gross_return",
        "transaction_cost",
        "net_return",
        "benchmark_return",
        "strategy_equity",
        "benchmark_equity",
        "train_start",
        "train_end",
    ]
    return [tuple(row) for row in daily.loc[:, columns].itertuples(index=False, name=None)]
