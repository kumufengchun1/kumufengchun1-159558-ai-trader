from __future__ import annotations

import numpy as np
import pandas as pd

from .config import OVERSEAS_FACTORS


def _pct(series: pd.Series, n: int = 1) -> pd.Series:
    return series.pct_change(n, fill_method=None)


def build_dataset(prices: pd.DataFrame) -> pd.DataFrame:
    df = prices.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["date"]).sort_values("date").drop_duplicates("date")
    if "159558" not in df.columns:
        raise ValueError("159558 data is missing")

    # Use target trading dates as the prediction calendar. Overseas closes are aligned
    # to the latest available date strictly before each target date.
    target = df[["date", "159558"]].dropna().copy()
    base = target[["date", "159558"]].sort_values("date")

    aligned = base.copy()
    for factor in OVERSEAS_FACTORS:
        if factor not in df.columns:
            continue
        right = df[["date", factor]].dropna().sort_values("date")
        right["factor_date"] = right["date"]
        aligned = pd.merge_asof(
            aligned.sort_values("date"),
            right.rename(columns={"date": "source_date"}).sort_values("source_date"),
            left_on="date",
            right_on="source_date",
            direction="backward",
            allow_exact_matches=False,
        ).drop(columns=["source_date"])
        aligned = aligned.rename(columns={"factor_date": f"{factor}_date"})

    out = aligned.copy()
    for factor in OVERSEAS_FACTORS:
        if factor in out.columns:
            out[f"{factor}_r1"] = _pct(out[factor], 1)
            out[f"{factor}_r3"] = _pct(out[factor], 3)

    semis = [c for c in ["SOX_r1", "NVDA_r1", "TSM_r1", "ASML_r1"] if c in out.columns]
    if semis:
        out["breadth_up"] = (out[semis] > 0).mean(axis=1)
        out["semiconductor_mean"] = out[semis].mean(axis=1)
    else:
        out["breadth_up"] = np.nan
        out["semiconductor_mean"] = np.nan

    risk_terms = []
    for col, sign in [("SOX_r1", 1), ("NASDAQ_r1", 1), ("VIX_r1", -1), ("USDCNH_r1", -1), ("SOXS_r1", -1)]:
        if col in out.columns:
            risk_terms.append(sign * out[col])
    out["risk_on"] = pd.concat(risk_terms, axis=1).mean(axis=1) if risk_terms else np.nan

    cn_ret = _pct(out["159558"], 1)
    out["cn_lag1"] = cn_ret.shift(1)
    out["cn_lag3"] = _pct(out["159558"], 3).shift(1)
    out["cn_ma5_gap"] = (out["159558"] / out["159558"].rolling(5).mean() - 1).shift(1)
    out["cn_ma20_gap"] = (out["159558"] / out["159558"].rolling(20).mean() - 1).shift(1)
    out["cn_vol20"] = cn_ret.rolling(20).std().shift(1)
    out["target_ret"] = cn_ret
    out["target_up"] = np.where(out["target_ret"].notna(), (out["target_ret"] > 0).astype(int), np.nan)
    return out.replace([np.inf, -np.inf], np.nan)
