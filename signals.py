import numpy as np
import pandas as pd

from config import ADX_THRESHOLD, FRESH_SIGNAL_BARS
from indicators import (
    get_ichimoku, get_supertrend, get_adx, rma
)


def determine_market_regime(jkse_df):
    h = jkse_df['High']
    l = jkse_df['Low']
    c = jkse_df['Close']

    ichi = get_ichimoku(h, l, c)
    _, st_dir = get_supertrend(h, l, c, 10, 3.0)
    adx, _, _ = get_adx(h, l, c, 14)

    last = {
        "above_cloud": ichi['price_above_cloud'].iloc[-1],
        "below_cloud": ichi['price_below_cloud'].iloc[-1],
        "st_bullish": st_dir.iloc[-1] > 0,
        "adx": adx.iloc[-1],
    }

    if last["above_cloud"] and last["st_bullish"] and last["adx"] > ADX_THRESHOLD:
        return "BULL"
    elif last["below_cloud"] and not last["st_bullish"] and last["adx"] > ADX_THRESHOLD:
        return "BEAR"
    else:
        return "SIDEWAYS"


def determine_stock_regime(full_df):
    last = full_df.iloc[-1]

    above_cloud = last.get('price_above_cloud', False)
    below_cloud = last.get('price_below_cloud', False)
    st_bullish = last.get('supertrend_bullish', False)

    if above_cloud and st_bullish:
        return "BULL"
    elif below_cloud and not st_bullish:
        return "BEAR"
    else:
        return "SIDEWAYS"


def detect_pre_breakout(full_df, adx_threshold=None):
    adx_threshold = adx_threshold or ADX_THRESHOLD
    last = full_df.iloc[-1]
    conditions = [
        last.get('vol_contraction', False),
        last.get('near_resistance', False),
        last.get('volume_pre_breakout', False),
        last.get('supertrend_bullish', False),
        last.get('adx', 0) > adx_threshold,
        last.get('rsi', 50) > 50,  # momentum naik
    ]
    score = sum(conditions)
    valid = score >= 5
    return valid, score


def detect_accumulation(full_df):
    last = full_df.iloc[-1]
    latest = full_df.tail(10)

    price_range_tight = last.get('donchian_width_pct', 1) < 0.08
    adx_low = last.get('adx', 100) < 22
    st_bullish = last.get('supertrend_bullish', False)
    price_in_cloud = last.get('price_in_cloud', False)

    stock_regime = determine_stock_regime(full_df)
    if stock_regime == "BEAR":
        return False, 0

    vol_ma_exists = 'vol_ma' in latest.columns and latest['vol_ma'].notna().any()
    if vol_ma_exists:
        vol_up_days = (latest['Volume'] > latest['vol_ma']).sum()
        vol_rising = vol_up_days >= 4
    else:
        vol_rising = False

    # Volume Pressure: check if money is flowing in during consolidation
    ad_rising = last.get('ad_rising', False)
    delta_positive = last.get('delta_positive', False)
    obv_rising = last.get('obv_rising', False)

    # Strong accumulation: volume rising + money flowing in
    accumulation_pressure = vol_rising and (ad_rising or delta_positive or obv_rising)

    # Momentum oversold confirmation
    rsi_oversold = last.get('rsi_oversold', False)
    stoch_oversold = last.get('stoch_oversold', False)
    momentum_oversold = rsi_oversold or stoch_oversold

    conditions = [
        price_range_tight,
        adx_low,
        st_bullish,
        price_in_cloud,
        accumulation_pressure,
        momentum_oversold,
    ]
    score = sum(conditions)
    valid = score >= 3
    return valid, score


def detect_early_reversal(full_df):
    last = full_df.iloc[-1]
    tail = full_df.tail(20)

    st_bullish = last.get('supertrend_bullish', False)
    st_prev = tail['supertrend_dir'].iloc[-2] if len(tail) >= 2 else -1

    fresh_st_flip = st_bullish and st_prev <= 0

    below_cloud = last.get('price_below_cloud', False)
    vol_spike = last.get('volume_expanding', False)

    # Check higher low
    lows = tail['Low']
    recent_low = lows.tail(5).min()
    prev_low = lows.tail(10).head(5).min()
    higher_low = recent_low > prev_low if not (pd.isna(recent_low) or pd.isna(prev_low)) else False

    adx_low = last.get('adx', 100) < 20

    # Leading: RSI/MACD divergence (alternative to SuperTrend flip)
    rsi_bull_div = last.get('rsi_bullish_div', False)
    macd_bull_div = last.get('macd_bullish_div', False)
    rsi_oversold = last.get('rsi_oversold', False)
    stoch_bull_cross = last.get('stoch_bullish_cross', False)
    macd_bull_cross = last.get('macd_bullish_cross', False)

    # Divergence signal (can trigger without SuperTrend flip)
    divergence_signal = (rsi_bull_div or macd_bull_div) and (rsi_oversold or stoch_bull_cross or macd_bull_cross)

    # Original: SuperTrend flip required
    # New: OR divergence signal detected
    reversal_signal = fresh_st_flip or divergence_signal

    conditions = [
        reversal_signal,
        vol_spike,
        higher_low,
        below_cloud,
        adx_low,
    ]
    score = sum(conditions)
    valid = reversal_signal and (score >= 2)
    return valid, score


def detect_fresh_breakout(full_df, adx_threshold=None):
    adx_threshold = adx_threshold or ADX_THRESHOLD
    fresh_bars = FRESH_SIGNAL_BARS
    tail = full_df.tail(fresh_bars + 2)
    fresh_signals = tail['fresh_breakout']
    has_fresh = fresh_signals.any()

    if not has_fresh:
        return False, 0

    last = full_df.iloc[-1]
    conditions = [
        has_fresh,
        last.get('volume_expanding', False),
        last.get('supertrend_bullish', False),
        last.get('adx', 0) > adx_threshold,
        last.get('macd_bullish_cross', False) or last.get('macd_histogram', 0) > 0,  # MACD confirmation
    ]
    score = sum(conditions)
    valid = conditions[0] and score >= 3
    return valid, score


def detect_vcp(full_df):
    last = full_df.iloc[-1]
    tail = full_df.tail(40)

    vol_contracting = last.get('vol_contraction', False)

    dw_pct = last.get('donchian_width_pct', 1)
    dw_min = tail['donchian_width_pct'].min() if len(tail) > 0 else 1
    dw_near_min = dw_pct < dw_min * 1.3 if not pd.isna(dw_min) else False

    contractions = tail['vol_contraction'].sum() if 'vol_contraction' in tail else 0
    multiple_contractions = contractions >= 3

    lows = tail['Low']
    if len(lows) >= 20:
        recent_low = lows.tail(10).min()
        prev_low = lows.head(10).min()
        pullback_shallower = recent_low > prev_low if not (pd.isna(recent_low) or pd.isna(prev_low)) else False
    else:
        pullback_shallower = False

    ma20 = last.get('ma20', None)
    above_ma20 = ma20 is not None and not pd.isna(ma20) and last['Close'] > ma20

    adx_low = last.get('adx', 100) < 20

    # Leading: momentum oversold before expansion
    stoch_oversold = last.get('stoch_oversold', False)
    rsi_low = last.get('rsi', 50) < 45
    momentum_ready = stoch_oversold or rsi_low

    conditions = [vol_contracting, dw_near_min, multiple_contractions,
                  pullback_shallower, above_ma20, adx_low, momentum_ready]
    score = sum(conditions)
    valid = score >= 3
    return valid, score


def detect_tight_base_breakout(full_df):
    last = full_df.iloc[-1]
    tail = full_df.tail(15)

    range_15 = (tail['High'].max() - tail['Low'].min()) / last['Close'] if last['Close'] > 0 else 1
    tight_range = range_15 < 0.05

    dw = last.get('donchian_width_pct', 1)
    dw_series = full_df['donchian_width_pct'].tail(50)
    dw_tight = False
    if len(dw_series) > 0 and not pd.isna(dw):
        dw_pctile = (dw_series < dw).sum() / len(dw_series)
        dw_tight = dw_pctile < 0.2

    consecutive_inside = last.get('consecutive_inside', 0)
    has_inside_bars = consecutive_inside >= 3

    adx_low = last.get('adx', 100) < 18

    vol_dry = not last.get('volume_expanding', True)

    st_bull = last.get('supertrend_bullish', False)

    # Leading: RSI netral = siap breakout
    rsi = last.get('rsi', 50)
    rsi_neutral = 40 <= rsi <= 60

    conditions = [tight_range, dw_tight, has_inside_bars, adx_low,
                  vol_dry, st_bull, rsi_neutral]
    score = sum(conditions)
    valid = score >= 4
    return valid, score


def detect_base_on_base(full_df):
    last = full_df.iloc[-1]

    if len(full_df) < 50:
        return False, 0

    current_tight = last.get('donchian_width_pct', 1) < 0.08

    prev_widths = full_df['donchian_width_pct'].iloc[-50:-15]
    prev_tight_zone = (prev_widths < 0.08).sum() >= 5

    prev_high = full_df['High'].iloc[-50:-15].max()
    broke_first_base = last['Close'] > prev_high * 0.98

    base2_low = full_df['Low'].tail(15).min()
    base1_low = full_df['Low'].iloc[-50:-15].min()
    higher_base = base2_low > base1_low

    vol_contracting = not last.get('volume_expanding', True)

    st_bull = last.get('supertrend_bullish', False)

    # Leading: momentum confirmation
    rsi_healthy = last.get('rsi', 0) > 40
    macd_positive = last.get('macd_histogram', 0) > 0

    conditions = [current_tight, prev_tight_zone, broke_first_base,
                  higher_base, vol_contracting, st_bull, rsi_healthy, macd_positive]
    score = sum(conditions)
    valid = score >= 6
    return valid, score


def detect_bull_flag(full_df):
    last = full_df.iloc[-1]
    tail = full_df.tail(30)

    if len(tail) < 15:
        return False, 0

    swing_low_30 = tail['Low'].iloc[:15].min()
    recent_high_idx = tail['High'].iloc[-15:].values.argmax()
    recent_high = tail['High'].iloc[-15:].max()
    flagpole_gain = (recent_high - swing_low_30) / swing_low_30 if swing_low_30 > 0 else 0
    strong_pole = flagpole_gain > 0.15

    flag_depth = (recent_high - last['Low']) / recent_high if recent_high > 0 else 1
    shallow_flag = flag_depth < 0.12

    high_idx_in_tail = len(tail) - 15 + recent_high_idx
    flag_duration = len(tail) - 1 - high_idx_in_tail
    reasonable_duration = 5 <= flag_duration <= 15

    vol_declining = not last.get('volume_expanding', True)

    ma20 = last.get('ma20', None)
    above_ma20 = ma20 is not None and not pd.isna(ma20) and last['Close'] > ma20

    st_bull = last.get('supertrend_bullish', False)

    close_near_top = (recent_high - last['Close']) / recent_high < 0.03 if recent_high > 0 else False

    # Leading: momentum masih hidup di flag
    rsi_healthy = last.get('rsi', 0) > 40

    conditions = [strong_pole, shallow_flag, reasonable_duration,
                  vol_declining, above_ma20, st_bull, close_near_top, rsi_healthy]
    score = sum(conditions)
    valid = score >= 4
    return valid, score


def detect_pullback_ma20(full_df):
    last = full_df.iloc[-1]
    tail = full_df.tail(10)

    ma20 = last.get('ma20', None)
    ma50 = last.get('ma50', None)
    if ma20 is None or pd.isna(ma20) or ma50 is None or pd.isna(ma50):
        return False, 0

    ma20_rising = last.get('ma20_slope', 0) > 0

    ma_order = ma20 > ma50

    dist = (last['Close'] - ma20) / ma20
    near_ma20 = -0.01 <= dist <= 0.005

    low = last['Low']
    touched_ma20 = low <= ma20 * 1.005
    bounce = last['Close'] >= ma20 * 0.995

    high_20d = tail['High'].max() if len(tail) >= 10 else last['Close']
    had_prior_strength = high_20d > ma20 * 1.03

    # Leading: oversold di MA20 = entry lebih awal
    rsi_oversold = last.get('rsi_oversold', False)
    stoch_bull_cross = last.get('stoch_bullish_cross', False)
    momentum_bounce = rsi_oversold or stoch_bull_cross

    conditions = [ma20_rising, ma_order, near_ma20, touched_ma20,
                  bounce, had_prior_strength, momentum_bounce]
    score = sum(conditions)
    valid = score >= 3
    return valid, score


def classify_setup_state(full_df, stock_regime, custom_params=None):
    p = custom_params or {}
    adx_thresh = p.get("adx_threshold", ADX_THRESHOLD)

    # 1. PRE_BREAKOUT (highest priority)
    pb_valid, pb_score = detect_pre_breakout(full_df, adx_thresh)
    if pb_valid and stock_regime != "BEAR":
        return "PRE_BREAKOUT", True

    # 2. VCP (Volatility Contraction Pattern)
    vcp_valid, vcp_score = detect_vcp(full_df)
    if vcp_valid:  # No regime filter - VCP can occur in SIDEWAYS
        return "VCP", True

    # 3. TIGHT_BASE_BREAKOUT
    tb_valid, tb_score = detect_tight_base_breakout(full_df)
    if tb_valid and stock_regime != "BEAR":
        return "TIGHT_BASE_BREAKOUT", True

    # 4. BASE_ON_BASE
    bob_valid, bob_score = detect_base_on_base(full_df)
    if bob_valid and stock_regime != "BEAR":  # Changed from BULL to not BEAR
        return "BASE_ON_BASE", True

    # 5. BULL_FLAG
    bf_valid, bf_score = detect_bull_flag(full_df)
    if bf_valid:  # No regime filter - BULL_FLAG can occur in SIDEWAYS
        return "BULL_FLAG", True

    # 6. Fresh BREAKOUT
    fb_valid, fb_score = detect_fresh_breakout(full_df, adx_thresh)
    if fb_valid and stock_regime != "BEAR":  # Changed from BULL to not BEAR
        return "BREAKOUT", True

    # 7. PULLBACK_MA20
    pb20_valid, pb20_score = detect_pullback_ma20(full_df)
    if pb20_valid and stock_regime != "BEAR":  # Changed from BULL to not BEAR
        return "PULLBACK_MA20", True

    # 8. ACCUMULATION
    acc_valid, acc_score = detect_accumulation(full_df)
    if acc_valid and stock_regime != "BEAR":
        return "ACCUMULATION", True

    # 9. EARLY_REVERSAL (lowest priority, works in BEAR)
    er_valid, er_score = detect_early_reversal(full_df)
    if er_valid and er_score >= 3:
        return "EARLY_REVERSAL", True

    return "NONE", False
