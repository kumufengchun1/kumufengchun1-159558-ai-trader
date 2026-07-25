from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    app_name: str = "159558 AI Trading System"
    app_password: str = ""
    twelve_api_key: str = ""
    database_url: str = f"sqlite:///{ROOT / 'data' / 'market.db'}"
    model_path: Path = ROOT / "models" / "ensemble.joblib"
    data_dir: Path = ROOT / "data"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.model_path.parent.mkdir(parents=True, exist_ok=True)
