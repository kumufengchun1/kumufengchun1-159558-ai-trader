from datetime import date, timedelta
from ats.services.quality import assess


def test_quality_required_missing_fails():
    assert assess(None, date.today(), 0, True)[0] == "failed"


def test_quality_recent_is_ok():
    latest = (date.today() - timedelta(days=2)).isoformat()
    assert assess(latest, date.today(), 10, True)[0] == "ok"
