from __future__ import annotations

import json

from ats.db.repository import Repository
from ats.experiments import ExperimentTracker


def test_register_model_experiment_is_idempotent(tmp_path):
    repo = Repository(tmp_path / "market.db")
    repo.initialize()
    run_id = repo.start_model_run(
        target_symbol="159558",
        model_name="test_model",
        model_version="v1",
        feature_version="features-v1",
        label_version="labels-v1",
        train_start="2025-01-01",
        train_end="2025-03-31",
        test_start="2025-04-01",
        test_end="2025-04-30",
        train_rows=60,
        test_rows=20,
    )
    repo.save_model_metrics(run_id, {"accuracy": 0.61, "roc_auc": 0.66}, "test")
    repo.finish_model_run(run_id, "success", "complete")

    output_dir = tmp_path / "experiments"
    tracker = ExperimentTracker(repo, output_dir=output_dir, repo_root=tmp_path)
    first = tracker.register_model_run(run_id, parameters={"random_state": 42})
    second = tracker.register_model_run(run_id, parameters={"random_state": 42})

    assert first.experiment_id == second.experiment_id == "EXP-MODEL-000001"
    with repo.connect() as conn:
        experiment_count = conn.execute("SELECT COUNT(*) AS n FROM experiments").fetchone()["n"]
        metric_count = conn.execute(
            "SELECT COUNT(*) AS n FROM experiment_metrics WHERE experiment_id=?",
            (first.experiment_id,),
        ).fetchone()["n"]
    assert experiment_count == 1
    assert metric_count == 2
    manifest = json.loads((output_dir / "EXP-MODEL-000001.json").read_text())
    assert manifest["parameters"]["random_state"] == 42
    assert manifest["metrics"]["test"]["accuracy"] == 0.61
    assert manifest["git_commit"] == "unknown"


def test_register_backtest_experiment_captures_parameters(tmp_path):
    repo = Repository(tmp_path / "market.db")
    repo.initialize()
    run_id = repo.start_backtest_run(
        target_symbol="159558",
        strategy_name="long_cash",
        strategy_version="v1",
        model_name="logistic",
        model_version="v1",
        feature_version="features-v1",
        label_version="labels-v1",
        start_date="2025-01-01",
        end_date="2025-12-31",
        min_train_rows=120,
        rebalance_rows=20,
        transaction_cost_bps=3.0,
        slippage_bps=2.0,
    )
    repo.save_backtest_metrics(run_id, {"sharpe": 1.2}, "strategy")
    repo.save_backtest_metrics(run_id, {"sharpe": 0.8}, "benchmark")
    repo.finish_backtest_run(run_id, "success", "complete")

    record = ExperimentTracker(repo, output_dir=None, repo_root=tmp_path).register_backtest_run(
        run_id, parameters={"entry_probability": 0.55}
    )

    assert record.experiment_id == "EXP-BACKTEST-000001"
    assert record.parameters["min_train_rows"] == 120
    assert record.parameters["entry_probability"] == 0.55
    assert record.metrics["strategy"]["sharpe"] == 1.2
    assert record.metrics["benchmark"]["sharpe"] == 0.8
