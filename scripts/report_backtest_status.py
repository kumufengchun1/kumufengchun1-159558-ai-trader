import sqlite3

from ats.settings import settings


def main() -> None:
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    try:
        run = conn.execute(
            """SELECT id,target_symbol,strategy_name,status,start_date,end_date,message
               FROM backtest_runs ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        if run is None:
            print("No backtest run found")
            return
        print(dict(run))
        metrics = conn.execute(
            """SELECT series_name,metric_name,metric_value
               FROM backtest_metrics WHERE backtest_run_id=?
               ORDER BY series_name,metric_name""",
            (run["id"],),
        ).fetchall()
        for row in metrics:
            print(dict(row))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
