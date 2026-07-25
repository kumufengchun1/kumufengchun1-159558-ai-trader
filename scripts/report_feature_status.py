from ats.db.repository import Repository
from ats.features.engine import FEATURE_VERSION
from ats.settings import settings


def main() -> int:
    repo = Repository(settings.database_path)
    repo.initialize()
    count = repo.feature_count("159558", FEATURE_VERSION)
    print(f"target=159558 feature_version={FEATURE_VERSION} rows={count}")
    return 0 if count else 1


if __name__ == "__main__":
    raise SystemExit(main())
