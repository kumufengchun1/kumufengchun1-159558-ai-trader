from __future__ import annotations

from datetime import date, datetime, timezone
from statistics import fmean, pstdev

from ats.db.repository import Repository
from ats.services.alignment import previous_source_date

FEATURE_VERSION = "v0.2.0"
ALIGNMENT_RULE = "latest_source_trading_date_strictly_before_target_date"


def _price(row) -> float:
    value = row["adj_close"] if row["adj_close"] is not None else row["close"]
    return float(value)


def _ret(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return current / previous - 1.0


def _mean(values: list[float]) -> float | None:
    return fmean(values) if values else None


class FeatureEngine:
    def __init__(self, repo: Repository, version: str = FEATURE_VERSION):
        self.repo = repo
        self.version = version

    def build(self, target_symbol: str, source_symbols: list[str]) -> tuple[int, int]:
        self.repo.initialize()
        run_id = self.repo.start_feature_run(target_symbol)
        generated_at = datetime.now(timezone.utc).isoformat()
        target_rows = self.repo.list_prices(target_symbol)
        if not target_rows:
            self.repo.finish_feature_run(run_id, "failed", 0, 0, "target has no prices")
            return 0, 0

        self.repo.clear_feature_version(target_symbol, self.version)
        source_rows = {symbol: self.repo.list_prices(symbol) for symbol in source_symbols}
        source_by_date = {
            symbol: {date.fromisoformat(row["trading_date"]): row for row in rows}
            for symbol, rows in source_rows.items()
        }
        source_dates = {symbol: sorted(mapping) for symbol, mapping in source_by_date.items()}

        target_dates = [date.fromisoformat(row["trading_date"]) for row in target_rows]
        target_prices = [_price(row) for row in target_rows]
        target_volumes = [float(row["volume"]) if row["volume"] is not None else None for row in target_rows]
        feature_rows: list[tuple] = []

        def add(
            feature_date: date,
            name: str,
            value: float | None,
            source_symbol: str | None,
            source_date: date | None,
        ) -> None:
            feature_rows.append(
                (
                    target_symbol,
                    feature_date.isoformat(),
                    name,
                    value,
                    source_symbol,
                    source_date.isoformat() if source_date else None,
                    self.version,
                    generated_at,
                )
            )

        for index, target_date in enumerate(target_dates):
            # Target-internal features use only information from the preceding target session.
            prior_index = index - 1
            if prior_index >= 0:
                prior_date = target_dates[prior_index]
                prior_price = target_prices[prior_index]
                prior_prior_price = target_prices[prior_index - 1] if prior_index >= 1 else None
                add(target_date, "TARGET_RETURN_1D_LAG1", _ret(prior_price, prior_prior_price), target_symbol, prior_date)

                window5 = target_prices[max(0, prior_index - 4) : prior_index + 1]
                sma5 = _mean(window5)
                add(
                    target_date,
                    "TARGET_CLOSE_VS_SMA5_LAG1",
                    prior_price / sma5 - 1.0 if sma5 else None,
                    target_symbol,
                    prior_date,
                )

                return_window = [
                    value
                    for j in range(max(1, prior_index - 4), prior_index + 1)
                    if (value := _ret(target_prices[j], target_prices[j - 1])) is not None
                ]
                add(
                    target_date,
                    "TARGET_VOLATILITY_5D_LAG1",
                    pstdev(return_window) if len(return_window) >= 2 else None,
                    target_symbol,
                    prior_date,
                )

                current_volume = target_volumes[prior_index]
                volume_window = [
                    value
                    for value in target_volumes[max(0, prior_index - 4) : prior_index + 1]
                    if value is not None
                ]
                mean_volume = _mean(volume_window)
                add(
                    target_date,
                    "TARGET_VOLUME_RATIO_5D_LAG1",
                    current_volume / mean_volume if current_volume is not None and mean_volume else None,
                    target_symbol,
                    prior_date,
                )

            for source_symbol in source_symbols:
                aligned_date = previous_source_date(target_date, source_dates[source_symbol])
                lag_days = (target_date - aligned_date).days if aligned_date else None
                self.repo.replace_alignment(
                    target_symbol,
                    target_date.isoformat(),
                    source_symbol,
                    aligned_date.isoformat() if aligned_date else None,
                    lag_days,
                    ALIGNMENT_RULE,
                )
                if aligned_date is None:
                    add(target_date, f"{source_symbol}_RETURN_1D", None, source_symbol, None)
                    continue
                mapping = source_by_date[source_symbol]
                dates = source_dates[source_symbol]
                source_index = dates.index(aligned_date)
                current = _price(mapping[aligned_date])
                previous = _price(mapping[dates[source_index - 1]]) if source_index >= 1 else None
                add(
                    target_date,
                    f"{source_symbol}_RETURN_1D",
                    _ret(current, previous),
                    source_symbol,
                    aligned_date,
                )

        count = self.repo.upsert_feature_values(feature_rows)
        status = "success" if count else "failed"
        message = f"version={self.version}, sources={len(source_symbols)}"
        self.repo.finish_feature_run(run_id, status, len(target_rows), count, message)
        return len(target_rows), count
