from __future__ import annotations

from bisect import bisect_left
from datetime import date


def previous_source_date(target_date: date, source_dates: list[date]) -> date | None:
    """Return the latest source trading date strictly before target_date.

    Strictly-before alignment prevents using a US close that was not yet known at the
    target market's opening. It also handles weekends and market-specific holidays.
    """
    index = bisect_left(source_dates, target_date) - 1
    return source_dates[index] if index >= 0 else None
