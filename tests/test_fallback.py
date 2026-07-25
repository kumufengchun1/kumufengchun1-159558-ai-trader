from datetime import UTC, datetime

from ats.db.repository import Repository
from ats.domain import Asset, Bar, ProviderResult
from ats.providers.base import MarketDataProvider
from ats.services.updater import MarketUpdater


class Failing(MarketDataProvider):
    name = "failing"
    def fetch(self, asset, start, end):
        return ProviderResult.failure(self.name, "simulated outage")


class Working(MarketDataProvider):
    name = "working"
    def fetch(self, asset, start, end):
        return ProviderResult.success(
            self.name,
            [
                Bar(
                    asset.symbol,
                    datetime.now(UTC).date(),
                    1,
                    2,
                    0.5,
                    1.5,
                    1.5,
                    100,
                    self.name,
                    datetime.now(UTC),
                )
            ],
        )


def test_provider_fallback_does_not_abort(tmp_path):
    asset = Asset("X", "Test", "US", "UTC", "USD", "X", "X", True)
    repo = Repository(tmp_path / "market.db")
    today = datetime.now(UTC).date()
    code = MarketUpdater(repo, [Failing(), Working()]).run(
        [asset],
        today,
        today,
    )
    assert code == 0
    assert repo.count_prices("X") == 1
