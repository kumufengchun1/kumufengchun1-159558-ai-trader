from __future__ import annotations

import csv
import sys

from ats.settings import settings


def main() -> None:
    import sqlite3

    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """SELECT id,target_symbol,model_name,model_version,status,
                      train_start,train_end,test_start,test_end,train_rows,test_rows,message
               FROM model_runs ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        if row is None:
            print("no model run")
            return
        writer = csv.writer(sys.stdout)
        writer.writerow(row.keys())
        writer.writerow([row[key] for key in row.keys()])
        metrics = conn.execute(
            """SELECT metric_name,metric_value,sample_name
               FROM model_metrics WHERE model_run_id=? ORDER BY metric_name""",
            (row["id"],),
        ).fetchall()
        writer.writerow([])
        writer.writerow(["metric_name", "metric_value", "sample_name"])
        for metric in metrics:
            writer.writerow([metric[key] for key in metric.keys()])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
