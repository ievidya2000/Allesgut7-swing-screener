import pytest
import numpy as np
import pandas as pd


def test_calculate_tp_sl_buy():
    from risk import calculate_tp_sl
    sl, tp1, tp2, tp3, profit_pct, risk_pct = calculate_tp_sl(1000, 50, "BUY")
    assert sl < 1000
    assert tp1 > 1000
    assert tp2 >= tp1
    assert tp3 >= tp2
    assert profit_pct > 0
    assert risk_pct > 0


def test_calculate_tp_sl_custom_params():
    from risk import calculate_tp_sl
    sl, tp1, tp2, tp3, _, _ = calculate_tp_sl(1000, 50, "BUY", {"sl_multiplier": 2.0, "rr1": 3.0})
    assert sl == pytest.approx(900, abs=1)
    assert tp1 > 1000


def test_calculate_tp_sl_invalid():
    from risk import calculate_tp_sl
    result = calculate_tp_sl(1000, 50, "HOLD")
    assert result == (None, None, None, None, None, None)


def test_check_tp_sl_hit_sl():
    from performance.backtest import check_tp_sl_hit
    df = pd.DataFrame({
        "High": [1050, 1060, 1040],
        "Low": [980, 990, 970],
        "Close": [1030, 1040, 1020],
    }, index=pd.date_range("2025-01-01", periods=3))
    result = check_tp_sl_hit(df, 1000, tp1=1050, tp2=1100, tp3=1150, sl=995)
    assert result["hit_sl"] is True
    assert result["exit_reason"] == "SL"


def test_check_tp_sl_hit_timeout():
    from performance.backtest import check_tp_sl_hit
    df = pd.DataFrame({
        "High": [1010, 1015, 1020],
        "Low": [990, 985, 995],
        "Close": [1005, 1010, 1015],
    }, index=pd.date_range("2025-01-01", periods=3))
    result = check_tp_sl_hit(df, 1000, tp1=1100, tp2=1200, tp3=1300, sl=950)
    assert result["hit_tp1"] is False
    assert result["exit_reason"] == "TIMEOUT"


def test_simulate_tp_sl_probability_insufficient_data():
    from risk import simulate_tp_sl_probability
    df = pd.DataFrame({"Close": np.random.randn(10).cumsum() + 1000})
    result = simulate_tp_sl_probability(df, 1000, 950, 1050, 1100, 1150)
    assert result is None


def test_signal_map_coverage():
    from config import SIGNAL_MAP, SETUP_ORDER
    for setup in SETUP_ORDER:
        assert setup in SIGNAL_MAP
    assert SIGNAL_MAP["BREAKOUT"] == "STRONG BUY"
    assert SIGNAL_MAP["TIGHT_BASE_BREAKOUT"] == "STRONG BUY"


def test_thread_local_db():
    from performance.journal import _get_conn
    conn = _get_conn()
    assert conn is not None
    conn2 = _get_conn()
    assert conn is conn2
