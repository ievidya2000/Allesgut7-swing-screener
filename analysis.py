import numpy as np
import pandas as pd

from config import (
    ATR_LENGTH, ATR_MULTIPLIER, SL_MULTIPLIER,
    RR1, RR2, RR3, FRESH_SIGNAL_BARS,
    ENTRY_ZONE_MAX_ATR, ENTRY_ZONE_MIN_ATR, ENTRY_ZONE_MAX_PCT
)
from indicators import get_atr, get_supertrend
from utils.price_utils import round_to_tick


def find_swing_points(df, window=10):
    h = df['High']
    l = df['Low']

    swing_high = (h == h.rolling(window=2 * window + 1, center=True).max())
    swing_low = (l == l.rolling(window=2 * window + 1, center=True).min())

    high_idx = np.where(swing_high)[0]
    low_idx = np.where(swing_low)[0]

    levels = {"support": [], "resistance": []}

    for i in low_idx[-min(30, len(low_idx)):]:
        levels["support"].append({"price": float(l.iloc[i]), "index": i, "strength": 1})
    for i in high_idx[-min(30, len(high_idx)):]:
        levels["resistance"].append({"price": float(h.iloc[i]), "index": i, "strength": 1})

    return levels


def cluster_levels(prices, atr_val, max_dist=None):
    if max_dist is None:
        max_dist = atr_val * 0.5
    if not prices:
        return []

    sorted_p = sorted(prices)
    clusters = [[sorted_p[0]]]

    for p in sorted_p[1:]:
        if abs(p - clusters[-1][-1]) <= max_dist:
            clusters[-1].append(p)
        else:
            clusters.append([p])

    result = []
    for c in clusters:
        avg_p = np.mean(c)
        strength = len(c)
        result.append({"price": round_to_tick(avg_p), "strength": strength,
                        "low": min(c), "high": max(c)})
    return result


def find_fib_levels(df, atr_val):
    tail = df.tail(30)
    recent_high = tail['High'].max()
    recent_low = tail['Low'].min()
    diff = recent_high - recent_low

    if diff < atr_val * 0.5:
        return []

    levels = [recent_high, recent_low]
    for ratio in [0.236, 0.382, 0.5, 0.618, 0.786]:
        levels.append(recent_high - diff * ratio)

    return [{"price": round_to_tick(p), "strength": 1, "source": "fib"} for p in set(levels)]


def find_key_levels(df, atr_val):
    swing = find_swing_points(df)

    support_prices = [s["price"] for s in swing["support"]]
    resistance_prices = [s["price"] for s in swing["resistance"]]

    fib_levels = find_fib_levels(df, atr_val)
    for fl in fib_levels:
        if fl["price"] < df['Close'].iloc[-1]:
            support_prices.append(fl["price"])
        else:
            resistance_prices.append(fl["price"])

    # MA levels
    close = df['Close']
    for period, label in [(20, "MA20"), (50, "MA50")]:
        if len(close) > period:
            ma = close.rolling(period).mean().iloc[-1]
            if pd.notna(ma):
                if ma < close.iloc[-1]:
                    support_prices.append(ma)
                else:
                    resistance_prices.append(ma)

    # AVWAP
    if 'avwap' in df.columns and pd.notna(df['avwap'].iloc[-1]):
        avwap = df['avwap'].iloc[-1]
        if avwap < close.iloc[-1]:
            support_prices.append(avwap)
        else:
            resistance_prices.append(avwap)

    supports = cluster_levels(support_prices, atr_val)
    resistances = cluster_levels(resistance_prices, atr_val)

    return {"supports": supports, "resistances": resistances}


def determine_entry_zone(full_df, levels, setup, close, atr_val):
    entry_low = entry_high = close
    conditions = []
    strategy = ""

    # Get Fibonacci levels from Elliott Wave
    fib_382 = full_df['fib_382'].iloc[-1] if 'fib_382' in full_df.columns else close
    fib_618 = full_df['fib_618'].iloc[-1] if 'fib_618' in full_df.columns else close

    # Get RSI/Stochastic for momentum confirmation
    rsi = full_df['rsi'].iloc[-1] if 'rsi' in full_df.columns else 50
    stoch_k = full_df['stoch_k'].iloc[-1] if 'stoch_k' in full_df.columns else 50

    if setup == "PRE_BREAKOUT":
        mid = full_df['donchian_mid'].iloc[-1]
        upper = full_df['donchian_upper'].iloc[-1]
        ma20 = full_df['Close'].rolling(20).mean().iloc[-1]

        zone_low = max(mid, ma20) if pd.notna(ma20) else mid
        zone_high = upper - atr_val * ENTRY_ZONE_MIN_ATR

        entry_low = round_to_tick(zone_low)
        entry_high = round_to_tick(zone_high)

        strategy = "Limit di zona konsolidasi"
        conditions = [
            "Volume > MA20",
            "Close > Donchian Mid",
            "ADX rising",
            f"RSI: {rsi:.0f} (konfirmasi momentum)",
        ]

    elif setup == "BREAKOUT":
        upper = full_df['donchian_upper'].iloc[-1]
        entry_low = round_to_tick(upper - atr_val * ENTRY_ZONE_MIN_ATR)
        entry_high = round_to_tick(upper + atr_val * ENTRY_ZONE_MIN_ATR)
        strategy = "Market on confirmation / Limit on retest"
        conditions = [
            "Volume > 150% MA20",
            "Close in upper 25% candle",
            "No gap fill",
            f"MACD histogram positive",
        ]

    elif setup == "ACCUMULATION":
        lower = full_df['donchian_lower'].iloc[-1]
        mid = full_df['donchian_mid'].iloc[-1]

        best_support = lower
        for s in levels["supports"]:
            if s["high"] >= lower and s["low"] <= mid:
                best_support = max(best_support, s["price"])

        # Use Fibonacci 61.8% as tighter anchor
        fib_anchor = fib_618 if lower <= fib_618 <= mid else mid
        entry_low = round_to_tick(min(best_support, fib_anchor))
        entry_high = round_to_tick(max(best_support, fib_anchor))

        # Cap zone width
        zone_width = entry_high - entry_low
        max_width = close * ENTRY_ZONE_MAX_PCT
        if zone_width > max_width:
            zone_mid = (entry_low + entry_high) / 2
            entry_low = round_to_tick(zone_mid - max_width / 2)
            entry_high = round_to_tick(zone_mid + max_width / 2)

        strategy = "Limit di support — range bound"
        conditions = [
            "Price touch lower band",
            "Volume contraction on pullback",
            f"RSI: {rsi:.0f} ({'oversold' if rsi < 30 else 'netral'})",
        ]

    elif setup == "VCP":
        bb_mid = full_df['Close'].rolling(20).mean().iloc[-1] if len(full_df) >= 20 else close
        # TIGHTENED: was 1.5 ATR, now 0.5 ATR
        bb_lower = bb_mid - atr_val * ENTRY_ZONE_MAX_ATR
        bb_upper = bb_mid + atr_val * ENTRY_ZONE_MAX_ATR

        entry_low = round_to_tick(bb_lower)
        entry_high = round_to_tick(bb_mid)

        # Cap zone width
        zone_width = entry_high - entry_low
        max_width = close * ENTRY_ZONE_MAX_PCT
        if zone_width > max_width:
            entry_high = round_to_tick(entry_low + max_width)

        strategy = "Limit saat volatilitas menyusut — tunggu expansion"
        conditions = [
            "BB width menyusut",
            "Volume decline 3+ bars",
            f"Stochastic: {stoch_k:.0f} ({'oversold' if stoch_k < 20 else 'netral'})",
        ]

    elif setup == "TIGHT_BASE_BREAKOUT":
        upper = full_df['donchian_upper'].iloc[-1]
        entry_low = round_to_tick(upper - atr_val * ENTRY_ZONE_MIN_ATR)
        entry_high = round_to_tick(upper + atr_val * ENTRY_ZONE_MIN_ATR)
        strategy = "Market on breakout / Limit on retest"
        conditions = [
            "Tight range < 5%",
            "Inside bars",
            "Volume dry",
            f"RSI netral: {rsi:.0f}",
        ]

    elif setup == "BASE_ON_BASE":
        mid = full_df['donchian_mid'].iloc[-1]
        upper = full_df['donchian_upper'].iloc[-1]
        # TIGHTENED: max 0.75 ATR instead of full Donchian half
        zone_low = mid
        zone_high = min(upper, mid + atr_val * ENTRY_ZONE_MAX_ATR)
        entry_low = round_to_tick(zone_low)
        entry_high = round_to_tick(zone_high)

        # Cap zone width
        zone_width = entry_high - entry_low
        max_width = close * ENTRY_ZONE_MAX_PCT
        if zone_width > max_width:
            entry_high = round_to_tick(entry_low + max_width)

        strategy = "Limit di atas base kedua — tunggu breakout"
        conditions = [
            "Two stacked bases",
            "Breakout from base 2",
            "Higher base structure",
        ]

    elif setup == "BULL_FLAG":
        ma20 = full_df['Close'].rolling(20).mean().iloc[-1] if len(full_df) >= 20 else close
        entry_low = round_to_tick(ma20 - atr_val * ENTRY_ZONE_MIN_ATR)
        entry_high = round_to_tick(ma20)
        strategy = "Limit di flag pullback — tunggu bounce"
        conditions = [
            "Flagpole > 15%",
            "Flag < 12%",
            "Declining volume in flag",
            f"RSI sehat: {rsi:.0f}",
        ]

    elif setup == "PULLBACK_MA20":
        ma20 = full_df['Close'].rolling(20).mean().iloc[-1] if len(full_df) >= 20 else close
        entry_low = round_to_tick(ma20 - atr_val * ENTRY_ZONE_MIN_ATR)
        entry_high = round_to_tick(ma20 + atr_val * ENTRY_ZONE_MIN_ATR)
        strategy = "Limit di MA20 — bounce confirmation"
        conditions = [
            "MA20 rising",
            "Bounce on MA20",
            "Prior uptrend strength",
            f"RSI: {rsi:.0f} / Stoch: {stoch_k:.0f}",
        ]

    elif setup == "EARLY_REVERSAL":
        ma20 = full_df['Close'].rolling(20).mean().iloc[-1] if len(full_df) >= 20 else close
        recent_swing_low = full_df['Low'].tail(15).min()
        sl_normal = round_to_tick(close - atr_val * 1.5)

        zone_low = recent_swing_low + atr_val * 1.0
        zone_high = min(ma20, close) if pd.notna(ma20) else close

        # Entry zone must be above SL
        min_entry = sl_normal + atr_val * 0.3
        if zone_low < min_entry:
            zone_low = min_entry
        if zone_high < zone_low:
            zone_high = zone_low + atr_val * 0.5

        entry_low = round_to_tick(zone_low)
        entry_high = round_to_tick(zone_high)

        # Cap zone width
        zone_width = entry_high - entry_low
        max_width = close * ENTRY_ZONE_MAX_PCT
        if zone_width > max_width:
            zone_mid = (entry_low + entry_high) / 2
            entry_low = round_to_tick(zone_mid - max_width / 2)
            entry_high = round_to_tick(zone_mid + max_width / 2)

        strategy = "Limit pada pullback — confirmation needed"
        rsi_bull_div = full_df['rsi_bullish_div'].iloc[-1] if 'rsi_bullish_div' in full_df.columns else False
        conditions = [
            "Divergence detected" if rsi_bull_div else "SuperTrend flip",
            "Volume confirmation",
            f"RSI: {rsi:.0f}",
        ]

    # Ensure low < high
    if entry_low > entry_high:
        entry_low, entry_high = entry_high, entry_low
    if entry_low == entry_high:
        entry_high = round_to_tick(entry_low + atr_val * ENTRY_ZONE_MIN_ATR)

    # Strengthen entry zone with confluence
    confluence = 0
    for s in levels["supports"]:
        if s["low"] <= entry_high and s["high"] >= entry_low:
            confluence += s["strength"]

    return {
        "low": entry_low,
        "high": entry_high,
        "strength": confluence,
        "strategy": strategy,
        "conditions": conditions,
    }


def determine_sl_wide(full_df, levels, close, atr_val, sl_normal, sl_mult=None):
    if sl_mult is None:
        sl_mult = SL_MULTIPLIER
    # Wide SL: 2.5×ATR from entry
    sl_by_atr = close - abs(close - sl_normal) * (2.5 / sl_mult)
    sl_by_atr = round_to_tick(sl_by_atr)

    # Structural: below nearest support
    best_support = None
    for s in levels["supports"]:
        if s["price"] < close:
            if best_support is None or s["price"] > best_support:
                best_support = s["price"]

    if best_support is not None:
        # Slightly below support
        sl_structural = round_to_tick(best_support - atr_val * 0.3)
        sl_wide = min(sl_by_atr, sl_structural)
        logic = f"2.5×ATR ({sl_by_atr}) atau struktural di bawah {best_support} ({sl_structural})"
    else:
        sl_wide = sl_by_atr
        logic = f"2.5×ATR ({sl_by_atr})"

    return {"price": sl_wide, "logic": logic}


def analyze_tp_targets(tp1, tp2, tp3, close, levels):
    result = []

    for tp_label, tp_val in [("TP1", tp1), ("TP2", tp2), ("TP3", tp3)]:
        if tp_val is None:
            continue

        # Check proximity to resistance
        near_resist = False
        resist_label = ""
        for r in levels["resistances"]:
            if abs(r["price"] - tp_val) / tp_val < 0.02:
                near_resist = True
                resist_label = f"dekat resist {r['price']}"
                break

        # Check if beyond last resistance
        max_resist = max([r["price"] for r in levels["resistances"]]) if levels["resistances"] else 0
        beyond_last_resist = tp_val > max_resist

        if beyond_last_resist:
            note = "breakout — open upside"
        elif near_resist:
            note = resist_label
        else:
            note = "open — no nearby resistance"

        result.append({
            "label": tp_label,
            "price": round_to_tick(tp_val),
            "note": note,
        })

    return result


def determine_timing(full_df, setup):
    last = full_df.iloc[-1]
    prev = full_df.iloc[-2] if len(full_df) >= 2 else last

    # Get momentum indicators
    rsi = last.get('rsi', 50)
    stoch_k = last.get('stoch_k', 50)
    macd_hist = last.get('macd_histogram', 0)

    if setup == "PRE_BREAKOUT":
        vol_ok = last.get('volume_pre_breakout', False)
        above_mid = last['Close'] > last.get('donchian_mid', 0)
        don_mid = last.get('donchian_mid', 0)
        rsi_ok = rsi > 50  # momentum naik

        if vol_ok and above_mid and rsi_ok:
            return {
                "label": "ENTRY_READY",
                "detail": f"Siap masuk! Volume naik, harga di atas tengah, RSI {rsi:.0f}",
                "target_price": None,
                "confirmation_type": "",
                "confirmation_value": None,
            }
        elif vol_ok and above_mid:
            return {
                "label": "WAIT_MOMENTUM",
                "detail": f"Volume OK, harga OK, tapi RSI {rsi:.0f} < 50. Tunggu momentum naik",
                "target_price": None,
                "confirmation_type": "RSI",
                "confirmation_value": 50,
            }
        elif vol_ok:
            return {
                "label": "WAIT_PRICE",
                "detail": f"Tunggu harga naik di atas {don_mid:.0f}",
                "target_price": don_mid,
                "confirmation_type": "Price",
                "confirmation_value": don_mid,
            }
        else:
            vol_ma = last.get('volume_ma', 0)
            return {
                "label": "WAIT_VOLUME",
                "detail": f"Tunggu volume naik di atas {vol_ma:.0f}",
                "target_price": None,
                "confirmation_type": "Volume",
                "confirmation_value": vol_ma,
            }

    elif setup == "BREAKOUT":
        macd_ok = macd_hist > 0
        if last.get('fresh_breakout', False) and macd_ok:
            return {
                "label": "ENTRY_READY",
                "detail": f"Breakout + MACD positif! Siap masuk",
                "target_price": None,
                "confirmation_type": "",
                "confirmation_value": None,
            }
        elif last.get('fresh_breakout', False):
            return {
                "label": "WAIT_MACD",
                "detail": f"Breakout terdeteksi tapi MACD belum konfirmasi (hist: {macd_hist:.2f})",
                "target_price": None,
                "confirmation_type": "MACD",
                "confirmation_value": 0,
            }
        elif last.get('donchian_breakout', False):
            don_upper = last.get('donchian_upper', 0)
            return {
                "label": "WAIT_RETEST",
                "detail": f"Tunggu harga kembali ke {don_upper:.0f}",
                "target_price": don_upper,
                "confirmation_type": "Price",
                "confirmation_value": don_upper,
            }
        return {"label": "WAIT", "detail": "Tunggu breakout baru", "target_price": None, "confirmation_type": "", "confirmation_value": None}

    elif setup == "ACCUMULATION":
        don_lower = last.get('donchian_lower', 0)
        near_lower = last['Close'] <= don_lower * 1.02
        rsi_oversold = rsi < 30
        stoch_oversold = stoch_k < 20

        if near_lower and (rsi_oversold or stoch_oversold):
            return {
                "label": "ENTRY_READY",
                "detail": f"Harga di batas bawah + oversold (RSI {rsi:.0f}, Stoch {stoch_k:.0f})",
                "target_price": None,
                "confirmation_type": "",
                "confirmation_value": None,
            }
        elif near_lower:
            return {
                "label": "WAIT_MOMENTUM",
                "detail": f"Harga di bawah tapi belum oversold (RSI {rsi:.0f}). Tunggu konfirmasi momentum",
                "target_price": None,
                "confirmation_type": "RSI",
                "confirmation_value": 30,
            }
        else:
            return {
                "label": "WAIT_PULLBACK",
                "detail": f"Tunggu harga turun ke {don_lower:.0f}",
                "target_price": don_lower,
                "confirmation_type": "Price",
                "confirmation_value": don_lower,
            }

    elif setup == "EARLY_REVERSAL":
        st_bullish = last.get('supertrend_bullish', False)
        st_prev_bullish = prev.get('supertrend_dir', -1) > 0 if 'supertrend_dir' in prev else False
        ma20 = last.get('ma20', 0)

        # Leading: Divergence detection
        rsi_bull_div = last.get('rsi_bullish_div', False)
        macd_bull_div = last.get('macd_bullish_div', False)
        stoch_bull_cross = last.get('stoch_bullish_cross', False)
        macd_bull_cross = last.get('macd_bullish_cross', False)

        fresh_st_flip = st_bullish and not st_prev_bullish
        divergence_signal = (rsi_bull_div or macd_bull_div) and (stoch_bull_cross or macd_bull_cross)

        if fresh_st_flip or divergence_signal:
            signal_type = "SuperTrend flip" if fresh_st_flip else "Divergence terdeteksi"
            return {
                "label": "ENTRY_READY",
                "detail": f"{signal_type}! Siap masuk (RSI {rsi:.0f})",
                "target_price": None,
                "confirmation_type": "",
                "confirmation_value": None,
            }
        elif st_bullish:
            return {
                "label": "WAIT_PULLBACK",
                "detail": f"Tunggu harga turun ke MA20 ({ma20:.0f})",
                "target_price": ma20,
                "confirmation_type": "Price",
                "confirmation_value": ma20,
            }
        return {
            "label": "WAIT_CONFIRMATION",
            "detail": f"Tunggu konfirmasi tren berbalik naik (RSI {rsi:.0f}, Stoch {stoch_k:.0f})",
            "target_price": None,
            "confirmation_type": "RSI",
            "confirmation_value": 50,
        }

    elif setup == "VCP":
        bb_width = last.get('bb_width', 0)
        bb_width_prev = prev.get('bb_width', 999) if len(full_df) >= 2 else 999
        contracting = bb_width < bb_width_prev
        vol_ma = last.get('volume_ma', 0)
        vol_low = vol_ma > 0 and last.get('Volume', 0) < vol_ma * 0.8
        stoch_ready = stoch_k < 20 or rsi < 45

        if contracting and vol_low and stoch_ready:
            return {
                "label": "ENTRY_READY",
                "detail": f"Harga tenang, volume rendah, momentum siap (Stoch {stoch_k:.0f})",
                "target_price": None,
                "confirmation_type": "",
                "confirmation_value": None,
            }
        elif contracting and vol_low:
            return {
                "label": "WAIT_MOMENTUM",
                "detail": f"Kontraksi OK, volume OK, tapi Stoch {stoch_k:.0f} belum oversold",
                "target_price": None,
                "confirmation_type": "Stoch",
                "confirmation_value": 20,
            }
        elif contracting:
            return {
                "label": "WAIT_VOLUME",
                "detail": f"Tunggu volume turun di bawah {vol_ma * 0.8:.0f}",
                "target_price": None,
                "confirmation_type": "Volume",
                "confirmation_value": vol_ma * 0.8,
            }
        return {"label": "WAIT", "detail": "Tunggu harga mulai tenang", "target_price": None, "confirmation_type": "", "confirmation_value": None}

    elif setup == "TIGHT_BASE_BREAKOUT":
        inside_bars = last.get('consecutive_inside', 0)
        breakout_ready = inside_bars >= 3
        rsi_neutral = 40 <= rsi <= 60

        if breakout_ready and rsi_neutral:
            return {
                "label": "ENTRY_READY",
                "detail": f"{inside_bars} inside bars + RSI netral ({rsi:.0f}), siap breakout",
                "target_price": None,
                "confirmation_type": "",
                "confirmation_value": None,
            }
        elif breakout_ready:
            return {
                "label": "WAIT_MOMENTUM",
                "detail": f"Inside bars OK tapi RSI {rsi:.0f} belum netral",
                "target_price": None,
                "confirmation_type": "RSI",
                "confirmation_value": 50,
            }
        return {
            "label": "WAIT",
            "detail": f"Inside bars: {inside_bars}/3 minimum",
            "target_price": None,
            "confirmation_type": "",
            "confirmation_value": None,
        }

    elif setup == "BASE_ON_BASE":
        don_mid = last.get('donchian_mid', 0)
        above_mid = last['Close'] > don_mid

        if above_mid:
            return {
                "label": "ENTRY_READY",
                "detail": "Harga di atas base, siap masuk",
                "target_price": None,
                "confirmation_type": "",
                "confirmation_value": None,
            }
        return {
            "label": "WAIT_PRICE",
            "detail": f"Tunggu harga naik di atas {don_mid:.0f}",
            "target_price": don_mid,
            "confirmation_type": "Price",
            "confirmation_value": don_mid,
        }

    elif setup == "BULL_FLAG":
        ma20_val = last.get('ma20', last['Close'])
        near_ma20 = abs(last['Close'] - ma20_val) / last['Close'] < 0.05 if last['Close'] > 0 else False
        vol_declining = last.get('Volume', 0) < last.get('volume_ma', last['Close']) * 0.8 if last.get('volume_ma', 0) > 0 else False
        rsi_healthy = rsi > 40

        if near_ma20 and vol_declining and rsi_healthy:
            return {
                "label": "ENTRY_READY",
                "detail": f"Harga bounce di MA20, volume rendah, RSI sehat ({rsi:.0f})",
                "target_price": None,
                "confirmation_type": "",
                "confirmation_value": None,
            }
        elif near_ma20 and vol_declining:
            return {
                "label": "WAIT_MOMENTUM",
                "detail": f"MA20 + volume OK, tapi RSI {rsi:.0f} lemah",
                "target_price": None,
                "confirmation_type": "RSI",
                "confirmation_value": 40,
            }
        elif vol_declining:
            return {
                "label": "WAIT_PULLBACK",
                "detail": f"Tunggu harga turun ke MA20 ({ma20_val:.0f})",
                "target_price": ma20_val,
                "confirmation_type": "Price",
                "confirmation_value": ma20_val,
            }
        return {"label": "WAIT", "detail": "Tunggu flag terbentuk", "target_price": None, "confirmation_type": "", "confirmation_value": None}

    elif setup == "PULLBACK_MA20":
        ma20 = last.get('ma20', 0)
        ma20_rising = last.get('ma20_slope', 0) > 0
        near_ma20 = abs(last['Close'] - ma20) / ma20 < 0.03 if ma20 > 0 else False
        rsi_oversold = rsi < 30
        stoch_bull_cross = last.get('stoch_bullish_cross', False)
        momentum_bounce = rsi_oversold or stoch_bull_cross

        if near_ma20 and ma20_rising and momentum_bounce:
            return {
                "label": "ENTRY_READY",
                "detail": f"Harga bounce di MA20 + momentum oversold (RSI {rsi:.0f})",
                "target_price": None,
                "confirmation_type": "",
                "confirmation_value": None,
            }
        elif near_ma20 and ma20_rising:
            return {
                "label": "WAIT_MOMENTUM",
                "detail": f"MA20 OK tapi RSI {rsi:.0f} belum oversold",
                "target_price": None,
                "confirmation_type": "RSI",
                "confirmation_value": 30,
            }
        elif ma20_rising:
            return {
                "label": "WAIT_PULLBACK",
                "detail": f"Tunggu harga turun ke MA20 ({ma20:.0f})",
                "target_price": ma20,
                "confirmation_type": "Price",
                "confirmation_value": ma20,
            }
        return {"label": "WAIT", "detail": "Tunggu MA20 mulai naik", "target_price": None, "confirmation_type": "", "confirmation_value": None}

    return {"label": "HOLD", "detail": "", "target_price": None, "confirmation_type": "", "confirmation_value": None}


def generate_ascii_chart(close, entry_zone, sl_normal, sl_wide, tp_analysis, levels):
    chart_width = 50
    lines = []

    # Collect all relevant prices
    prices = [close, entry_zone["low"], entry_zone["high"],
              sl_normal, sl_wide["price"]]
    labels = {}

    for ta in tp_analysis:
        prices.append(ta["price"])
        labels[ta["price"]] = ta["label"]

    for s in levels["supports"][:3]:
        prices.append(s["price"])
        labels[s["price"]] = f"Supp {s['strength']}x"
    for r in levels["resistances"][:3]:
        prices.append(r["price"])
        labels[r["price"]] = f"Res {r['strength']}x"

    prices = sorted(set(p for p in prices if p > 0 and not np.isnan(p) and not np.isinf(p)))
    if not prices:
        return ""

    price_min, price_max = prices[0], prices[-1]
    range_p = price_max - price_min
    if range_p == 0:
        return ""

    # Show ~12 price levels
    step = max(1, len(prices) // 12)
    displayed = prices[::step]
    if displayed[-1] != prices[-1]:
        displayed.append(prices[-1])

    for p in displayed:
        label = labels.get(p, "")
        marker = " "

        if entry_zone["low"] <= p <= entry_zone["high"]:
            if entry_zone["low"] < p < entry_zone["high"]:
                marker = "▓"
            else:
                marker = "▒"

        prefix = " "
        if p == sl_normal:
            prefix = "SL1"
        elif p == sl_wide["price"]:
            prefix = "SL2"
        elif p == close:
            prefix = "▸▸"

        lbl = f"  {label}" if label else ""
        line = f"  {prefix:>4s} {p:>8.0f}  {marker * 10}{lbl}"
        lines.append(line)

    # Add entry zone bracket only if we have the right prices
    if entry_zone["low"] in prices and entry_zone["high"] in prices:
        pass

    chart_lines = [
        f"  {close:.0f} ─── Price (current)",
        f"  Entry Zone: {entry_zone['low']} - {entry_zone['high']} ({entry_zone['strategy']})",
        f"  SL1 (Normal): {sl_normal} | SL2 (Wide): {sl_wide['price']}",
        "",
    ]

    for ta in tp_analysis:
        chart_lines.append(f"  {ta['label']}: {ta['price']} — {ta['note']}")

    chart_lines.append("")
    chart_lines.append("  Levels:")
    for p in displayed[-8:]:
        lbl = labels.get(p, "")
        if lbl:
            chart_lines.append(f"    {p:.0f}  {lbl}")

    chart_lines.append("")
    chart_lines.append(f"  Entry Conditions:")
    for c in entry_zone["conditions"]:
        chart_lines.append(f"    ✓ {c}")

    return "\n".join(chart_lines)


def generate_deep_analysis(full_df, setup, close, atr_val, custom_params=None):
    p = custom_params or {}
    sl_mult = p.get("sl_multiplier", SL_MULTIPLIER)
    rr1 = p.get("rr1", RR1)
    rr2 = p.get("rr2", RR2)
    rr3 = p.get("rr3", RR3)

    levels = find_key_levels(full_df, atr_val)
    entry_zone = determine_entry_zone(full_df, levels, setup, close, atr_val)

    # Gunakan midpoint entry zone sebagai acuan SL & TP
    entry_mid = (entry_zone["low"] + entry_zone["high"]) / 2
    ref_price = max(entry_mid, close * 0.92)  # Jangan terlalu jauh dari harga aktual

    sl_normal = round_to_tick(ref_price - atr_val * sl_mult)
    risk = abs(ref_price - sl_normal)
    tp1 = round_to_tick(ref_price + risk * rr1)
    tp2 = round_to_tick(ref_price + risk * rr2)
    tp3 = round_to_tick(ref_price + risk * rr3)

    # Pastikan TP selalu di atas harga saat ini (untuk long setups)
    if tp1 <= close:
        sl_normal = round_to_tick(close - atr_val * sl_mult)
        risk = close - sl_normal
        tp1 = round_to_tick(close + risk * rr1)
        tp2 = round_to_tick(close + risk * rr2)
        tp3 = round_to_tick(close + risk * rr3)
        ref_price = close

    # ── Enforce: SL must be below entry zone ──
    entry_low = entry_zone["low"]
    entry_high = entry_zone["high"]
    zone_width = entry_high - entry_low
    min_sl = entry_low - zone_width * 0.20
    if sl_normal >= entry_low:
        sl_normal = round_to_tick(min_sl)
        risk = abs(ref_price - sl_normal)
        tp1 = round_to_tick(ref_price + risk * rr1)
        tp2 = round_to_tick(ref_price + risk * rr2)
        tp3 = round_to_tick(ref_price + risk * rr3)

    # ── Enforce: SL must be below entry price (close) ──
    if sl_normal >= close:
        sl_normal = round_to_tick(close - atr_val * sl_mult)
        risk = abs(close - sl_normal)
        tp1 = round_to_tick(close + risk * rr1)
        tp2 = round_to_tick(close + risk * rr2)
        tp3 = round_to_tick(close + risk * rr3)
        ref_price = close

    sl_wide = determine_sl_wide(full_df, levels, ref_price, atr_val, sl_normal, sl_mult)
    tp_analysis = analyze_tp_targets(tp1, tp2, tp3, ref_price, levels)
    timing = determine_timing(full_df, setup)

    # Reconcile entry strategy with timing
    if timing["label"] == "ENTRY_READY":
        ready_strategies = {
            "BASE_ON_BASE": "Breakout dari base — entry zone aktif",
            "BULL_FLAG": "Bounce di MA20 — entry zone aktif",
            "PULLBACK_MA20": "Bounce di MA20 — entry zone aktif",
            "ACCUMULATION": "Support + oversold — entry zone aktif",
            "EARLY_REVERSAL": "Reversal terkonfirmasi — entry zone aktif",
            "PRE_BREAKOUT": "Momentum naik — entry zone aktif",
            "BREAKOUT": "Breakout terkonfirmasi — entry zone aktif",
            "VCP": "Kontraksi selesai — entry zone aktif",
            "TIGHT_BASE_BREAKOUT": "Base siap breakout — entry zone aktif",
        }
        entry_zone["strategy"] = ready_strategies.get(setup, "Entry zone aktif — siap masuk")

    # Recalculate profit/risk dari harga aktual
    risk_pct = abs(close - sl_normal) / close * 100
    profit_pct = abs(tp1 - close) / close * 100

    chart = generate_ascii_chart(close, entry_zone, sl_normal, sl_wide, tp_analysis, levels)

    return {
        "entry_zone": entry_zone,
        "sl_normal": sl_normal,
        "sl_wide": sl_wide,
        "tp_analysis": tp_analysis,
        "timing": timing,
        "chart": chart,
        "levels": levels,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "risk_pct": round(risk_pct, 2),
        "profit_pct": round(profit_pct, 2),
    }
