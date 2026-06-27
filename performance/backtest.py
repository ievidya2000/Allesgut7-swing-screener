import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from functools import lru_cache

from screener_v2.config import TICKERS, MC_HORIZON, SIGNAL_MAP
from screener_v2.data import get_all_market_data, get_jkse_data
from screener_v2.indicators import calculate_full_indicators
from screener_v2.signals import determine_market_regime, determine_stock_regime, classify_setup_state
from screener_v2.risk import calculate_tp_sl
from screener_v2.analysis import generate_deep_analysis
from screener_v2.performance.journal import (
    init_db, log_prediction, log_trade_result, log_predictions_batch,
    update_prediction_status, get_pending_predictions
)
from screener_v2.adaptive.config import load_adaptive_config
from screener_v2.utils.date_utils import normalize_screen_date


def check_tp_sl_hit(df_slice, entry_price, tp1, tp2, tp3, sl):
    if df_slice is None or df_slice.empty or len(df_slice) < 2:
        return {
            "hit_tp1": False, "hit_tp2": False, "hit_tp3": False, "hit_sl": False,
            "exit_price": entry_price, "exit_reason": "TIMEOUT",
            "days_held": 0, "max_favorable": 0, "max_adverse": 0,
        }

    hit_tp1 = hit_tp2 = hit_tp3 = hit_sl = False
    tp1_day = tp2_day = tp3_day = sl_day = None
    max_favorable = 0
    max_adverse = 0

    for i, (idx, row) in enumerate(df_slice.iterrows()):
        high = row["High"]
        low = row["Low"]
        day = i + 1

        price_change_pct = (high - entry_price) / entry_price
        price_drop_pct = (entry_price - low) / entry_price
        max_favorable = max(max_favorable, price_change_pct)
        max_adverse = max(max_adverse, price_drop_pct)

        if sl and not hit_sl and low <= sl:
            hit_sl = True
            sl_day = day
            break

        if tp1 and not hit_tp1 and high >= tp1:
            hit_tp1 = True
            tp1_day = day

        if tp2 and not hit_tp2 and high >= tp2:
            hit_tp2 = True
            tp2_day = day

        if tp3 and not hit_tp3 and high >= tp3:
            hit_tp3 = True
            tp3_day = day

    if hit_sl:
        exit_price = sl
        exit_reason = "SL"
        days_held = sl_day or 1
    elif hit_tp3:
        exit_price = tp3
        exit_reason = "TP3"
        days_held = tp3_day or 1
    elif hit_tp2:
        exit_price = tp2
        exit_reason = "TP2"
        days_held = tp2_day or 1
    elif hit_tp1:
        exit_price = tp1
        exit_reason = "TP1"
        days_held = tp1_day or 1
    else:
        last_close = df_slice["Close"].iloc[-1]
        exit_price = last_close
        exit_reason = "TIMEOUT"
        days_held = len(df_slice)

    return_pct = ((exit_price - entry_price) / entry_price) * 100

    return {
        "hit_tp1": hit_tp1,
        "hit_tp2": hit_tp2,
        "hit_tp3": hit_tp3,
        "hit_sl": hit_sl,
        "exit_price": round(exit_price, 2),
        "exit_reason": exit_reason,
        "days_held": days_held,
        "max_favorable": round(max_favorable * 100, 2),
        "max_adverse": round(max_adverse * 100, 2),
        "return_pct": round(return_pct, 2),
        "return_abs": round((exit_price - entry_price), 2),
    }


def _precompute_all_indicators(market_data, adaptive_params, chunk_size=100):
    indicator_cache = {}
    tickers = list(market_data.items())
    for chunk_start in range(0, len(tickers), chunk_size):
        chunk = tickers[chunk_start:chunk_start + chunk_size]
        for ticker, df in chunk:
            if len(df) >= 100:
                try:
                    full = calculate_full_indicators(df, adaptive_params)
                    indicator_cache[ticker] = full
                except Exception:
                    pass
        import gc
        gc.collect()
    return indicator_cache


def _precompute_market_regimes(jkse_df, signal_dates):
    regimes = {}
    for sig_date in signal_dates:
        jkse_slice = jkse_df[jkse_df.index <= sig_date]
        if len(jkse_slice) >= 100:
            regimes[sig_date] = determine_market_regime(jkse_slice)
        else:
            regimes[sig_date] = "SIDEWAYS"
    return regimes


MAX_MC_TICKERS = 30


def run_screening_at_date(market_data, signal_date, market_regime=None, jkse_df=None,
                          adaptive_params=None, indicator_cache=None, markov_cache=None):
    results = []
    if adaptive_params is None:
        adaptive_params = load_adaptive_config()

    if market_regime is None:
        if jkse_df is None:
            jkse_df = get_jkse_data()
        if jkse_df is not None:
            jkse_slice = jkse_df[jkse_df.index <= signal_date]
            if len(jkse_slice) >= 100:
                market_regime = determine_market_regime(jkse_slice)
            else:
                market_regime = "SIDEWAYS"
        else:
            market_regime = "SIDEWAYS"

    candidates = []
    for ticker, df in market_data.items():
        try:
            if indicator_cache and ticker in indicator_cache:
                full = indicator_cache[ticker]
                full_slice = full[full.index <= signal_date]
                if len(full_slice) < 100:
                    continue
                last = full_slice.iloc[-1]
            else:
                df_slice = df[df.index <= signal_date]
                if len(df_slice) < 100:
                    continue
                full = calculate_full_indicators(df_slice, adaptive_params)
                full_slice = full
                last = full.iloc[-1]

            stock_regime = determine_stock_regime(full_slice)
            setup, is_valid = classify_setup_state(full_slice, stock_regime, adaptive_params)

            if not is_valid:
                continue

            close = last["Close"]
            if close < 70:
                continue

            atr = last.get("atr_rm", None)
            if atr is None or pd.isna(atr) or atr / close < 0.001:
                continue

            signal_type = SIGNAL_MAP[setup]
            sl, tp1, tp2, tp3, profit_pct, risk_pct = calculate_tp_sl(close, atr, signal_type, adaptive_params)
            if sl is None:
                continue

            adx_val = last.get("adx", 0) or 0
            candidates.append({
                "ticker": ticker, "full_slice": full_slice, "last": last,
                "setup": setup, "signal_type": signal_type, "close": close,
                "atr": atr, "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3,
                "stock_regime": stock_regime, "adx": adx_val,
            })
        except Exception:
            continue

    candidates.sort(key=lambda c: c["adx"], reverse=True)
    top_candidates = candidates[:MAX_MC_TICKERS]

    for cand in top_candidates:
        try:
            ticker = cand["ticker"]
            full_slice = cand["full_slice"]
            last = cand["last"]
            setup = cand["setup"]
            signal_type = cand["signal_type"]
            close = cand["close"]
            atr = cand["atr"]

            is_bear_filtered = (market_regime == "BEAR" and setup != "EARLY_REVERSAL")

            analysis = generate_deep_analysis(full_slice, setup, close, atr, adaptive_params)

            df_for_mc = market_data[ticker]
            df_slice = df_for_mc[df_for_mc.index <= signal_date]
            from screener_v2.risk import simulate_tp_sl_probability
            prob = simulate_tp_sl_probability(
                df_slice, close,
                analysis["sl_normal"], analysis["tp1"], analysis["tp2"], analysis["tp3"],
                markov_cache=markov_cache, markov_cache_key=ticker
            )
            if prob is None:
                prob = {"P_TP1": None, "P_TP2": None, "P_TP3": None, "P_SL": None,
                        "AVG_DAYS_TP1": None, "AVG_DAYS_TP2": None, "AVG_DAYS_TP3": None}

            def _parse_prob(val):
                if val is None:
                    return 0.0
                try:
                    return float(str(val).strip().rstrip('%'))
                except (ValueError, TypeError):
                    return 0.0

            p_sl_val = _parse_prob(prob.get("P_SL"))
            if p_sl_val > 60:
                continue

            p_tp1 = _parse_prob(prob["P_TP1"])
            p_sl = _parse_prob(prob["P_SL"])
            avg_d1 = prob["AVG_DAYS_TP1"] or 999

            w_tp = adaptive_params.get("score_w_prob_tp", 1.0)
            w_pf = adaptive_params.get("score_w_profit_pct", 0.5)
            w_sl = adaptive_params.get("score_w_prob_sl", -1.0)
            w_d1 = adaptive_params.get("score_w_avg_days", -0.3)

            score = round(
                w_tp * p_tp1
                + w_pf * (p_tp1 / (p_sl + 0.01))
                + w_sl * p_sl
                + w_d1 * avg_d1,
                2
            )

            if is_bear_filtered and score < 0.5:
                continue

            result = {
                "ticker": ticker,
                "setup": setup,
                "signal": signal_type,
                "price_at_signal": round(close, 2),
                "stop_loss": round(analysis["sl_normal"], 2),
                "tp1": round(analysis["tp1"], 2),
                "tp2": round(analysis["tp2"], 2),
                "tp3": round(analysis["tp3"], 2),
                "entry_zone_low": analysis["entry_zone"]["low"],
                "entry_zone_high": analysis["entry_zone"]["high"],
                "entry_strategy": analysis["entry_zone"]["strategy"],
                "timing": analysis["timing"]["label"],
                "prob_tp1": prob["P_TP1"],
                "prob_tp2": prob["P_TP2"],
                "prob_tp3": prob["P_TP3"],
                "prob_sl": prob["P_SL"],
                "avg_days_tp1": prob["AVG_DAYS_TP1"],
                "avg_days_tp2": prob["AVG_DAYS_TP2"],
                "avg_days_tp3": prob["AVG_DAYS_TP3"],
                "market_regime": market_regime,
                "stock_regime": stock_regime,
                "adx": round(last.get("adx", 0), 2),
                "atr": round(atr, 2),
                "screen_date": normalize_screen_date(signal_date).isoformat(),
                "score": score,
            }

            if result["timing"] != "ENTRY_READY":
                continue

            results.append(result)

        except Exception as e:
            continue

    return results


def forward_test_trade(prediction, market_data, max_days=MC_HORIZON):
    ticker = prediction["ticker"]
    signal_date = normalize_screen_date(prediction["screen_date"])

    if ticker not in market_data:
        return None

    df = market_data[ticker]
    future_data = df[df.index > signal_date].head(max_days)

    if future_data.empty or len(future_data) < 2:
        return None

    entry_price = prediction["price_at_signal"]
    tp1 = prediction.get("tp1")
    tp2 = prediction.get("tp2")
    tp3 = prediction.get("tp3")
    sl = prediction.get("stop_loss")

    result = check_tp_sl_hit(future_data, entry_price, tp1, tp2, tp3, sl)
    result["prediction_id"] = prediction["id"]
    result["ticker"] = ticker
    result["entry_date"] = signal_date.isoformat()
    result["entry_price"] = entry_price

    days_held = result["days_held"]
    if days_held > 0 and days_held <= len(future_data):
        actual_exit_date = future_data.index[days_held - 1] if days_held <= len(future_data) else future_data.index[-1]
        result["exit_date"] = actual_exit_date.isoformat()
    else:
        result["exit_date"] = signal_date.isoformat()
    result["status"] = "CLOSED"

    return result


def run_historical_backtest(start_date=None, end_date=None):
    init_db()

    if end_date is None:
        end_date = datetime.now()
    if start_date is None:
        start_date = end_date - timedelta(days=365)

    if isinstance(start_date, str):
        start_date = datetime.fromisoformat(start_date)
    if isinstance(end_date, str):
        end_date = datetime.fromisoformat(end_date)

    print(f"\n{'='*60}", flush=True)
    print(f"  HISTORICAL BACKTEST: {start_date.date()} → {end_date.date()}", flush=True)
    print(f"{'='*60}\n", flush=True)

    adaptive_params = load_adaptive_config()
    jkse_df = get_jkse_data(
        start=start_date.strftime("%Y-%m-%d"),
        end=end_date.strftime("%Y-%m-%d"),
    )

    print("  Loading market data...", flush=True)
    all_market_data = get_all_market_data(
        TICKERS,
        start=start_date.strftime("%Y-%m-%d"),
        end=end_date.strftime("%Y-%m-%d"),
    )
    print(f"  Loaded {len(all_market_data)} tickers from cache", flush=True)

    print("  Precomputing indicators...", flush=True)
    t0 = time.time()
    indicator_cache = _precompute_all_indicators(all_market_data, adaptive_params)
    print(f"  Indicators: {time.time()-t0:.1f}s for {len(indicator_cache)} tickers", flush=True)

    import os, psutil
    process = psutil.Process(os.getpid())
    print(f"  Memory: {process.memory_info().rss/1024/1024:.0f}MB", flush=True)

    years = list(range(start_date.year, end_date.year + 1))
    total_predictions = 0
    total_closed = 0

    for year in years:
        year_start = max(start_date, datetime(year, 1, 1))
        year_end = min(end_date, datetime(year, 12, 31))

        signal_dates = pd.bdate_range(start=year_start, end=year_end, freq="B")
        market_regimes = _precompute_market_regimes(jkse_df, signal_dates)

        markov_cache = {}
        year_predictions = []
        for i, sig_date in enumerate(signal_dates):
            if i % 20 == 0:
                print(f"  {year}-{sig_date.date()} ({i+1}/{len(signal_dates)})...", flush=True)

            regime = market_regimes.get(sig_date, "SIDEWAYS")
            results = run_screening_at_date(all_market_data, sig_date, market_regime=regime,
                                            adaptive_params=adaptive_params,
                                            indicator_cache=indicator_cache,
                                            markov_cache=markov_cache)
            if results:
                pred_ids = log_predictions_batch(results)
                for r, pid in zip(results, pred_ids):
                    r["id"] = pid
                year_predictions.extend(results)

        print(f"  Year {year}: {len(year_predictions)} predictions "
              f"({signal_dates[0].date()} to {signal_dates[-1].date()})", flush=True)

        closed_count = 0
        for pred in year_predictions:
            trade_result = forward_test_trade(pred, all_market_data)
            if trade_result:
                log_trade_result(trade_result)
                update_prediction_status(pred["id"], "CLOSED")
                closed_count += 1

        print(f"  Year {year}: {closed_count} trades closed", flush=True)
        total_predictions += len(year_predictions)
        total_closed += closed_count

        del markov_cache, year_predictions
        import gc
        gc.collect()

    print(f"\n{'='*60}", flush=True)
    print(f"  TOTAL: {total_predictions} predictions, {total_closed} trades closed", flush=True)
    print(f"{'='*60}", flush=True)

    print(f"\n[4/4] Generating report...", flush=True)
    from screener_v2.performance.journal import get_trade_results
    from screener_v2.performance.metrics import full_report, format_report

    trades = get_trade_results(filters={
        "from_date": start_date.isoformat() if hasattr(start_date, "isoformat") else str(start_date),
        "to_date": end_date.isoformat() if hasattr(end_date, "isoformat") else str(end_date),
    })
    report = full_report(trades)
    print(format_report(report))

    return report


def backtest_single_ticker(ticker, start_date=None, end_date=None):
    init_db()

    if end_date is None:
        end_date = datetime.now()
    if start_date is None:
        start_date = end_date - timedelta(days=365)

    if isinstance(start_date, str):
        start_date = datetime.fromisoformat(start_date)
    if isinstance(end_date, str):
        end_date = datetime.fromisoformat(end_date)

    print(f"\n  Backtesting {ticker}: {start_date.date()} → {end_date.date()}")

    LOOKBACK_DAYS = 300
    fetch_start = start_date - timedelta(days=LOOKBACK_DAYS)
    market_data = get_all_market_data([ticker], start=fetch_start.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"))
    if ticker not in market_data:
        print(f"  Error: could not load data for {ticker}")
        return None

    signal_dates = pd.bdate_range(start=start_date, end=end_date, freq="B")
    predictions = []

    for sig_date in signal_dates:
        results = run_screening_at_date(market_data, sig_date)
        for r in results:
            pred_id = log_prediction(r)
            r["id"] = pred_id
            predictions.append(r)

    print(f"  Predictions: {len(predictions)}")

    for pred in predictions:
        trade_result = forward_test_trade(pred, market_data)
        if trade_result:
            log_trade_result(trade_result)
            update_prediction_status(pred["id"], "CLOSED")

    from screener_v2.performance.journal import get_trade_results
    from screener_v2.performance.metrics import full_report, format_report

    trades = get_trade_results(filters={"ticker": ticker})
    if trades:
        report = full_report(trades)
        print(format_report(report))
        return report
    else:
        print("  No trades recorded")
        return None
