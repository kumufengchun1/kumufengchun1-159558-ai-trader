from __future__ import annotations

import json
import logging

from ats.db.repository import Repository
from ats.experiments import ExperimentTracker
from ats.labels import build_labels
from ats.models.baseline import BaselineTrainer
from ats.settings import settings

TARGET_SYMBOL = "159558"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    repo = Repository(settings.database_path)
    repo.initialize()
    label_count = build_labels(repo, TARGET_SYMBOL)
    result = BaselineTrainer(repo).train(TARGET_SYMBOL)
    experiment = ExperimentTracker(repo).register_model_run(
        result.run_id,
        parameters={"test_fraction": 0.20, "random_state": 42},
        metadata={"feature_count": len(result.feature_names)},
    )
    summary = {
        "model_run_id": result.run_id,
        "labels": label_count,
        "train_rows": result.train_rows,
        "test_rows": result.test_rows,
        "features": len(result.feature_names),
        "metrics": result.metrics,
        "experiment_id": experiment.experiment_id,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
