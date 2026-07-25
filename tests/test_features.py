import pandas as pd
from src.features import build_dataset


def test_build_dataset_has_target():
    dates = pd.date_range("2025-01-01", periods=50, freq="B")
    df = pd.DataFrame({
        "date": dates,
        "159558": range(100, 150),
        "SOX": range(200, 250),
        "NVDA": range(300, 350),
        "VIX": range(50, 100),
    })
    out = build_dataset(df)
    assert "target_ret" in out.columns
    assert "SOX_r1" in out.columns
