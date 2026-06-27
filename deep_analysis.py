import numpy as np
import pandas as pd
import yfinance as yf

from indicators import (
    get_supertrend, get_ichimoku, rma, calculate_full_indicators
)
from signals import determine_stock_regime, classify_setup_state
from analysis import generate_deep_analysis
from patterns import detect_patterns
from data import normalize_yfinance_df
from config import ATR_LENGTH, ATR_MULTIPLIER


def _validate_ohlc(df):
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        level_0 = df.columns.get_level_values(0)
        level_1 = df.columns.get_level_values(1)
        if "Close" in level_0:
            df.columns = level_0
        elif "Close" in level_1:
            df.columns = level_1
        else:
            return None
    required = ["Open", "High", "Low", "Close", "Volume"]
    if not all(c in df.columns for c in required):
        return None
    return df[required].dropna(how="all")


def multi_timeframe_analysis(ticker):
    result = {"weekly": {}, "daily": {}, "alignment": ""}

    try:
        wk = yf.download(ticker, period="1y", interval="1wk",
                         auto_adjust=False, progress=False, threads=False)
        wk = _validate_ohlc(wk)
        if wk is not None and len(wk) >= 8:
            h, l, c = wk['High'], wk['Low'], wk['Close']

            _, st_dir = get_supertrend(h, l, c, ATR_LENGTH, ATR_MULTIPLIER)
            ma20 = c.rolling(20).mean().iloc[-1] if len(c) >= 20 else c.iloc[-1]

            ichi = get_ichimoku(h, l, c)
            above_cloud = ichi['price_above_cloud'].iloc[-1]
            below_cloud = ichi['price_below_cloud'].iloc[-1]

            st_bull = st_dir.iloc[-1] > 0
            price_vs_ma = "ABOVE" if c.iloc[-1] > ma20 else "BELOW"

            if above_cloud and st_bull:
                wk_trend = "BULLISH"
            elif below_cloud and not st_bull:
                wk_trend = "BEARISH"
            else:
                wk_trend = "SIDEWAYS"

            result["weekly"] = {
                "trend": wk_trend,
                "supertrend": "UP" if st_bull else "DOWN",
                "price_vs_ma20": price_vs_ma,
                "ma20": round(ma20, 2) if pd.notna(ma20) else None,
            }
    except Exception:
        result["weekly"] = {"trend": "N/A", "supertrend": "N/A", "price_vs_ma20": "N/A"}

    return result


def volume_profile_analysis(df, bins=10):
    tail = df.tail(30)
    price_min = tail['Low'].min()
    price_max = tail['High'].max()
    range_p = price_max - price_min
    if range_p == 0:
        return {"hvns": [], "current_zone": "N/A"}

    bin_width = range_p / bins
    tail = tail.copy()
    tail['price_bin'] = ((tail['Close'] - price_min) / bin_width).astype(int)
    tail['price_bin'] = tail['price_bin'].clip(0, bins - 1)

    vol_by_bin = tail.groupby('price_bin')['Volume'].sum()
    mean_vol = vol_by_bin.mean()
    hvns = vol_by_bin[vol_by_bin > mean_vol * 1.2]

    zones = []
    for bin_idx in hvns.index:
        zone_low = price_min + bin_idx * bin_width
        zone_high = zone_low + bin_width
        zones.append({
            "low": round(zone_low, 2),
            "high": round(zone_high, 2),
            "volume": int(hvns[bin_idx]),
        })

    current_price = df['Close'].iloc[-1]
    current_bin = int((current_price - price_min) / bin_width) if bin_width > 0 else 0
    current_bin = max(0, min(current_bin, bins - 1))
    is_hvn = current_bin in hvns.index

    return {
        "hvns": zones,
        "current_zone": "HVN" if is_hvn else "low volume zone",
        "current_price": round(current_price, 2),
    }


def trendline_analysis(df):
    tail = df.tail(40)
    h = tail['High'].values
    l = tail['Low'].values
    idx = np.arange(len(tail))

    result = {"uptrend": None, "downtrend": None, "broken_downtrend": None}

    # Find swing lows for uptrend
    window = 5
    swing_lows = []
    for i in range(window, len(tail) - window):
        if l[i] == l[i - window:i + window + 1].min():
            swing_lows.append((i, l[i]))

    if len(swing_lows) >= 2:
        p1, p2 = swing_lows[-2], swing_lows[-1]
        slope = (p2[1] - p1[1]) / max(p2[0] - p1[0], 1)
        if slope > 0:
            extended = p2[1] + slope * (len(tail) - 1 - p2[0])
            result["uptrend"] = {
                "slope": round(slope, 2),
                "start_price": round(p1[1], 2),
                "end_price": round(extended, 2),
                "active": tail['Close'].iloc[-1] >= extended * 0.98,
            }

    # Find swing highs for downtrend
    swing_highs = []
    for i in range(window, len(tail) - window):
        if h[i] == h[i - window:i + window + 1].max():
            swing_highs.append((i, h[i]))

    if len(swing_highs) >= 2:
        p1, p2 = swing_highs[-2], swing_highs[-1]
        slope = (p2[1] - p1[1]) / max(p2[0] - p1[0], 1)
        if slope < 0:
            extended = p2[1] + slope * (len(tail) - 1 - p2[0])
            close = tail['Close'].iloc[-1]
            result["downtrend"] = {
                "slope": round(slope, 2),
                "start_price": round(p1[1], 2),
                "end_price": round(extended, 2),
                "active": close <= extended * 1.02,
                "broken": close > extended * 1.02,
            }

    return result


def risk_scenario_analysis(stock_df, market_df):
    try:
        stock_ret = np.log(stock_df['Close'] / stock_df['Close'].shift(1)).dropna()
        market_ret = np.log(market_df['Close'] / market_df['Close'].shift(1)).dropna()

        common = stock_ret.index.intersection(market_ret.index)
        if len(common) < 20:
            return {"beta": None, "scenarios": []}

        s_ret = stock_ret.loc[common].values
        m_ret = market_ret.loc[common].values

        beta = np.cov(s_ret, m_ret)[0, 1] / np.var(m_ret) if np.var(m_ret) > 0 else 1.0

        current_price = stock_df['Close'].iloc[-1]

        scenarios = []
        for mkt_change in [-0.05, -0.03, -0.02, 0.02, 0.03, 0.05]:
            est_change = beta * mkt_change
            est_price = current_price * (1 + est_change)
            scenarios.append({
                "market": f"{mkt_change * 100:+.0f}%",
                "estimated": f"{est_change * 100:+.1f}%",
                "price": round(est_price, 2),
            })

        return {"beta": round(beta, 2), "scenarios": scenarios}

    except Exception:
        return {"beta": None, "scenarios": []}


def _pad_inner(text, inner_w):
    """Pad text to inner_w width, keeping leading/trailing spaces minimal."""
    visible = len(text)
    if visible >= inner_w:
        return text[:inner_w]
    return text + " " * (inner_w - visible)


def generate_interpretation(full_df, setup, da, mta, vp, tl, rs, patterns, meta):
    last = full_df.iloc[-1]
    close = last['Close']
    lines = []

    # ── 1. Trend Interpretation ──
    st_bull = last.get('supertrend_bullish', False)
    above_cloud = last.get('price_above_cloud', False)
    below_cloud = last.get('price_below_cloud', False)
    adx = last.get('adx', 0)
    don_upper = last.get('donchian_upper', 0)
    don_mid = last.get('donchian_mid', 0)

    trend_parts = []
    if above_cloud and st_bull:
        trend_parts.append("Harga di atas awan Ichimoku dan SuperTrend bullish → tren naik aktif")
    elif below_cloud and not st_bull:
        trend_parts.append("Harga di bawah awan Ichimoku dan SuperTrend bearish → tren turun aktif")
    elif above_cloud and not st_bull:
        trend_parts.append("Harga di atas awan Ichimoku tapi SuperTrend bearish → potensi koreksi dalam tren naik")
    elif below_cloud and st_bull:
        trend_parts.append("Harga di bawah awan Ichimoku tapi SuperTrend bullish → potensi reversal dari tren turun")
    else:
        trend_parts.append("Harga di dalam awan Ichimoku → tren tidak jelas, konsolidasi")

    if adx > 25:
        trend_parts.append(f"ADX {adx:.1f} → tren kuat")
    elif adx > 18:
        trend_parts.append(f"ADX {adx:.1f} → tren moderat")
    else:
        trend_parts.append(f"ADX {adx:.1f} → tren lemah")

    if don_upper and close:
        pct_to_upper = (don_upper - close) / close * 100
        if pct_to_upper < 2:
            trend_parts.append(f"Harga mendekat Donchian upper ({don_upper:.0f}), {pct_to_upper:.1f}% lagi → resistensi terdekat")
        else:
            trend_parts.append(f"Donchian upper ({don_upper:.0f}) sebagai resistensi, {pct_to_upper:.1f}% di atas harga")

    wk = mta.get("weekly", {})
    if wk.get("trend") and wk["trend"] != "N/A":
        if wk["trend"] == "BULLISH":
            trend_parts.append(f"Weekly trend BULLISH (SuperTrend {wk['supertrend']}) → mendukung posisi long")
        elif wk["trend"] == "BEARISH":
            trend_parts.append(f"Weekly trend BEARISH → hati-hati, kontra tren weekly")
        else:
            trend_parts.append(f"Weekly SIDEWAYS → tidak ada konfirmasi dari timeframe lebih besar")

    lines.append("TREND:")
    for p in trend_parts:
        lines.append(f"  • {p}")

    # ── 2. Volume Interpretation ──
    vol_parts = []
    vol_expanding = last.get('volume_expanding', False)
    vol_pre_breakout = last.get('volume_pre_breakout', False)
    vol_contraction = last.get('vol_contraction', False)

    if vol_expanding:
        vol_parts.append("Volume di atas MA20 → minat beli meningkat")
    else:
        vol_parts.append("Volume di bawah MA20 → minat beli rendah")

    if vol_pre_breakout:
        vol_parts.append("Volume MA5 di atas MA20 dan rising → pola akumulasi pra-breakout")
    if vol_contraction:
        vol_parts.append("ATR10/ATR50 < 0.8 → volatilitas menyusut, potensi breakout segera")

    if vp.get("current_zone") == "HVN":
        vol_parts.append(f"Harga di zona HVN (high volume node) → area konsolidasi, banyak transaksi di level ini")
    elif vp.get("current_zone") == "low volume zone":
        vol_parts.append(f"Harga di zona low volume → bisa bergerak cepat karena sedikit support/resistance")

    if vp.get("hvns"):
        hvns = vp["hvns"]
        nearest = min(hvns, key=lambda z: abs((z["low"] + z["high"]) / 2 - close))
        vol_parts.append(f"HVN terdekat: {nearest['low']:.0f}-{nearest['high']:.0f} → zona support/resistance kuat")

    lines.append("")
    lines.append("VOLUME:")
    for p in vol_parts:
        lines.append(f"  • {p}")

    # ── 3. Pattern Interpretation ──
    pat_parts = []
    if patterns:
        recent_names = [p[0] for p in patterns[-3:]]
        bullish_patterns = [n for n in recent_names if "Bullish" in n or "Hammer" in n or "Morning" in n or "Piercing" in n or "Soldiers" in n]
        bearish_patterns = [n for n in recent_names if "Bearish" in n or "Shooting" in n or "Evening" in n or "Dark Cloud" in n or "Crows" in n]

        if bullish_patterns and not bearish_patterns:
            pat_parts.append(f"Pola bullish terdeteksi: {', '.join(bullish_patterns)} → tekanan beli")
        elif bearish_patterns and not bullish_patterns:
            pat_parts.append(f"Pola bearish terdeteksi: {', '.join(bearish_patterns)} → tekanan jual")
        elif bullish_patterns and bearish_patterns:
            pat_parts.append(f"Pola campuran: {', '.join(recent_names)} → indecision, tunggu konfirmasi")
        else:
            pat_parts.append(f"Pola netral/inside bar → pasar sedang indecision")

        if meta.get("bars_since_last", 0) > 3:
            pat_parts.append(f"Tidak ada pola signifikan dalam {meta['bars_since_last']} bar terakhir → wait and see")
    else:
        pat_parts.append("Tidak ada pola candlestick signifikan → tidak ada sinyal dari price action")

    lines.append("")
    lines.append("PATTERN:")
    for p in pat_parts:
        lines.append(f"  • {p}")

    # ── 4. Risk Interpretation ──
    risk_parts = []
    beta = rs.get("beta")
    if beta:
        if beta > 1.3:
            risk_parts.append(f"Beta {beta:.2f} → sangat volatile, pergerakan lebih besar dari market")
        elif beta > 1.0:
            risk_parts.append(f"Beta {beta:.2f} → lebih volatile dari market")
        elif beta > 0.7:
            risk_parts.append(f"Beta {beta:.2f} → volatilitas sebanding dengan market")
        else:
            risk_parts.append(f"Beta {beta:.2f} → less volatile dari market, defensif")

    atr = last.get('atr_rm', 0)
    if atr and close:
        atr_pct = atr / close * 100
        risk_parts.append(f"ATR {atr_pct:.1f}% dari harga → volatilitas {'tinggi' if atr_pct > 3 else 'moderat' if atr_pct > 1.5 else 'rendah'}")

    risk_pct = da.get("risk_pct", 0)
    profit_pct = da.get("profit_pct", 0)
    if risk_pct and profit_pct:
        rr = profit_pct / risk_pct if risk_pct > 0 else 0
        risk_parts.append(f"Risk {risk_pct:.1f}% vs Reward {profit_pct:.1f}% (TP1) → R:R = 1:{rr:.2f}")

    sl_normal = da.get("sl_normal", 0)
    if sl_normal and close:
        sl_dist = (close - sl_normal) / close * 100
        risk_parts.append(f"SL normal {sl_normal:.0f} → {sl_dist:.1f}% di bawah harga saat ini")

    lines.append("")
    lines.append("RISK:")
    for p in risk_parts:
        lines.append(f"  • {p}")

    # ── 5. Action Summary ──
    timing = da.get("timing", {})
    timing_label = timing.get("label", "UNKNOWN")
    entry_zone = da.get("entry_zone", {})

    action_parts = []
    action_parts.append(f"Setup: {setup}")

    if timing_label == "ENTRY_READY":
        action_parts.append("Timing: ENTRY READY → kondisi entry terpenuhi")
    elif timing_label in ("WAIT_VOLUME", "WAIT_PRICE", "WAIT_PULLBACK", "WAIT_RETEST", "WAIT_CONFIRMATION"):
        action_parts.append(f"Timing: {timing_label.replace('_', ' ')} → {timing.get('detail', '')}")
    else:
        action_parts.append(f"Timing: {timing_label}")

    if entry_zone.get("low") and entry_zone.get("high"):
        action_parts.append(f"Entry zone: {entry_zone['low']:.0f} - {entry_zone['high']:.0f} ({entry_zone.get('strategy', '')})")

    # Overall assessment
    bullish_signals = 0
    bearish_signals = 0
    if st_bull: bullish_signals += 1
    else: bearish_signals += 1
    if above_cloud: bullish_signals += 1
    elif below_cloud: bearish_signals += 1
    if vol_expanding: bullish_signals += 1
    if vol_contraction: bullish_signals += 1  # positive for breakout
    if patterns:
        last_pat = patterns[-1][0]
        if any(x in last_pat for x in ["Bullish", "Hammer", "Morning", "Piercing", "Soldiers"]):
            bullish_signals += 1
        elif any(x in last_pat for x in ["Bearish", "Shooting", "Evening", "Dark Cloud", "Crows"]):
            bearish_signals += 1
    if wk.get("trend") == "BULLISH": bullish_signals += 1
    elif wk.get("trend") == "BEARISH": bearish_signals += 1

    total = bullish_signals + bearish_signals
    if total > 0:
        bull_pct = bullish_signals / total * 100
        if bull_pct >= 70:
            action_parts.append(f"Kesimpulan: BULLISH ({bullish_signals}/{total} sinyal positif) → mendukung entry long")
        elif bull_pct >= 50:
            action_parts.append(f"Kesimpulan: NETRAL-BULLISH ({bullish_signals}/{total} sinyal positif) → entry dengan caution")
        elif bull_pct >= 30:
            action_parts.append(f"Kesimpulan: NETRAL-BEARISH ({bearish_signals}/{total} sinyal negatif) → pertimbangkan menunggu")
        else:
            action_parts.append(f"Kesimpulan: BEARISH ({bearish_signals}/{total} sinyal negatif) → hindari entry long")

    lines.append("")
    lines.append("ACTION:")
    for p in action_parts:
        lines.append(f"  • {p}")

    return "\n".join(lines)


def generate_report(ticker, df, market_data):
    last = df.iloc[-1]
    lines = []
    W = 74
    IW = W - 2  # inner width

    # Header
    lines.append(f"╔{'═' * IW}╗")
    lines.append(f"║{_pad_inner(f'  {ticker}', IW)}║")
    h2 = f"  Price: {last['Close']:<8.2f} | Close: {df.index[-1].strftime('%d %b %Y')}"
    lines.append(f"║{_pad_inner(h2, IW)}║")
    lines.append(f"╚{'═' * IW}╝")
    lines.append("")

    # Candlestick Patterns
    patterns, meta = detect_patterns(df)
    lines.append(f"┌─ Candlestick Patterns {_pad_inner('', IW - 22)}┐")
    if patterns:
        for name, date, conf in patterns[-6:]:
            bar = "█" * int(conf * 20)
            line = f"  {date:<8s} {name:<22s} {bar:<20s} {conf:.0%}"
            lines.append(f"│{_pad_inner(line, IW)}│")
        if meta["bars_since_last"] > 3:
            note = f"  Last pattern {meta['bars_since_last']} bars ago. No patterns in last {meta['bars_since_last']} bars."
            lines.append(f"│{_pad_inner(note, IW)}│")
    else:
        lines.append(f"│{_pad_inner('  No significant patterns detected in last 7 bars', IW)}│")
    lines.append(f"└{'─' * IW}┘")
    lines.append("")

    # Multi-timeframe
    mta = multi_timeframe_analysis(ticker)
    lines.append(f"┌─ Multi-Timeframe {_pad_inner('', IW - 18)}┐")
    wk = mta["weekly"]
    if wk.get("trend"):
        line = f"  Weekly : SuperTrend {wk['supertrend']:<5s} | MA20: {wk['price_vs_ma20']:<6s} | Trend: {wk['trend']:<8s}"
        lines.append(f"│{_pad_inner(line, IW)}│")
    st_bull = last.get('supertrend_bullish', False)
    daily_trend = "BULLISH" if st_bull else "BEARISH" if last.get('price_below_cloud', False) else "SIDEWAYS"
    line = f"  Daily  : SuperTrend {'UP' if st_bull else 'DOWN':<5s} | Setup: {daily_trend:<8s}"
    lines.append(f"│{_pad_inner(line, IW)}│")
    alignment = "ALIGNED" if wk.get("trend") == daily_trend else "CONFLICT" if wk.get("trend") else "N/A"
    line = f"  Alignment : {alignment}"
    lines.append(f"│{_pad_inner(line, IW)}│")
    lines.append(f"└{'─' * IW}┘")
    lines.append("")

    # Volume Profile
    vp = volume_profile_analysis(df)
    lines.append(f"┌─ Volume Profile (30d) {_pad_inner('', IW - 22)}┐")
    line = f"  Current price: {vp['current_price']:<8.2f} | Zone: {vp['current_zone']:<18s}"
    lines.append(f"│{_pad_inner(line, IW)}│")
    for zone in vp["hvns"][:4]:
        line = f"  HVN: {zone['low']:<8.2f} - {zone['high']:<8.2f}  vol: {zone['volume']:>12,}"
        lines.append(f"│{_pad_inner(line, IW)}│")
    lines.append(f"└{'─' * IW}┘")
    lines.append("")

    # Trendlines
    tl = trendline_analysis(df)
    lines.append(f"┌─ Trendlines {_pad_inner('', IW - 13)}┐")
    if tl.get("uptrend"):
        u = tl["uptrend"]
        status = "ACTIVE" if u["active"] else "BROKEN"
        line = f"  Uptrend  : slope {u['slope']:<+6.2f} | {u['start_price']:<8.2f} -> {u['end_price']:<8.2f} [{status:<6s}]"
        lines.append(f"│{_pad_inner(line, IW)}│")
    else:
        lines.append(f"│{_pad_inner('  Uptrend  : None detected', IW)}│")
    if tl.get("downtrend"):
        d = tl["downtrend"]
        status = "BROKEN" if d.get("broken") else "ACTIVE"
        line = f"  Downtrend: slope {d['slope']:<+6.2f} | {d['start_price']:<8.2f} -> {d['end_price']:<8.2f} [{status:<6s}]"
        if d.get("broken"):
            line += " ^"
        lines.append(f"│{_pad_inner(line, IW)}│")
    else:
        lines.append(f"│{_pad_inner('  Downtrend: None detected', IW)}│")
    lines.append(f"└{'─' * IW}┘")
    lines.append("")

    # Risk Scenario
    jkse = market_data.get("^JKSE") if isinstance(market_data, dict) else None
    if jkse is None:
        try:
            jkse = yf.download("^JKSE", period="1y", interval="1d",
                               auto_adjust=False, progress=False, threads=False)
            jkse = normalize_yfinance_df(jkse)
        except Exception:
            jkse = None

    rs = risk_scenario_analysis(df, jkse) if jkse is not None else {"beta": None, "scenarios": []}
    lines.append(f"┌─ Risk Scenario {_pad_inner('', IW - 16)}┐")
    if rs.get("beta"):
        line = f"  Beta vs IHSG : {rs['beta']:<6.2f}"
        lines.append(f"│{_pad_inner(line, IW)}│")
        for s in rs["scenarios"][:4]:
            line = f"  IHSG {s['market']:<4s} -> stock {s['estimated']:<6s} -> price {s['price']:<8.2f}"
            lines.append(f"│{_pad_inner(line, IW)}│")
    else:
        lines.append(f"│{_pad_inner('  Beta: N/A (insufficient data)', IW)}│")
    lines.append(f"└{'─' * IW}┘")
    lines.append("")

    # ── Interpretation ──
    try:
        from adaptive.config import load_adaptive_config
        adaptive_params = load_adaptive_config()
        full_df = calculate_full_indicators(df, custom_params=adaptive_params)
        last_full = full_df.iloc[-1]
        stock_regime = determine_stock_regime(full_df)
        setup, valid = classify_setup_state(full_df, stock_regime, adaptive_params)
        close = last['Close']
        atr = last_full.get('atr_rm', 0)

        if valid and atr and not pd.isna(atr):
            da = generate_deep_analysis(full_df, setup, close, atr, adaptive_params)
            interp = generate_interpretation(full_df, setup, da, mta, vp, tl, rs, patterns, meta)
            lines.append(f"┌─ INTERPRETASI {_pad_inner('', IW - 16)}┐")
            for line in interp.split("\n"):
                lines.append(f"│{_pad_inner(line, IW)}│")
            lines.append(f"└{'─' * IW}┘")
        else:
            lines.append(f"┌─ INTERPRETASI {_pad_inner('', IW - 16)}┐")
            lines.append(f"│{_pad_inner('  Tidak ada setup aktif untuk interpretasi', IW)}│")
            lines.append(f"└{'─' * IW}┘")
    except Exception as e:
        lines.append(f"┌─ INTERPRETASI {_pad_inner('', IW - 16)}┐")
        lines.append(f"│{_pad_inner(f'  Error: {e}', IW)}│")
        lines.append(f"└{'─' * IW}┘")

    return "\n".join(lines)
