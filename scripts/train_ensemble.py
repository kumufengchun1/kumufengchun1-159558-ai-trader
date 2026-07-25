import json

from ats.db.repository import Repository
from ats.models.ensemble import EnsembleTrainer
from ats.settings import settings


def main() -> int:
    repo = Repository(settings.database_path)
    repo.initialize()
    result = EnsembleTrainer(repo).train("159558")
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "train_rows": result.train_rows,
                "calibration_rows": result.calibration_rows,
                "test_rows": result.test_rows,
                "metrics": result.metrics,
                "weights": result.weights,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
