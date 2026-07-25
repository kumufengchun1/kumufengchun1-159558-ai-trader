from __future__ import annotations

from datetime import UTC, datetime

from ats.db.repository import Repository

LABEL_VERSION = "v0.3.0"
LABEL_NAME = "TARGET_RETURN_1D"


def build_labels(
    repo: Repository,
    target_symbol: str,
    version: str = LABEL_VERSION,
) -> int:
    """Create same-session close-to-close returns for each feature date.

    Features for date T are constructed only from information available before T,
    while the label is the adjusted return from T-1 close to T close.
    """
    rows = repo.list_prices(target_symbol)
    generated_at = datetime.now(UTC).isoformat()
    output: list[tuple] = []
    for index in range(1, len(rows)):
        previous = _price(rows[index - 1])
        current = _price(rows[index])
        value = current / previous - 1.0 if previous else None
        output.append(
            (
                target_symbol,
                rows[index]["trading_date"],
                LABEL_NAME,
                value,
                1,
                version,
                generated_at,
            )
        )
    repo.replace_labels(target_symbol, version, output)
    return len(output)


def _price(row) -> float:
    value = row["adj_close"] if row["adj_close"] is not None else row["close"]
    return float(value)
