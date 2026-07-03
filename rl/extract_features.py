import pandas as pd
import numpy as np
from pathlib import Path

from data import get_all_market_data, get_fundamental_data, get_jkse_data
from indicators import calculate_full_indicators
from adaptive.config import load_adaptive_config
from performance.journal import _get_conn, init_db
from signals import determine_market_regime
from patterns import detect_patterns, get_pattern_score
from utils.date_utils import normalize_screen_date


FEATURE_COLUMNS = [
    "score", "prob_tp1", "prob_tp2", "prob_tp3", "prob_sl",
    "avg_days_tp1", "adx", "atr",
    "atr_pct", "supertrend_bullish", "st_fast_bullish", "st_slow_bullish",
    "st_bullish_count", "st_layered_entry", "price_above_cloud",
    "donchian_width_pct", "volume_expanding",
    "adx_rising", "ma20_slope", "ma20_above_ma50",
    "consecutive_inside", "bb_width", "dw_percentile_50",
    "fresh_breakout", "volume_pre_breakout", "price_to_donchian_mid",
    "price_to_donchian_upper", "vol_ma_ratio",
    "price_to_supertrend", "price_to_st_fast", "price_to_st_slow",
    "di_spread", "atr_10_slope",
    "price_to_avwap", "tenkan_kijun_spread", "cloud_thickness",
    "return_5d", "volume_zscore", "plus_di", "minus_di",
    "di_spread_x_score", "adx_x_di_spread", "cloud_x_supertrend",
    "tp1_sl_ratio", "tp3_sl_ratio", "setup_encoded", "regime_encoded",
    "pe_ratio", "forward_pe", "pb_ratio", "roe", "revenue_growth",
    "earnings_growth", "dividend_yield", "log_market_cap", "ps_ratio", "book_value",
    "pe_ratio_rank", "roe_rank", "log_market_cap_rank", "return_5d_rank", "vol_ma_ratio_rank",
    "day_of_week", "month", "quarter",
    "obv_rising", "ad_rising", "delta_positive", "volume_delta",
    "rsi", "rsi_oversold", "stoch_k", "stoch_oversold",
    "macd_histogram", "macd_bullish_cross",
    "rsi_bullish_div", "macd_bullish_div",
    "pattern_score", "bullish_patterns", "bearish_patterns",
    "dollar_volume", "vol_cv", "vol_per_atr",
]

RETURN_THRESHOLD = 30

CATEGORICAL_COLUMNS = ["setup", "market_regime"]


def _safe(val, default=0.0):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    try:
        v = float(val)
        # Clip extreme values to prevent inf in ML models
        if np.isinf(v) or abs(v) > 1e10:
            return default
        return v
    except (ValueError, TypeError):
        return default


def _parse_prob(val):
    if val is None:
        return 0.0
    try:
        return float(str(val).strip().rstrip('%'))
    except (ValueError, TypeError):
        return 0.0


def extract_indicator_features(ticker, signal_date_str, market_data, adaptive_params, indicator_cache=None):
    if ticker not in market_data:
        return None

    signal_date = pd.Timestamp(signal_date_str)
    df = market_data[ticker]
    df_slice = df[df.index <= signal_date]

    if indicator_cache is not None and ticker in indicator_cache:
        full = indicator_cache[ticker]
        full_slice = full[full.index <= signal_date]
    else:
        if len(df_slice) < 60:
            return None
        try:
            full = calculate_full_indicators(df_slice, adaptive_params)
            full_slice = full
        except Exception:
            return None

    if len(full_slice) < 60:
        return None

    last = full_slice.iloc[-1]

    c = _safe(last.get("Close"))
    supertrend_line = _safe(last.get("supertrend_line"))
    st_fast_line = _safe(last.get("st_fast_line"))
    st_slow_line = _safe(last.get("st_slow_line"))
    plus_di = _safe(last.get("plus_di"))
    minus_di = _safe(last.get("minus_di"))
    di_sum = plus_di + minus_di
    tenkan = _safe(last.get("tenkan"))
    kijun = _safe(last.get("kijun"))
    senkou_a = _safe(last.get("senkou_a"))
    senkou_b = _safe(last.get("senkou_b"))
    cloud_top = max(senkou_a, senkou_b)
    cloud_bottom = min(senkou_a, senkou_b)
    avwap = _safe(last.get("avwap"))
    vol_ma_val = _safe(last.get("vol_ma"))
    vol_std = _safe(df_slice["Volume"].rolling(20).std().iloc[-1]) if len(df_slice) >= 20 else 0

    features = {
        "adx": _safe(last.get("adx")),
        "atr": _safe(last.get("atr_rm")),
        "atr_pct": _safe(last.get("atr_rm")) / max(c, 1) * 100,
        "supertrend_bullish": 1 if last.get("supertrend_bullish") else 0,
        "st_fast_bullish": 1 if last.get("st_fast_bullish") else 0,
        "st_slow_bullish": 1 if last.get("st_slow_bullish") else 0,
        "st_bullish_count": int(last.get("st_bullish_count", 0)),
        "st_layered_entry": 1 if last.get("st_layered_entry") else 0,
        "price_above_cloud": 1 if last.get("price_above_cloud") else 0,
        "donchian_width_pct": _safe(last.get("donchian_width_pct")),
        "volume_expanding": 1 if last.get("volume_expanding") else 0,
        "adx_rising": 1 if last.get("adx_rising") else 0,
        "ma20_slope": _safe(last.get("ma20_slope")),
        "ma20_above_ma50": 1 if _safe(last.get("ma20")) > _safe(last.get("ma50")) else 0,
        "consecutive_inside": _safe(last.get("consecutive_inside")),
        "bb_width": _safe(last.get("bb_width")),
        "dw_percentile_50": _safe(last.get("dw_percentile_50")),
        "fresh_breakout": 1 if last.get("fresh_breakout") else 0,
        "volume_pre_breakout": 1 if last.get("volume_pre_breakout") else 0,
        "price_to_donchian_mid": c / max(_safe(last.get("donchian_mid")), 1),
        "price_to_donchian_upper": c / max(_safe(last.get("donchian_upper")), 1),
        "vol_ma_ratio": _safe(last.get("vol_ma_ratio")),
        "price_to_supertrend": (c - supertrend_line) / max(c, 1) * 100 if supertrend_line > 0 else 0,
        "price_to_st_fast": (c - st_fast_line) / max(c, 1) * 100 if st_fast_line > 0 else 0,
        "price_to_st_slow": (c - st_slow_line) / max(c, 1) * 100 if st_slow_line > 0 else 0,
        "di_spread": (plus_di - minus_di) / max(di_sum, 1),
        "atr_10_slope": np.clip(_safe(last.get("atr_10_slope")), -10, 10),
        "price_to_avwap": (c - avwap) / max(c, 1) * 100 if avwap > 0 else 0,
        "tenkan_kijun_spread": (tenkan - kijun) / max(abs(kijun), 1) * 100,
        "cloud_thickness": (cloud_top - cloud_bottom) / max(c, 1) * 100,
        "return_5d": c / max(_safe(df_slice["Close"].iloc[-6]) if len(df_slice) >= 6 else c, 1) - 1,
        "volume_zscore": (_safe(last.get("Volume")) - vol_ma_val) / max(vol_std, 1),
        "plus_di": plus_di,
        "minus_di": minus_di,
        # Volume Pressure features
        "obv_rising": 1 if last.get("obv_rising") else 0,
        "ad_rising": 1 if last.get("ad_rising") else 0,
        "delta_positive": 1 if last.get("delta_positive") else 0,
        "volume_delta": np.clip(_safe(last.get("volume_delta")), -1e9, 1e9),
        # Momentum Oscillator features
        "rsi": _safe(last.get("rsi")),
        "rsi_oversold": 1 if last.get("rsi_oversold") else 0,
        "stoch_k": _safe(last.get("stoch_k")),
        "stoch_oversold": 1 if last.get("stoch_oversold") else 0,
        "macd_histogram": _safe(last.get("macd_histogram")),
        "macd_bullish_cross": 1 if last.get("macd_bullish_cross") else 0,
        "rsi_bullish_div": 1 if last.get("rsi_bullish_div") else 0,
        "macd_bullish_div": 1 if last.get("macd_bullish_div") else 0,
    }

    # Pattern features
    try:
        patterns_list, _ = detect_patterns(df_slice)
        pattern_info = get_pattern_score(patterns_list)
        features["pattern_score"] = pattern_info["score"]
        features["bullish_patterns"] = pattern_info["bullish_count"]
        features["bearish_patterns"] = pattern_info["bearish_count"]
    except Exception:
        features["pattern_score"] = 0.0
        features["bullish_patterns"] = 0
        features["bearish_patterns"] = 0

    # Volume Quality features
    features["dollar_volume"] = _safe(last.get("dollar_volume"))
    features["vol_cv"] = _safe(last.get("vol_cv"))
    features["vol_per_atr"] = _safe(last.get("vol_per_atr"))

    return features


def extract_training_data(output_path="rl/training_data.parquet"):
    init_db()
    conn = _get_conn()
    adaptive_params = load_adaptive_config()

    preds = pd.read_sql("""
        SELECT p.*, t.return_pct, t.exit_reason, t.days_held,
               t.hit_tp1, t.hit_tp2, t.hit_tp3, t.hit_sl,
               t.max_favorable, t.max_adverse, t.exit_price
        FROM predictions p
        LEFT JOIN trade_results t ON p.id = t.prediction_id
        WHERE t.return_pct IS NOT NULL
    """, conn)

    if preds.empty:
        print("No training data found. Run backtest first.")
        return None

    preds["screen_date"] = preds["screen_date"].apply(normalize_screen_date)
    preds = preds.dropna(subset=["screen_date"]).reset_index(drop=True)

    LOW_QUALITY_SETUPS = ["TIGHT_BASE_BREAKOUT", "ACCUMULATION"]
    before_count = len(preds)
    preds = preds[~preds["setup"].isin(LOW_QUALITY_SETUPS)].reset_index(drop=True)
    print(f"Filtered {before_count - len(preds)} low-quality setups. Remaining: {len(preds)}")

    print(f"Found {len(preds)} labeled trades. Loading market data...")

    tickers = preds["ticker"].unique().tolist()

    print("Loading fundamental data...", flush=True)
    fundamental_df = get_fundamental_data(tickers)
    fundamental_df['log_market_cap'] = np.log(fundamental_df['market_cap'].clip(lower=1))
    preds = preds.merge(fundamental_df, left_on='ticker', right_index=True, how='left')

    data_start = (preds["screen_date"].min() - pd.Timedelta(days=365)).strftime("%Y-%m-%d")
    data_end = (preds["screen_date"].max() + pd.Timedelta(days=60)).strftime("%Y-%m-%d")
    market_data = get_all_market_data(tickers, start=data_start, end=data_end)

    print(f"Loaded {len(market_data)} tickers. Precomputing indicators...", flush=True)
    indicator_cache = {}
    for ticker in market_data:
        df = market_data[ticker]
        if len(df) >= 60:
            try:
                indicator_cache[ticker] = calculate_full_indicators(df, adaptive_params)
            except Exception:
                pass
    print(f"Precomputed {len(indicator_cache)} tickers.", flush=True)

    print("Loading JKSE and computing market regimes per date...", flush=True)
    jkse_df = get_jkse_data(start=data_start, end=data_end)
    jkse_regime_cache = {}
    if jkse_df is not None:
        unique_dates = sorted(preds["screen_date"].unique())
        for d in unique_dates:
            d_ts = normalize_screen_date(d)
            jkse_slice = jkse_df[jkse_df.index <= d_ts]
            if len(jkse_slice) >= 30:
                jkse_regime_cache[d] = determine_market_regime(jkse_slice)
            else:
                jkse_regime_cache[d] = "SIDEWAYS"
        regime_dist = pd.Series(jkse_regime_cache.values()).value_counts()
        print(f"  Regime distribution: {dict(regime_dist)}", flush=True)
    else:
        print("  WARNING: JKSE data not found, defaulting to SIDEWAYS", flush=True)
    print(f"Extracting features...", flush=True)

    rows = []
    for i, (_, row) in enumerate(preds.iterrows()):
        ticker = row["ticker"]
        screen_date = row["screen_date"]

        if (i + 1) % 1000 == 0:
            print(f"  {i+1}/{len(preds)} processed, {len(rows)} rows", flush=True)

        ind_features = extract_indicator_features(
            ticker, screen_date, market_data, adaptive_params, indicator_cache
        )
        if ind_features is None:
            continue

        features = {
            "ticker": ticker,
            "screen_date": screen_date,
            "setup": row["setup"],
            "score": _safe(row.get("score")),
            "prob_tp1": _parse_prob(row.get("prob_tp1")),
            "prob_tp2": _parse_prob(row.get("prob_tp2")),
            "prob_tp3": _parse_prob(row.get("prob_tp3")),
            "prob_sl": _parse_prob(row.get("prob_sl")),
            "avg_days_tp1": _safe(row.get("avg_days_tp1")),
            "market_regime": jkse_regime_cache.get(screen_date, "SIDEWAYS"),
            "pe_ratio": _safe(row.get("pe_ratio")),
            "forward_pe": _safe(row.get("forward_pe")),
            "pb_ratio": _safe(row.get("pb_ratio")),
            "roe": _safe(row.get("roe")),
            "revenue_growth": _safe(row.get("revenue_growth")),
            "earnings_growth": _safe(row.get("earnings_growth")),
            "dividend_yield": _safe(row.get("dividend_yield")),
            "log_market_cap": _safe(row.get("log_market_cap")),
            "ps_ratio": _safe(row.get("ps_ratio")),
            "book_value": _safe(row.get("book_value")),
        }

        features.update(ind_features)

        features["label_return"] = _safe(row.get("return_pct"))
        features["label_profit"] = 1 if features["label_return"] > RETURN_THRESHOLD else 0
        features["label_exit_reason"] = row.get("exit_reason", "UNKNOWN")

        rows.append(features)

    df = pd.DataFrame(rows)

    print("Computing engineered features...", flush=True)
    setup_mean = df.groupby("setup")["label_return"].mean().to_dict()
    df["setup_encoded"] = df["setup"].map(setup_mean).fillna(0)

    regime_mean = df.groupby("market_regime")["label_return"].mean().to_dict()
    df["regime_encoded"] = df["market_regime"].map(regime_mean).fillna(0)

    df["di_spread_x_score"] = df["di_spread"].astype(float) * df["score"].astype(float)
    df["adx_x_di_spread"] = df["adx"].astype(float) * df["di_spread"].astype(float)
    df["cloud_x_supertrend"] = df["cloud_thickness"].astype(float) * df["supertrend_bullish"].astype(float)
    df["tp1_sl_ratio"] = df["prob_tp1"].astype(float) / (df["prob_sl"].astype(float) + 0.01)
    df["tp3_sl_ratio"] = df["prob_tp3"].astype(float) / (df["prob_sl"].astype(float) + 0.01)

    print("Computing cross-sectional features...", flush=True)
    for col in ['pe_ratio', 'roe', 'log_market_cap', 'return_5d', 'vol_ma_ratio']:
        if col in df.columns:
            df[f'{col}_rank'] = df.groupby('screen_date')[col].rank(pct=True)

    print("Computing temporal features...", flush=True)
    df['day_of_week'] = df['screen_date'].dt.dayofweek
    df['month'] = df['screen_date'].dt.month
    df['quarter'] = df['screen_date'].dt.quarter

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    print(f"Saved {len(df)} samples to {output_path}")
    print(f"Label threshold: >{RETURN_THRESHOLD}%, Profit ratio: {df['label_profit'].mean():.1%}")

    return df
