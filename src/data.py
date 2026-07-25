from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yfinance as yf

from .config import ASSETS, DATA_DIR, AssetSpec


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def _download_yahoo(symbol: str, start: str, end: str) -> pd.DataFrame:
    df = yf.download(
        symbol,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        threads=False,
        timeout=20,
    )
    if df.empty:
        return pd.DataFrame()
    df = _flatten_columns(df).reset_index()
    date_col = "Date" if "Date" in df.columns else "Datetime"
    df = df.rename(columns={date_col: "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    keep = [c for c in ["date", "Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    out = df[keep].dropna(subset=["date", "Close"]).copy()
    out.columns = [c.lower() for c in out.columns]
    return out.drop_duplicates("date").sort_values("date")


def _try_asset(spec: AssetSpec, start: str, end: str) -> tuple[pd.DataFrame, str | None, list[str]]:
    errors: list[str] = []
    for alias in spec.aliases:
        try:
            data = _download_yahoo(alias, start, end)
            if not data.empty:
                return data, alias, errors
            errors.append(f"{alias}: empty")
        except Exception as exc:  # provider failures should not kill all updates
            errors.append(f"{alias}: {type(exc).__name__}")
    return pd.DataFrame(), None, errors


def _load_manual_target_seed() -> pd.DataFrame:
    seed = DATA_DIR / "v1_model_daily.csv"
    if not seed.exists():
        return pd.DataFrame()
    df = pd.read_csv(seed)
    needed = {"date", "open_cn", "high_cn", "low_cn", "close_cn"}
    if not needed.issubset(df.columns):
        return pd.DataFrame()
    out = df[["date", "open_cn", "high_cn", "low_cn", "close_cn"]].copy()
    out.columns = ["date", "open", "high", "low", "close"]
    out["volume"] = np.nan
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    return out.dropna(subset=["date", "close"]).drop_duplicates("date").sort_values("date")


def _merge_prefer_new(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if old.empty:
        return new.copy()
    if new.empty:
        return old.copy()
    both = pd.concat([old, new], ignore_index=True)
    return both.sort_values("date").drop_duplicates("date", keep="last")


def update_market_data(years: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    end = dt.date.today() + dt.timedelta(days=2)
    start = end - dt.timedelta(days=366 * years)
    status_rows: list[dict] = []
    close_frames: list[pd.DataFrame] = []

    for spec in ASSETS:
        data, used_alias, errors = _try_asset(spec, str(start), str(end))
        raw_path = DATA_DIR / f"raw_{spec.name}.csv"
        old = pd.read_csv(raw_path, parse_dates=["date"]) if raw_path.exists() else pd.DataFrame()

        if spec.name == "159558":
            old = _merge_prefer_new(_load_manual_target_seed(), old)
        merged = _merge_prefer_new(old, data)

        if not merged.empty:
            merged.to_csv(raw_path, index=False)
            close_frames.append(merged[["date", "close"]].rename(columns={"close": spec.name}))
            latest = pd.to_datetime(merged["date"]).max().date()
            state = "ok" if not data.empty else "cache"
            message = f"{state}: {latest}"
        else:
            latest = None
            state = "missing"
            message = "missing"

        status_rows.append({
            "asset": spec.name,
            "state": state,
            "alias": used_alias or "",
            "latest": str(latest or ""),
            "required": spec.required,
            "message": message,
            "errors": " | ".join(errors[-3:]),
        })

    if not close_frames:
        raise RuntimeError("No market data is available. Run the updater again or import target data.")

    merged = close_frames[0]
    for frame in close_frames[1:]:
        merged = merged.merge(frame, on="date", how="outer")
    merged = merged.sort_values("date").drop_duplicates("date")
    merged.to_parquet(DATA_DIR / "market_prices.parquet", index=False)

    status = pd.DataFrame(status_rows)
    status.to_csv(DATA_DIR / "data_status.csv", index=False)
    meta = {
        "updated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "rows": int(len(merged)),
        "columns": list(merged.columns),
    }
    (DATA_DIR / "update_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged, status


def load_prices(auto_update: bool = False) -> pd.DataFrame:
    path = DATA_DIR / "market_prices.parquet"
    if path.exists():
        return pd.read_parquet(path)
    if auto_update:
        return update_market_data()[0]

    seed = _load_manual_target_seed()
    if seed.empty:
        raise FileNotFoundError("market_prices.parquet does not exist and no seed data is available")
    return seed[["date", "close"]].rename(columns={"close": "159558"})


def load_status() -> pd.DataFrame:
    path = DATA_DIR / "data_status.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def save_uploaded_target(file) -> int:
    """Import a user CSV containing date/open/high/low/close/volume columns."""
    df = pd.read_csv(file)
    aliases = {
        "日期": "date", "时间": "date", "收盘": "close", "收盘价": "close",
        "开盘": "open", "最高": "high", "最低": "low", "成交量": "volume",
    }
    df = df.rename(columns={c: aliases.get(c, c.lower()) for c in df.columns})
    if not {"date", "close"}.issubset(df.columns):
        raise ValueError("CSV must include date and close columns")
    for col in ["open", "high", "low", "volume"]:
        if col not in df.columns:
            df[col] = np.nan
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["date", "close"])[["date", "open", "high", "low", "close", "volume"]]
    path = DATA_DIR / "raw_159558.csv"
    old = pd.read_csv(path, parse_dates=["date"]) if path.exists() else pd.DataFrame()
    merged = _merge_prefer_new(old, df)
    merged.to_csv(path, index=False)
    return len(df)
