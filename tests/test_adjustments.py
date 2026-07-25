from datetime import date, datetime, timezone

from ats.db.repository import Repository
from ats.domain import Asset, Bar
from ats.services.adjustments import audit_adjustments


def bar(day: date, close: float, adjusted: float) -> Bar:
    return Bar(
        asset_symbol="SOXS",
        trading_date=day,
        open=close,
        high=close,
        low=close,
        close=close,
        adj_close=adjusted,
        volume=1.0,
        provider="test",
        fetched_at=datetime.now(timezone.utc),
    )


def test_adjustment_audit_flags_split_like_raw_jump(tmp_path):
    repo = Repository(tmp_path / "market.db")
    repo.initialize()
    repo.upsert_assets(
        [Asset("SOXS", "SOXS", "US", "America/New_York", "USD", None, None, True)]
    )
    repo.upsert_bars(
        (
            bar(date(2026, 7, 14), 10.0, 100.0),
            bar(date(2026, 7, 15), 50.0, 101.0),
        )
    )
    assert audit_adjustments(repo, ["SOXS"]) == 2
    with repo.connect() as conn:
        row = conn.execute(
            "SELECT status,details FROM adjustment_audit WHERE trading_date='2026-07-15'"
        ).fetchone()
    assert row["status"] == "review"
    assert "possible_corporate_action" in row["details"]
