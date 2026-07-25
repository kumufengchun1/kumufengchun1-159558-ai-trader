import sqlite3
from ats.settings import settings


def main() -> None:
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT q.asset_symbol,q.latest_date,q.row_count,q.status,q.details,a.note
        FROM data_quality q
        JOIN assets a ON a.symbol=q.asset_symbol
        WHERE q.run_id=(SELECT MAX(id) FROM update_runs)
        ORDER BY a.required DESC,q.asset_symbol
        """
    ).fetchall()
    print("asset,latest_date,row_count,status,details,note")
    for r in rows:
        values = [r[k] if r[k] is not None else "" for k in r.keys()]
        print(",".join(str(v).replace(",", ";") for v in values))


if __name__ == "__main__":
    main()
