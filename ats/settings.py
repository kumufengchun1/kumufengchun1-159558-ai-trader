from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_path: Path = Path("data/market.db")
    assets_config: Path = Path("config/assets.yml")
    twelve_api_key: str | None = None
    request_timeout_seconds: int = 25
    max_stale_calendar_days: int = 7


settings = Settings()
