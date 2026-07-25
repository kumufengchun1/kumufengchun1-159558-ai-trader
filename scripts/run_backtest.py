import logging

from ats.backtest.walk_forward import WalkForwardBacktester
from ats.db.repository import Repository
from ats.settings import settings

TARGET_SYMBOL = "159558"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = WalkForwardBacktester(Repository(settings.database_path)).run(TARGET_SYMBOL)
    logging.info(
        "backtest_run=%s rows=%s retrains=%s strategy=%s benchmark=%s",
        result.run_id,
        result.rows,
        result.retrains,
        result.strategy_metrics,
        result.benchmark_metrics,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
