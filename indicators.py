import numpy as np
import pandas as pd

from screener_v2.config import (
    ICHIMOKU_TENKAN, ICHIMOKU_KIJUN, ICHIMOKU_SENKOU_B,
    DONCHIAN_PERIOD, ATR_LENGTH, ATR_MULTIPLIER,
    ADX_LENGTH, AVWAP_LOOKBACK, VOLUME_MA_PERIOD,
    ATR_PERIOD_RM, ATR_CONTRACTION_SHORT, ATR_CONTRACTION_LONG,
    VOL_MA_SHORT, VOLUME_RISING_LOOKBACK, FRESH_SIGNAL_BARS,
    RESISTANCE_ATR_MULTIPLIER, VOL_CONTRACTION_THRESHOLD
)


def rma(series, length):
    """Vectorized RMA using pandas ewm (exponential weighted moving average)."""
    # RMA is equivalent to EMA with alpha = 1/length
    # pandas ewm with adjust=False matches the RMA formula exactly
    return series.ewm(alpha=1.0/length, adjust=False, min_periods=length).mean()


def get_atr(high, low, close, period):
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return rma(tr, period)


def get_adx(high, low, close, period):
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = rma(tr, period)
    plus_dm = rma(pd.Series(plus_dm, index=high.index), period)
    minus_dm = rma(pd.Series(minus_dm, index=high.index), period)

    plus_di = 100 * (plus_dm / atr)
    minus_di = 100 * (minus_dm / atr)

    di_sum = plus_di + minus_di
    dx = np.where(di_sum > 0, 100 * (abs(plus_di - minus_di) / di_sum), 0.0)
    dx = pd.Series(dx, index=high.index)
    adx = rma(dx, period)

    return adx, plus_di, minus_di


def get_supertrend(high, low, close, period, multiplier):
    atr = get_atr(high, low, close, period)
    hl2 = (high + low) / 2

    upper_band = hl2 + multiplier * atr
    lower_band = hl2 - multiplier * atr

    n = len(close)
    supertrend = np.full(n, np.nan)
    direction = np.ones(n)

    first_valid = atr.first_valid_index()
    if first_valid is None:
        return pd.Series(supertrend, index=close.index), pd.Series(direction, index=close.index)

    idx = close.index.get_loc(first_valid)
    supertrend[idx] = lower_band.iloc[idx]
    direction[idx] = 1

    # Convert to numpy arrays for faster access
    close_arr = close.values
    upper_arr = upper_band.values
    lower_arr = lower_band.values

    for i in range(idx + 1, n):
        prev_st = supertrend[i - 1]
        prev_dir = direction[i - 1]

        if close_arr[i] > prev_st:
            direction[i] = 1
        elif close_arr[i] < prev_st:
            direction[i] = -1
        else:
            direction[i] = prev_dir

        if direction[i] == 1:
            supertrend[i] = max(lower_arr[i], prev_st)
        else:
            supertrend[i] = min(upper_arr[i], prev_st)

    return (pd.Series(supertrend, index=close.index),
            pd.Series(direction, index=close.index))


def get_ichimoku(high, low, close, tenkan=None, kijun=None, senkou_b=None):
    tenkan = tenkan if tenkan is not None else ICHIMOKU_TENKAN
    kijun = kijun if kijun is not None else ICHIMOKU_KIJUN
    senkou_b = senkou_b if senkou_b is not None else ICHIMOKU_SENKOU_B

    high_9 = high.rolling(window=tenkan).max()
    low_9 = low.rolling(window=tenkan).min()
    tenkan_line = (high_9 + low_9) / 2

    high_26 = high.rolling(window=kijun).max()
    low_26 = low.rolling(window=kijun).min()
    kijun_line = (high_26 + low_26) / 2

    senkou_a = (tenkan_line + kijun_line) / 2
    senkou_b_line = (high.rolling(window=senkou_b).max()
                + low.rolling(window=senkou_b).min()) / 2

    cloud_top = np.maximum(senkou_a.shift(kijun), senkou_b_line.shift(kijun))
    cloud_bottom = np.minimum(senkou_a.shift(kijun), senkou_b_line.shift(kijun))

    price_above_cloud = close > cloud_top
    price_below_cloud = close < cloud_bottom
    price_in_cloud = ~(price_above_cloud | price_below_cloud)

    return pd.DataFrame({
        "tenkan": tenkan_line,
        "kijun": kijun_line,
        "senkou_a": senkou_a,
        "senkou_b": senkou_b_line,
        "cloud_top": cloud_top,
        "cloud_bottom": cloud_bottom,
        "price_above_cloud": price_above_cloud,
        "price_below_cloud": price_below_cloud,
        "price_in_cloud": price_in_cloud,
    })


def get_donchian(high, low, close, period=DONCHIAN_PERIOD):
    upper = high.rolling(window=period).max()
    lower = low.rolling(window=period).min()
    mid = (upper + lower) / 2

    breakout = (close > upper.shift(1)).fillna(False)
    breakdown = (close < lower.shift(1)).fillna(False)

    return pd.DataFrame({
        "donchian_upper": upper,
        "donchian_lower": lower,
        "donchian_mid": mid,
        "donchian_breakout": breakout,
        "donchian_breakdown": breakdown,
    })


def get_avwap(high, low, close, volume, supertrend_bullish, lookback=AVWAP_LOOKBACK):
    pivot_low = low == low.rolling(window=2 * lookback + 1, center=True).min()
    pivot_high = high == high.rolling(window=2 * lookback + 1, center=True).max()

    pivot_low_detected = pivot_low.shift(lookback)
    pivot_high_detected = pivot_high.shift(lookback)

    n = len(close)
    tp = (high + low + close) / 3
    tp_vol = (tp * volume).values

    # Vectorized anchor detection
    bull_vals = supertrend_bullish.values if hasattr(supertrend_bullish, 'values') else np.array(supertrend_bullish)
    pivot_low_vals = pivot_low_detected.values if hasattr(pivot_low_detected, 'values') else np.array(pivot_low_detected)
    pivot_high_vals = pivot_high_detected.values if hasattr(pivot_high_detected, 'values') else np.array(pivot_high_detected)

    # Determine anchor indices
    anchor_mask = (bull_vals & pivot_low_vals) | (~bull_vals & pivot_high_vals)
    anchor_indices = np.where(anchor_mask, np.maximum(0, np.arange(n) - lookback), -1)

    # Forward-fill anchor indices
    active_anchor = -1
    cum_tp_vol = 0.0
    cum_vol = 0.0
    avwap = np.full(n, np.nan)
    vol_vals = volume.values

    for i in range(n):
        if anchor_indices[i] != -1:
            active_anchor = anchor_indices[i]
            cum_tp_vol = tp_vol[active_anchor]
            cum_vol = vol_vals[active_anchor]
        elif active_anchor != -1 and i > active_anchor:
            cum_tp_vol += tp_vol[i]
            cum_vol += vol_vals[i]

        if active_anchor != -1 and i >= active_anchor and cum_vol > 0:
            avwap[i] = cum_tp_vol / cum_vol

    return pd.Series(avwap, index=close.index)


def calculate_full_indicators(df, custom_params=None):
    df = df.copy()
    h, l, c, v = df['High'], df['Low'], df['Close'], df['Volume']

    p = custom_params or {}

    st_atr_len = p.get("supertrend_atr_length", ATR_LENGTH)
    st_mult = p.get("supertrend_multiplier", ATR_MULTIPLIER)
    adx_len = p.get("adx_length", ADX_LENGTH)
    donchian_p = p.get("donchian_period", DONCHIAN_PERIOD)
    vol_ma_p = p.get("volume_ma_period", VOLUME_MA_PERIOD)
    ichi_tenkan = p.get("ichimoku_tenkan", ICHIMOKU_TENKAN)
    ichi_kijun = p.get("ichimoku_kijun", ICHIMOKU_KIJUN)
    ichi_senkou = p.get("ichimoku_senkou_b", ICHIMOKU_SENKOU_B)
    vol_thresh = p.get("vol_contraction_threshold", VOL_CONTRACTION_THRESHOLD)
    fresh_bars = p.get("fresh_signal_bars", FRESH_SIGNAL_BARS)

    # Ichimoku
    ichi = get_ichimoku(h, l, c, tenkan=ichi_tenkan, kijun=ichi_kijun, senkou_b=ichi_senkou)
    for col in ichi.columns:
        df[col] = ichi[col]

    # Donchian
    dnch = get_donchian(h, l, c, period=donchian_p)
    for col in dnch.columns:
        df[col] = dnch[col]

    # SuperTrend
    df['supertrend_line'], df['supertrend_dir'] = get_supertrend(h, l, c, st_atr_len, st_mult)
    df['supertrend_bullish'] = df['supertrend_dir'] > 0

    # AVWAP
    df['avwap'] = get_avwap(h, l, c, v, df['supertrend_bullish'])
    df['price_above_avwap'] = c > df['avwap']

    # ADX
    df['adx'], df['plus_di'], df['minus_di'] = get_adx(h, l, c, adx_len)
    df['adx_rising'] = df['adx'] > df['adx'].shift(1)

    # Volume
    df['vol_ma'] = v.rolling(window=vol_ma_p).mean()
    df['volume_expanding'] = v > df['vol_ma']
    df['vol_ma_ratio'] = v / df['vol_ma'].replace(0, 1)

    # ATR Risk Management
    df['atr_rm'] = get_atr(h, l, c, ATR_PERIOD_RM)
    df['atr_10'] = get_atr(h, l, c, ATR_CONTRACTION_SHORT)
    df['atr_50'] = get_atr(h, l, c, ATR_CONTRACTION_LONG)

    # Volume MA short
    df['vol_ma_5'] = v.rolling(window=VOL_MA_SHORT).mean()

    # Volatility contraction
    df['vol_contraction'] = (df['atr_10'] / df['atr_50']) < vol_thresh

    # Near resistance
    df['near_resistance'] = ((df['donchian_upper'] - c) <= df['atr_10'] * RESISTANCE_ATR_MULTIPLIER) & (c <= df['donchian_upper'])

    # Volume rising
    df['vol_ma_5_rising'] = df['vol_ma_5'] > df['vol_ma_5'].shift(VOLUME_RISING_LOOKBACK)
    df['vol_above_ma_long'] = df['vol_ma_5'] > df['vol_ma']
    df['volume_pre_breakout'] = df['vol_above_ma_long'] & df['vol_ma_5_rising']

    # Donchian width for accumulation
    df['donchian_width'] = df['donchian_upper'] - df['donchian_lower']
    df['donchian_width_pct'] = df['donchian_width'] / df['donchian_mid']

    # Fresh breakout
    prev_breakout = df['donchian_breakout'].shift(1).fillna(False)
    df['fresh_breakout'] = df['donchian_breakout'] & ~prev_breakout & df['volume_expanding']

    # --- Moving Averages (for new setups) ---
    df['ma20'] = c.rolling(20).mean()
    df['ma50'] = c.rolling(50).mean()
    df['ma20_slope'] = df['ma20'].diff(5) / df['ma20'].shift(5)
    df['ma20_above_ma50'] = df['ma20'] > df['ma50']

    # --- Inside Bars (for tight base detection) ---
    inside = (h <= h.shift(1)) & (l >= l.shift(1))
    df['inside_bar'] = inside
    df['consecutive_inside'] = inside.astype(int).groupby(
        (~inside).cumsum()
    ).cumsum()

    # --- Bollinger Band Width (for VCP) ---
    bb_mid = df['ma20']
    bb_std = c.rolling(20).std()
    df['bb_width'] = (4 * bb_std) / bb_mid

    # --- Donchian Width Percentile (for tight base) ---
    dw = df['donchian_width_pct']
    rolling_min = dw.rolling(50).min()
    rolling_max = dw.rolling(50).max()
    rolling_range = rolling_max - rolling_min
    df['dw_percentile_50'] = (dw - rolling_min) / rolling_range.replace(0, 1)

    # --- ATR Slope (for VCP) ---
    df['atr_10_slope'] = df['atr_10'].diff(3) / df['atr_10'].shift(3)

    return df
