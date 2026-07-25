import sqlite3

from ats.settings import settings


def main() -> None:
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    try:
        run = conn.execute(
            """SELECT id,status,train_rows,test_rows,message
               FROM model_runs
               WHERE model_name='calibrated_ensemble'
               ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        if run is None:
            print("No ensemble model run found")
            return
        print(
            "ensemble_run=",
            dict(run),
        )
        weights = conn.execute(
            """SELECT component_name,calibration_brier,ensemble_weight
               FROM ensemble_weights
               WHERE model_run_id=? ORDER BY component_name""",
            (run["id"],),
        ).fetchall()
        for row in weights:
            print("component=", dict(row))
        latest = conn.execute(
            """SELECT prediction_date,probability_up,agreement,confidence,position,signal
               FROM ensemble_decisions
               WHERE model_run_id=? ORDER BY prediction_date DESC LIMIT 1""",
            (run["id"],),
        ).fetchone()
        if latest is not None:
            print("latest_decision=", dict(latest))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
