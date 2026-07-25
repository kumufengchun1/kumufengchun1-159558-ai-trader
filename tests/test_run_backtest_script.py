from scripts.run_backtest import TARGET_SYMBOL


def test_backtest_uses_canonical_target_symbol():
    assert TARGET_SYMBOL == "159558"
