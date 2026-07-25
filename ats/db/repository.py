from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from collections.abc import Iterator

from ats.db.schema import SCHEMA_SQL
from ats.domain import Asset, Bar


class Repository:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def upsert_assets(self, assets: list[Asset]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO assets(symbol,name,market,timezone,currency,required,note)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(symbol) DO UPDATE SET
                  name=excluded.name, market=excluded.market, timezone=excluded.timezone,
                  currency=excluded.currency, required=excluded.required, note=excluded.note
                """,
                [
                    (a.symbol, a.name, a.market, a.timezone, a.currency, int(a.required), a.note)
                    for a in assets
                ],
            )

    def start_run(self, total: int) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO update_runs(started_at,status,assets_total) VALUES(?,?,?)",
                (datetime.now(UTC).isoformat(), "running", total),
            )
            return int(cur.lastrowid)

    def finish_run(self, run_id: int, status: str, updated: int, failed: int, message: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """UPDATE update_runs SET finished_at=?,status=?,assets_updated=?,assets_failed=?,message=?
                   WHERE id=?""",
                (datetime.now(UTC).isoformat(), status, updated, failed, message, run_id),
            )

    def upsert_bars(self, bars: tuple[Bar, ...]) -> int:
        if not bars:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO daily_prices(
                  asset_symbol,trading_date,open,high,low,close,adj_close,volume,
                  provider,fetched_at,is_cached
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(asset_symbol,trading_date) DO UPDATE SET
                  open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,
                  adj_close=excluded.adj_close,volume=excluded.volume,provider=excluded.provider,
                  fetched_at=excluded.fetched_at,is_cached=excluded.is_cached
                """,
                [
                    (
                        b.asset_symbol,
                        b.trading_date.isoformat(),
                        b.open,
                        b.high,
                        b.low,
                        b.close,
                        b.adj_close,
                        b.volume,
                        b.provider,
                        b.fetched_at.isoformat(),
                        int(b.is_cached),
                    )
                    for b in bars
                ],
            )
        return len(bars)

    def record_failure(self, run_id: int, asset: str, provider: str, error: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO provider_failures(run_id,asset_symbol,provider,occurred_at,error)
                   VALUES(?,?,?,?,?)""",
                (run_id, asset, provider, datetime.now(UTC).isoformat(), error[:2000]),
            )

    def latest_date(self, symbol: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT MAX(trading_date) AS latest FROM daily_prices WHERE asset_symbol=?",
                (symbol,),
            ).fetchone()
            return row["latest"] if row else None

    def count_prices(self, symbol: str) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM daily_prices WHERE asset_symbol=?", (symbol,)
            ).fetchone()
            return int(row["n"])

    def record_quality(
        self, run_id: int, symbol: str, latest: str | None, row_count: int, status: str, details: str
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO data_quality(
                   run_id,asset_symbol,latest_date,row_count,status,details
                   ) VALUES(?,?,?,?,?,?)""",
                (run_id, symbol, latest, row_count, status, details),
            )

    def list_prices(self, symbol: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    """SELECT asset_symbol,trading_date,open,high,low,close,adj_close,volume,provider
                       FROM daily_prices WHERE asset_symbol=? ORDER BY trading_date""",
                    (symbol,),
                ).fetchall()
            )

    def list_symbols(self) -> list[str]:
        with self.connect() as conn:
            return [row["symbol"] for row in conn.execute("SELECT symbol FROM assets ORDER BY symbol")]

    def start_feature_run(self, target_symbol: str) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO feature_runs(target_symbol,started_at,status) VALUES(?,?,?)",
                (target_symbol, datetime.now(UTC).isoformat(), "running"),
            )
            return int(cur.lastrowid)

    def finish_feature_run(
        self,
        run_id: int,
        status: str,
        target_rows: int,
        feature_rows: int,
        message: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """UPDATE feature_runs SET finished_at=?,status=?,target_rows=?,feature_rows=?,message=?
                   WHERE id=?""",
                (
                    datetime.now(UTC).isoformat(),
                    status,
                    target_rows,
                    feature_rows,
                    message,
                    run_id,
                ),
            )

    def replace_alignment(
        self,
        target_symbol: str,
        target_date: str,
        source_symbol: str,
        source_date: str | None,
        lag_days: int | None,
        rule: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO alignment_map(
                   target_symbol,target_date,source_symbol,source_date,lag_calendar_days,
                   alignment_rule,generated_at
                   ) VALUES(?,?,?,?,?,?,?)""",
                (
                    target_symbol,
                    target_date,
                    source_symbol,
                    source_date,
                    lag_days,
                    rule,
                    datetime.now(UTC).isoformat(),
                ),
            )

    def upsert_feature_values(self, rows: list[tuple]) -> int:
        if not rows:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """INSERT INTO feature_values(
                   target_symbol,feature_date,feature_name,value,source_symbol,source_date,
                   feature_version,generated_at
                   ) VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(target_symbol,feature_date,feature_name,feature_version) DO UPDATE SET
                     value=excluded.value,source_symbol=excluded.source_symbol,
                     source_date=excluded.source_date,generated_at=excluded.generated_at""",
                rows,
            )
        return len(rows)

    def clear_feature_version(self, target_symbol: str, version: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM feature_values WHERE target_symbol=? AND feature_version=?",
                (target_symbol, version),
            )
            conn.execute("DELETE FROM alignment_map WHERE target_symbol=?", (target_symbol,))

    def upsert_adjustment_audit(self, rows: list[tuple]) -> int:
        if not rows:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO adjustment_audit(
                   asset_symbol,trading_date,close_to_adj_ratio,prior_ratio,ratio_change,
                   raw_return,adjusted_return,status,details,audited_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
        return len(rows)

    def feature_count(self, target_symbol: str, version: str) -> int:
        with self.connect() as conn:
            row = conn.execute(
                """SELECT COUNT(*) AS n FROM feature_values
                   WHERE target_symbol=? AND feature_version=?""",
                (target_symbol, version),
            ).fetchone()
            return int(row["n"])
