import logging

from ats.config import load_assets
from ats.db.repository import Repository
from ats.features.engine import FeatureEngine
from ats.services.adjustments import audit_adjustments
from ats.settings import settings


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    repo = Repository(settings.database_path)
    repo.initialize()
    assets = load_assets(settings.assets_config)
    symbols = [asset.symbol for asset in assets]
    target = "159558"
    sources = [symbol for symbol in symbols if symbol != target]
    audited = audit_adjustments(repo, symbols)
    target_rows, features = FeatureEngine(repo).build(target, sources)
    logging.info("adjustment_audit=%s target_rows=%s features=%s", audited, target_rows, features)
    return 0 if target_rows and features else 1


if __name__ == "__main__":
    raise SystemExit(main())
