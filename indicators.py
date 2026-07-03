import numpy as np
import pandas as pd

from config import (
    ICHIMOKU_TENKAN, ICHIMOKU_KIJUN, ICHIMOKU_SENKOU_B,
    DONCHIAN_PERIOD, ATR_LENGTH, ATR_MULTIPLIER,
    ST_FAST_PERIOD, ST_FAST_MULTIPLIER,
    ST_MED_PERIOD, ST_MED_MULTIPLIER,
    ST_SLOW_PERIOD, ST_SLOW_MULTIPLIER,
    ADX_LENGTH, AVWAP_LOOKBACK, VOLUME_MA_PERIOD,
    ATR_PERIOD_RM, ATR_CONTRACTION_SHORT, ATR_CONTRACTION_LONG,
    VOL_MA_SHORT, VOLUME_RISING_LOOKBACK, FRESH_SIGNAL_BARS,
    RESISTANCE_ATR_MULTIPLIER, VOL_CONTRACTION_THRESHOLD,
    OBV_MA_PERIOD, DELTA_MA_PERIOD,
    RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    STOCH_K, STOCH_D, STOCH_SMOOTH, ELLIOTT_SWING_LOOKBACK
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

    # Ensure boolean type (handle NaN from rolling operations)
    bull_vals = np.asarray(bull_vals, dtype=bool)
    pivot_low_vals = np.nan_to_num(pivot_low_vals, nan=False).astype(bool)
    pivot_high_vals = np.nan_to_num(pivot_high_vals, nan=False).astype(bool)

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


def get_obv(close, volume):
    """On-Balance Volume: cumulative volume weighted by price direction."""
    direction = np.where(close > close.shift(1), 1,
                np.where(close < close.shift(1), -1, 0))
    direction = pd.Series(direction, index=close.index)
    obv = (volume * direction).cumsum()
    return obv


def get_ad_line(high, low, close, volume):
    """Accumulation/Distribution Line: cumulative volume weighted by close position in range."""
    hl_range = (high - low).replace(0, 1)
    clv = ((close - low) - (high - close)) / hl_range
    ad = (clv * volume).cumsum()
    return ad


def get_volume_delta(high, low, close, volume):
    """Estimate buying vs selling volume based on close position in range."""
    hl_range = (high - low).replace(0, 1)
    buy_vol = volume * (close - low) / hl_range
    sell_vol = volume * (high - close) / hl_range
    delta = buy_vol - sell_vol
    return buy_vol, sell_vol, delta


def get_rsi(close, period=None):
    """Relative Strength Index using RMA smoothing."""
    period = period or RSI_PERIOD
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = rma(gain, period)
    avg_loss = rma(loss, period)
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(100)  # If no losses, RSI = 100
    return rsi


def get_macd(close, fast=None, slow=None, signal_period=None):
    """MACD: line, signal, histogram."""
    fast = fast or MACD_FAST
    slow = slow or MACD_SLOW
    signal_period = signal_period or MACD_SIGNAL
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def get_stochastic(high, low, close, k_period=None, d_period=None, smooth=None):
    """Stochastic Oscillator: %K and %D."""
    k_period = k_period or STOCH_K
    d_period = d_period or STOCH_D
    smooth = smooth or STOCH_SMOOTH
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    hl_range = (highest_high - lowest_low).replace(0, 1)
    fast_k = 100 * (close - lowest_low) / hl_range
    slow_k = fast_k.rolling(window=smooth).mean()
    slow_d = slow_k.rolling(window=d_period).mean()
    return slow_k, slow_d


def get_elliott_wave(high, low, close, lookback=None):
    """Simple Elliott Wave detection: find swing highs/lows and estimate wave position."""
    lookback = lookback or ELLIOTT_SWING_LOOKBACK
    n = len(close)
    
    # Find swing highs and lows
    swing_highs = []
    swing_lows = []
    for i in range(lookback, n - lookback):
        if high.iloc[i] == high.iloc[i-lookback:i+lookback+1].max():
            swing_highs.append((i, high.iloc[i]))
        if low.iloc[i] == low.iloc[i-lookback:i+lookback+1].min():
            swing_lows.append((i, low.iloc[i]))
    
    # Get last 5 pivots (mix of highs and lows)
    pivots = [(idx, price, 'H') for idx, price in swing_highs] + \
             [(idx, price, 'L') for idx, price in swing_lows]
    pivots.sort(key=lambda x: x[0])
    pivots = pivots[-5:] if len(pivots) >= 5 else pivots
    
    # Estimate wave position based on pivot pattern
    # For simplicity: count how many swings we've seen
    wave_position = len(pivots) % 5 + 1  # 1-5 for impulse
    if len(pivots) >= 3:
        last3 = pivots[-3:]
        # Check if corrective (A-B-C pattern: down-up-down or up-down-up)
        if last3[0][2] == 'L' and last3[1][2] == 'H' and last3[2][2] == 'L':
            wave_position = 'B'  # Corrective wave B
        elif last3[0][2] == 'H' and last3[1][2] == 'L' and last3[2][2] == 'H':
            wave_position = 'C'  # Corrective wave C
    
    # Fibonacci levels from last swing range
    if len(pivots) >= 2:
        last_high = max(p for _, p, _ in pivots)
        last_low = min(p for _, p, _ in pivots)
        fib_range = last_high - last_low
        fib_382 = last_high - fib_range * 0.382
        fib_500 = last_high - fib_range * 0.500
        fib_618 = last_high - fib_range * 0.618
        fib_786 = last_high - fib_range * 0.786
    else:
        fib_382 = fib_500 = fib_618 = fib_786 = close.iloc[-1]
    
    return wave_position, fib_382, fib_500, fib_618, fib_786


def detect_divergence(price, indicator, lookback=20):
    """Detect bullish/bearish divergence between price and indicator."""
    n = len(price)
    if n < lookback:
        return False, False
    
    tail_price = price.tail(lookback)
    tail_ind = indicator.tail(lookback)
    
    # Find 2 lowest points in price
    price_arr = tail_price.values
    ind_arr = tail_ind.values
    
    # Split into two halves for comparison
    half = lookback // 2
    first_half_price = price_arr[:half]
    second_half_price = price_arr[half:]
    first_half_ind = ind_arr[:half]
    second_half_ind = ind_arr[half:]
    
    if len(first_half_price) == 0 or len(second_half_price) == 0:
        return False, False
    
    # Bullish divergence: price lower low, indicator higher low
    price_lower = np.nanmin(second_half_price) < np.nanmin(first_half_price)
    ind_higher = np.nanmin(second_half_ind) > np.nanmin(first_half_ind)
    bullish_div = price_lower and ind_higher
    
    # Bearish divergence: price higher high, indicator lower high
    price_higher = np.nanmax(second_half_price) > np.nanmax(first_half_price)
    ind_lower = np.nanmax(second_half_ind) < np.nanmax(first_half_ind)
    bearish_div = price_higher and ind_lower
    
    return bullish_div, bearish_div


def calculate_full_indicators(df, custom_params=None):
    df = df.copy()
    h, l, c, v = df['High'], df['Low'], df['Close'], df['Volume']

    p = custom_params or {}

    st_fast_period = p.get("st_fast_period", ST_FAST_PERIOD)
    st_fast_mult = p.get("st_fast_multiplier", ST_FAST_MULTIPLIER)
    st_med_period = p.get("st_med_period", ST_MED_PERIOD)
    st_med_mult = p.get("st_med_multiplier", ST_MED_MULTIPLIER)
    st_slow_period = p.get("st_slow_period", ST_SLOW_PERIOD)
    st_slow_mult = p.get("st_slow_multiplier", ST_SLOW_MULTIPLIER)
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

    # SuperTrend - Multi Instance
    # Fast: sensitif untuk entry awal
    df['st_fast_line'], df['st_fast_dir'] = get_supertrend(h, l, c, st_fast_period, st_fast_mult)
    df['st_fast_bullish'] = df['st_fast_dir'] > 0

    # Medium: konfirmasi (backward compatible)
    df['supertrend_line'], df['supertrend_dir'] = get_supertrend(h, l, c, st_med_period, st_med_mult)
    df['supertrend_bullish'] = df['supertrend_dir'] > 0
    df['st_med_line'] = df['supertrend_line']
    df['st_med_dir'] = df['supertrend_dir']
    df['st_med_bullish'] = df['supertrend_bullish']

    # Slow: filter trend utama (gate)
    df['st_slow_line'], df['st_slow_dir'] = get_supertrend(h, l, c, st_slow_period, st_slow_mult)
    df['st_slow_bullish'] = df['st_slow_dir'] > 0

    # Composite columns
    df['st_bullish_count'] = (df['st_fast_bullish'].astype(int) +
                              df['st_med_bullish'].astype(int) +
                              df['st_slow_bullish'].astype(int))
    df['st_layered_entry'] = df['st_slow_bullish'] & df['st_fast_bullish']

    # AVWAP - pakai medium ST sebagai anchor
    df['avwap'] = get_avwap(h, l, c, v, df['supertrend_bullish'])
    df['price_above_avwap'] = c > df['avwap']

    # ADX
    df['adx'], df['plus_di'], df['minus_di'] = get_adx(h, l, c, adx_len)
    df['adx_rising'] = df['adx'] > df['adx'].shift(1)

    # Volume
    df['vol_ma'] = v.rolling(window=vol_ma_p).mean()
    df['volume_expanding'] = v > df['vol_ma']
    df['vol_ma_ratio'] = v / df['vol_ma'].replace(0, 1)

    # Volume Pressure: OBV, A/D Line, Volume Delta
    df['obv'] = get_obv(c, v)
    df['obv_ma'] = df['obv'].rolling(window=OBV_MA_PERIOD).mean()
    df['obv_rising'] = df['obv'] > df['obv'].shift(5)

    df['ad_line'] = get_ad_line(h, l, c, v)
    df['ad_rising'] = df['ad_line'] > df['ad_line'].shift(5)

    df['buy_volume'], df['sell_volume'], df['volume_delta'] = get_volume_delta(h, l, c, v)
    df['delta_ma'] = df['volume_delta'].rolling(window=DELTA_MA_PERIOD).mean()
    df['delta_positive'] = df['volume_delta'] > 0

    # ATR Risk Management
    df['atr_rm'] = get_atr(h, l, c, ATR_PERIOD_RM)
    df['atr_10'] = get_atr(h, l, c, ATR_CONTRACTION_SHORT)
    df['atr_50'] = get_atr(h, l, c, ATR_CONTRACTION_LONG)

    # Volume Quality Metrics
    df['dollar_volume'] = c * v
    df['vol_per_atr'] = df['dollar_volume'] / df['atr_rm'].replace(0, 1)
    vol_std = v.rolling(window=20).std()
    vol_mean = df['vol_ma'].replace(0, 1)
    df['vol_cv'] = vol_std / vol_mean
    df['volume_quality'] = 'Low'
    df.loc[df['dollar_volume'] >= 1_000_000_000, 'volume_quality'] = 'Medium'
    df.loc[df['dollar_volume'] >= 5_000_000_000, 'volume_quality'] = 'High'
    df.loc[df['dollar_volume'] >= 20_000_000_000, 'volume_quality'] = 'Very High'

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

    # --- Too Late Filter Indicators ---
    # Price extension from MA20
    df['price_to_ma20_pct'] = (c - df['ma20']) / df['ma20'].replace(0, 1)

    # Price extension from AVWAP
    df['price_to_avwap_pct'] = (c - df['avwap']) / df['avwap'].replace(0, 1)

    # Run-up from 50-day low
    low_50d = l.rolling(50).min()
    df['runup_50d'] = (c - low_50d) / low_50d.replace(0, 1)

    # Volume selling ratio (volume on down days vs up days)
    o = df['Open']
    is_red = c < o  # Bearish candle
    is_green = c > o  # Bullish candle
    vol_red = v.where(is_red, 0)
    vol_green = v.where(is_green, 0)
    vol_red_ma = vol_red.rolling(10).mean()
    vol_green_ma = vol_green.rolling(10).mean()
    df['vol_selling_ratio'] = vol_red_ma / vol_green_ma.replace(0, 1)

    # Distribution signal: volume selling ratio > 1.5 means selling pressure dominates
    df['distribution_signal'] = df['vol_selling_ratio'] > 1.5

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

    # --- RSI ---
    df['rsi'] = get_rsi(c)
    df['rsi_oversold'] = df['rsi'] < 30
    df['rsi_overbought'] = df['rsi'] > 70

    # --- MACD ---
    df['macd_line'], df['macd_signal'], df['macd_histogram'] = get_macd(c)
    df['macd_bullish_cross'] = (df['macd_histogram'] > 0) & (df['macd_histogram'].shift(1) <= 0)
    df['macd_bearish_cross'] = (df['macd_histogram'] < 0) & (df['macd_histogram'].shift(1) >= 0)

    # --- Stochastic ---
    df['stoch_k'], df['stoch_d'] = get_stochastic(h, l, c)
    df['stoch_oversold'] = df['stoch_k'] < 20
    df['stoch_overbought'] = df['stoch_k'] > 80
    df['stoch_bullish_cross'] = (df['stoch_k'] > df['stoch_d']) & (df['stoch_k'].shift(1) <= df['stoch_d'].shift(1))

    # Momentum exhaustion: RSI overbought AND Stoch overbought
    df['momentum_exhaustion'] = (df['rsi'] > 70) & (df['stoch_k'] > 80)

    # --- Elliott Wave ---
    wave_pos, fib_382, fib_500, fib_618, fib_786 = get_elliott_wave(h, l, c)
    df['wave_position'] = wave_pos
    df['fib_382'] = fib_382
    df['fib_500'] = fib_500
    df['fib_618'] = fib_618
    df['fib_786'] = fib_786

    # --- Divergence Detection ---
    rsi_bull_div, rsi_bear_div = detect_divergence(c, df['rsi'])
    df['rsi_bullish_div'] = rsi_bull_div
    df['rsi_bearish_div'] = rsi_bear_div

    macd_bull_div, macd_bear_div = detect_divergence(c, df['macd_histogram'])
    df['macd_bullish_div'] = macd_bull_div
    df['macd_bearish_div'] = macd_bear_div

    return df
