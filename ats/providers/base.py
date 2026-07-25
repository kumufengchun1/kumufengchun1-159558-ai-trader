from abc import ABC, abstractmethod
from datetime import date

from ats.domain import Asset, ProviderResult


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def fetch(self, asset: Asset, start: date, end: date) -> ProviderResult:
        raise NotImplementedError
