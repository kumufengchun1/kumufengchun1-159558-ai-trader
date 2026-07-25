from sqlalchemy import create_engine, text
from app.config import settings

engine = create_engine(settings.database_url, future=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS market_prices (
  symbol TEXT NOT NULL,
  trade_date TEXT NOT NULL,
  open REAL, high REAL, low REAL, close REAL, volume REAL,
  source TEXT, updated_at TEXT,
  PRIMARY KEY(symbol, trade_date)
);
CREATE TABLE IF NOT EXISTS predictions (
  trade_date TEXT PRIMARY KEY,
  probability REAL, score INTEGER, signal TEXT, suggested_position REAL,
  model_health REAL, explanation TEXT, created_at TEXT
);
"""

def init_db() -> None:
    with engine.begin() as conn:
        for stmt in SCHEMA.strip().split(";"):
            if stmt.strip():
                conn.execute(text(stmt))
