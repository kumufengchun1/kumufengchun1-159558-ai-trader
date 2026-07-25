from datetime import date


def assess(latest_iso: str | None, today: date, row_count: int, required: bool) -> tuple[str, str]:
    if row_count == 0 or latest_iso is None:
        return ("failed" if required else "missing_optional", "no stored daily bars")
    latest = date.fromisoformat(latest_iso)
    age = (today - latest).days
    if age <= 4:
        return "ok", f"latest bar is {age} calendar day(s) old"
    if age <= 7:
        return "stale", f"latest bar is {age} calendar day(s) old; check holidays/provider"
    return ("failed" if required else "stale"), f"latest bar is {age} calendar day(s) old"
