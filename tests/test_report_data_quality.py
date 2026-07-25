import sqlite3

from scripts import report_data_quality


def test_report_data_quality_uses_column_names(tmp_path, monkeypatch, capsys):
    database_path = tmp_path / "market.db"
    conn = sqlite3.connect(database_path)
    conn.executescript(
        """
        CREATE TABLE assets (
            symbol TEXT PRIMARY KEY,
            required INTEGER NOT NULL,
            note TEXT
        );
        CREATE TABLE update_runs (
            id INTEGER PRIMARY KEY
        );
        CREATE TABLE data_quality (
            run_id INTEGER NOT NULL,
            asset_symbol TEXT NOT NULL,
            latest_date TEXT,
            row_count INTEGER NOT NULL,
            status TEXT NOT NULL,
            details TEXT
        );
        INSERT INTO assets(symbol, required, note) VALUES ('SOX', 1, 'primary');
        INSERT INTO update_runs(id) VALUES (1);
        INSERT INTO data_quality(
            run_id, asset_symbol, latest_date, row_count, status, details
        ) VALUES (1, 'SOX', '2026-07-24', 100, 'ok', 'complete');
        """
    )
    conn.close()

    monkeypatch.setattr(report_data_quality.settings, "database_path", database_path)
    report_data_quality.main()

    output = capsys.readouterr().out.splitlines()
    assert output[0] == "asset,latest_date,row_count,status,details,note"
    assert output[1] == "SOX,2026-07-24,100,ok,complete,primary"
