from datetime import UTC, datetime, timedelta

from ats.services.quality import assess


def test_quality_required_missing_fails():
    assert assess(None, datetime.now(UTC).date(), 0, True)[0] == "failed"


def test_quality_recent_is_ok():
    latest = (datetime.now(UTC).date() - timedelta(days=2)).isoformat()
    assert assess(latest, datetime.now(UTC).date(), 10, True)[0] == "ok"
