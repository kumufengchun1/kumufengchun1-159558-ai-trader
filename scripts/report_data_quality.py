import csv
import sqlite3
import sys

from ats.settings import settings


COLUMNS = (
    "asset_symbol",
    "latest_date",
    "row_count",
    "status",
    "details",
    "note",
)


def main() -> None:
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT q.asset_symbol,q.latest_date,q.row_count,q.status,q.details,a.note
            FROM data_quality q
            JOIN assets a ON a.symbol=q.asset_symbol
            WHERE q.run_id=(SELECT MAX(id) FROM update_runs)
            ORDER BY a.required DESC,q.asset_symbol
            """
        ).fetchall()
    finally:
        conn.close()

    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(("asset", "latest_date", "row_count", "status", "details", "note"))
    for row in rows:
        writer.writerow(tuple(row[column] if row[column] is not None else "" for column in COLUMNS))


if __name__ == "__main__":
    main()
