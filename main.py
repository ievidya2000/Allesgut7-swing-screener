import sys
import argparse
import pandas as pd
import warnings
warnings.filterwarnings("ignore", message=".*could not convert.*")
warnings.filterwarnings("default", message=".*valid.*convergent.*")
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

from config import TICKERS, SELECTED_TP, SETUP_ORDER, SIGNAL_MAP, MAX_DISPLAY
from data import get_all_market_data, get_jkse_data
from indicators import calculate_full_indicators
from signals import (
    determine_market_regime, determine_stock_regime, classify_setup_state
)
from risk import calculate_tp_sl, simulate_tp_sl_probability
from adaptive.config import load_adaptive_config
from analysis import generate_deep_analysis
from deep_analysis import generate_report as deep_report
from patterns import detect_patterns, get_pattern_score
from output import (
    print_banner, print_summary, print_header, print_subheader,
    print_analysis_box, sep
)


def run_screener():
    print_banner()

    # 1. Market Regime
    print("\n[1/3] Determining market regime...")
    jkse_df = get_jkse_data()
    market_regime = determine_market_regime(jkse_df) if jkse_df is not None else "SIDEWAYS"
    print(f"  Market Regime (IHSG): {market_regime}")

    if market_regime == "BEAR":
        print("  BEAR regime — only EARLY_REVERSAL setups will be considered")

    # 2. Get data
    print("\n[2/3] Loading market data...")
    market_data = get_all_market_data(TICKERS)
    print(f"  Loaded {len(market_data)} tickers")

    failed_tickers = [t for t in TICKERS if t not in market_data]
    if failed_tickers:
        print(f"  No data ({len(failed_tickers)}): {failed_tickers}")

    # 3. Scan
    print("\n[3/3] Scanning for setups...")
    print(sep("-"))

    results = []
    skipped = {"short_data": 0, "bear_regime": 0, "no_setup": 0, "error": 0}
    adaptive_params = load_adaptive_config()

    for ticker, df in market_data.items():
        try:
            if len(df) < 50:
                skipped["short_data"] += 1
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            full = calculate_full_indicators(df, adaptive_params)
            last = full.iloc[-1]

            stock_regime = determine_stock_regime(full)
            setup, is_valid = classify_setup_state(full, stock_regime, adaptive_params)

            if not is_valid:
                skipped["no_setup"] += 1
                continue

            if market_regime == "BEAR" and setup != "EARLY_REVERSAL":
                skipped["bear_regime"] += 1
                continue

            signal_type = SIGNAL_MAP[setup]

            close = last['Close']
            atr = last['atr_rm']
            adx = last['adx'] if pd.notna(last['adx']) else 0

            # Skip penny stocks (consistent with Streamlit)
            if close < 70:
                skipped["no_setup"] += 1
                continue

            if atr is None or pd.isna(atr) or close <= 0 or atr / close < 0.001:
                skipped["no_setup"] += 1
                continue

            # Volume Quality Filter
            from config import MIN_DOLLAR_VOLUME
            dollar_volume = last.get('dollar_volume', 0)
            if pd.isna(dollar_volume) or dollar_volume < MIN_DOLLAR_VOLUME:
                skipped["no_setup"] += 1
                continue

            # Basic TP/SL
            sl, tp1, tp2, tp3, profit_pct, risk_pct = calculate_tp_sl(close, atr, signal_type, adaptive_params)

            if sl is None or (risk_pct is not None and risk_pct < 0.1):
                skipped["no_setup"] += 1
                continue

            # Deep analysis
            analysis = generate_deep_analysis(full, setup, close, atr, adaptive_params)

            # Override TP/SL with analysis values (which include full logic)
            sl_normal = analysis["sl_normal"]
            sl_wide = analysis["sl_wide"]
            tp1_an = analysis["tp1"]
            tp2_an = analysis["tp2"]
            tp3_an = analysis["tp3"]
            tp_analysis = analysis["tp_analysis"]
            entry_zone = analysis["entry_zone"]
            timing = analysis["timing"]
            chart = analysis["chart"]
            risk_pct = analysis["risk_pct"]  # Konsisten dengan analysis

            selected_tp = {"TP1": tp1_an, "TP2": tp2_an, "TP3": tp3_an}.get(SELECTED_TP)

            if selected_tp and close > 0:
                profit_pct = ((selected_tp - close) / close) * 100

            # Monte Carlo
            prob = simulate_tp_sl_probability(
                df, entry_price=close, stop_loss=sl_normal,
                tp1=tp1_an, tp2=tp2_an, tp3=tp3_an
            )

            if prob is None:
                prob = {
                    "P_TP1": None, "P_TP2": None, "P_TP3": None, "P_SL": None,
                    "AVG_DAYS_TP1": None, "AVG_DAYS_TP2": None, "AVG_DAYS_TP3": None,
                }

            # Pattern Detection
            patterns_list, pattern_meta = detect_patterns(df)
            pattern_info = get_pattern_score(patterns_list)

            cloud = ("ABOVE" if last.get('price_above_cloud', False) else
                     "BELOW" if last.get('price_below_cloud', False) else "INSIDE")
            # Multi-ST consensus
            st_count = int(last.get('st_bullish_count', 0))
            trend = f"BULLISH ({st_count}/3)" if st_count >= 2 else f"BEARISH ({st_count}/3)"

            result = {
                "Ticker": ticker,
                "Setup": setup,
                "Signal": signal_type,
                "Price": round(close, 2),
                "Stock Regime": stock_regime,
                "Cloud": cloud,
                "Trend": trend,
                "ADX": round(adx, 2),
                "ATR": round(atr, 2),
                "Stop Loss": round(sl_normal, 2),
                "TP1": round(tp1_an, 2),
                "TP2": round(tp2_an, 2),
                "TP3": round(tp3_an, 2),
                "Profit %": round(profit_pct, 2) if profit_pct else None,
                "Risk %": round(risk_pct, 2) if risk_pct else None,
                "Prob(TP1)": prob["P_TP1"],
                "Prob(TP2)": prob["P_TP2"],
                "Prob(TP3)": prob["P_TP3"],
                "Prob(SL)": prob["P_SL"],
                "Avg Days TP1": round(prob["AVG_DAYS_TP1"], 2) if prob["AVG_DAYS_TP1"] else None,
                "Avg Days TP2": round(prob["AVG_DAYS_TP2"], 2) if prob["AVG_DAYS_TP2"] else None,
                "Avg Days TP3": round(prob["AVG_DAYS_TP3"], 2) if prob["AVG_DAYS_TP3"] else None,
                "Entry Zone Low": entry_zone["low"],
                "Entry Zone High": entry_zone["high"],
                "Entry Strategy": entry_zone["strategy"],
                "SL Wide": sl_wide["price"],
                "Timing": timing["label"],
                "Timing Detail": timing["detail"],
                "Timing Confirm Type": timing.get("confirmation_type", ""),
                "Timing Confirm Value": timing.get("confirmation_value"),
                "Chart": chart,
                "Pattern Score": pattern_info["score"],
                "Pattern Bias": pattern_info["bias"],
                "Bullish Patterns": pattern_info["bullish_count"],
                "Bearish Patterns": pattern_info["bearish_count"],
            }

            results.append(result)

        except Exception as e:
            skipped["error"] += 1
            print(f"  ERROR [{ticker}]: {e}")

    # 4. Output per-ticker detail boxes
    print(sep("-"))
    print_summary(market_regime, len(market_data), len(results), skipped)

    if not results:
        print("No setups found.")
        return pd.DataFrame()

    df_out = pd.DataFrame(results)

    def _parse_prob(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return 0.0
        s = str(val).strip().rstrip('%')
        try:
            return float(s)
        except (ValueError, TypeError):
            return 0.0

    for tp in ["TP1", "TP2", "TP3"]:
        df_out[f"Prob_{tp}_float"] = (
            df_out[f"Prob({tp})"].apply(_parse_prob)
        )
    df_out["Prob_SL_float"] = (
        df_out["Prob(SL)"].apply(_parse_prob)
    )
    df_out["Avg Days TP1"] = df_out["Avg Days TP1"].fillna(999)
    df_out["Avg Days TP3"] = df_out.get("Avg Days TP3", pd.Series(dtype=float)).fillna(999)

    ap = load_adaptive_config()
    w_tp = ap.get("score_w_prob_tp", 1.0)
    w_pf = ap.get("score_w_profit_pct", 0.5)
    w_sl = ap.get("score_w_prob_sl", -1.0)
    w_d3 = ap.get("score_w_avg_days", -0.3)
    w_pattern = ap.get("score_w_pattern", 0.5)

    # Use SELECTED_TP for score calculation (consistent with displayed profit)
    tp_col = f"Prob_{SELECTED_TP}_float"
    days_col = f"Avg Days {SELECTED_TP}"
    if tp_col not in df_out.columns:
        tp_col = "Prob_TP1_float"
    if days_col not in df_out.columns:
        days_col = "Avg Days TP1"

    df_out["TP_Likelihood"] = (
        w_tp * df_out[tp_col]
        + w_pf * (df_out[tp_col] / (df_out["Prob_SL_float"] + 0.01))
        + w_sl * df_out["Prob_SL_float"]
        + w_d3 * df_out[days_col]
        + w_pattern * df_out["Pattern Score"]
    )
    # Normalize score to 0-100 (matches Streamlit normalization)
    s_min = df_out["TP_Likelihood"].min()
    s_max = df_out["TP_Likelihood"].max()
    if s_max > s_min:
        df_out["Score"] = ((df_out["TP_Likelihood"] - s_min) / (s_max - s_min) * 100).round(1)
    else:
        df_out["Score"] = 50.0
    df_out = df_out.sort_values("Score", ascending=False).reset_index(drop=True)

    # Print detail boxes grouped by setup (from DataFrame with scores)
    print_header("DETAIL ANALYSIS")
    print(f"  Market Regime: {market_regime} | Setups found: {len(results)}")
    print()

    for st in SETUP_ORDER:
        group = df_out[df_out["Setup"] == st].sort_values("Score", ascending=False)
        if group.empty:
            continue

        group_display = group.head(MAX_DISPLAY)
        remaining = len(group) - len(group_display)
        print_subheader(f"{st} ({len(group)})" + (f" — showing top {len(group_display)}" if remaining > 0 else ""))

        for _, r in group_display.iterrows():
            print_analysis_box(
                ticker=r["Ticker"],
                setup=r["Setup"],
                stock_regime=r["Stock Regime"],
                market_regime=market_regime,
                price=r["Price"],
                entry_zone={"low": r["Entry Zone Low"],
                            "high": r["Entry Zone High"],
                            "strategy": r["Entry Strategy"],
                            "strength": 0,
                            "conditions": []},
                sl_normal=r["Stop Loss"],
                sl_wide={"price": r["SL Wide"], "logic": ""},
                tp_analysis=[{"label": "TP1", "price": r["TP1"], "note": ""},
                             {"label": "TP2", "price": r["TP2"], "note": ""},
                             {"label": "TP3", "price": r["TP3"], "note": ""}],
                timing={"label": r["Timing"], "detail": r["Timing Detail"]},
                chart=r["Chart"],
                score=r["Score"],
                adx=r["ADX"],
                profit_pct=r["Profit %"],
                risk_pct=r["Risk %"],
                prob_tp1=r.get("Prob(TP1)", "N/A"),
                prob_tp2=r.get("Prob(TP2)", "N/A"),
                prob_sl=r.get("Prob(SL)", "N/A"),
            )

    # Save CSV — clean columns and formatting
    def _clean_prob(val):
        """Convert probability string like '72.5%' to float 72.5"""
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        s = str(val).strip().rstrip('%')
        try:
            return round(float(s), 2)
        except (ValueError, TypeError):
            return None

    csv_df = df_out.copy()

    # Clean probability columns
    for col in ["Prob(TP1)", "Prob(TP2)", "Prob(TP3)", "Prob(SL)"]:
        if col in csv_df.columns:
            csv_df[col] = csv_df[col].apply(_clean_prob)

    # Remove internal columns
    drop_cols = ["Chart"]
    csv_df = csv_df.drop(columns=[c for c in drop_cols if c in csv_df.columns], errors="ignore")

    # Curated column order
    save_cols = [
        "Ticker", "Signal", "Setup", "Score", "Price", "Stock Regime",
        "Cloud", "Trend", "ADX", "ATR",
        "Stop Loss", "SL Wide", "TP1", "TP2", "TP3",
        "Entry Zone Low", "Entry Zone High", "Entry Strategy",
        "Profit %", "Risk %",
        "Prob(TP1)", "Prob(TP2)", "Prob(TP3)", "Prob(SL)",
        "Avg Days TP1", "Avg Days TP2", "Avg Days TP3",
        "Timing", "Timing Confirm Type", "Timing Confirm Value",
    ]
    avail_cols = [c for c in save_cols if c in csv_df.columns]
    csv_df = csv_df[avail_cols].sort_values("Score" if "Score" in csv_df.columns else avail_cols[0], ascending=False)

    # Round numeric columns
    num_cols = csv_df.select_dtypes(include=["float", "float64"]).columns
    csv_df[num_cols] = csv_df[num_cols].round(2)

    csv_df.to_csv("hasil_screener_v2.csv", index=False)

    print(sep("="))
    print("  Saved to hasil_screener_v2.csv")
    print(sep("="))

    # Performance: log predictions + check open trades
    try:
        from performance.realtime import (
            log_new_predictions, check_open_trades, print_performance_summary
        )
        print()
        print(sep("-"))
        print("  PERFORMANCE TRACKING")
        print(sep("-"))

        logged = log_new_predictions(results, market_regime)
        print(f"  Logged {logged} new predictions to journal")

        check_result = check_open_trades(market_data)
        if check_result["closed"] > 0:
            print(f"  Closed {check_result['closed']} expired trades")
        if check_result["still_active"] > 0:
            print(f"  Active trades: {check_result['still_active']}")

        print_performance_summary()
    except Exception as e:
        print(f"  [Performance] Tracking skipped: {e}")

    # Interactive deep analysis
    print()
    print("  ── Interactive Deep Analysis ──")
    print("  Type a ticker for detailed analysis (candlestick, multi-tf,")
    print("  volume profile, trendlines, risk scenario).")
    print()

    while True:
        try:
            inp = input("  Enter ticker (or 'q' to quit): ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if inp in ("Q", "QUIT", "EXIT", ""):
            break

        if inp not in market_data:
            print(f"  Ticker '{inp}' not found in loaded data.")
            print("  (Run full scan first or check the ticker name)")
            continue

        # Cek hasil screening
        screening_tickers = set(df_out["Ticker"].tolist()) if not df_out.empty else set()
        if screening_tickers and inp not in screening_tickers:
            print(f"  '{inp}' did not PASS SCREENING (no valid setup detected).")
            override = input("  Analyze anyway? (y/N): ").strip().lower()
            if override != "y":
                print()
                continue

        print()
        print("  Generating deep analysis...")
        print()

        df_stock = market_data[inp]
        if isinstance(df_stock.columns, pd.MultiIndex):
            df_stock.columns = df_stock.columns.get_level_values(0)

        # Build market_data dict with JKSE for risk scenario
        md_for_report = dict(market_data)
        jkse_df = get_jkse_data()
        if jkse_df is not None:
            md_for_report["^JKSE"] = jkse_df

        try:
            report_text = deep_report(inp, df_stock, md_for_report)
            print(report_text)
        except Exception as e:
            print(f"  Error generating deep analysis: {e}")

        print()

    return df_out


def cli_analyze(ticker):
    """Run analysis for a single ticker via CLI."""
    import yfinance as yf
    from data import normalize_yfinance_df, load_ticker_cache, save_ticker_cache

    print(f"  Loading data for {ticker}...")

    cached = load_ticker_cache(ticker)
    if cached is not None and len(cached) >= 50:
        df = cached
        print(f"  Loaded from cache ({len(df)} rows)")
    else:
        df = yf.download(ticker, period="1y", interval="1d",
                         auto_adjust=False, progress=False, threads=False)
        df = normalize_yfinance_df(df)
        if df is not None:
            save_ticker_cache(ticker, df)
            print(f"  Downloaded and cached ({len(df)} rows)")
    if df is None:
        print(f"  Error: could not load data for {ticker}")
        return

    md_for_report = {ticker: df}
    jkse = get_jkse_data()
    if jkse is not None:
        md_for_report["^JKSE"] = jkse

    print()
    report = deep_report(ticker, df, md_for_report)
    print(report)


def cli_main():
    parser = argparse.ArgumentParser(
        prog="python -m main",
        description="IDX Swing Trading Screener - AI-Powered Stock Scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python -m main                          Run full screening 600+ saham IDX
  python -m main --analyze BBCA.JK        Analisis mendalam 1 ticker
  python -m main --auto-trade             Auto paper trading ke Google Sheets
  python -m main --auto-trade --dry-run   Simulasi tanpa eksekusi
  python -m main --auto-trade --force     Paksa retrain meski tidak ada data baru

Documentation:
  screener_v2/guide.md    User guide lengkap
  screener_v2/readme.md   Quick start & architecture
        """
    )
    parser.add_argument(
        "--analyze", metavar="TICKER",
        help="Analisis mendalam 1 ticker (contoh: BBCA.JK)"
    )
    parser.add_argument(
        "--auto-trade", action="store_true",
        help="Jalankan auto paper trading ke Google Sheets"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simulasi tanpa eksekusi (gabung dengan --auto-trade)"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Paksa retrain meskipun tidak ada data baru (gabung dengan --auto-trade)"
    )

    args = parser.parse_args()

    if args.analyze:
        cli_analyze(args.analyze.upper())
    elif args.auto_trade:
        df_out = run_screener()
        if df_out is not None and not df_out.empty:
            try:
                from paper_trading.run_auto import run_auto_paper_trading
                run_auto_paper_trading(df_out, dry_run=args.dry_run, force=args.force)
            except ImportError as e:
                print(f"\n  Paper trading module error: {e}")
                print("  Install: pip install gspread google-auth")
            except Exception as e:
                print(f"\n  Auto-trade error: {e}")
    else:
        run_screener()


if __name__ == "__main__":
    cli_main()
