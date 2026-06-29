from datetime import datetime
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


def generate_interpretation(full_df, setup, da, mta, vp, tl, rs, patterns, meta, fundamental_data=None):
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
        trend_parts.append("Harga sedang naik dan momentum positif")
    elif below_cloud and not st_bull:
        trend_parts.append("Harga sedang turun dan momentum negatif")
    elif above_cloud and not st_bull:
        trend_parts.append("Harga masih di atas support tapi momentum mulai melemah")
    elif below_cloud and st_bull:
        trend_parts.append("Harga di bawah resistance tapi momentum mulai naik")
    else:
        trend_parts.append("Harga bergerak datar, belum ada arah jelas")

    if adx > 25:
        trend_parts.append(f"Tren cukup kuat (kekuatan tren: {adx:.0f})")
    elif adx > 18:
        trend_parts.append(f"Tren sedang (kekuatan tren: {adx:.0f})")
    else:
        trend_parts.append(f"Tren lemah (kekuatan tren: {adx:.0f})")

    if don_upper and close:
        pct_to_upper = (don_upper - close) / close * 100
        if pct_to_upper < 2:
            trend_parts.append(f"Batas atas di {don_upper:.0f} ({pct_to_upper:.1f}% dari harga sekarang)")
        else:
            trend_parts.append(f"Batas atas di {don_upper:.0f} ({pct_to_upper:.1f}% di atas harga)")

    wk = mta.get("weekly", {})
    if wk.get("trend") and wk["trend"] != "N/A":
        if wk["trend"] == "BULLISH":
            trend_parts.append("Tren mingguan naik, mendukung posisi beli")
        elif wk["trend"] == "BEARISH":
            trend_parts.append("Tren mingguan turun, hati-hati melawan arah")
        else:
            trend_parts.append("Tren mingguan datar, tidak ada konfirmasi")

    lines.append("KONDISI HARGA:")
    for p in trend_parts:
        lines.append(f"  • {p}")

    # ── 2. Volume Interpretation ──
    vol_parts = []
    vol_expanding = last.get('volume_expanding', False)
    vol_pre_breakout = last.get('volume_pre_breakout', False)
    vol_contraction = last.get('vol_contraction', False)

    # Volume Delta Analysis
    volume_delta = last.get('volume_delta', 0)
    delta_positive = last.get('delta_positive', False)
    obv_rising = last.get('obv_rising', False)
    ad_rising = last.get('ad_rising', False)

    if vol_expanding:
        if delta_positive:
            vol_parts.append(f"Volume tinggi, didominasi pembeli (delta +{volume_delta:,.0f})")
        else:
            vol_parts.append(f"Volume tinggi, didominasi penjual (delta {volume_delta:,.0f})")
    else:
        vol_parts.append("Volume rendah, aktivitas transaksi sedikit")

    # OBV Trend
    if obv_rising:
        vol_parts.append("OBV naik — tekanan beli akumulasi")
    else:
        vol_parts.append("OBV turun — tekanan jual distribusi")

    # A/D Line Trend
    if ad_rising:
        vol_parts.append("A/D Line naik — uang masuk ke saham")
    else:
        vol_parts.append("A/D Line turun — uang keluar dari saham")

    if vol_pre_breakout:
        vol_parts.append("Volume mulai naik, biasanya sebelum harga naik")
    if vol_contraction:
        vol_parts.append("Harga mulai tenang, biasanya sebelum bergerak besar")

    if vp.get("current_zone") == "HVN":
        vol_parts.append("Harga di zona ramai transaksi")
    elif vp.get("current_zone") == "low volume zone":
        vol_parts.append("Harga di zona sepi, bisa naik/turun cepat")

    if vp.get("hvns"):
        hvns = vp["hvns"]
        nearest = min(hvns, key=lambda z: abs((z["low"] + z["high"]) / 2 - close))
        vol_parts.append(f"Zona penting terdekat: {nearest['low']:.0f}-{nearest['high']:.0f}")

    lines.append("")
    lines.append("VOLUME:")
    for p in vol_parts:
        lines.append(f"  • {p}")

    # ── 2b. Momentum Oscillators ──
    mom_parts = []
    rsi = last.get('rsi', 50)
    stoch_k = last.get('stoch_k', 50)
    stoch_d = last.get('stoch_d', 50)
    macd_hist = last.get('macd_histogram', 0)
    rsi_bull_div = last.get('rsi_bullish_div', False)
    macd_bull_div = last.get('macd_bullish_div', False)
    wave_pos = last.get('wave_position', '-')
    fib_382 = last.get('fib_382', 0)
    fib_618 = last.get('fib_618', 0)

    # RSI
    if rsi < 30:
        mom_parts.append(f"RSI {rsi:.0f} — OVERSOLD, potensi bounce")
    elif rsi > 70:
        mom_parts.append(f"RSI {rsi:.0f} — OVERBOUGHT, potensi koreksi")
    else:
        mom_parts.append(f"RSI {rsi:.0f} — netral")

    # Stochastic
    if stoch_k < 20:
        mom_parts.append(f"Stochastic {stoch_k:.0f}/{stoch_d:.0f} — OVERSOLD, siap reversal")
    elif stoch_k > 80:
        mom_parts.append(f"Stochastic {stoch_k:.0f}/{stoch_d:.0f} — OVERBOUGHT")
    else:
        mom_parts.append(f"Stochastic {stoch_k:.0f}/{stoch_d:.0f}")

    # MACD
    if macd_hist > 0:
        mom_parts.append(f"MACD histogram positif — momentum naik")
    else:
        mom_parts.append(f"MACD histogram negatif — momentum turun")

    # Divergence
    if rsi_bull_div:
        mom_parts.append("RSI BULLISH DIVERGENCE — pembalikan naik terdeteksi!")
    if macd_bull_div:
        mom_parts.append("MACD BULLISH DIVERGENCE — pembalikan naik terdeteksi!")

    # Elliott Wave
    mom_parts.append(f"Elliott Wave position: {wave_pos}")
    if fib_618 > 0:
        mom_parts.append(f"Fibonacci levels: 38.2%={fib_382:.0f}, 61.8%={fib_618:.0f}")

    lines.append("")
    lines.append("MOMENTUM:")
    for p in mom_parts:
        lines.append(f"  • {p}")

    # ── 3. Pattern Interpretation ──
    pat_parts = []
    if patterns:
        recent_names = [p[0] for p in patterns[-3:]]
        bullish_patterns = [n for n in recent_names if "Bullish" in n or "Hammer" in n or "Morning" in n or "Piercing" in n or "Soldiers" in n]
        bearish_patterns = [n for n in recent_names if "Bearish" in n or "Shooting" in n or "Evening" in n or "Dark Cloud" in n or "Crows" in n]

        if bullish_patterns and not bearish_patterns:
            pat_parts.append(f"Ada sinyal beli: {', '.join(bullish_patterns)}")
        elif bearish_patterns and not bullish_patterns:
            pat_parts.append(f"Ada sinyal jual: {', '.join(bearish_patterns)}")
        elif bullish_patterns and bearish_patterns:
            pat_parts.append(f"Sinyal campuran: {', '.join(recent_names)}, tunggu konfirmasi")
        else:
            pat_parts.append("Pola netral, pasar sedang menunggu")

        if meta.get("bars_since_last", 0) > 3:
            pat_parts.append(f"Tidak ada pola dalam {meta['bars_since_last']} hari terakhir")
    else:
        pat_parts.append("Tidak ada sinyal beli/jual dari pola candlestick")

    lines.append("")
    lines.append("POLA:")
    for p in pat_parts:
        lines.append(f"  • {p}")

    # ── 4. Fundamental Interpretation ──
    fund_parts = []
    if fundamental_data:
        pe = fundamental_data.get('pe_ratio', 0) or 0
        pb = fundamental_data.get('pb_ratio', 0) or 0
        roe = fundamental_data.get('roe', 0) or 0
        rev_growth = fundamental_data.get('revenue_growth', 0) or 0
        earn_growth = fundamental_data.get('earnings_growth', 0) or 0
        div_yield = fundamental_data.get('dividend_yield', 0) or 0
        mcap = fundamental_data.get('market_cap', 0) or 0

        # Valuasi (PE + PB)
        if pe > 0 and pb > 0:
            if pe < 10:
                fund_parts.append(f"Valuasi murah (PE {pe:.1f}, PB {pb:.1f})")
            elif pe < 20:
                fund_parts.append(f"Valuasi wajar (PE {pe:.1f}, PB {pb:.1f})")
            else:
                fund_parts.append(f"Valuasi mahal (PE {pe:.1f}, PB {pb:.1f})")

        # Profitabilitas (ROE) - stored as decimal (0.22972 = 22.97%)
        if roe > 0:
            roe_pct = roe * 100 if roe < 1 else roe  # Handle both formats
            if roe_pct > 20:
                fund_parts.append(f"Profitabilitas bagus (ROE {roe_pct:.0f}%)")
            elif roe_pct > 10:
                fund_parts.append(f"Profitabilitas sedang (ROE {roe_pct:.0f}%)")
            else:
                fund_parts.append(f"Profitabilitas rendah (ROE {roe_pct:.0f}%)")

        # Pertumbuhan - stored as decimal (0.025 = 2.5%)
        if rev_growth != 0 or earn_growth != 0:
            growth_parts = []
            rev_pct = rev_growth * 100 if abs(rev_growth) < 1 else rev_growth
            earn_pct = earn_growth * 100 if abs(earn_growth) < 1 else earn_growth
            if rev_pct > 0:
                growth_parts.append(f"revenue {rev_pct:.1f}%")
            if earn_pct > 0:
                growth_parts.append(f"earnings {earn_pct:.1f}%")
            if growth_parts:
                fund_parts.append(f"Pertumbuhan {' dan '.join(growth_parts)}")

        # Dividen
        if div_yield > 0:
            if div_yield > 3:
                fund_parts.append(f"Dividen tinggi ({div_yield:.1f}%)")
            elif div_yield > 1:
                fund_parts.append(f"Dividen sedang ({div_yield:.1f}%)")
            else:
                fund_parts.append(f"Dividen rendah ({div_yield:.1f}%)")

        # Market Cap
        if mcap > 0:
            mcap_t = mcap / 1e12
            if mcap_t > 100:
                fund_parts.append(f"Large Cap (Rp {mcap_t:.0f}T)")
            elif mcap_t > 10:
                fund_parts.append(f"Mid Cap (Rp {mcap_t:.0f}T)")
            else:
                fund_parts.append(f"Small Cap (Rp {mcap_t:.1f}T)")

    if fund_parts:
        lines.append("")
        lines.append("FUNDAMENTAL:")
        for p in fund_parts:
            lines.append(f"  • {p}")

    # ── 5. Risk Interpretation ──
    risk_parts = []
    beta = rs.get("beta")
    if beta:
        if beta > 1.3:
            risk_parts.append(f"Sangat volatile (beta {beta:.2f}), pergerakan lebih besar dari IHSG")
        elif beta > 1.0:
            risk_parts.append(f"Lebih volatile dari IHSG (beta {beta:.2f})")
        elif beta > 0.7:
            risk_parts.append(f"Volatilitas sebanding IHSG (beta {beta:.2f})")
        else:
            risk_parts.append(f"Kurang volatile, lebih defensif (beta {beta:.2f})")

    atr = last.get('atr_rm', 0)
    if atr and close:
        atr_pct = atr / close * 100
        vol_desc = 'tinggi' if atr_pct > 3 else 'sedang' if atr_pct > 1.5 else 'rendah'
        risk_parts.append(f"Volatilitas {vol_desc} ({atr_pct:.1f}%)")

    risk_pct = da.get("risk_pct", 0)
    profit_pct = da.get("profit_pct", 0)
    if risk_pct and profit_pct:
        rr = profit_pct / risk_pct if risk_pct > 0 else 0
        risk_parts.append(f"Potensi rugi {risk_pct:.1f}% vs untung {profit_pct:.1f}% (rasio 1:{rr:.1f})")

    sl_normal = da.get("sl_normal", 0)
    if sl_normal and close:
        sl_dist = (close - sl_normal) / close * 100
        risk_parts.append(f"Batas rugi di {sl_normal:.0f} ({sl_dist:.1f}% dari harga)")

    lines.append("")
    lines.append("RISIKO:")
    for p in risk_parts:
        lines.append(f"  • {p}")

    # ── 5. Action Summary ──
    timing = da.get("timing", {})
    timing_label = timing.get("label", "UNKNOWN")
    entry_zone = da.get("entry_zone", {})
    target_price = timing.get("target_price")

    action_parts = []

    if timing_label == "ENTRY_READY":
        action_parts.append("Siap masuk! Semua kondisi sudah terpenuhi")
    elif "WAIT_PULLBACK" in timing_label:
        if target_price:
            action_parts.append(f"Tunggu harga turun ke {target_price:.0f} dulu")
        else:
            action_parts.append("Tunggu harga turun dulu sebelum masuk")
    elif "WAIT_RETEST" in timing_label:
        if target_price:
            action_parts.append(f"Tunggu harga kembali ke {target_price:.0f}")
        else:
            action_parts.append("Tunggu harga test ulang level kunci")
    elif "WAIT_VOLUME" in timing_label:
        action_parts.append("Tunggu volume naik dulu sebelum masuk")
    elif "WAIT_PRICE" in timing_label:
        if target_price:
            action_parts.append(f"Tunggu harga naik di atas {target_price:.0f}")
        else:
            action_parts.append("Tunggu harga bergerak lebih tinggi")
    elif timing_label == "WAIT_CONFIRMATION":
        action_parts.append("Tunggu konfirmasi lebih lanjut")
    else:
        action_parts.append("Belum ada sinyal entry yang jelas")

    if entry_zone.get("low") and entry_zone.get("high"):
        action_parts.append(f"Entry di zona {entry_zone['low']:.0f} - {entry_zone['high']:.0f}")

    # Overall assessment
    bullish_signals = 0
    bearish_signals = 0
    if st_bull: bullish_signals += 1
    else: bearish_signals += 1
    if above_cloud: bullish_signals += 1
    elif below_cloud: bearish_signals += 1
    if vol_expanding: bullish_signals += 1
    if vol_contraction: bullish_signals += 1
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
            action_parts.append(f"Kesimpulan: Banyak sinyal positif ({bullish_signals}/{total}), mendukung beli")
        elif bull_pct >= 50:
            action_parts.append(f"Kesimpulan: Sinyal campuran ({bullish_signals}/{total} positif), beli dengan hati-hati")
        elif bull_pct >= 30:
            action_parts.append(f"Kesimpulan: Lebih banyak sinyal negatif ({bearish_signals}/{total}), pertimbangkan tunggu")
        else:
            action_parts.append(f"Kesimpulan: Banyak sinyal negatif ({bearish_signals}/{total}), hindari beli")

    lines.append("")
    lines.append("LANGKAH SELANJUTNYA:")
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
    data_date = df.index[-1]
    is_today = hasattr(data_date, 'date') and data_date.date() == datetime.now().date()
    price_label = "Last" if is_today else "Close"
    h2 = f"  Price: {last['Close']:<8.2f} | {price_label}: {data_date.strftime('%d %b %Y')}"
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

    lines.append(f"┌{'─' * IW}┐")
    lines.append(f"│{_pad_inner('⚠️  Think First. Trade Second. DYOR - Do Your Own Research', IW)}│")
    lines.append(f"└{'─' * IW}┘")

    return "\n".join(lines)
