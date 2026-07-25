from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable


@dataclass(frozen=True)
class Asset:
    symbol: str
    name: str
    market: str
    timezone: str
    currency: str
    yahoo: str | None
    twelve: str | None
    required: bool
    note: str | None = None


@dataclass(frozen=True)
class Bar:
    asset_symbol: str
    trading_date: date
    open: float | None
    high: float | None
    low: float | None
    close: float
    adj_close: float | None
    volume: float | None
    provider: str
    fetched_at: datetime
    is_cached: bool = False


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    bars: tuple[Bar, ...]
    error: str | None = None

    @property
    def ok(self) -> bool:
        return bool(self.bars) and self.error is None

    @classmethod
    def success(cls, provider: str, bars: Iterable[Bar]) -> "ProviderResult":
        return cls(provider=provider, bars=tuple(bars))

    @classmethod
    def failure(cls, provider: str, error: str) -> "ProviderResult":
        return cls(provider=provider, bars=(), error=error)


@dataclass(frozen=True)
class PriceRow:
    asset_symbol: str
    trading_date: date
    open: float | None
    high: float | None
    low: float | None
    close: float
    adj_close: float | None
    volume: float | None
    provider: str


@dataclass(frozen=True)
class FeatureValue:
    target_symbol: str
    feature_date: date
    feature_name: str
    value: float | None
    source_symbol: str | None
    source_date: date | None
    feature_version: str
