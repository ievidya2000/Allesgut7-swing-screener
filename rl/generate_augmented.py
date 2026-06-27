import pandas as pd
from datetime import datetime, timedelta

from screener_v2.config import TICKERS, SIGNAL_MAP
from screener_v2.data import get_all_market_data, get_jkse_data
from screener_v2.indicators import calculate_full_indicators
from screener_v2.signals import determine_market_regime, determine_stock_regime, classify_setup_state
from screener_v2.risk import calculate_tp_sl
from screener_v2.analysis import generate_deep_analysis
from screener_v2.adaptive.config import load_adaptive_config
from screener_v2.utils.date_utils import normalize_screen_date


def _parse_prob(val):
    if val is None:
        return 0.0
    try:
        return float(str(val).strip().rstrip('%'))
    except (ValueError, TypeError):
        return 0.0


def run_augmented_screening(market_data, signal_date, market_regime=None, jkse_df=None):
    results = []
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

    for ticker, df in market_data.items():
        try:
            df_slice = df[df.index <= signal_date]
            if len(df_slice) < 100:
                continue

            full = calculate_full_indicators(df_slice, adaptive_params)
            last = full.iloc[-1]

            stock_regime = determine_stock_regime(full)
            setup, is_valid = classify_setup_state(full, stock_regime, adaptive_params)

            if not is_valid:
                continue

            signal_type = SIGNAL_MAP[setup]
            close = last["Close"]

            if close < 50:
                continue

            atr = last.get("atr_rm", None)
            if atr is None or pd.isna(atr) or atr / close < 0.001:
                continue

            sl, tp1, tp2, tp3, profit_pct, risk_pct = calculate_tp_sl(close, atr, signal_type, adaptive_params)
            if sl is None:
                continue

            analysis = generate_deep_analysis(full, setup, close, atr, adaptive_params)

            from screener_v2.risk import simulate_tp_sl_probability
            prob = simulate_tp_sl_probability(
                df_slice, close,
                analysis["sl_normal"], analysis["tp1"], analysis["tp2"], analysis["tp3"]
            )
            if prob is None:
                prob = {"P_TP1": None, "P_TP2": None, "P_TP3": None, "P_SL": None,
                        "AVG_DAYS_TP1": None, "AVG_DAYS_TP2": None, "AVG_DAYS_TP3": None}

            p_tp1 = _parse_prob(prob["P_TP1"])
            p_tp2 = _parse_prob(prob["P_TP2"])
            p_tp3 = _parse_prob(prob["P_TP3"])
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

            features = _extract_indicator_features(full, last, analysis, market_regime, stock_regime)

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
                "rl_features": features,
            }

            results.append(result)

        except Exception:
            continue

    return results


def _extract_indicator_features(full, last, analysis, market_regime, stock_regime):
    def _safe(val, default=0.0):
        if val is None or pd.isna(val):
            return default
        return float(val)

    features = {
        "adx": _safe(last.get("adx")),
        "atr": _safe(last.get("atr_rm")),
        "atr_pct": _safe(last.get("atr_rm")) / max(_safe(last.get("Close")), 1) * 100,
        "supertrend_bullish": 1 if last.get("supertrend_bullish") else 0,
        "price_above_cloud": 1 if last.get("price_above_cloud") else 0,
        "price_in_cloud": 1 if last.get("price_in_cloud") else 0,
        "donchian_width_pct": _safe(last.get("donchian_width_pct")),
        "volume_expanding": 1 if last.get("volume_expanding") else 0,
        "vol_contraction": 1 if last.get("vol_contraction") else 0,
        "near_resistance": 1 if last.get("near_resistance") else 0,
        "adx_rising": 1 if last.get("adx_rising") else 0,
        "ma20_slope": _safe(last.get("ma20_slope")),
        "ma20_above_ma50": 1 if _safe(last.get("ma20")) > _safe(last.get("ma50")) else 0,
        "consecutive_inside": _safe(last.get("consecutive_inside")),
        "bb_width": _safe(last.get("bb_width")),
        "dw_percentile_50": _safe(last.get("dw_percentile_50")),
        "fresh_breakout": 1 if last.get("fresh_breakout") else 0,
        "volume_pre_breakout": 1 if last.get("volume_pre_breakout") else 0,
        "price_to_donchian_mid": _safe(last.get("Close")) / max(_safe(last.get("donchian_mid")), 1),
        "price_to_donchian_upper": _safe(last.get("Close")) / max(_safe(last.get("donchian_upper")), 1),
        "vol_ma_ratio": _safe(last.get("vol_ma_ratio")),
        "close": _safe(last.get("Close")),
        "market_regime": market_regime,
        "stock_regime": stock_regime,
    }

    ez = analysis.get("entry_zone", {})
    features["entry_zone_width_pct"] = (
        (_safe(ez.get("high")) - _safe(ez.get("low"))) / max(_safe(last.get("Close")), 1) * 100
    )

    return features
