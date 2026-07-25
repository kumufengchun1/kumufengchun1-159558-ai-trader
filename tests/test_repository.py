from datetime import date, datetime, timezone

from ats.db.repository import Repository
from ats.domain import Asset, Bar


def test_upsert_is_idempotent(tmp_path):
    repo = Repository(tmp_path / "market.db")
    repo.initialize()
    asset = Asset("X", "Test", "US", "UTC", "USD", "X", None, True)
    repo.upsert_assets([asset])
    bar = Bar("X", date(2025, 1, 2), 1, 2, 0.5, 1.5, 1.5, 100, "mock", datetime.now(timezone.utc))
    repo.upsert_bars((bar,))
    repo.upsert_bars((bar,))
    assert repo.count_prices("X") == 1
