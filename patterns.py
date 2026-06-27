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


def detect_patterns(df, lookback=7):
    o = df['Open'].values
    c = df['Close'].values
    h = df['High'].values
    l = df['Low'].values

    results = []
    results.extend(detect_engulfing(o, c, h, l))
    results.extend(detect_hammer_shooting(o, c, h, l))
    results.extend(detect_doji(o, c, h, l))
    results.extend(detect_inside_bar(o, c, h, l))
    results.extend(detect_harami(o, c, h, l))
    results.extend(detect_three_soldiers(o, c, h, l))
    results.extend(detect_morning_evening_star(o, c, h, l))
    results.extend(detect_piercing_dark_cloud(o, c, h, l))

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
