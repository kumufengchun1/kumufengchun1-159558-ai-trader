from __future__ import annotations
from datetime import datetime, timezone
import pandas as pd
import yfinance as yf
from sqlalchemy import text
from app.db import engine
from app.services.symbols import SYMBOLS

COLS = ["Open", "High", "Low", "Close", "Volume"]

def _download_one(ticker: str, period: str = "3y") -> pd.DataFrame:
    df = yf.download(ticker, period=period, auto_adjust=True, progress=False, threads=False)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index().rename(columns={"Date": "trade_date"})
    keep = [c for c in ["trade_date", *COLS] if c in df.columns]
    return df[keep].copy()

def fetch_symbol(key: str, period: str = "3y") -> tuple[pd.DataFrame, str]:
    cfg = SYMBOLS[key]
    candidates = cfg.get("yahoo_candidates") or [cfg["yahoo"]]
    for ticker in candidates:
        try:
            df = _download_one(ticker, period)
            if not df.empty:
                return df, f"Yahoo:{ticker}"
        except Exception:
            continue
    return pd.DataFrame(), "missing"

def upsert_prices(symbol: str, df: pd.DataFrame, source: str) -> int:
    if df.empty:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    records = []
    for _, r in df.iterrows():
        dt = pd.Timestamp(r["trade_date"]).date().isoformat()
        records.append({
            "symbol": symbol, "trade_date": dt,
            "open": float(r.get("Open", float("nan"))) if pd.notna(r.get("Open")) else None,
            "high": float(r.get("High", float("nan"))) if pd.notna(r.get("High")) else None,
            "low": float(r.get("Low", float("nan"))) if pd.notna(r.get("Low")) else None,
            "close": float(r.get("Close", float("nan"))) if pd.notna(r.get("Close")) else None,
            "volume": float(r.get("Volume", float("nan"))) if pd.notna(r.get("Volume")) else None,
            "source": source, "updated_at": now,
        })
    sql = text("""
    INSERT INTO market_prices(symbol,trade_date,open,high,low,close,volume,source,updated_at)
    VALUES(:symbol,:trade_date,:open,:high,:low,:close,:volume,:source,:updated_at)
    ON CONFLICT(symbol,trade_date) DO UPDATE SET
      open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,
      volume=excluded.volume,source=excluded.source,updated_at=excluded.updated_at
    """)
    with engine.begin() as conn:
        conn.execute(sql, records)
    return len(records)

def update_all(period: str = "3y") -> dict:
    result = {}
    for key in SYMBOLS:
        df, source = fetch_symbol(key, period)
        result[key] = {"rows": upsert_prices(key, df, source), "source": source}
    return result
