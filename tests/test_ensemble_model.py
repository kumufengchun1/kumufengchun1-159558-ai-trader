from datetime import UTC, datetime, timedelta

import numpy as np

from ats.db.repository import Repository
from ats.features.engine import FEATURE_VERSION
from ats.labels import LABEL_NAME, LABEL_VERSION
from ats.models.ensemble import EnsembleTrainer, position_from_probability


def _seed(repo: Repository, rows: int = 140) -> None:
    repo.initialize()
    generated = datetime.now(UTC).isoformat()
    start = datetime(2024, 1, 1, tzinfo=UTC)
    features = []
    labels = []
    for index in range(rows):
        day = (start + timedelta(days=index)).date().isoformat()
        signal = float(np.sin(index / 5.0))
        secondary = float(np.cos(index / 9.0))
        return_value = 0.012 if signal + 0.25 * secondary > 0 else -0.009
        for name, value in (
            ("SYNTHETIC_SIGNAL", signal),
            ("SECONDARY_SIGNAL", secondary),
        ):
            features.append(
                (
                    "159558",
                    day,
                    name,
                    value,
                    "TEST",
                    day,
                    FEATURE_VERSION,
                    generated,
                )
            )
        labels.append(
            (
                "159558",
                day,
                LABEL_NAME,
                return_value,
                1,
                LABEL_VERSION,
                generated,
            )
        )
    repo.upsert_feature_values(features)
    repo.replace_labels("159558", LABEL_VERSION, labels)


def test_ensemble_persists_weights_components_and_decisions(tmp_path):
    repo = Repository(tmp_path / "market.db")
    _seed(repo)

    result = EnsembleTrainer(repo).train("159558")

    assert result.test_rows > 0
    assert abs(sum(result.weights.values()) - 1.0) < 1e-9
    assert set(result.weights) == {
        "logistic",
        "extra_trees",
        "hist_gradient_boosting",
    }
    with repo.connect() as conn:
        weight_count = conn.execute(
            "SELECT COUNT(*) AS n FROM ensemble_weights WHERE model_run_id=?",
            (result.run_id,),
        ).fetchone()["n"]
        component_count = conn.execute(
            """SELECT COUNT(*) AS n FROM ensemble_component_predictions
               WHERE model_run_id=?""",
            (result.run_id,),
        ).fetchone()["n"]
        decision_count = conn.execute(
            "SELECT COUNT(*) AS n FROM ensemble_decisions WHERE model_run_id=?",
            (result.run_id,),
        ).fetchone()["n"]
    assert weight_count == 3
    assert component_count == result.test_rows * 3
    assert decision_count == result.test_rows


def test_position_tiers_respect_probability_and_agreement():
    assert position_from_probability(0.51, 0.95) == 0.0
    assert position_from_probability(0.56, 0.90) == 0.25
    assert position_from_probability(0.60, 0.90) == 0.50
    assert position_from_probability(0.66, 0.90) == 0.75
    assert position_from_probability(0.66, 0.60) == 0.25
    assert position_from_probability(0.66, 0.40) == 0.0
