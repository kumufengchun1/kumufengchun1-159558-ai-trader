from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MODEL_DIR = ROOT / "models"


@dataclass(frozen=True)
class AssetSpec:
    name: str
    aliases: tuple[str, ...]
    group: str
    invert: bool = False
    required: bool = False


ASSETS = (
    AssetSpec("159558", ("159558.SZ",), "target", required=True),
    AssetSpec("SOX", ("^SOX", "SOXX"), "semiconductor", required=True),
    AssetSpec("NVDA", ("NVDA",), "semiconductor", required=True),
    AssetSpec("TSM", ("TSM",), "semiconductor"),
    AssetSpec("ASML", ("ASML",), "semiconductor"),
    AssetSpec("SOXS", ("SOXS",), "semiconductor", invert=True),
    AssetSpec("VIX", ("^VIX",), "risk", invert=True),
    AssetSpec("NASDAQ", ("^IXIC", "QQQ"), "market"),
    AssetSpec("USDCNH", ("CNH=X",), "fx", invert=True),
    # Yahoo aliases can change. The updater tries each alias and records which one worked.
    AssetSpec("A50", ("XIN9.F", "CN1!", "CN=F"), "china"),
)

OVERSEAS_FACTORS = [a.name for a in ASSETS if a.group != "target"]

RAW_FEATURES = [
    "SOX_r1", "SOX_r3", "NVDA_r1", "NVDA_r3", "TSM_r1", "ASML_r1",
    "SOXS_r1", "VIX_r1", "NASDAQ_r1", "USDCNH_r1", "A50_r1",
    "breadth_up", "semiconductor_mean", "risk_on",
    "cn_lag1", "cn_lag3", "cn_ma5_gap", "cn_ma20_gap", "cn_vol20",
]

MIN_HISTORY = 120
MIN_TRAIN = 100
TEST_FRACTION = 0.25
RANDOM_STATE = 42
