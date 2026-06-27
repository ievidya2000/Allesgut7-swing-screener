import numpy as np
import pandas as pd

from config import (
    ATR_LENGTH, ATR_MULTIPLIER, SL_MULTIPLIER,
    RR1, RR2, RR3, FRESH_SIGNAL_BARS
)
from indicators import get_atr, get_supertrend


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
        result.append({"price": round(avg_p, 2), "strength": strength,
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

    return [{"price": round(p, 2), "strength": 1, "source": "fib"} for p in set(levels)]


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

    if setup == "PRE_BREAKOUT":
        mid = full_df['donchian_mid'].iloc[-1]
        upper = full_df['donchian_upper'].iloc[-1]
        ma20 = full_df['Close'].rolling(20).mean().iloc[-1]

        zone_low = max(mid, ma20) if pd.notna(ma20) else mid
        zone_high = upper - atr_val * 0.3

        entry_low = round(zone_low, 2)
        entry_high = round(zone_high, 2)

        strategy = "Limit di zona konsolidasi"
        conditions = [
            "Volume > MA20",
            "Close > Donchian Mid",
            "ADX rising",
        ]

    elif setup == "BREAKOUT":
        upper = full_df['donchian_upper'].iloc[-1]
        entry_low = round(upper - atr_val * 0.5, 2)
        entry_high = round(upper + atr_val * 0.5, 2)
        strategy = "Market on confirmation / Limit on retest"
        conditions = [
            "Volume > 150% MA20",
            "Close in upper 25% candle",
            "No gap fill",
        ]

    elif setup == "ACCUMULATION":
        lower = full_df['donchian_lower'].iloc[-1]
        mid = full_df['donchian_mid'].iloc[-1]

        best_support = lower
        for s in levels["supports"]:
            if s["high"] >= lower and s["low"] <= mid:
                best_support = max(best_support, s["price"])

        entry_low = round(min(best_support, mid), 2)
        entry_high = round(max(best_support, mid), 2)
        strategy = "Limit di support — range bound"
        conditions = [
            "Price touch lower band",
            "Volume contraction on pullback",
            "Oversold RSI (optional)",
        ]

    elif setup == "VCP":
        bb_mid = full_df['Close'].rolling(20).mean().iloc[-1] if len(full_df) >= 20 else close
        bb_lower = bb_mid - atr_val * 1.5
        bb_upper = bb_mid + atr_val * 1.5

        entry_low = round(bb_lower, 2)
        entry_high = round(bb_mid, 2)
        strategy = "Limit saat volatilitas menyusut — tunggu expansion"
        conditions = [
            "BB width menyusut",
            "Volume decline 3+ bars",
            "Wait for volume spike",
        ]

    elif setup == "TIGHT_BASE_BREAKOUT":
        upper = full_df['donchian_upper'].iloc[-1]
        entry_low = round(upper - atr_val * 0.3, 2)
        entry_high = round(upper + atr_val * 0.3, 2)
        strategy = "Market on breakout / Limit on retest"
        conditions = [
            "Tight range < 5%",
            "Inside bars",
            "Volume dry",
        ]

    elif setup == "BASE_ON_BASE":
        mid = full_df['donchian_mid'].iloc[-1]
        upper = full_df['donchian_upper'].iloc[-1]
        entry_low = round(mid, 2)
        entry_high = round(upper, 2)
        strategy = "Limit di atas base kedua — tunggu breakout"
        conditions = [
            "Two stacked bases",
            "Breakout from base 2",
            "Higher base structure",
        ]

    elif setup == "BULL_FLAG":
        ma20 = full_df['Close'].rolling(20).mean().iloc[-1] if len(full_df) >= 20 else close
        entry_low = round(ma20 - atr_val * 0.3, 2)
        entry_high = round(ma20, 2)
        strategy = "Limit di flag pullback — tunggu bounce"
        conditions = [
            "Flagpole > 15%",
            "Flag < 12%",
            "Declining volume in flag",
        ]

    elif setup == "PULLBACK_MA20":
        ma20 = full_df['Close'].rolling(20).mean().iloc[-1] if len(full_df) >= 20 else close
        entry_low = round(ma20 - atr_val * 0.2, 2)
        entry_high = round(ma20 + atr_val * 0.2, 2)
        strategy = "Limit di MA20 — bounce confirmation"
        conditions = [
            "MA20 rising",
            "Bounce on MA20",
            "Prior uptrend strength",
        ]

    elif setup == "EARLY_REVERSAL":
        ma20 = full_df['Close'].rolling(20).mean().iloc[-1] if len(full_df) >= 20 else close
        recent_swing_low = full_df['Low'].tail(15).min()
        sl_normal = round(close - atr_val * 1.5, 2)

        zone_low = recent_swing_low + atr_val * 1.0
        zone_high = min(ma20, close) if pd.notna(ma20) else close

        # Entry zone must be above SL
        min_entry = sl_normal + atr_val * 0.3
        if zone_low < min_entry:
            zone_low = min_entry
        if zone_high < zone_low:
            zone_high = zone_low + atr_val * 0.5

        entry_low = round(zone_low, 2)
        entry_high = round(zone_high, 2)
        strategy = "Limit pada pullback — confirmation needed"
        conditions = [
            "Close > previous candle high",
            "Volume confirmation",
            "SuperTrend tetap bullish",
        ]

    # Ensure low < high
    if entry_low > entry_high:
        entry_low, entry_high = entry_high, entry_low
    if entry_low == entry_high:
        entry_high = round(entry_low + atr_val * 0.3, 2)

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
    sl_by_atr = round(sl_by_atr, 2)

    # Structural: below nearest support
    best_support = None
    for s in levels["supports"]:
        if s["price"] < close:
            if best_support is None or s["price"] > best_support:
                best_support = s["price"]

    if best_support is not None:
        # Slightly below support
        sl_structural = round(best_support - atr_val * 0.3, 2)
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
            "price": round(tp_val, 2),
            "note": note,
        })

    return result


def determine_timing(full_df, setup):
    last = full_df.iloc[-1]
    prev = full_df.iloc[-2] if len(full_df) >= 2 else last

    if setup == "PRE_BREAKOUT":
        vol_ok = last.get('volume_pre_breakout', False)
        above_mid = last['Close'] > last.get('donchian_mid', 0)

        if vol_ok and above_mid:
            return {
                "label": "ENTRY_READY",
                "detail": "Volume confirmation + price above Donchian mid",
            }
        elif vol_ok:
            return {
                "label": "WAIT_PRICE",
                "detail": f"Tunggu harga > Donchian mid ({last['donchian_mid']:.0f})",
            }
        else:
            return {
                "label": "WAIT_VOLUME",
                "detail": "Tunggu volume > MA20 + MA5 rising",
            }

    elif setup == "BREAKOUT":
        if last.get('fresh_breakout', False):
            return {
                "label": "ENTRY_READY",
                "detail": "Fresh breakout terdeteksi — entry market di konfirmasi",
            }
        elif last.get('donchian_breakout', False):
            return {
                "label": "WAIT_RETEST",
                "detail": f"Tunggu pullback ke Donchian upper ({last['donchian_upper']:.0f})",
            }
        return {"label": "WAIT", "detail": "Menunggu breakout baru"}

    elif setup == "ACCUMULATION":
        near_lower = last['Close'] <= last.get('donchian_lower', 0) * 1.02
        if near_lower:
            return {
                "label": "ENTRY_READY",
                "detail": "Price near lower band — limit order siap",
            }
        else:
            return {
                "label": "WAIT_PULLBACK",
                "detail": f"Tunggu pullback ke Donchian lower ({last['donchian_lower']:.0f})",
            }

    elif setup == "EARLY_REVERSAL":
        st_bullish = last.get('supertrend_bullish', False)
        st_prev_bullish = prev.get('supertrend_dir', -1) > 0 if 'supertrend_dir' in prev else False

        if st_bullish and not st_prev_bullish:
            return {
                "label": "ENTRY_READY",
                "detail": "SuperTrend baru flip bullish — entry on confirmation",
            }
        elif st_bullish:
            return {
                "label": "WAIT_PULLBACK",
                "detail": "Cari pullback ke AVWAP / MA20 untuk entry",
            }
        return {
            "label": "WAIT_CONFIRMATION",
            "detail": "Tunggu SuperTrend flip + volume confirmation",
        }

    elif setup == "VCP":
        bb_width = last.get('bb_width', 0)
        bb_width_prev = prev.get('bb_width', 999) if len(full_df) >= 2 else 999
        contracting = bb_width < bb_width_prev
        vol_low = last.get('volume_ma', 0) > 0 and last.get('Volume', 0) < last.get('volume_ma', 0) * 0.8

        if contracting and vol_low:
            return {
                "label": "ENTRY_READY",
                "detail": "Volatilitas menyusut + volume rendah — siap untuk entry",
            }
        elif contracting:
            return {
                "label": "WAIT_VOLUME",
                "detail": "Kontraksi volatilitas aktif — tunggu volume kering",
            }
        return {"label": "WAIT", "detail": "Tunggu volatilitas mulai menyusut"}

    elif setup == "TIGHT_BASE_BREAKOUT":
        inside_bars = last.get('consecutive_inside', 0)
        breakout_ready = inside_bars >= 3

        if breakout_ready:
            return {
                "label": "ENTRY_READY",
                "detail": f"{inside_bars} inside bars — breakout siap",
            }
        return {
            "label": "WAIT",
            "detail": f"Inside bars: {inside_bars}/3 minimum",
        }

    elif setup == "BASE_ON_BASE":
        above_mid = last['Close'] > last.get('donchian_mid', 0)

        if above_mid:
            return {
                "label": "ENTRY_READY",
                "detail": "Harga di atas base — tunggu breakout confirmation",
            }
        return {
            "label": "WAIT_PRICE",
            "detail": f"Tunggu harga > Donchian mid ({last.get('donchian_mid', 0):.0f})",
        }

    elif setup == "BULL_FLAG":
        ma20_val = last.get('ma20', last['Close'])
        near_ma20 = abs(last['Close'] - ma20_val) / last['Close'] < 0.05 if last['Close'] > 0 else False
        vol_declining = last.get('Volume', 0) < last.get('volume_ma', last['Close']) * 0.8 if last.get('volume_ma', 0) > 0 else False

        if near_ma20 and vol_declining:
            return {
                "label": "ENTRY_READY",
                "detail": "Flag pullback ke MA20 + volume rendah",
            }
        elif vol_declining:
            return {
                "label": "WAIT_PULLBACK",
                "detail": "Volume sudah rendah — tunggu pullback ke MA20",
            }
        return {"label": "WAIT", "detail": "Tunggu flag terbentuk + volume decline"}

    elif setup == "PULLBACK_MA20":
        ma20 = last.get('ma20', 0)
        ma20_rising = last.get('ma20_slope', 0) > 0
        near_ma20 = abs(last['Close'] - ma20) / ma20 < 0.03 if ma20 > 0 else False

        if near_ma20 and ma20_rising:
            return {
                "label": "ENTRY_READY",
                "detail": "Bounce di MA20 + MA20 rising",
            }
        elif ma20_rising:
            return {
                "label": "WAIT_PULLBACK",
                "detail": "MA20 rising — tunggu pullback ke MA20",
            }
        return {"label": "WAIT", "detail": "Tunggu MA20 mulai rising"}

    return {"label": "HOLD", "detail": ""}


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

    sl_normal = round(ref_price - atr_val * sl_mult, 2)
    risk = abs(ref_price - sl_normal)
    tp1 = round(ref_price + risk * rr1, 2)
    tp2 = round(ref_price + risk * rr2, 2)
    tp3 = round(ref_price + risk * rr3, 2)

    # Pastikan TP selalu di atas harga saat ini (untuk long setups)
    if tp1 <= close:
        sl_normal = round(close - atr_val * sl_mult, 2)
        risk = close - sl_normal
        tp1 = round(close + risk * rr1, 2)
        tp2 = round(close + risk * rr2, 2)
        tp3 = round(close + risk * rr3, 2)
        ref_price = close

    # ── Enforce: SL must be below entry zone ──
    entry_low = entry_zone["low"]
    entry_high = entry_zone["high"]
    zone_width = entry_high - entry_low
    min_sl = entry_low - zone_width * 0.20
    if sl_normal >= entry_low:
        sl_normal = round(min_sl, 2)
        risk = abs(ref_price - sl_normal)
        tp1 = round(ref_price + risk * rr1, 2)
        tp2 = round(ref_price + risk * rr2, 2)
        tp3 = round(ref_price + risk * rr3, 2)

    # ── Enforce: SL must be below entry price (close) ──
    if sl_normal >= close:
        sl_normal = round(close - atr_val * sl_mult, 2)
        risk = abs(close - sl_normal)
        tp1 = round(close + risk * rr1, 2)
        tp2 = round(close + risk * rr2, 2)
        tp3 = round(close + risk * rr3, 2)
        ref_price = close

    sl_wide = determine_sl_wide(full_df, levels, ref_price, atr_val, sl_normal, sl_mult)
    tp_analysis = analyze_tp_targets(tp1, tp2, tp3, ref_price, levels)
    timing = determine_timing(full_df, setup)

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
