from datetime import date

from ats.services.alignment import previous_source_date


def test_previous_source_date_is_strict_and_holiday_safe():
    dates = [date(2026, 7, 2), date(2026, 7, 6), date(2026, 7, 7)]
    assert previous_source_date(date(2026, 7, 7), dates) == date(2026, 7, 6)
    assert previous_source_date(date(2026, 7, 6), dates) == date(2026, 7, 2)
    assert previous_source_date(date(2026, 7, 2), dates) is None
