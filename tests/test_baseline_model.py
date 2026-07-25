from datetime import UTC, date, datetime, timedelta

from ats.db.repository import Repository
from ats.domain import Asset, Bar
from ats.features.engine import FEATURE_VERSION
from ats.labels import build_labels
from ats.models.baseline import BaselineTrainer


def test_baseline_uses_chronological_holdout_and_persists_results(tmp_path):
    repo = Repository(tmp_path / "market.db")
    repo.initialize()
    repo.upsert_assets([Asset("159558", "Target", "CN", "UTC", "CNY", None, None, True)])
    start = date(2024, 1, 1)
    bars = []
    features = []
    price = 100.0
    generated_at = datetime.now(UTC).isoformat()
    for index in range(80):
        trading_date = start + timedelta(days=index)
        direction = 1 if index % 4 in (1, 2) else -1
        price *= 1.0 + direction * 0.01
        bars.append(
            Bar(
                "159558",
                trading_date,
                price,
                price,
                price,
                price,
                price,
                1000,
                "test",
                datetime.now(UTC),
            )
        )
        features.append(
            (
                "159558",
                trading_date.isoformat(),
                "SYNTHETIC_SIGNAL",
                float(direction),
                "159558",
                trading_date.isoformat(),
                FEATURE_VERSION,
                generated_at,
            )
        )
        features.append(
            (
                "159558",
                trading_date.isoformat(),
                "ALL_MISSING_SIGNAL",
                None,
                "159558",
                trading_date.isoformat(),
                FEATURE_VERSION,
                generated_at,
            )
        )
    repo.upsert_bars(tuple(bars))
    repo.upsert_feature_values(features)
    build_labels(repo, "159558")

    result = BaselineTrainer(repo, test_fraction=0.25).train("159558")

    assert result.train_rows > result.test_rows
    assert result.metrics["accuracy"] is not None
    assert "ALL_MISSING_SIGNAL" not in result.feature_names
    with repo.connect() as conn:
        run = conn.execute("SELECT * FROM model_runs WHERE id=?", (result.run_id,)).fetchone()
        prediction_count = conn.execute(
            "SELECT COUNT(*) AS n FROM predictions WHERE model_run_id=?",
            (result.run_id,),
        ).fetchone()["n"]
        journal_count = conn.execute(
            "SELECT COUNT(*) AS n FROM decision_journal WHERE model_run_id=?",
            (result.run_id,),
        ).fetchone()["n"]
    assert run["status"] == "success"
    assert run["train_end"] < run["test_start"]
    assert prediction_count == result.test_rows
    assert journal_count == result.test_rows
