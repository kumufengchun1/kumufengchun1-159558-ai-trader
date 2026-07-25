from __future__ import annotations

from datetime import date, timedelta
import logging

from ats.db.repository import Repository
from ats.domain import Asset
from ats.providers.base import MarketDataProvider
from ats.services.quality import assess

logger = logging.getLogger(__name__)


class MarketUpdater:
    def __init__(self, repo: Repository, providers: list[MarketDataProvider]):
        self.repo = repo
        self.providers = providers

    def run(self, assets: list[Asset], start: date, end: date) -> int:
        self.repo.initialize()
        self.repo.upsert_assets(assets)
        run_id = self.repo.start_run(len(assets))
        updated_assets = 0
        failed_assets = 0

        for asset in assets:
            success = False
            for provider in self.providers:
                result = provider.fetch(asset, start, end)
                if result.ok:
                    self.repo.upsert_bars(result.bars)
                    updated_assets += 1
                    success = True
                    logger.info("%s updated by %s with %s rows", asset.symbol, provider.name, len(result.bars))
                    break
                self.repo.record_failure(run_id, asset.symbol, provider.name, result.error or "unknown")
                logger.warning("%s/%s failed: %s", asset.symbol, provider.name, result.error)

            if not success:
                failed_assets += 1

            latest = self.repo.latest_date(asset.symbol)
            count = self.repo.count_prices(asset.symbol)
            status, details = assess(latest, date.today(), count, asset.required)
            self.repo.record_quality(run_id, asset.symbol, latest, count, status, details)

        required_failures = sum(
            1
            for asset in assets
            if asset.required and assess(
                self.repo.latest_date(asset.symbol), date.today(), self.repo.count_prices(asset.symbol), True
            )[0] == "failed"
        )
        status = "failed" if required_failures else ("partial" if failed_assets else "success")
        message = (
            f"updated={updated_assets}, failed_fetches={failed_assets}, "
            f"required_data_failures={required_failures}"
        )
        self.repo.finish_run(run_id, status, updated_assets, failed_assets, message)
        return 1 if required_failures else 0


def default_date_range(years: int = 3) -> tuple[date, date]:
    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=365 * years + 10)
    return start, end
