from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def dashboard_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "database_ready": False,
            "latest_decision": None,
            "ensemble_run": None,
            "weights": [],
            "backtest_run": None,
            "backtest_metrics": [],
            "equity": [],
            "quality": [],
            "update_run": None,
        }

    conn = _connect(path)
    try:
        ensemble_run = conn.execute(
            """SELECT id,status,started_at,finished_at,train_rows,test_rows,message
               FROM model_runs
               WHERE model_name='calibrated_ensemble'
               ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        latest_decision = None
        weights: list[dict[str, Any]] = []
        if ensemble_run is not None:
            latest_decision = conn.execute(
                """SELECT prediction_date,probability_up,agreement,confidence,position,
                          signal,actual_return,outcome,generated_at
                   FROM ensemble_decisions
                   WHERE model_run_id=?
                   ORDER BY prediction_date DESC LIMIT 1""",
                (ensemble_run["id"],),
            ).fetchone()
            weights = [
                dict(row)
                for row in conn.execute(
                    """SELECT component_name,calibration_brier,ensemble_weight
                       FROM ensemble_weights
                       WHERE model_run_id=? ORDER BY ensemble_weight DESC""",
                    (ensemble_run["id"],),
                ).fetchall()
            ]

        backtest_run = conn.execute(
            """SELECT id,target_symbol,strategy_name,strategy_version,status,start_date,
                      end_date,finished_at,message
               FROM backtest_runs ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        backtest_metrics: list[dict[str, Any]] = []
        equity: list[dict[str, Any]] = []
        if backtest_run is not None:
            backtest_metrics = [
                dict(row)
                for row in conn.execute(
                    """SELECT series_name,metric_name,metric_value
                       FROM backtest_metrics
                       WHERE backtest_run_id=? ORDER BY series_name,metric_name""",
                    (backtest_run["id"],),
                ).fetchall()
            ]
            equity = [
                dict(row)
                for row in conn.execute(
                    """SELECT trading_date,strategy_equity,benchmark_equity,position,
                              probability_up
                       FROM backtest_daily
                       WHERE backtest_run_id=? ORDER BY trading_date""",
                    (backtest_run["id"],),
                ).fetchall()
            ]

        quality = [
            dict(row)
            for row in conn.execute(
                """SELECT q.asset_symbol,q.latest_date,q.row_count,q.status,q.details
                   FROM data_quality q
                   JOIN (
                     SELECT asset_symbol,MAX(run_id) AS run_id
                     FROM data_quality GROUP BY asset_symbol
                   ) latest
                   ON q.asset_symbol=latest.asset_symbol AND q.run_id=latest.run_id
                   ORDER BY q.asset_symbol"""
            ).fetchall()
        ]
        update_run = conn.execute(
            """SELECT id,started_at,finished_at,status,assets_total,assets_updated,
                      assets_failed,message
               FROM update_runs ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        return {
            "database_ready": True,
            "latest_decision": _dict(latest_decision),
            "ensemble_run": _dict(ensemble_run),
            "weights": weights,
            "backtest_run": _dict(backtest_run),
            "backtest_metrics": backtest_metrics,
            "equity": equity,
            "quality": quality,
            "update_run": _dict(update_run),
        }
    except sqlite3.OperationalError:
        return {
            "database_ready": True,
            "latest_decision": None,
            "ensemble_run": None,
            "weights": [],
            "backtest_run": None,
            "backtest_metrics": [],
            "equity": [],
            "quality": [],
            "update_run": None,
        }
    finally:
        conn.close()
