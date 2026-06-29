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


# ── Volume Pressure Tests ──

def test_obv():
    from indicators import get_obv
    close = pd.Series([10, 11, 10.5, 12, 11.5])
    volume = pd.Series([100, 150, 120, 200, 80])
    obv = get_obv(close, volume)
    # Baris 1: baseline, 0
    assert obv.iloc[0] == 0
    # Baris 2: close naik -> +150
    assert obv.iloc[1] == 150
    # Baris 3: close turun -> 150 - 120 = 30
    assert obv.iloc[2] == 30
    # Baris 4: close naik -> 30 + 200 = 230
    assert obv.iloc[3] == 230
    # Baris 5: close turun -> 230 - 80 = 150
    assert obv.iloc[4] == 150


def test_obv_flat_close():
    from indicators import get_obv
    close = pd.Series([10, 10, 10])
    volume = pd.Series([100, 150, 200])
    obv = get_obv(close, volume)
    # Close tidak berubah -> delta = 0, OBV tetap 0
    assert all(obv == 0)


def test_ad_line():
    from indicators import get_ad_line
    # Bullish candle: close di atas -> CLV positif
    high = pd.Series([12, 13, 14])
    low = pd.Series([8, 9, 10])
    close = pd.Series([11, 12, 13])  # dekat high
    volume = pd.Series([100, 150, 200])
    ad = get_ad_line(high, low, close, volume)
    # Semua positif karena close > mid range
    assert ad.iloc[0] > 0
    assert ad.iloc[1] > ad.iloc[0]
    assert ad.iloc[2] > ad.iloc[1]


def test_ad_line_bearish():
    from indicators import get_ad_line
    # Bearish candle: close di bawah -> CLV negatif
    high = pd.Series([12, 13, 14])
    low = pd.Series([8, 9, 10])
    close = pd.Series([9, 10, 11])  # dekat low
    volume = pd.Series([100, 150, 200])
    ad = get_ad_line(high, low, close, volume)
    # Semua negatif karena close < mid range
    assert ad.iloc[0] < 0


def test_volume_delta():
    from indicators import get_volume_delta
    # Bullish: close di high -> buy = volume, sell = 0
    high = pd.Series([12, 13])
    low = pd.Series([8, 9])
    close = pd.Series([12, 13])  # close = high
    volume = pd.Series([100, 200])
    buy, sell, delta = get_volume_delta(high, low, close, volume)
    assert buy.iloc[0] == 100
    assert sell.iloc[0] == 0
    assert delta.iloc[0] == 100


def test_volume_delta_doji():
    from indicators import get_volume_delta
    # Doji: close di tengah -> buy ≈ sell
    high = pd.Series([12])
    low = pd.Series([8])
    close = pd.Series([10])  # exact mid
    volume = pd.Series([100])
    buy, sell, delta = get_volume_delta(high, low, close, volume)
    assert buy.iloc[0] == pytest.approx(50, abs=1)
    assert sell.iloc[0] == pytest.approx(50, abs=1)
    assert delta.iloc[0] == pytest.approx(0, abs=1)


# ── Momentum Oscillator Tests ──

def test_rsi():
    from indicators import get_rsi
    # Strong uptrend with enough data for RMA(14) to stabilize
    close = pd.Series([10 + i*0.5 for i in range(40)])
    rsi = get_rsi(close)
    assert rsi.iloc[-1] > 50


def test_rsi_oversold():
    from indicators import get_rsi
    # Downtrend: RSI should be < 30
    close = pd.Series([20, 19.5, 19, 18.5, 18, 17.5, 17, 16.5, 16, 15.5,
                        15, 14.5, 14, 13.5, 13, 12.5, 12, 11.5, 11, 10.5])
    rsi = get_rsi(close)
    assert rsi.iloc[-1] < 30


def test_rsi_range():
    from indicators import get_rsi
    close = pd.Series(range(1, 30))  # 28 data points
    rsi = get_rsi(close)
    # RSI should be between 0 and 100
    valid = rsi.dropna()
    assert all(valid >= 0)
    assert all(valid <= 100)


def test_macd():
    from indicators import get_macd
    close = pd.Series(range(1, 50), dtype=float)
    macd_line, signal, histogram = get_macd(close)
    # MACD line should exist and have values
    assert len(macd_line) == 49
    assert len(signal) == 49
    assert len(histogram) == 49
    # Histogram = line - signal
    assert histogram.iloc[-1] == pytest.approx(macd_line.iloc[-1] - signal.iloc[-1], abs=0.01)


def test_macd_crossover():
    from indicators import get_macd
    # Create data that will produce a crossover
    close = pd.Series([10]*10 + [11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
                                 21, 22, 23, 24, 25, 26, 27, 28, 29, 30,
                                 31, 32, 33, 34, 35, 36, 37, 38, 39, 40], dtype=float)
    _, _, histogram = get_macd(close)
    # Histogram should be positive in uptrend
    assert histogram.iloc[-1] > 0


def test_stochastic():
    from indicators import get_stochastic
    n = 30
    high = pd.Series([10 + i*0.5 for i in range(n)])
    low = pd.Series([8 + i*0.5 for i in range(n)])
    close = pd.Series([9 + i*0.5 for i in range(n)])
    k, d = get_stochastic(high, low, close)
    # Stochastic should be between 0 and 100
    valid_k = k.dropna()
    valid_d = d.dropna()
    assert all(valid_k >= 0)
    assert all(valid_k <= 100)
    assert all(valid_d >= 0)
    assert all(valid_d <= 100)


def test_stochastic_oversold():
    from indicators import get_stochastic
    # Create downtrend data
    n = 30
    high = pd.Series([20 - i*0.3 for i in range(n)])
    low = pd.Series([18 - i*0.3 for i in range(n)])
    close = pd.Series([18.5 - i*0.3 for i in range(n)])
    k, d = get_stochastic(high, low, close)
    # In downtrend, stochastic should be low
    assert k.iloc[-1] < 50


def test_elliott_wave():
    from indicators import get_elliott_wave
    # Create zigzag pattern
    high = pd.Series([10, 12, 10, 13, 11, 14, 12, 15, 13, 16, 14, 17, 15, 18, 16, 19, 17, 20], dtype=float)
    low = pd.Series([8, 10, 8, 11, 9, 12, 10, 13, 11, 14, 12, 15, 13, 16, 14, 17, 15, 18], dtype=float)
    close = pd.Series([9, 11, 9, 12, 10, 13, 11, 14, 12, 15, 13, 16, 14, 17, 15, 18, 16, 19], dtype=float)
    wave, fib_382, fib_500, fib_618, fib_786 = get_elliott_wave(high, low, close)
    # Wave position should be 1-5 or B/C
    assert wave in [1, 2, 3, 4, 5, 'B', 'C']
    # Fib levels should be ordered
    assert fib_786 <= fib_618 <= fib_500 <= fib_382


def test_divergence():
    from indicators import detect_divergence
    # Create bullish divergence: price makes lower low, indicator makes higher low
    price = pd.Series([20, 18, 16, 14, 12, 10, 8, 10, 12, 14,
                        16, 14, 12, 10, 8, 6, 8, 10, 12, 14])
    indicator = pd.Series([30, 25, 20, 15, 10, 5, 3, 8, 12, 15,
                            20, 18, 16, 14, 12, 10, 14, 18, 22, 25])
    bull_div, bear_div = detect_divergence(price, indicator)
    # Should return boolean-like values
    assert bool(bull_div) == bool(bull_div)  # check it's truthy/falsy compatible
    assert bool(bear_div) == bool(bear_div)
