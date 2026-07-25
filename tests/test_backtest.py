from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from ats.backtest.walk_forward import WalkForwardBacktester, performance_metrics
from ats.db.repository import Repository
from ats.features.engine import FEATURE_VERSION
from ats.labels import LABEL_NAME, LABEL_VERSION


def _seed(repo: Repository, rows: int = 90) -> None:
    repo.initialize()
    generated = datetime.now(UTC).isoformat()
    start = datetime(2025, 1, 1, tzinfo=UTC)
    features = []
    labels = []
    for index in range(rows):
        day = (start + timedelta(days=index)).date().isoformat()
        feature = float(np.sin(index / 4.0))
        return_value = 0.01 if feature > 0 else -0.008
        features.append(
            (
                "159558.SZ",
                day,
                "SYNTHETIC_SIGNAL",
                feature,
                "TEST",
                day,
                FEATURE_VERSION,
                generated,
            )
        )
        labels.append(
            (
                "159558.SZ",
                day,
                LABEL_NAME,
                return_value,
                1,
                LABEL_VERSION,
                generated,
            )
        )
    repo.upsert_feature_values(features)
    repo.replace_labels("159558.SZ", LABEL_VERSION, labels)


def test_walk_forward_persists_daily_and_metrics(tmp_path):
    repo = Repository(tmp_path / "market.db")
    _seed(repo)
    result = WalkForwardBacktester(
        repo,
        min_train_rows=40,
        rebalance_rows=10,
        transaction_cost_bps=3,
        slippage_bps=2,
    ).run("159558.SZ")
    assert result.rows == 50
    assert result.retrains == 5
    assert result.strategy_metrics["total_return"] is not None
    with repo.connect() as conn:
        daily = conn.execute(
            "SELECT COUNT(*) AS n FROM backtest_daily WHERE backtest_run_id=?",
            (result.run_id,),
        ).fetchone()
        metrics = conn.execute(
            "SELECT COUNT(*) AS n FROM backtest_metrics WHERE backtest_run_id=?",
            (result.run_id,),
        ).fetchone()
    assert daily["n"] == 50
    assert metrics["n"] >= 12


def test_performance_metrics_drawdown_is_non_positive():
    metrics = performance_metrics(np.asarray([0.10, -0.20, 0.05]))
    assert metrics["max_drawdown"] <= 0
    assert metrics["total_return"] == pytest.approx(-0.076, abs=1e-12)


def test_cost_is_charged_when_position_changes(tmp_path):
    repo = Repository(tmp_path / "market.db")
    _seed(repo)
    backtester = WalkForwardBacktester(repo, min_train_rows=40, rebalance_rows=10)
    result = backtester.run("159558.SZ")
    with repo.connect() as conn:
        row = conn.execute(
            """SELECT turnover,transaction_cost FROM backtest_daily
               WHERE backtest_run_id=? AND turnover>0 LIMIT 1""",
            (result.run_id,),
        ).fetchone()
    assert row is not None
    assert row["transaction_cost"] > 0
