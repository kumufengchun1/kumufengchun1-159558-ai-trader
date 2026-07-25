from datetime import UTC, date, datetime

from ats.db.repository import Repository
from ats.domain import Asset, Bar
from ats.features.engine import FEATURE_VERSION, FeatureEngine


def make_bar(symbol: str, day: date, close: float, volume: float = 100.0) -> Bar:
    return Bar(
        asset_symbol=symbol,
        trading_date=day,
        open=close,
        high=close,
        low=close,
        close=close,
        adj_close=close,
        volume=volume,
        provider="test",
        fetched_at=datetime.now(UTC),
    )


def test_feature_engine_aligns_previous_us_session_without_lookahead(tmp_path):
    repo = Repository(tmp_path / "market.db")
    repo.initialize()
    repo.upsert_assets(
        [
            Asset("159558", "target", "CN", "Asia/Shanghai", "CNY", None, None, True),
            Asset("SOX", "source", "US", "America/New_York", "USD", None, None, True),
        ]
    )
    repo.upsert_bars(
        (
            make_bar("159558", date(2026, 7, 6), 1.00),
            make_bar("159558", date(2026, 7, 7), 1.02),
            make_bar("159558", date(2026, 7, 8), 1.03),
            make_bar("SOX", date(2026, 7, 2), 100.0),
            make_bar("SOX", date(2026, 7, 6), 110.0),
            make_bar("SOX", date(2026, 7, 7), 121.0),
        )
    )

    target_rows, feature_rows = FeatureEngine(repo).build("159558", ["SOX"])

    assert target_rows == 3
    assert feature_rows > 0
    with repo.connect() as conn:
        aligned = conn.execute(
            """SELECT source_date FROM alignment_map
               WHERE target_symbol='159558' AND target_date='2026-07-07' AND source_symbol='SOX'"""
        ).fetchone()
        feature = conn.execute(
            """SELECT value,source_date FROM feature_values
               WHERE target_symbol='159558' AND feature_date='2026-07-07'
                 AND feature_name='SOX_RETURN_1D' AND feature_version=?""",
            (FEATURE_VERSION,),
        ).fetchone()
    assert aligned["source_date"] == "2026-07-06"
    assert feature["source_date"] == "2026-07-06"
    assert round(feature["value"], 6) == 0.1
