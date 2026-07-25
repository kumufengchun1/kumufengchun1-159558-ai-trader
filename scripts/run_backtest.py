import logging

from ats.backtest.walk_forward import WalkForwardBacktester
from ats.db.repository import Repository
from ats.experiments import ExperimentTracker
from ats.settings import settings

TARGET_SYMBOL = "159558"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    repo = Repository(settings.database_path)
    repo.initialize()
    backtester = WalkForwardBacktester(repo)
    result = backtester.run(TARGET_SYMBOL)
    experiment = ExperimentTracker(repo).register_backtest_run(
        result.run_id,
        parameters={"entry_probability": backtester.entry_probability},
        metadata={"rows": result.rows, "retrains": result.retrains},
    )
    logging.info(
        "backtest_run=%s rows=%s retrains=%s strategy=%s benchmark=%s",
        result.run_id,
        result.rows,
        result.retrains,
        result.strategy_metrics,
        result.benchmark_metrics,
    )
    logging.info("experiment_id=%s", experiment.experiment_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
