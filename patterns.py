import numpy as np


def _body(o, c):
    return abs(c - o)


def _upper_shadow(h, o, c):
    return h - max(o, c)


def _lower_shadow(l, o, c):
    return min(o, c) - l


def _range(h, l):
    return h - l if h > l else 0.001


def _is_bullish(o, c):
    return c > o


def _is_bearish(o, c):
    return c < o


def detect_engulfing(o, c, h, l):
    result = []
    n = len(o)
    if n < 3:
        return result

    prev_bear = np.zeros(n, dtype=bool)
    curr_bull = np.zeros(n, dtype=bool)
    body_engulf = np.zeros(n, dtype=bool)
    prev_bull = np.zeros(n, dtype=bool)
    curr_bear = np.zeros(n, dtype=bool)
    body_engulf_bear = np.zeros(n, dtype=bool)

    prev_bear[1:] = c[:-1] < o[:-1]
    curr_bull[1:] = c[1:] > o[1:]
    body_engulf[2:] = (c[2:] > o[1:-1]) & (o[2:] < c[1:-1])

    prev_bull[1:] = c[:-1] > o[:-1]
    curr_bear[1:] = c[1:] < o[1:]
    body_engulf_bear[2:] = (o[2:] > c[1:-1]) & (c[2:] < o[1:-1])

    bull_mask = prev_bear & curr_bull & body_engulf
    bear_mask = prev_bull & curr_bear & body_engulf_bear

    for i in np.where(bull_mask)[0]:
        b_prev = abs(c[i - 1] - o[i - 1])
        b_curr = abs(c[i] - o[i])
        confidence = min(1.0, b_curr / max(b_prev, 0.001) * 0.5)
        result.append(("Bullish Engulfing", i, round(confidence, 2)))

    for i in np.where(bear_mask)[0]:
        b_prev = abs(c[i - 1] - o[i - 1])
        b_curr = abs(c[i] - o[i])
        confidence = min(1.0, b_curr / max(b_prev, 0.001) * 0.5)
        result.append(("Bearish Engulfing", i, round(confidence, 2)))

    return result


def detect_hammer_shooting(o, c, h, l):
    result = []
    for i in range(1, len(o)):
        body = _body(o[i], c[i])
        r = _range(h[i], l[i])
        if r == 0:
            continue
        lower = _lower_shadow(l[i], o[i], c[i])
        upper = _upper_shadow(h[i], o[i], c[i])
        body_pct = body / r

        if body_pct < 0.35:
            # Hammer: lower shadow > 2x body
            if lower > body * 2 and upper < body:
                trend_before = c[max(0, i - 5):i].mean() < c[i]
                confidence = 0.6 if trend_before else 0.3
                result.append(("Hammer", i, round(confidence, 2)))

            # Shooting Star: upper shadow > 2x body
            if upper > body * 2 and lower < body:
                trend_before = c[max(0, i - 5):i].mean() > c[i]
                confidence = 0.6 if trend_before else 0.3
                result.append(("Shooting Star", i, round(confidence, 2)))

    return result


def detect_doji(o, c, h, l):
    result = []
    for i in range(1, len(o)):
        r = _range(h[i], l[i])
        if r == 0:
            continue
        body = _body(o[i], c[i])
        if body / r < 0.1:
            result.append(("Doji", i, 0.7))
    return result


def detect_inside_bar(o, c, h, l):
    result = []
    if len(h) < 2:
        return result

    inside_mask = (h[1:] <= h[:-1]) & (l[1:] >= l[:-1])

    for i in np.where(inside_mask)[0] + 1:
        result.append(("Inside Bar", i, 0.5))
    return result


def detect_harami(o, c, h, l):
    result = []
    for i in range(2, len(o)):
        prev_body = _body(o[i - 1], c[i - 1])
        curr_body = _body(o[i], c[i])
        r = _range(h[i], l[i])
        if prev_body == 0 or r == 0:
            continue

        prev_bull = _is_bullish(o[i - 1], c[i - 1])
        curr_bear = _is_bearish(o[i], c[i])
        if prev_bull and curr_bear and curr_body < prev_body:
            result.append(("Bearish Harami", i, 0.5))

        prev_bear = _is_bearish(o[i - 1], c[i - 1])
        curr_bull = _is_bullish(o[i], c[i])
        if prev_bear and curr_bull and curr_body < prev_body:
            result.append(("Bullish Harami", i, 0.5))

    return result


def detect_three_soldiers(o, c, h, l):
    result = []
    for i in range(3, len(o)):
        b1 = _is_bullish(o[i - 2], c[i - 2])
        b2 = _is_bullish(o[i - 1], c[i - 1])
        b3 = _is_bullish(o[i], c[i])
        if b1 and b2 and b3:
            # Progressive higher closes
            if c[i] > c[i - 1] > c[i - 2]:
                # Each opens within prior body
                if o[i] >= o[i - 1] and o[i] <= c[i - 1]:
                    if o[i - 1] >= o[i - 2] and o[i - 1] <= c[i - 2]:
                        result.append(("Three White Soldiers", i, 0.7))

    for i in range(3, len(o)):
        b1 = _is_bearish(o[i - 2], c[i - 2])
        b2 = _is_bearish(o[i - 1], c[i - 1])
        b3 = _is_bearish(o[i], c[i])
        if b1 and b2 and b3:
            # Progressive lower closes
            if c[i] < c[i - 1] < c[i - 2]:
                # Each opens within prior body
                if o[i] <= o[i - 1] and o[i] >= c[i - 1]:
                    if o[i - 1] <= o[i - 2] and o[i - 1] >= c[i - 2]:
                        result.append(("Three Black Crows", i, 0.7))

    return result


def detect_morning_evening_star(o, c, h, l):
    result = []
    for i in range(3, len(o)):
        r1 = _range(h[i - 2], l[i - 2])
        r0 = _range(h[i], l[i])
        if r1 == 0 or r0 == 0:
            continue
        body_mid = _body(o[i - 1], c[i - 1])
        body_prev = _body(o[i - 2], c[i - 2])
        body_curr = _body(o[i], c[i])

        prev_bear = _is_bearish(o[i - 2], c[i - 2])
        curr_bull = _is_bullish(o[i], c[i])
        small_mid = body_mid < body_prev * 0.5

        if prev_bear and curr_bull and small_mid:
            if c[i] > (o[i - 2] + c[i - 2]) / 2:
                result.append(("Morning Star", i, 0.8))

        prev_bull = _is_bullish(o[i - 2], c[i - 2])
        curr_bear = _is_bearish(o[i], c[i])

        if prev_bull and curr_bear and small_mid:
            if c[i] < (o[i - 2] + c[i - 2]) / 2:
                result.append(("Evening Star", i, 0.8))

    return result


def detect_piercing_dark_cloud(o, c, h, l):
    result = []
    for i in range(2, len(o)):
        r1 = _range(h[i - 1], l[i - 1])
        r0 = _range(h[i], l[i])
        if r1 == 0 or r0 == 0:
            continue

        prev_bear = _is_bearish(o[i - 1], c[i - 1])
        curr_bull = _is_bullish(o[i], c[i])

        if prev_bear and curr_bull:
            mid_prev = (o[i - 1] + c[i - 1]) / 2
            if c[i] > mid_prev and o[i] <= l[i - 1]:
                result.append(("Piercing Pattern", i, 0.65))

        prev_bull = _is_bullish(o[i - 1], c[i - 1])
        curr_bear = _is_bearish(o[i], c[i])

        if prev_bull and curr_bear:
            mid_prev = (o[i - 1] + c[i - 1]) / 2
            if c[i] < mid_prev and o[i] >= h[i - 1]:
                result.append(("Dark Cloud Cover", i, 0.65))

    return result


# === NEW PATTERNS ===

# --- Doji Variations ---

def detect_doji_variations(o, c, h, l):
    result = []
    for i in range(1, len(o)):
        r = _range(h[i], l[i])
        if r == 0:
            continue
        body = _body(o[i], c[i])
        body_pct = body / r
        upper = _upper_shadow(h[i], o[i], c[i])
        lower = _lower_shadow(l[i], o[i], c[i])

        if body_pct < 0.1:
            # Dragonfly Doji: long lower shadow, no upper shadow
            if lower > r * 0.7 and upper < r * 0.1:
                trend_before = c[max(0, i - 5):i].mean() < c[i]
                confidence = 0.75 if trend_before else 0.5
                result.append(("Dragonfly Doji", i, round(confidence, 2)))

            # Gravestone Doji: long upper shadow, no lower shadow
            elif upper > r * 0.7 and lower < r * 0.1:
                trend_before = c[max(0, i - 5):i].mean() > c[i]
                confidence = 0.75 if trend_before else 0.5
                result.append(("Gravestone Doji", i, round(confidence, 2)))

            # Long-Legged Doji: both shadows are long
            elif lower > r * 0.3 and upper > r * 0.3:
                result.append(("Long-Legged Doji", i, 0.6))
    return result


# --- Single Bar Variations ---

def detect_marubozu(o, c, h, l):
    result = []
    for i in range(1, len(o)):
        r = _range(h[i], l[i])
        if r == 0:
            continue
        body = _body(o[i], c[i])
        upper = _upper_shadow(h[i], o[i], c[i])
        lower = _lower_shadow(l[i], o[i], c[i])

        # Marubozu: body is 90%+ of range, minimal shadows
        if body / r > 0.9 and upper < r * 0.05 and lower < r * 0.05:
            if _is_bullish(o[i], c[i]):
                result.append(("Bullish Marubozu", i, 0.8))
            else:
                result.append(("Bearish Marubozu", i, 0.8))
    return result


def detect_spinning_top(o, c, h, l):
    result = []
    for i in range(1, len(o)):
        r = _range(h[i], l[i])
        if r == 0:
            continue
        body = _body(o[i], c[i])
        body_pct = body / r
        upper = _upper_shadow(h[i], o[i], c[i])
        lower = _lower_shadow(l[i], o[i], c[i])

        # Spinning Top: small body (10-30%), shadows on both sides
        if 0.1 <= body_pct <= 0.3 and upper > body and lower > body:
            result.append(("Spinning Top", i, 0.4))
    return result


def detect_hanging_man(o, c, h, l):
    result = []
    for i in range(2, len(o)):
        body = _body(o[i], c[i])
        r = _range(h[i], l[i])
        if r == 0:
            continue
        lower = _lower_shadow(l[i], o[i], c[i])
        upper = _upper_shadow(h[i], o[i], c[i])
        body_pct = body / r

        # Hanging Man: small body at top, long lower shadow, in uptrend
        if body_pct < 0.35 and lower > body * 2 and upper < body * 0.5:
            trend_before = c[max(0, i - 5):i].mean() < c[i]
            if trend_before:
                result.append(("Hanging Man", i, 0.65))
    return result


def detect_inverted_hammer(o, c, h, l):
    result = []
    for i in range(2, len(o)):
        body = _body(o[i], c[i])
        r = _range(h[i], l[i])
        if r == 0:
            continue
        lower = _lower_shadow(l[i], o[i], c[i])
        upper = _upper_shadow(h[i], o[i], c[i])
        body_pct = body / r

        # Inverted Hammer: small body at bottom, long upper shadow, in downtrend
        if body_pct < 0.35 and upper > body * 2 and lower < body * 0.5:
            trend_before = c[max(0, i - 5):i].mean() > c[i]
            if trend_before:
                result.append(("Inverted Hammer", i, 0.65))
    return result


# --- 2-Bar Reversal Patterns ---

def detect_tweezer(o, c, h, l):
    result = []
    for i in range(2, len(o)):
        r = _range(h[i], l[i])
        if r == 0:
            continue

        # Tweezer Top: similar highs, first bullish then bearish
        high_diff = abs(h[i] - h[i - 1]) / r
        if high_diff < 0.02:
            if _is_bullish(o[i - 1], c[i - 1]) and _is_bearish(o[i], c[i]):
                result.append(("Tweezer Top", i, 0.7))

        # Tweezer Bottom: similar lows, first bearish then bullish
        low_diff = abs(l[i] - l[i - 1]) / r
        if low_diff < 0.02:
            if _is_bearish(o[i - 1], c[i - 1]) and _is_bullish(o[i], c[i]):
                result.append(("Tweezer Bottom", i, 0.7))
    return result


def detect_belt_hold(o, c, h, l):
    result = []
    for i in range(2, len(o)):
        r = _range(h[i], l[i])
        if r == 0:
            continue
        body = _body(o[i], c[i])
        upper = _upper_shadow(h[i], o[i], c[i])
        lower = _lower_shadow(l[i], o[i], c[i])

        # Bullish Belt Hold: opens at low, strong bullish candle
        if _is_bullish(o[i], c[i]) and body / r > 0.7 and lower < r * 0.05:
            prev_bear = _is_bearish(o[i - 1], c[i - 1])
            if prev_bear:
                result.append(("Bullish Belt Hold", i, 0.65))

        # Bearish Belt Hold: opens at high, strong bearish candle
        if _is_bearish(o[i], c[i]) and body / r > 0.7 and upper < r * 0.05:
            prev_bull = _is_bullish(o[i - 1], c[i - 1])
            if prev_bull:
                result.append(("Bearish Belt Hold", i, 0.65))
    return result


# --- 3-Bar Continuation Patterns ---

def detect_three_inside(o, c, h, l):
    result = []
    for i in range(3, len(o)):
        # Three Inside Up: bearish, harami bullish, bullish confirmation
        if _is_bearish(o[i - 2], c[i - 2]):
            prev_body = _body(o[i - 2], c[i - 2])
            mid_body = _body(o[i - 1], c[i - 1])
            if mid_body < prev_body and _is_bullish(o[i - 1], c[i - 1]):
                if _is_bullish(o[i], c[i]) and c[i] > c[i - 2]:
                    result.append(("Three Inside Up", i, 0.7))

        # Three Inside Down: bullish, harami bearish, bearish confirmation
        if _is_bullish(o[i - 2], c[i - 2]):
            prev_body = _body(o[i - 2], c[i - 2])
            mid_body = _body(o[i - 1], c[i - 1])
            if mid_body < prev_body and _is_bearish(o[i - 1], c[i - 1]):
                if _is_bearish(o[i], c[i]) and c[i] < c[i - 2]:
                    result.append(("Three Inside Down", i, 0.7))
    return result


def detect_three_methods(o, c, h, l):
    result = []
    for i in range(5, len(o)):
        # Rising Three Methods: long bullish, 3 small bearish, long bullish
        if _is_bullish(o[i - 5], c[i - 5]) and _is_bullish(o[i], c[i]):
            body_first = _body(o[i - 5], c[i - 5])
            body_last = _body(o[i], c[i])
            if body_first > 0 and body_last > 0:
                # Middle 3 candles are small and bearish
                mid_small = all(
                    _body(o[i - j], c[i - j]) < body_first * 0.4
                    for j in range(1, 4)
                )
                mid_bearish = all(
                    _is_bearish(o[i - j], c[i - j])
                    for j in range(1, 4)
                )
                if mid_small and mid_bearish and c[i] > c[i - 5]:
                    result.append(("Rising Three Methods", i, 0.75))

        # Falling Three Methods: long bearish, 3 small bullish, long bearish
        if _is_bearish(o[i - 5], c[i - 5]) and _is_bearish(o[i], c[i]):
            body_first = _body(o[i - 5], c[i - 5])
            body_last = _body(o[i], c[i])
            if body_first > 0 and body_last > 0:
                mid_small = all(
                    _body(o[i - j], c[i - j]) < body_first * 0.4
                    for j in range(1, 4)
                )
                mid_bullish = all(
                    _is_bullish(o[i - j], c[i - j])
                    for j in range(1, 4)
                )
                if mid_small and mid_bullish and c[i] < c[i - 5]:
                    result.append(("Falling Three Methods", i, 0.75))
    return result


# --- Gap-Based Patterns ---

def detect_abandoned_baby(o, c, h, l):
    result = []
    for i in range(3, len(o)):
        # Bullish Abandoned Baby: bearish, doji gap down, bullish gap up
        if _is_bearish(o[i - 2], c[i - 2]):
            r_mid = _range(h[i - 1], l[i - 1])
            if r_mid == 0:
                continue
            body_mid = _body(o[i - 1], c[i - 1])
            is_doji = body_mid / r_mid < 0.1
            gap_down = h[i - 1] < l[i - 2]
            gap_up = l[i] > h[i - 1]
            if is_doji and gap_down and gap_up and _is_bullish(o[i], c[i]):
                result.append(("Bullish Abandoned Baby", i, 0.85))

        # Bearish Abandoned Baby: bullish, doji gap up, bearish gap down
        if _is_bullish(o[i - 2], c[i - 2]):
            r_mid = _range(h[i - 1], l[i - 1])
            if r_mid == 0:
                continue
            body_mid = _body(o[i - 1], c[i - 1])
            is_doji = body_mid / r_mid < 0.1
            gap_up = l[i - 1] > h[i - 2]
            gap_down = h[i] < l[i - 1]
            if is_doji and gap_up and gap_down and _is_bearish(o[i], c[i]):
                result.append(("Bearish Abandoned Baby", i, 0.85))
    return result


def detect_kicking(o, c, h, l):
    result = []
    for i in range(2, len(o)):
        body_prev = _body(o[i - 1], c[i - 1])
        body_curr = _body(o[i], c[i])
        r_prev = _range(h[i - 1], l[i - 1])
        r_curr = _range(h[i], l[i])
        if r_prev == 0 or r_curr == 0:
            continue

        # Both must be marubozu-like (strong bodies)
        if body_prev / r_prev < 0.85 or body_curr / r_curr < 0.85:
            continue

        # Bullish Kicking: bearish marubozu then bullish marubozu with gap up
        if _is_bearish(o[i - 1], c[i - 1]) and _is_bullish(o[i], c[i]):
            if o[i] > h[i - 1]:  # gap up
                result.append(("Bullish Kicking", i, 0.8))

        # Bearish Kicking: bullish marubozu then bearish marubozu with gap down
        if _is_bullish(o[i - 1], c[i - 1]) and _is_bearish(o[i], c[i]):
            if o[i] < l[i - 1]:  # gap down
                result.append(("Bearish Kicking", i, 0.8))
    return result


def detect_counterattack(o, c, h, l):
    result = []
    for i in range(2, len(o)):
        r = _range(h[i], l[i])
        if r == 0:
            continue

        # Bullish Counterattack: bearish then bullish close near prior close
        if _is_bearish(o[i - 1], c[i - 1]) and _is_bullish(o[i], c[i]):
            close_diff = abs(c[i] - c[i - 1]) / r
            if close_diff < 0.03:
                result.append(("Bullish Counterattack", i, 0.6))

        # Bearish Counterattack: bullish then bearish close near prior close
        if _is_bullish(o[i - 1], c[i - 1]) and _is_bearish(o[i], c[i]):
            close_diff = abs(c[i] - c[i - 1]) / r
            if close_diff < 0.03:
                result.append(("Bearish Counterattack", i, 0.6))
    return result


def detect_on_neck_in_neck_thrusting(o, c, h, l):
    result = []
    for i in range(2, len(o)):
        r = _range(h[i], l[i])
        if r == 0:
            continue

        if _is_bearish(o[i - 1], c[i - 1]) and _is_bullish(o[i], c[i]):
            # On-Neck: bullish closes exactly at prior low
            if abs(c[i] - l[i - 1]) / r < 0.02:
                result.append(("On-Neck", i, 0.5))

            # In-Neck: bullish closes slightly above prior low
            elif c[i] > l[i - 1] and c[i] < (o[i - 1] + c[i - 1]) / 2:
                if abs(c[i] - l[i - 1]) / r < 0.05:
                    result.append(("In-Neck", i, 0.5))

            # Thrusting: bullish closes above prior low but below midpoint
            elif c[i] > l[i - 1] and c[i] < (o[i - 1] + c[i - 1]) / 2:
                if _body(o[i], c[i]) > _body(o[i - 1], c[i - 1]) * 0.5:
                    result.append(("Thrusting", i, 0.55))
    return result


def detect_patterns(df, lookback=7):
    o = df['Open'].values
    c = df['Close'].values
    h = df['High'].values
    l = df['Low'].values

    results = []
    # Original patterns
    results.extend(detect_engulfing(o, c, h, l))
    results.extend(detect_hammer_shooting(o, c, h, l))
    results.extend(detect_doji(o, c, h, l))
    results.extend(detect_inside_bar(o, c, h, l))
    results.extend(detect_harami(o, c, h, l))
    results.extend(detect_three_soldiers(o, c, h, l))
    results.extend(detect_morning_evening_star(o, c, h, l))
    results.extend(detect_piercing_dark_cloud(o, c, h, l))
    # New patterns - Doji variations
    results.extend(detect_doji_variations(o, c, h, l))
    # New patterns - Single bar
    results.extend(detect_marubozu(o, c, h, l))
    results.extend(detect_spinning_top(o, c, h, l))
    results.extend(detect_hanging_man(o, c, h, l))
    results.extend(detect_inverted_hammer(o, c, h, l))
    # New patterns - 2-bar reversal
    results.extend(detect_tweezer(o, c, h, l))
    results.extend(detect_belt_hold(o, c, h, l))
    # New patterns - 3-bar continuation
    results.extend(detect_three_inside(o, c, h, l))
    results.extend(detect_three_methods(o, c, h, l))
    # New patterns - Gap-based
    results.extend(detect_abandoned_baby(o, c, h, l))
    results.extend(detect_kicking(o, c, h, l))
    results.extend(detect_counterattack(o, c, h, l))
    results.extend(detect_on_neck_in_neck_thrusting(o, c, h, l))

    # Filter to last `lookback` bars
    min_idx = max(0, len(df) - lookback - 5)
    recent = [(n, i, conf) for n, i, conf in results if i >= min_idx]

    # Sort by index (most recent last)
    recent.sort(key=lambda x: x[1])

    has_dt_index = hasattr(df.index, 'strftime')

    if has_dt_index:
        patterns = [(name, df.index[i].strftime('%d %b'), conf)
                    for name, i, conf in recent]
    else:
        patterns = [(name, str(i), conf)
                    for name, i, conf in recent]

    # Metadata
    total_bars = len(df)
    if has_dt_index:
        last_bar_date = df.index[-1].strftime('%d %b %Y')
        window_start = df.index[min_idx].strftime('%d %b %Y')
    else:
        last_bar_date = str(df.index[-1])
        window_start = str(df.index[min_idx])

    if recent:
        last_pattern_idx = recent[-1][1]
        bars_since_last = total_bars - 1 - last_pattern_idx
        last_pattern_date = df.index[last_pattern_idx].strftime('%d %b %Y') if has_dt_index else str(df.index[last_pattern_idx])
    else:
        bars_since_last = total_bars
        last_pattern_date = None

    metadata = {
        "total_bars": total_bars,
        "last_bar_date": last_bar_date,
        "window_start": window_start,
        "bars_checked": total_bars - min_idx,
        "last_pattern_date": last_pattern_date,
        "bars_since_last": bars_since_last,
        "total_patterns": len(patterns),
    }

    return patterns, metadata


def get_pattern_score(patterns):
    bullish_patterns = [
        "Bullish Engulfing", "Hammer", "Dragonfly Doji", "Bullish Marubozu",
        "Tweezer Bottom", "Bullish Belt Hold", "Three Inside Up",
        "Rising Three Methods", "Bullish Abandoned Baby", "Bullish Kicking",
        "Bullish Counterattack", "Morning Star", "Piercing Pattern",
        "Bullish Harami", "Three White Soldiers", "Inverted Hammer",
        "On-Neck", "In-Neck", "Thrusting"
    ]
    bearish_patterns = [
        "Bearish Engulfing", "Shooting Star", "Gravestone Doji", "Bearish Marubozu",
        "Tweezer Top", "Bearish Belt Hold", "Three Inside Down",
        "Falling Three Methods", "Bearish Abandoned Baby", "Bearish Kicking",
        "Bearish Counterattack", "Evening Star", "Dark Cloud Cover",
        "Bearish Harami", "Three Black Crows", "Hanging Man"
    ]

    score = 0.0
    bullish_count = 0
    bearish_count = 0

    for name, date, conf in patterns:
        if name in bullish_patterns:
            score += conf
            bullish_count += 1
        elif name in bearish_patterns:
            score -= conf * 0.7
            bearish_count += 1

    return {
        "score": round(score, 2),
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "total_patterns": len(patterns),
        "bias": "BULLISH" if score > 0.5 else "BEARISH" if score < -0.5 else "NEUTRAL"
    }
