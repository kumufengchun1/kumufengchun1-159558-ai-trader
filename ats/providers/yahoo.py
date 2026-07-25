from __future__ import annotations

from datetime import date, datetime, timezone
import math

import pandas as pd
import yfinance as yf

from ats.domain import Asset, Bar, ProviderResult
from ats.providers.base import MarketDataProvider


def _num(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return float(value)


class YahooProvider(MarketDataProvider):
    name = "yahoo"

    def fetch(self, asset: Asset, start: date, end: date) -> ProviderResult:
        if not asset.yahoo:
            return ProviderResult.failure(self.name, "no Yahoo symbol configured")
        try:
            frame = yf.download(
                asset.yahoo,
                start=start.isoformat(),
                end=end.isoformat(),
                auto_adjust=False,
                progress=False,
                threads=False,
                timeout=25,
            )
            if frame.empty:
                return ProviderResult.failure(self.name, "empty response")
            if isinstance(frame.columns, pd.MultiIndex):
                frame.columns = frame.columns.get_level_values(0)
            fetched_at = datetime.now(timezone.utc)
            bars = []
            for idx, row in frame.iterrows():
                close = _num(row.get("Close"))
                if close is None:
                    continue
                bars.append(
                    Bar(
                        asset_symbol=asset.symbol,
                        trading_date=idx.date(),
                        open=_num(row.get("Open")),
                        high=_num(row.get("High")),
                        low=_num(row.get("Low")),
                        close=close,
                        adj_close=_num(row.get("Adj Close")),
                        volume=_num(row.get("Volume")),
                        provider=self.name,
                        fetched_at=fetched_at,
                    )
                )
            return ProviderResult.success(self.name, bars) if bars else ProviderResult.failure(
                self.name, "no valid rows"
            )
        except Exception as exc:  # provider boundary: never crash the full update
            return ProviderResult.failure(self.name, f"{type(exc).__name__}: {exc}")
