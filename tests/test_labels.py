from datetime import UTC, date, datetime

import pytest

from ats.db.repository import Repository
from ats.domain import Asset, Bar
from ats.labels import LABEL_NAME, LABEL_VERSION, build_labels


def test_labels_use_adjusted_close_and_same_feature_date(tmp_path):
    repo = Repository(tmp_path / "market.db")
    repo.initialize()
    repo.upsert_assets([Asset("159558", "Target", "CN", "UTC", "CNY", None, None, True)])
    bars = (
        Bar("159558", date(2025, 1, 2), 10, 10, 10, 10, 10, 1, "test", datetime.now(UTC)),
        Bar("159558", date(2025, 1, 3), 11, 11, 11, 11, 12, 1, "test", datetime.now(UTC)),
    )
    repo.upsert_bars(bars)

    assert build_labels(repo, "159558") == 1
    with repo.connect() as conn:
        row = conn.execute(
            """SELECT label_date,label_name,value,label_version
               FROM label_values WHERE target_symbol='159558'"""
        ).fetchone()
    assert row["label_date"] == "2025-01-03"
    assert row["label_name"] == LABEL_NAME
    assert row["label_version"] == LABEL_VERSION
    assert row["value"] == pytest.approx(0.2)
