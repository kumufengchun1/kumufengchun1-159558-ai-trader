from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from collections.abc import Iterator

from ats.db.schema import (
    BACKTEST_SCHEMA_SQL,
    ENSEMBLE_SCHEMA_SQL,
    EXPERIMENT_SCHEMA_SQL,
    MODEL_SCHEMA_SQL,
    SCHEMA_SQL,
)
from ats.domain import Asset, Bar


class Repository:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.executescript(MODEL_SCHEMA_SQL)
            conn.executescript(BACKTEST_SCHEMA_SQL)
            conn.executescript(ENSEMBLE_SCHEMA_SQL)
            conn.executescript(EXPERIMENT_SCHEMA_SQL)

    def upsert_assets(self, assets: list[Asset]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO assets(symbol,name,market,timezone,currency,required,note)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(symbol) DO UPDATE SET
                  name=excluded.name, market=excluded.market, timezone=excluded.timezone,
                  currency=excluded.currency, required=excluded.required, note=excluded.note
                """,
                [
                    (a.symbol, a.name, a.market, a.timezone, a.currency, int(a.required), a.note)
                    for a in assets
                ],
            )

    def start_run(self, total: int) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO update_runs(started_at,status,assets_total) VALUES(?,?,?)",
                (datetime.now(UTC).isoformat(), "running", total),
            )
            return int(cur.lastrowid)

    def finish_run(self, run_id: int, status: str, updated: int, failed: int, message: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """UPDATE update_runs
                   SET finished_at=?, status=?, assets_updated=?, assets_failed=?, message=?
                   WHERE id=?""",
                (datetime.now(UTC).isoformat(), status, updated, failed, message, run_id),
            )

    def upsert_bars(self, bars: tuple[Bar, ...]) -> int:
        if not bars:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO daily_prices(
                  asset_symbol,trading_date,open,high,low,close,adj_close,volume,
                  provider,fetched_at,is_cached
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(asset_symbol,trading_date) DO UPDATE SET
                  open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,
                  adj_close=excluded.adj_close,volume=excluded.volume,provider=excluded.provider,
                  fetched_at=excluded.fetched_at,is_cached=excluded.is_cached
                """,
                [
                    (
                        b.asset_symbol,
                        b.trading_date.isoformat(),
                        b.open,
                        b.high,
                        b.low,
                        b.close,
                        b.adj_close,
                        b.volume,
                        b.provider,
                        b.fetched_at.isoformat(),
                        int(b.is_cached),
                    )
                    for b in bars
                ],
            )
        return len(bars)

    def record_failure(self, run_id: int, asset: str, provider: str, error: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO provider_failures(run_id,asset_symbol,provider,occurred_at,error)
                   VALUES(?,?,?,?,?)""",
                (run_id, asset, provider, datetime.now(UTC).isoformat(), error[:2000]),
            )

    def latest_date(self, symbol: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT MAX(trading_date) AS latest FROM daily_prices WHERE asset_symbol=?",
                (symbol,),
            ).fetchone()
            return row["latest"] if row else None

    def count_prices(self, symbol: str) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM daily_prices WHERE asset_symbol=?", (symbol,)
            ).fetchone()
            return int(row["n"])

    def record_quality(
        self,
        run_id: int,
        symbol: str,
        latest: str | None,
        row_count: int,
        status: str,
        details: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO data_quality(
                   run_id,asset_symbol,latest_date,row_count,status,details
                   ) VALUES(?,?,?,?,?,?)""",
                (run_id, symbol, latest, row_count, status, details),
            )

    def list_prices(self, symbol: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    """SELECT asset_symbol, trading_date, open, high, low, close,
                              adj_close, volume, provider
                       FROM daily_prices
                       WHERE asset_symbol=?
                       ORDER BY trading_date""",
                    (symbol,),
                ).fetchall()
            )

    def list_symbols(self) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute("SELECT symbol FROM assets ORDER BY symbol")
            return [row["symbol"] for row in rows]

    def start_feature_run(self, target_symbol: str) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO feature_runs(target_symbol,started_at,status) VALUES(?,?,?)",
                (target_symbol, datetime.now(UTC).isoformat(), "running"),
            )
            return int(cur.lastrowid)

    def finish_feature_run(
        self,
        run_id: int,
        status: str,
        target_rows: int,
        feature_rows: int,
        message: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """UPDATE feature_runs
                   SET finished_at=?, status=?, target_rows=?, feature_rows=?, message=?
                   WHERE id=?""",
                (
                    datetime.now(UTC).isoformat(),
                    status,
                    target_rows,
                    feature_rows,
                    message,
                    run_id,
                ),
            )

    def replace_alignment(
        self,
        target_symbol: str,
        target_date: str,
        source_symbol: str,
        source_date: str | None,
        lag_days: int | None,
        rule: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO alignment_map(
                   target_symbol,target_date,source_symbol,source_date,lag_calendar_days,
                   alignment_rule,generated_at
                   ) VALUES(?,?,?,?,?,?,?)""",
                (
                    target_symbol,
                    target_date,
                    source_symbol,
                    source_date,
                    lag_days,
                    rule,
                    datetime.now(UTC).isoformat(),
                ),
            )

    def upsert_feature_values(self, rows: list[tuple]) -> int:
        if not rows:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """INSERT INTO feature_values(
                   target_symbol,feature_date,feature_name,value,source_symbol,source_date,
                   feature_version,generated_at
                   ) VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(
                     target_symbol, feature_date, feature_name, feature_version
                   ) DO UPDATE SET
                     value=excluded.value,source_symbol=excluded.source_symbol,
                     source_date=excluded.source_date,generated_at=excluded.generated_at""",
                rows,
            )
        return len(rows)

    def clear_feature_version(self, target_symbol: str, version: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM feature_values WHERE target_symbol=? AND feature_version=?",
                (target_symbol, version),
            )
            conn.execute("DELETE FROM alignment_map WHERE target_symbol=?", (target_symbol,))

    def upsert_adjustment_audit(self, rows: list[tuple]) -> int:
        if not rows:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO adjustment_audit(
                   asset_symbol,trading_date,close_to_adj_ratio,prior_ratio,ratio_change,
                   raw_return,adjusted_return,status,details,audited_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
        return len(rows)

    def feature_count(self, target_symbol: str, version: str) -> int:
        with self.connect() as conn:
            row = conn.execute(
                """SELECT COUNT(*) AS n FROM feature_values
                   WHERE target_symbol=? AND feature_version=?""",
                (target_symbol, version),
            ).fetchone()
            return int(row["n"])

    def replace_labels(self, target_symbol: str, version: str, rows: list[tuple]) -> int:
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM label_values WHERE target_symbol=? AND label_version=?",
                (target_symbol, version),
            )
            if rows:
                conn.executemany(
                    """INSERT INTO label_values(
                       target_symbol,label_date,label_name,value,horizon_sessions,
                       label_version,generated_at
                       ) VALUES(?,?,?,?,?,?,?)""",
                    rows,
                )
        return len(rows)

    def load_model_frame(
        self,
        target_symbol: str,
        feature_version: str,
        label_name: str,
        label_version: str,
    ):
        import pandas as pd

        with self.connect() as conn:
            feature_rows = conn.execute(
                """SELECT feature_date, feature_name, value
                   FROM feature_values
                   WHERE target_symbol=? AND feature_version=?
                   ORDER BY feature_date, feature_name""",
                (target_symbol, feature_version),
            ).fetchall()
            label_rows = conn.execute(
                """SELECT label_date, value
                   FROM label_values
                   WHERE target_symbol=? AND label_name=? AND label_version=?
                   ORDER BY label_date""",
                (target_symbol, label_name, label_version),
            ).fetchall()
        if not feature_rows or not label_rows:
            return pd.DataFrame()
        features = pd.DataFrame(feature_rows, columns=["feature_date", "feature_name", "value"])
        pivot = features.pivot(index="feature_date", columns="feature_name", values="value")
        pivot = pivot.reset_index()
        labels = pd.DataFrame(label_rows, columns=["feature_date", "label"])
        return pivot.merge(labels, on="feature_date", how="inner")

    def start_model_run(
        self,
        target_symbol: str,
        model_name: str,
        model_version: str,
        feature_version: str,
        label_version: str,
        train_start: str,
        train_end: str,
        test_start: str,
        test_end: str,
        train_rows: int,
        test_rows: int,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """INSERT INTO model_runs(
                   target_symbol,model_name,model_version,feature_version,label_version,
                   started_at,status,train_start,train_end,test_start,test_end,
                   train_rows,test_rows
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    target_symbol,
                    model_name,
                    model_version,
                    feature_version,
                    label_version,
                    datetime.now(UTC).isoformat(),
                    "running",
                    train_start,
                    train_end,
                    test_start,
                    test_end,
                    train_rows,
                    test_rows,
                ),
            )
            return int(cursor.lastrowid)

    def finish_model_run(self, run_id: int, status: str, message: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """UPDATE model_runs
                   SET finished_at=?, status=?, message=?
                   WHERE id=?""",
                (datetime.now(UTC).isoformat(), status, message, run_id),
            )

    def save_model_metrics(
        self,
        run_id: int,
        metrics: dict[str, float | None],
        sample_name: str,
    ) -> None:
        with self.connect() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO model_metrics(
                   model_run_id,metric_name,metric_value,sample_name
                   ) VALUES(?,?,?,?)""",
                [(run_id, name, value, sample_name) for name, value in metrics.items()],
            )

    def save_model_coefficients(self, run_id: int, coefficients: dict[str, float]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO model_coefficients(
                   model_run_id,feature_name,coefficient
                   ) VALUES(?,?,?)""",
                [(run_id, name, float(value)) for name, value in coefficients.items()],
            )

    def save_predictions(
        self,
        run_id: int,
        target_symbol: str,
        dates: list[str],
        probabilities: list[float],
        predicted: list[int],
        actual: list[int],
        actual_returns: list[float],
        sample_name: str,
    ) -> None:
        generated_at = datetime.now(UTC).isoformat()
        rows = [
            (
                run_id,
                target_symbol,
                prediction_date,
                float(probability),
                int(predicted_class),
                int(actual_class),
                float(actual_return),
                sample_name,
                generated_at,
            )
            for prediction_date, probability, predicted_class, actual_class, actual_return
            in zip(
                dates,
                probabilities,
                predicted,
                actual,
                actual_returns,
                strict=True,
            )
        ]
        with self.connect() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO predictions(
                   model_run_id,target_symbol,prediction_date,probability_up,
                   predicted_class,actual_class,actual_return,sample_name,generated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?)""",
                rows,
            )

    def save_decision_journal(self, rows: list[tuple]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO decision_journal(
                   target_symbol,decision_date,model_run_id,probability_up,signal,
                   confidence,actual_return,outcome,created_at
                   ) VALUES(?,?,?,?,?,?,?,?,?)""",
                rows,
            )


    def start_backtest_run(
        self,
        target_symbol: str,
        strategy_name: str,
        strategy_version: str,
        model_name: str,
        model_version: str,
        feature_version: str,
        label_version: str,
        start_date: str,
        end_date: str,
        min_train_rows: int,
        rebalance_rows: int,
        transaction_cost_bps: float,
        slippage_bps: float,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """INSERT INTO backtest_runs(
                   target_symbol,strategy_name,strategy_version,model_name,model_version,
                   feature_version,label_version,started_at,status,start_date,end_date,
                   min_train_rows,rebalance_rows,transaction_cost_bps,slippage_bps
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    target_symbol,
                    strategy_name,
                    strategy_version,
                    model_name,
                    model_version,
                    feature_version,
                    label_version,
                    datetime.now(UTC).isoformat(),
                    "running",
                    start_date,
                    end_date,
                    min_train_rows,
                    rebalance_rows,
                    transaction_cost_bps,
                    slippage_bps,
                ),
            )
            return int(cursor.lastrowid)

    def finish_backtest_run(self, run_id: int, status: str, message: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """UPDATE backtest_runs
                   SET finished_at=?, status=?, message=?
                   WHERE id=?""",
                (datetime.now(UTC).isoformat(), status, message, run_id),
            )

    def save_backtest_metrics(
        self,
        run_id: int,
        metrics: dict[str, float | None],
        series_name: str,
    ) -> None:
        with self.connect() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO backtest_metrics(
                   backtest_run_id,metric_name,metric_value,series_name
                   ) VALUES(?,?,?,?)""",
                [(run_id, name, value, series_name) for name, value in metrics.items()],
            )

    def save_backtest_daily(self, run_id: int, rows: list[tuple]) -> None:
        if not rows:
            return
        generated_at = datetime.now(UTC).isoformat()
        values = [(*row, generated_at) for row in rows]
        with self.connect() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO backtest_daily(
                   backtest_run_id,trading_date,probability_up,position,prior_position,
                   turnover,gross_return,transaction_cost,net_return,benchmark_return,
                   strategy_equity,benchmark_equity,train_start,train_end,generated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [(run_id, *row) for row in values],
            )


    def save_ensemble_weights(
        self,
        run_id: int,
        weights: dict[str, tuple[float | None, float]],
    ) -> None:
        with self.connect() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO ensemble_weights(
                   model_run_id,component_name,calibration_brier,ensemble_weight
                   ) VALUES(?,?,?,?)""",
                [
                    (run_id, name, brier, weight)
                    for name, (brier, weight) in weights.items()
                ],
            )

    def save_ensemble_component_predictions(
        self,
        run_id: int,
        rows: list[tuple[str, str, float, float]],
    ) -> None:
        with self.connect() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO ensemble_component_predictions(
                   model_run_id,prediction_date,component_name,raw_probability,
                   calibrated_probability
                   ) VALUES(?,?,?,?,?)""",
                [(run_id, *row) for row in rows],
            )

    def save_ensemble_decisions(self, run_id: int, rows: list[tuple]) -> None:
        generated_at = datetime.now(UTC).isoformat()
        with self.connect() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO ensemble_decisions(
                   model_run_id,target_symbol,prediction_date,probability_up,agreement,
                   confidence,position,signal,actual_return,outcome,generated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                [(run_id, *row, generated_at) for row in rows],
            )

    def get_model_run(self, run_id: int):
        with self.connect() as conn:
            return conn.execute("SELECT * FROM model_runs WHERE id=?", (run_id,)).fetchone()

    def get_model_metrics(self, run_id: int) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """SELECT metric_name, metric_value, sample_name
                   FROM model_metrics WHERE model_run_id=?
                   ORDER BY sample_name, metric_name""",
                (run_id,),
            ).fetchall()

    def get_backtest_run(self, run_id: int):
        with self.connect() as conn:
            return conn.execute("SELECT * FROM backtest_runs WHERE id=?", (run_id,)).fetchone()

    def get_backtest_metrics(self, run_id: int) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """SELECT metric_name, metric_value, series_name AS sample_name
                   FROM backtest_metrics WHERE backtest_run_id=?
                   ORDER BY series_name, metric_name""",
                (run_id,),
            ).fetchall()

    def latest_price_date(self, target_symbol: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT MAX(trading_date) AS latest_date FROM daily_prices WHERE asset_symbol=?",
                (target_symbol,),
            ).fetchone()
        return str(row["latest_date"]) if row and row["latest_date"] else None

    def upsert_experiment(self, values: tuple, metrics: list[tuple]) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO experiments(
                   experiment_id,source_type,source_run_id,target_symbol,experiment_name,
                   status,started_at,finished_at,git_commit,data_version,feature_version,
                   label_version,model_name,model_version,strategy_name,strategy_version,
                   parameters_json,metadata_json,created_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(source_type, source_run_id) DO UPDATE SET
                     experiment_name=excluded.experiment_name,status=excluded.status,
                     finished_at=excluded.finished_at,git_commit=excluded.git_commit,
                     data_version=excluded.data_version,parameters_json=excluded.parameters_json,
                     metadata_json=excluded.metadata_json""",
                values,
            )
            experiment_id = values[0]
            conn.execute(
                "DELETE FROM experiment_metrics WHERE experiment_id=?", (experiment_id,)
            )
            if metrics:
                conn.executemany(
                    """INSERT INTO experiment_metrics(
                       experiment_id,metric_name,metric_value,sample_name
                       ) VALUES(?,?,?,?)""",
                    [(experiment_id, *metric) for metric in metrics],
                )

    def get_experiment(self, experiment_id: str):
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM experiments WHERE experiment_id=?", (experiment_id,)
            ).fetchone()

    def list_experiment_metrics(self, experiment_id: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """SELECT metric_name,metric_value,sample_name
                   FROM experiment_metrics WHERE experiment_id=?
                   ORDER BY sample_name,metric_name""",
                (experiment_id,),
            ).fetchall()

