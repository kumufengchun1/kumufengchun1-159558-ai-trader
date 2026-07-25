from app.services.scoring import make_signal

def test_position_is_capped():
    score, signal, pos = make_signal(0.9, 100)
    assert score == 90
    assert signal == "强偏多"
    assert 0 <= pos <= 0.35
