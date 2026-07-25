from __future__ import annotations
import numpy as np
import pandas as pd
from sqlalchemy import text
from app.db import engine

US_FACTORS = ["SOX", "SOXS", "NVDA", "TSM", "ASML", "VIX", "NASDAQ", "USDCNH", "A50"]

def load_prices() -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text("SELECT * FROM market_prices ORDER BY trade_date"), conn)

def build_dataset() -> pd.DataFrame:
    raw = load_prices()
    if raw.empty:
        return pd.DataFrame()
    raw["trade_date"] = pd.to_datetime(raw["trade_date"])
    close = raw.pivot(index="trade_date", columns="symbol", values="close").sort_index()
    volume = raw.pivot(index="trade_date", columns="symbol", values="volume").sort_index()
    target_dates = close.index[close.get("159558", pd.Series(index=close.index)).notna()]
    out = pd.DataFrame(index=target_dates)
    # Last available overseas close before each China trading date.
    for s in US_FACTORS:
        ser = close.get(s)
        if ser is None:
            continue
        shifted = ser.shift(1).pct_change(fill_method=None)
        out[f"ret_{s}"] = shifted.reindex(target_dates, method="ffill")
        out[f"mom3_{s}"] = ser.shift(1).pct_change(3, fill_method=None).reindex(target_dates, method="ffill")
    c = close["159558"].reindex(target_dates)
    v = volume.get("159558", pd.Series(index=target_dates, dtype=float)).reindex(target_dates)
    out["cn_ret1"] = c.pct_change(fill_method=None).shift(1)
    out["cn_mom5"] = c.pct_change(5, fill_method=None).shift(1)
    out["cn_ma5_gap"] = (c / c.rolling(5).mean() - 1).shift(1)
    out["cn_vol_ratio"] = (v / v.rolling(5).mean()).shift(1)
    out["cn_volatility10"] = c.pct_change(fill_method=None).rolling(10).std().shift(1)
    out["target_return"] = c.pct_change(fill_method=None)
    out["target_up"] = (out["target_return"] > 0).astype(int)
    out = out.replace([np.inf, -np.inf], np.nan)
    out.index.name = "trade_date"
    return out.reset_index()
