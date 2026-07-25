import logging

from ats.config import load_assets
from ats.db.repository import Repository
from ats.providers.twelve import TwelveDataProvider
from ats.providers.yahoo import YahooProvider
from ats.services.updater import MarketUpdater, default_date_range
from ats.settings import settings


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    assets = load_assets(settings.assets_config)
    providers = [
        YahooProvider(),
        TwelveDataProvider(
            settings.twelve_api_key,
            settings.request_timeout_seconds,
        ),
    ]
    updater = MarketUpdater(Repository(settings.database_path), providers)
    start, end = default_date_range(years=3)
    return updater.run(assets, start, end)


if __name__ == "__main__":
    raise SystemExit(main())
