from __future__ import annotations

from datetime import UTC, date, datetime

import requests

from ats.domain import Asset, Bar, ProviderResult
from ats.providers.base import MarketDataProvider


class TwelveDataProvider(MarketDataProvider):
    name = "twelve_data"

    def __init__(self, api_key: str | None, timeout: int = 25):
        self.api_key = api_key
        self.timeout = timeout

    def fetch(self, asset: Asset, start: date, end: date) -> ProviderResult:
        if not self.api_key:
            return ProviderResult.failure(self.name, "TWELVE_API_KEY is not configured")
        if not asset.twelve:
            return ProviderResult.failure(self.name, "no Twelve Data symbol configured")
        try:
            response = requests.get(
                "https://api.twelvedata.com/time_series",
                params={
                    "symbol": asset.twelve,
                    "interval": "1day",
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "outputsize": 5000,
                    "apikey": self.api_key,
                    "format": "JSON",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") == "error":
                return ProviderResult.failure(self.name, payload.get("message", "API error"))
            values = payload.get("values") or []
            fetched_at = datetime.now(UTC)
            bars = []
            for item in reversed(values):
                bars.append(
                    Bar(
                        asset_symbol=asset.symbol,
                        trading_date=date.fromisoformat(item["datetime"][:10]),
                        open=float(item["open"]) if item.get("open") else None,
                        high=float(item["high"]) if item.get("high") else None,
                        low=float(item["low"]) if item.get("low") else None,
                        close=float(item["close"]),
                        adj_close=None,
                        volume=float(item["volume"]) if item.get("volume") else None,
                        provider=self.name,
                        fetched_at=fetched_at,
                    )
                )
            return ProviderResult.success(self.name, bars) if bars else ProviderResult.failure(
                self.name, "empty response"
            )
        except Exception as exc:  # noqa: BLE001 - provider boundary isolates upstream failures
            return ProviderResult.failure(self.name, f"{type(exc).__name__}: {exc}")
