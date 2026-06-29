import sys
import warnings
warnings.filterwarnings("ignore", message=".*could not convert.*")
warnings.filterwarnings("default", message=".*valid.*convergent.*")
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# ── Module path ──
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from config import TICKERS, INITIAL_CAPITAL, POSITION_SIZE, MAX_POSITIONS, SETUP_ORDER, SIGNAL_MAP, COLOR_MAP, MAX_DISPLAY, MC_HORIZON
from data import get_all_market_data, get_jkse_data, get_fundamental_data
from indicators import calculate_full_indicators
from signals import determine_market_regime, determine_stock_regime, classify_setup_state
from risk import calculate_tp_sl, simulate_tp_sl_probability
from analysis import generate_deep_analysis
from patterns import detect_patterns
from deep_analysis import (
    multi_timeframe_analysis, volume_profile_analysis,
    trendline_analysis, risk_scenario_analysis, generate_interpretation
)

# Performance module
from performance.journal import (
    init_db, get_journal_summary, get_all_predictions, get_trade_results,
    log_prediction, log_trade_result, update_prediction_status, clear_backtest_data
)
from adaptive.config import load_adaptive_config
from performance.metrics import full_report, format_report, setup_breakdown, exit_reason_breakdown, sharpe_ratio, max_drawdown, win_rate
from performance.calibration import calibration_analysis, brier_score, expected_calibration_error, maximum_calibration_error
from performance.backtest import run_screening_at_date
from rl.auto_retrain import auto_retrain, get_retrain_status
from utils.date_utils import normalize_screen_date, safe_screen_date_str
from utils.price_utils import round_to_tick

# ── Page config ──
st.set_page_config(page_title="Swing Screener v2", layout="wide", initial_sidebar_state="expanded")

# ── Load custom CSS ──
@st.cache_resource
def load_css():
    css_path = Path(__file__).parent / ".streamlit" / "styles.css"
    if css_path.exists():
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        # Inline fallback CSS
        st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        [data-testid="stMetric"] {
            background: linear-gradient(135deg, #1a1f2e 0%, #16192a 100%);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 14px;
            padding: 18px 22px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.25);
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        }
        [data-testid="stMetric"]:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.35);
            border-color: rgba(66, 165, 245, 0.2);
        }
        [data-testid="stMetricValue"] {
            font-family: 'Inter', monospace;
            font-weight: 700;
            font-size: 1.75rem;
            letter-spacing: -0.5px;
        }
        [data-testid="stMetricLabel"] {
            font-family: 'Inter', monospace;
            font-weight: 500;
            font-size: 0.8rem;
            color: #78909C;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 6px;
            background: rgba(255,255,255,0.02);
            border-radius: 12px;
            padding: 6px;
            border: 1px solid rgba(255,255,255,0.04);
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 10px;
            padding: 10px 20px;
            font-family: 'Inter', monospace;
            font-weight: 500;
            font-size: 0.85rem;
            color: #90A4AE;
            transition: all 0.2s;
            border: none;
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #1a237e 0%, #0d47a1 100%) !important;
            color: #FFFFFF !important;
            font-weight: 600;
            box-shadow: 0 2px 8px rgba(21, 101, 192, 0.3);
        }
        .stButton > button {
            font-family: 'Inter', monospace;
            font-weight: 600;
            border-radius: 10px;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #1565C0 0%, #0D47A1 100%);
            border: none;
            box-shadow: 0 4px 12px rgba(21, 101, 192, 0.35);
        }
        .stButton > button[kind="primary"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(21, 101, 192, 0.45);
        }
        h1, h2, h3, h4, h5, h6 {
            font-family: 'Inter', monospace !important;
            letter-spacing: -0.3px;
        }
        </style>
        """, unsafe_allow_html=True)

load_css()

# ── Constants ──
TIMING_MAP = {
    "ENTRY_READY": ("🟢", "Ready to enter"),
    "WAIT_VOLUME": ("🟡", "Wait for volume"),
    "WAIT_PRICE": ("🟡", "Wait for price"),
    "WAIT_PULLBACK": ("🟡", "Wait for pullback"),
    "WAIT_RETEST": ("🟡", "Wait for retest"),
    "WAIT_CONFIRMATION": ("🟡", "Wait for confirmation"),
    "WAIT": ("🔴", "Wait"),
    "HOLD": ("⚪", "Hold"),
}

# ── Session state defaults ──
for key in ["screening_df", "market_data", "market_regime", "screening_done"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "screening_done" else False


# ═══════════════════════════════════════════
# CACHED FUNCTIONS
# ═══════════════════════════════════════════

@st.cache_data(ttl=3600 * 18, show_spinner="Loading market data...")
def cached_load_data(start_date=None, end_date=None):
    return get_all_market_data(TICKERS, start=start_date, end=end_date)


@st.cache_data(ttl=3600 * 18, show_spinner="Loading IHSG...")
def cached_jkse():
    return get_jkse_data()


@st.cache_data(ttl=3600 * 24 * 3, show_spinner="Loading fundamental data...")
def cached_fundamental():
    return get_fundamental_data(TICKERS)


# Setup encoding (from training data analysis)
SETUP_ENCODING = {
    "PRE_BREAKOUT": 3.60,
    "BASE_ON_BASE": 3.21,
    "PULLBACK_MA20": 1.95,
    "EARLY_REVERSAL": 0.01,
    "ACCUMULATION": 0.58,
    "BREAKOUT": 0.14,
    "TIGHT_BASE_BREAKOUT": 0.07,
}

REGIME_ENCODING = {
    "BULL": 5.0,
    "SIDEWAYS": 3.0,
    "BEAR": 1.0,
}


@st.cache_data(ttl=3600, show_spinner="Running screener...")
def cached_run_screener(market_data_hash, market_regime):
    results = []
    skipped = {"short_data": 0, "no_setup": 0, "error": 0}
    adaptive_params = load_adaptive_config()
    markov_cache = {}

    progress_data = list(st.session_state.get("market_data", {}).items())
    total = len(progress_data)

    import time as _time
    start_time = _time.time()

    for idx, (ticker, df) in enumerate(progress_data):
        if (idx + 1) % 100 == 0:
            elapsed = _time.time() - start_time
            rate = (idx + 1) / elapsed if elapsed > 0 else 0
            eta = (total - idx - 1) / rate if rate > 0 else 0
            print(f"  Screening: {idx+1}/{total} tickers ({elapsed:.1f}s elapsed, ETA {eta:.0f}s)", flush=True)

        try:
            if len(df) < 100:
                skipped["short_data"] += 1
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            full = calculate_full_indicators(df, adaptive_params)
            last = full.iloc[-1]
            stock_regime = determine_stock_regime(full)
            setup, valid = classify_setup_state(full, stock_regime, adaptive_params)

            if not valid:
                skipped["no_setup"] += 1
                continue

            is_bear_filtered = False
            if market_regime == "BEAR" and setup != "EARLY_REVERSAL":
                is_bear_filtered = True

            close = last['Close']
            atr = last['atr_rm']
            adx = last['adx'] if pd.notna(last['adx']) else 0

            if close < 70:
                skipped["no_setup"] += 1
                continue

            if atr is None or pd.isna(atr) or atr / close < 0.001:
                skipped["no_setup"] += 1
                continue

            signal_type = SIGNAL_MAP.get(setup, "BUY")
            sl, tp1, tp2, tp3, profit_pct, risk_pct = calculate_tp_sl(close, atr, signal_type, adaptive_params)
            if sl is None or (risk_pct is not None and risk_pct < 0.1):
                skipped["no_setup"] += 1
                continue

            analysis = generate_deep_analysis(full, setup, close, atr, adaptive_params)
            entry_zone = analysis["entry_zone"]

            prob = simulate_tp_sl_probability(df, close, analysis["sl_normal"], analysis["tp1"], analysis["tp2"], analysis["tp3"],
                                               markov_cache=markov_cache, markov_cache_key=ticker)
            if prob is None:
                prob = {"P_TP1": None, "P_TP2": None, "P_TP3": None, "P_SL": None,
                        "AVG_DAYS_TP1": None, "AVG_DAYS_TP2": None, "AVG_DAYS_TP3": None}

            def _pf(val):
                if val is None: return 0.0
                try: return float(str(val).strip().rstrip('%'))
                except: return 0.0
            p_sl_val = _pf(prob.get("P_SL"))
            p_tp3_val = _pf(prob.get("P_TP3"))
            if p_sl_val > 60 or (p_tp3_val == 0 and p_sl_val > 55):
                skipped["no_setup"] += 1
                continue

            def _safe_float(val, default=0.0):
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    return default
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return default

            ma20_val = _safe_float(last.get("ma20"))
            ma50_val = _safe_float(last.get("ma50"))
            donchian_mid_val = _safe_float(last.get("donchian_mid"))
            donchian_upper_val = _safe_float(last.get("donchian_upper"))

            supertrend_line_val = _safe_float(last.get("supertrend_line"))
            plus_di_val = _safe_float(last.get("plus_di"))
            minus_di_val = _safe_float(last.get("minus_di"))
            di_sum_val = plus_di_val + minus_di_val
            tenkan_val = _safe_float(last.get("tenkan_sen"))
            kijun_val = _safe_float(last.get("kijun_sen"))
            senkou_a_val = _safe_float(last.get("senkou_a"))
            senkou_b_val = _safe_float(last.get("senkou_b"))
            cloud_top_val = max(senkou_a_val, senkou_b_val)
            cloud_bottom_val = min(senkou_a_val, senkou_b_val)
            avwap_val = _safe_float(last.get("avwap"))
            vol_ma_val = _safe_float(last.get("vol_ma"))
            vol_std_val = 1.0

            di_spread_val = (plus_di_val - minus_di_val) / max(di_sum_val, 1)
            score_val = 0  # Will be computed later

            rl_features = {
                "setup": setup,
                "score": score_val,
                "prob_tp1": _pf(prob.get("P_TP1")),
                "prob_tp2": _pf(prob.get("P_TP2")),
                "prob_tp3": _pf(prob.get("P_TP3")),
                "prob_sl": p_sl_val,
                "avg_days_tp1": _safe_float(prob.get("AVG_DAYS_TP1"), 999),
                "market_regime": market_regime,
                "adx": _safe_float(last.get("adx")),
                "atr": atr,
                "atr_pct": atr / close * 100 if close > 0 else 0,
                "supertrend_bullish": 1 if last.get("supertrend_bullish") else 0,
                "price_above_cloud": 1 if last.get("price_above_cloud") else 0,
                "donchian_width_pct": _safe_float(last.get("donchian_width_pct")),
                "volume_expanding": 1 if last.get("volume_expanding") else 0,
                "adx_rising": 1 if last.get("adx_rising") else 0,
                "ma20_slope": _safe_float(last.get("ma20_slope")),
                "ma20_above_ma50": 1 if ma20_val > ma50_val else 0,
                "consecutive_inside": _safe_float(last.get("consecutive_inside")),
                "bb_width": _safe_float(last.get("bb_width")),
                "dw_percentile_50": _safe_float(last.get("dw_percentile_50")),
                "fresh_breakout": 1 if last.get("fresh_breakout") else 0,
                "volume_pre_breakout": 1 if last.get("volume_pre_breakout") else 0,
                "price_to_donchian_mid": close / donchian_mid_val if donchian_mid_val > 0 else 1.0,
                "price_to_donchian_upper": close / donchian_upper_val if donchian_upper_val > 0 else 1.0,
                "vol_ma_ratio": _safe_float(last.get("vol_ma_ratio")),
                "price_to_supertrend": (close - supertrend_line_val) / max(close, 1) * 100 if supertrend_line_val > 0 else 0,
                "di_spread": di_spread_val,
                "atr_10_slope": _safe_float(last.get("atr_10_slope")),
                "price_to_avwap": (close - avwap_val) / max(close, 1) * 100 if avwap_val > 0 else 0,
                "tenkan_kijun_spread": (tenkan_val - kijun_val) / max(abs(kijun_val), 1) * 100,
                "cloud_thickness": (cloud_top_val - cloud_bottom_val) / max(close, 1) * 100,
                "return_5d": 0,
                "volume_zscore": 0,
                "plus_di": plus_di_val,
                "minus_di": minus_di_val,
                # Interaction features
                "di_spread_x_score": di_spread_val * score_val,
                # Encoded features
                "setup_encoded": SETUP_ENCODING.get(setup, 0),
                "regime_encoded": REGIME_ENCODING.get(market_regime, 3.0),
                # Temporal features
                "day_of_week": datetime.now().weekday(),
                "month": datetime.now().month,
            }

            results.append({
                "Ticker": ticker,
                "Setup": setup,
                "Price": round(close, 2),
                "Stock Regime": stock_regime,
                "ADX": round(adx, 2),
                "Profit %": profit_pct if profit_pct else 0,
                "Risk %": risk_pct if risk_pct else 0,
                "Prob(TP1)": prob["P_TP1"],
                "Prob(TP2)": prob["P_TP2"],
                "Prob(TP3)": prob["P_TP3"],
                "Prob(SL)": prob["P_SL"],
                "Avg Days TP1": round(prob["AVG_DAYS_TP1"], 2) if prob["AVG_DAYS_TP1"] else None,
                "Avg Days TP3": round(prob["AVG_DAYS_TP3"], 2) if prob["AVG_DAYS_TP3"] else None,
                "Stop Loss": round(analysis["sl_normal"], 2),
                "SL Wide": round(analysis["sl_wide"]["price"], 2),
                "TP1": round(analysis["tp1"], 2),
                "TP2": round(analysis["tp2"], 2),
                "TP3": round(analysis["tp3"], 2),
                "Entry Zone Low": entry_zone["low"],
                "Entry Zone High": entry_zone["high"],
                "Entry Strategy": entry_zone["strategy"],
                "Timing": analysis["timing"]["label"],
                "Timing Detail": analysis["timing"]["detail"],
                "Chart": analysis["chart"],
                "Score": 0,
                "BearFiltered": is_bear_filtered,
                "rl_features": rl_features,
            })
        except Exception:
            skipped["error"] += 1

    df_out = pd.DataFrame(results)
    if not df_out.empty:
        def _parse_prob(val):
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return 0.0
            s = str(val).strip().rstrip('%')
            try:
                return float(s)
            except (ValueError, TypeError):
                return 0.0

        for tp in ["TP1", "TP2", "TP3"]:
            col = f"Prob({tp})"
            if col in df_out.columns:
                df_out[f"Prob_{tp}_float"] = df_out[col].apply(_parse_prob)
        df_out["Prob_SL_float"] = df_out.get("Prob(SL)", pd.Series(dtype=str)).apply(_parse_prob)
        df_out["Avg Days TP1"] = df_out.get("Avg Days TP1", pd.Series(dtype=float)).fillna(999)
        df_out["Avg Days TP3"] = df_out.get("Avg Days TP3", pd.Series(dtype=float)).fillna(999)

        ap = load_adaptive_config()
        w_tp = ap.get("score_w_prob_tp", 1.0)
        w_pf = ap.get("score_w_profit_pct", 0.5)
        w_sl = ap.get("score_w_prob_sl", -1.0)
        w_d3 = ap.get("score_w_avg_days", -0.3)

        df_out["TP_Likelihood"] = (
            w_tp * df_out.get("Prob_TP1_float", 0)
            + w_pf * (df_out.get("Prob_TP1_float", 0) / (df_out["Prob_SL_float"] + 0.01))
            + w_sl * df_out["Prob_SL_float"]
            + w_d3 * df_out["Avg Days TP1"]
        )
        df_out["Score"] = df_out["TP_Likelihood"]
        bear_mask = df_out.get("BearFiltered", False)
        low_score_mask = df_out["Score"] < 0.5
        df_out = df_out[~(bear_mask & low_score_mask)].reset_index(drop=True)

        # Add fundamental data features
        try:
            fundamental_df = cached_fundamental()
            fundamental_features = ['pe_ratio', 'forward_pe', 'pb_ratio', 'roe', 'revenue_growth',
                                   'earnings_growth', 'dividend_yield', 'log_market_cap', 'ps_ratio', 'book_value']

            for col in fundamental_features:
                if col in fundamental_df.columns:
                    df_out[col] = df_out['Ticker'].map(fundamental_df[col]).fillna(0)
                else:
                    df_out[col] = 0

            # Update rl_features with fundamental data
            for idx, row in df_out.iterrows():
                if row.get('rl_features'):
                    for col in fundamental_features:
                        row['rl_features'][col] = row.get(col, 0)
        except Exception:
            # If fundamental data fails, add defaults
            for col in ['pe_ratio', 'forward_pe', 'pb_ratio', 'roe', 'revenue_growth',
                       'earnings_growth', 'dividend_yield', 'log_market_cap', 'ps_ratio', 'book_value']:
                df_out[col] = 0

        # Add rank features (relative to other screened stocks)
        rank_features = ['pe_ratio', 'roe', 'log_market_cap', 'vol_ma_ratio']
        for col in rank_features:
            if col in df_out.columns and df_out[col].notna().any():
                df_out[f'{col}_rank'] = df_out[col].rank(pct=True)
            else:
                df_out[f'{col}_rank'] = 0.5

        # Update rl_features with rank features
        for idx, row in df_out.iterrows():
            if row.get('rl_features'):
                for col in rank_features:
                    row['rl_features'][f'{col}_rank'] = row.get(f'{col}_rank', 0.5)

        rl_scores = []
        profit_probs = []
        # Batch RL scoring
        rl_inputs = []
        for _, row in df_out.iterrows():
            rl_feat = row.get("rl_features", None)
            if rl_feat is None or (isinstance(rl_feat, float) and pd.isna(rl_feat)):
                rl_feat = row.to_dict()
            rl_inputs.append(rl_feat)

        from rl.ranker import predict_rl_scores_batch
        batch_results = predict_rl_scores_batch(rl_inputs)
        for rl_s, p_prob in batch_results:
            rl_scores.append(rl_s)
            profit_probs.append(p_prob * 100 if p_prob is not None else p_prob)
        df_out["RL Score"] = rl_scores
        df_out["Profit Prob"] = profit_probs

        df_out = df_out.sort_values("Score", ascending=False).reset_index(drop=True)

    return df_out, skipped


# ═══════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════

def render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div style="padding: 8px 0 16px;">
            <h1 style="margin: 0; font-size: 1.6rem; background: linear-gradient(135deg, #42A5F5, #26A69A);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800;">
                ⚡ Swing Screener
            </h1>
            <p style="color: #607D8B; margin: 4px 0 0 0; font-size: 0.8rem; font-weight: 500;">v2 — AI-Powered Detection</p>
        </div>
        """, unsafe_allow_html=True)

        # Market regime badge
        regime = st.session_state.get("market_regime")
        if regime:
            emoji = {"BULL": "🟢", "SIDEWAYS": "🟡", "BEAR": "🔴"}.get(regime, "⚪")
            color = {"BULL": "#66BB6A", "SIDEWAYS": "#FFA726", "BEAR": "#EF5350"}.get(regime, "#90A4AE")
            st.markdown(f"""
            <div style="background: {color}15; border: 1px solid {color}30; border-radius: 10px;
                padding: 12px 16px; text-align: center; margin-bottom: 16px;">
                <span style="color: {color}; font-weight: 600; font-size: 0.95rem;">{emoji} Market: {regime}</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 10px;
                padding: 12px 16px; text-align: center; margin-bottom: 16px;">
                <span style="color: #90A4AE; font-weight: 500; font-size: 0.95rem;">⚪ Market: --</span>
            </div>
            """, unsafe_allow_html=True)

        # Run button
        if st.button("🚀 Run Screener", type="primary", use_container_width=True):
            with st.spinner("Loading data..."):
                md = cached_load_data()
                jkse = cached_jkse()
                mr = determine_market_regime(jkse) if jkse is not None else "SIDEWAYS"
                st.session_state.market_data = md
                st.session_state.market_regime = mr

            market_hash = hash(frozenset(md.keys()))
            df_out, skipped = cached_run_screener(market_hash, mr)
            st.session_state.screening_df = df_out
            st.session_state.screening_done = True

            st.success(f"Done! {len(df_out)} setups found.")
            st.caption(f"Skipped: short_data={skipped.get('short_data',0)}, no_setup={skipped.get('no_setup',0)}, errors={skipped.get('error',0)}")

            ap = load_adaptive_config()
            if ap.get("rl_auto_retrain", True):
                min_trades = ap.get("rl_min_new_trades", 50)
                try:
                    retrain_result = auto_retrain(min_new_trades=min_trades)
                    if retrain_result.get("retrained"):
                        if retrain_result.get("deployed"):
                            st.info(f"🔄 RL model retrained & deployed: {retrain_result.get('reason', '')}")
                        else:
                            st.info(f"🔄 RL model retrained but kept old: {retrain_result.get('reason', '')}")
                except Exception as e:
                    pass

            st.rerun()

        st.divider()

        # Filters (visible after screening)
        if st.session_state.screening_done and st.session_state.screening_df is not None:
            df = st.session_state.screening_df
            if df.empty or "Setup" not in df.columns:
                st.warning("No screening results. Run the screener first.")
            else:
                st.subheader("🔎 Filters")

                selected_setups = []
                for s in SETUP_ORDER:
                    cnt = len(df[df["Setup"] == s])
                    if st.checkbox(f"{s} ({cnt})", value=True, key=f"filt_{s}"):
                        selected_setups.append(s)

                st.session_state._filter_setups = selected_setups

                st.slider("Min Score", 0, 200, 0, key="filt_min_score")

                timing_opts = ["All"] + [k for k, v in TIMING_MAP.items() if v[0] in ("🟢", "🟡")]
                st.selectbox("Timing", timing_opts, key="filt_timing")

        st.divider()
        # st.markdown("""
        # <div style="text-align: center; padding: 8px 0;">
        #     <div class="dyor-disclaimer-small">
        #         ⚠️ Think First. Trade Second. DYOR - Do Your Own Research
        #     </div>
        #     <p style="color: #455A64; font-size: 0.7rem; margin: 0;">Built with Streamlit + yfinance</p>
        #     <p style="color: #37474F; font-size: 0.65rem; margin: 4px 0 0 0;">Swing Screener v2</p>
        # </div>
        # """, unsafe_allow_html=True)


# ═══════════════════════════════════════════
# DASHBOARD TAB
# ═══════════════════════════════════════════

def render_dashboard():
    df = st.session_state.screening_df
    if df is None or df.empty or "Setup" not in df.columns:
        st.info("Run the screener first from the sidebar.")
        return

    regime = st.session_state.get("market_regime", "N/A")

    # ── Header with market regime ──
    regime_color = {"BULL": "#66BB6A", "SIDEWAYS": "#FFA726", "BEAR": "#EF5350"}.get(regime, "#90A4AE")
    regime_emoji = {"BULL": "🟢", "SIDEWAYS": "🟡", "BEAR": "🔴"}.get(regime, "⚪")
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; color: #ECEFF1;">Dashboard</h2>
        <span style="background: {regime_color}22; color: {regime_color}; padding: 6px 14px; border-radius: 8px;
            font-weight: 600; font-size: 0.85rem; border: 1px solid {regime_color}44;">
            {regime_emoji} Market: {regime}
        </span>
        <span style="color: #78909C; font-size: 0.9rem; margin-left: auto;">
            {len(df)} setups detected
        </span>
    </div>
    """, unsafe_allow_html=True)

    # ── Metrics row ──
    st.metric("Total Setups", len(df))

    row1_cols = st.columns(5)
    row2_cols = st.columns(5)
    all_cols = row1_cols + row2_cols

    for i, s in enumerate(SETUP_ORDER):
        cnt = len(df[df["Setup"] == s])
        all_cols[i].metric(s.replace("_", " ").title(), cnt)

    st.divider()

    # ── Charts row ──
    chart_col1, chart_col2 = st.columns([2, 1])

    with chart_col1:
        st.subheader("📊 Setup Distribution")
        dist = df["Setup"].value_counts().reset_index()
        dist.columns = ["Setup", "Count"]
        fig = px.bar(dist, x="Setup", y="Count", color="Setup",
                     color_discrete_map=COLOR_MAP, text="Count")
        fig.update_layout(
            showlegend=False, height=320,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#B0BEC5", font_family="Inter",
            xaxis=dict(tickfont=dict(size=11)),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
            margin=dict(l=40, r=20, t=10, b=40),
        )
        fig.update_traces(textposition="outside", textfont=dict(size=11, color="#B0BEC5"))
        st.plotly_chart(fig, use_container_width=True)

    with chart_col2:
        st.subheader("🎯 Setup Mix")
        setup_counts = df["Setup"].value_counts()
        fig_pie = px.pie(
            values=setup_counts.values, names=setup_counts.index,
            color=setup_counts.index, color_discrete_map=COLOR_MAP,
            hole=0.45,
        )
        fig_pie.update_traces(textinfo="percent", textfont=dict(size=10, color="#fff"))
        fig_pie.update_layout(
            height=320, showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#B0BEC5", font_family="Inter",
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    # ── Timing Summary ──
    if "Timing" in df.columns:
        st.subheader("⏱️ Timing Overview")
        timing_counts = df["Timing"].value_counts()
        tcols = st.columns(min(len(timing_counts), 6))
        for i, (timing, count) in enumerate(timing_counts.items()):
            if i >= 6:
                break
            emoji = TIMING_MAP.get(timing, ("⚪", ""))[0]
            tcols[i].metric(f"{emoji} {timing.replace('_', ' ').title()}", count)

        st.divider()

    # ── All Screening Results ──
    st.subheader(f"📋 All Screening Results ({len(df)} stocks)")
    display_cols = ["Ticker", "Setup", "Price", "Score", "RL Score", "Profit Prob", "Prob(TP1)", "Prob(SL)",
                    "Timing", "Entry Zone Low", "Entry Zone High", "Stop Loss"]
    avail_cols = [c for c in display_cols if c in df.columns]

    def _color_setup(val):
        return f"background-color: {COLOR_MAP.get(val, '#888')}; color: black; font-weight: bold"

    styled = df[avail_cols].style.map(_color_setup, subset=["Setup"])
    st.dataframe(styled, use_container_width=True, hide_index=True,
                 column_config={
                     "Ticker": st.column_config.TextColumn("Ticker", width="small"),
                     "Setup": st.column_config.TextColumn("Setup", width="medium"),
                     "Price": st.column_config.NumberColumn("Price", format="%.2f"),
                     "Score": st.column_config.NumberColumn("Score", format="%.1f"),
                     "RL Score": st.column_config.NumberColumn("RL Score", format="%.1f"),
                     "Profit Prob": st.column_config.NumberColumn("Profit %", format="%.1f%%"),
                     "Prob(TP1)": st.column_config.TextColumn("P(TP1)", width="small"),
                     "Prob(SL)": st.column_config.TextColumn("P(SL)", width="small"),
                     "Timing": st.column_config.TextColumn("Timing", width="medium"),
                     "Entry Zone Low": st.column_config.NumberColumn("Entry Low", format="%.2f"),
                     "Entry Zone High": st.column_config.NumberColumn("Entry High", format="%.2f"),
                     "Stop Loss": st.column_config.NumberColumn("Stop Loss", format="%.2f"),
                 })


# ═══════════════════════════════════════════
# RESULTS TAB
# ═══════════════════════════════════════════

def render_results():
    df = st.session_state.screening_df
    if df is None or df.empty or "Setup" not in df.columns:
        st.info("Run the screener first.")
        return

    # Apply filters
    filtered = df.copy()
    if hasattr(st.session_state, "_filter_setups") and st.session_state._filter_setups:
        filtered = filtered[filtered["Setup"].isin(st.session_state._filter_setups)]
    if st.session_state.get("filt_min_score", 0) > 0:
        filtered = filtered[filtered["Score"] >= st.session_state.filt_min_score]
    if st.session_state.get("filt_timing", "All") != "All":
        filtered = filtered[filtered["Timing"] == st.session_state.filt_timing]

    st.subheader(f"Results: {len(filtered)} setups")

    # Data table
    display_cols = ["Ticker", "Setup", "Price", "Stock Regime", "Score", "RL Score", "Profit Prob",
                    "Prob(TP1)", "Prob(TP2)", "Prob(SL)", "Profit %", "Risk %",
                    "Timing", "Entry Zone Low", "Entry Zone High", "Stop Loss",
                    "TP1", "TP2"]

    avail = [c for c in display_cols if c in filtered.columns]
    display_df = filtered[avail].copy()

    event = st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Ticker": st.column_config.TextColumn("Ticker", width="small"),
            "Setup": st.column_config.TextColumn("Setup", width="medium"),
            "Score": st.column_config.NumberColumn("Score", format="%.0f"),
            "RL Score": st.column_config.NumberColumn("RL Score", format="%.1f"),
            "Profit Prob": st.column_config.NumberColumn("Profit Prob", format="%.0f%%"),
            "Price": st.column_config.NumberColumn("Price", format="%.2f"),
            "Prob(TP1)": st.column_config.TextColumn("P(TP1)", width="small"),
            "Prob(TP2)": st.column_config.TextColumn("P(TP2)", width="small"),
            "Prob(SL)": st.column_config.TextColumn("P(SL)", width="small"),
            "Profit %": st.column_config.NumberColumn("Profit%", format="%.1f"),
            "Risk %": st.column_config.NumberColumn("Risk%", format="%.1f"),
            "Entry Zone Low": st.column_config.NumberColumn("Entry Low", format="%.2f"),
            "Entry Zone High": st.column_config.NumberColumn("Entry High", format="%.2f"),
            "Stop Loss": st.column_config.NumberColumn("Stop Loss", format="%.2f"),
        }
    )

    # Show detail box on selection
    if event.selection and event.selection.rows:
        idx = event.selection.rows[0]
        row = filtered.iloc[idx]
        ticker = row["Ticker"]
        st.divider()
        st.subheader(f"📋 {ticker} — Detail")

        md = st.session_state.get("market_data", {})
        ticker_df = md.get(ticker)
        if ticker_df is not None:
            if isinstance(ticker_df.columns, pd.MultiIndex):
                ticker_df.columns = ticker_df.columns.get_level_values(0)
            adaptive_params = load_adaptive_config()
            full = calculate_full_indicators(ticker_df, adaptive_params)
            last = full.iloc[-1]
            da = generate_deep_analysis(full, row["Setup"], last["Close"], last["atr_rm"], adaptive_params)

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Entry Zone", f"{da['entry_zone']['low']} - {da['entry_zone']['high']}")
                st.caption(da['entry_zone']['strategy'])
            with c2:
                st.metric("Stop Loss", f"Norm: {da['sl_normal']} / Wide: {da['sl_wide']['price']}")
            with c3:
                st.metric("Timing", da['timing']['label'])
                st.caption(da['timing']['detail'])

            st.text(da['chart'])

    # CSV download with analysis date
    analysis_date = datetime.now().strftime("%d%b%Y")
    csv_filename = f"hasil_screener_{analysis_date}.csv"
    
    analysis_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    market_regime = st.session_state.get('market_regime', 'N/A')
    header = f"# Swing Screener Analysis - {analysis_timestamp}\n"
    header += f"# Market Regime: {market_regime}\n"
    header += f"# Total Setups: {len(filtered)}\n#\n"
    
    csv_content = filtered.to_csv(index=False)
    csv = (header + csv_content).encode("utf-8")
    st.download_button("📥 Download CSV", csv, csv_filename, "text/csv", use_container_width=True)

    # Per-Setup Top 5
    st.divider()
    st.subheader("🎯 Top 5 Per Setup (Ranked by RL Score)")

    def _color_setup_r(val):
        return f"background-color: {COLOR_MAP.get(val, '#888')}; color: black; font-weight: bold"

    shown = False
    for s in SETUP_ORDER:
        setup_df = df[df["Setup"] == s]
        if setup_df.empty:
            continue
        shown = True
        has_rl = "RL Score" in setup_df.columns and setup_df["RL Score"].notna().any()
        if has_rl:
            top5 = setup_df.nlargest(5, "RL Score")
        else:
            top5 = setup_df.nlargest(5, "Score")
        display_cols = ["Ticker", "Price", "Prob(TP1)", "Prob(SL)", "Score", "RL Score", "Profit Prob", "Timing"]
        avail_cols = [c for c in display_cols if c in top5.columns]
        t5 = top5[avail_cols].copy()
        t5.insert(0, "Setup", s)

        with st.expander(f"**{s.replace('_', ' ').title()}** ({len(setup_df)} stocks)", expanded=False):
            styled_t5 = t5.style.map(_color_setup_r, subset=["Setup"])
            st.dataframe(styled_t5, use_container_width=True, hide_index=True,
                         column_config={
                             "Setup": st.column_config.TextColumn("Setup", width="medium"),
                             "Ticker": st.column_config.TextColumn("Ticker", width="small"),
                             "Price": st.column_config.NumberColumn("Price", format="%.2f"),
                             "Prob(TP1)": st.column_config.TextColumn("P(TP1)", width="small"),
                             "Prob(SL)": st.column_config.TextColumn("P(SL)", width="small"),
                             "Score": st.column_config.NumberColumn("TP Score", format="%.1f"),
                             "RL Score": st.column_config.NumberColumn("RL Score", format="%.1f"),
                             "Profit Prob": st.column_config.NumberColumn("Profit Prob", format="%.0f%%"),
                             "Timing": st.column_config.TextColumn("Timing", width="medium"),
                         })

    if not shown:
        st.info("No setups found.")


# ═══════════════════════════════════════════
# PLOTLY CHART
# ═══════════════════════════════════════════

def render_plotly_chart(full, da, levels):
    n_bars = min(120, len(full))
    df = full.tail(n_bars).copy()
    df = df.reset_index()

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6, 0.2, 0.2],
    )

    # ── Candlestick ──
    fig.add_trace(go.Candlestick(
        x=df['Date'], open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'],
        increasing_line_color='#26a69a', decreasing_line_color='#ef5350',
        increasing_fillcolor='#26a69a', decreasing_fillcolor='#ef5350',
        name='Price', showlegend=False,
    ), row=1, col=1)

    # ── SuperTrend line + markers ──
    if 'supertrend_line' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['Date'], y=df['supertrend_line'],
            mode='lines', name='SuperTrend',
            line=dict(color='orange', width=1.5),
            showlegend=True,
        ), row=1, col=1)

        # Markers
        bull_idx = df[df['supertrend_dir'] > 0].index
        bear_idx = df[df['supertrend_dir'] <= 0].index
        if len(bull_idx) > 0:
            fig.add_trace(go.Scatter(
                x=df.loc[bull_idx, 'Date'], y=df.loc[bull_idx, 'Low'] * 0.99,
                mode='markers', name='ST Bullish',
                marker=dict(symbol='triangle-up', size=7, color='#26a69a'),
                showlegend=False,
            ), row=1, col=1)
        if len(bear_idx) > 0:
            fig.add_trace(go.Scatter(
                x=df.loc[bear_idx, 'Date'], y=df.loc[bear_idx, 'High'] * 1.01,
                mode='markers', name='ST Bearish',
                marker=dict(symbol='triangle-down', size=7, color='#ef5350'),
                showlegend=False,
            ), row=1, col=1)

    # ── MA20 + MA50 ──
    if 'ma20' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['Date'], y=df['ma20'],
            mode='lines', name='MA20',
            line=dict(color='#42a5f5', width=1.5),
            showlegend=True,
        ), row=1, col=1)
    if 'ma50' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['Date'], y=df['ma50'],
            mode='lines', name='MA50',
            line=dict(color='#ab47bc', width=1.5),
            showlegend=True,
        ), row=1, col=1)

    # ── Entry Zone highlight ──
    entry_low = da['entry_zone']['low']
    entry_high = da['entry_zone']['high']
    entry_low_ticked = round_to_tick(entry_low)
    entry_high_ticked = round_to_tick(entry_high)
    fig.add_hrect(
        y0=entry_low, y1=entry_high,
        fillcolor='rgba(255, 235, 59, 0.15)', line_width=0,
        row=1, col=1,
    )
    fig.add_trace(go.Scatter(
        x=[None], y=[None],
        mode='lines',
        line=dict(color='rgba(255, 235, 59, 0.5)', width=2),
        name=f'Entry Zone ({entry_low_ticked:.0f}-{entry_high_ticked:.0f})',
        showlegend=True,
    ), row=1, col=1)

    # ── SL lines ──
    sl_normal = da['sl_normal']
    sl_wide = da['sl_wide']['price']
    fig.add_hline(y=sl_normal, line_dash='solid', line_color='#ef5350',
                  line_width=2, annotation_text=f"SL {round_to_tick(sl_normal):.0f}",
                  annotation_position='bottom left', row=1, col=1)
    fig.add_hline(y=sl_wide, line_dash='dash', line_color='#ef5350',
                  line_width=1.5, annotation_text=f"SL Wide {round_to_tick(sl_wide):.0f}",
                  annotation_position='bottom left', row=1, col=1)

    # ── TP lines ──
    for ta in da['tp_analysis']:
        fig.add_hline(y=ta['price'], line_dash='solid', line_color='#66bb6a',
                      line_width=1.5, annotation_text=f"{ta['label']} {round_to_tick(ta['price']):.0f}",
                      annotation_position='top left', row=1, col=1)

    # ── Volume bars (colored by delta) ──
    if 'delta_positive' in df.columns:
        colors = ['#26a69a' if dp else '#ef5350' for dp in df['delta_positive']]
    else:
        colors = ['#26a69a' if c >= o else '#ef5350'
                  for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(
        x=df['Date'], y=df['Volume'],
        marker_color=colors, name='Volume',
        showlegend=False,
    ), row=2, col=1)

    # ── Volume MA ──
    if 'vol_ma' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['Date'], y=df['vol_ma'],
            mode='lines', name='Vol MA20',
            line=dict(color='white', width=1),
            showlegend=False,
        ), row=2, col=1)

    # ── Momentum: RSI + Stochastic + MACD ──
    if 'rsi' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['Date'], y=df['rsi'],
            mode='lines', name='RSI',
            line=dict(color='#42a5f5', width=1.5),
            showlegend=True,
        ), row=3, col=1)
        # RSI levels
        fig.add_hline(y=30, line_dash='dot', line_color='#66bb6a', line_width=0.5, row=3, col=1)
        fig.add_hline(y=70, line_dash='dot', line_color='#ef5350', line_width=0.5, row=3, col=1)

    if 'stoch_k' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['Date'], y=df['stoch_k'],
            mode='lines', name='Stoch %K',
            line=dict(color='#ffa726', width=1),
            showlegend=True,
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=df['Date'], y=df['stoch_d'],
            mode='lines', name='Stoch %D',
            line=dict(color='#ff7043', width=1),
            showlegend=True,
        ), row=3, col=1)
        # Stochastic levels
        fig.add_hline(y=20, line_dash='dot', line_color='#66bb6a', line_width=0.5, row=3, col=1)
        fig.add_hline(y=80, line_dash='dot', line_color='#ef5350', line_width=0.5, row=3, col=1)

    # ── Layout ──
    fig.update_layout(
        height=750,
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis_rangeslider_visible=False,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(l=50, r=20, t=30, b=20),
    )
    fig.update_xaxes(gridcolor='rgba(128,128,128,0.2)')
    fig.update_yaxes(gridcolor='rgba(128,128,128,0.2)')
    fig.update_yaxes(title_text='Price', row=1, col=1)
    fig.update_yaxes(title_text='Volume', row=2, col=1)
    fig.update_yaxes(title_text='RSI/Stoch', row=3, col=1)

    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════
# DEEP ANALYSIS TAB
# ═══════════════════════════════════════════

def render_analysis():
    md = st.session_state.get("market_data", {})
    if not md:
        st.info("Run the screener first to load market data.")
        return

    # Default: only screening results; optional: show all
    screening_df = st.session_state.get("screening_df")
    screening_tickers = set(screening_df["Ticker"].tolist()) if screening_df is not None and not screening_df.empty and "Ticker" in screening_df.columns else set()

    show_all = st.checkbox("Show all tickers (including non-screened)", value=False)
    if show_all:
        all_tickers = sorted(md.keys())
    else:
        if not screening_tickers:
            st.info("No screening results yet. Run the screener first.")
            return
        all_tickers = sorted(screening_tickers)

    ticker = st.selectbox("Select Ticker", all_tickers, key="analysis_ticker")

    if not ticker:
        return

    if not show_all and ticker not in screening_tickers:
        st.warning(f"'{ticker}' did not pass screening. Enable 'Show all tickers' above for full analysis.")

    df_stock = md[ticker]
    if isinstance(df_stock.columns, pd.MultiIndex):
        df_stock.columns = df_stock.columns.get_level_values(0)

    adaptive_params = load_adaptive_config()
    with st.spinner("Generating deep analysis..."):
        full = calculate_full_indicators(df_stock, adaptive_params)
        last = full.iloc[-1]
        stock_regime = determine_stock_regime(full)
        setup, valid = classify_setup_state(full, stock_regime, adaptive_params)

        close = last['Close']
        atr = last['atr_rm']

        # Format last date
        last_date = full.index[-1]
        now = datetime.now()
        try:
            last_date_formatted = last_date.strftime("%A, %d %B %Y")
            is_today = hasattr(last_date, 'date') and last_date.date() == now.date()
            price_label = "last price" if is_today else "close"
        except Exception:
            last_date_formatted = last_date.strftime("%Y-%m-%d")
            price_label = "close"

        # ── Trade Assistant Header ──
        setup_color = COLOR_MAP.get(setup, "#888") if valid else "#888"
        regime_emoji = {"BULL": "🟢", "SIDEWAYS": "🟡", "BEAR": "🔴"}.get(stock_regime, "⚪")

        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #1a1f2e 0%, #16192a 100%); border: 1px solid rgba(255,255,255,0.06);
            border-radius: 14px; padding: 14px; margin-bottom: 0.6rem; box-shadow: 0 4px 16px rgba(0,0,0,0.25);">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
                <h2 style="margin: 0; color: #ECEFF1; font-size: 1.2rem;">Trade Assistant</h2>
                <span style="background: {setup_color}22; color: {setup_color}; padding: 4px 10px; border-radius: 6px;
                    font-weight: 600; font-size: 0.8rem; border: 1px solid {setup_color}44;">
                    {setup if valid else 'NO SETUP'}
                </span>
                <span style="background: rgba(255,255,255,0.05); color: #B0BEC5; padding: 4px 10px; border-radius: 6px;
                    font-weight: 500; font-size: 0.8rem; border: 1px solid rgba(255,255,255,0.08);">
                    📈 {ticker}
                </span>
                <span style="background: rgba(255,255,255,0.05); color: #B0BEC5; padding: 4px 10px; border-radius: 6px;
                    font-weight: 500; font-size: 0.8rem; border: 1px solid rgba(255,255,255,0.08);">
                    💰 {round_to_tick(close):.0f} ({price_label} {last_date_formatted})
                </span>
                <span style="background: rgba(255,255,255,0.05); color: #B0BEC5; padding: 4px 10px; border-radius: 6px;
                    font-weight: 500; font-size: 0.8rem; border: 1px solid rgba(255,255,255,0.08);">
                    {regime_emoji} {stock_regime}
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if valid:
            da = generate_deep_analysis(full, setup, close, atr, adaptive_params)

            # ── Signal Assessment Cards ──
            timing_data = da['timing']
            timing_label = timing_data['label']
            timing_emoji = TIMING_MAP.get(timing_label, ("⚪", ""))[0]
            timing_color = "#66BB6A" if timing_label == "ENTRY_READY" else "#FFA726" if "WAIT" in timing_label else "#90A4AE"
            target_price = timing_data.get('target_price')

            # Format timing display with target price
            if target_price:
                timing_display = f"{timing_label.replace('_', ' ').title()} ({target_price:.0f})"
            else:
                timing_display = timing_label.replace('_', ' ').title()

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #1a1f2e 0%, #16192a 100%); border: 1px solid rgba(255,255,255,0.06);
                    border-radius: 14px; padding: 20px; text-align: center; box-shadow: 0 4px 16px rgba(0,0,0,0.25);">
                    <div style="color: #78909C; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">Entry Zone</div>
                    <div style="color: #ECEFF1; font-size: 1.5rem; font-weight: 700; font-family: 'Inter', monospace;">{round_to_tick(da['entry_zone']['low']):.0f} - {round_to_tick(da['entry_zone']['high']):.0f}</div>
                    <div style="color: #78909C; font-size: 0.75rem; margin-top: 4px;">{da['entry_zone']['strategy']}</div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #1a1f2e 0%, #16192a 100%); border: 1px solid rgba(255,255,255,0.06);
                    border-radius: 14px; padding: 20px; text-align: center; box-shadow: 0 4px 16px rgba(0,0,0,0.25);">
                    <div style="color: #78909C; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">Batas Rugi</div>
                    <div style="color: #EF5350; font-size: 1.5rem; font-weight: 700; font-family: 'Inter', monospace;">{round_to_tick(da['sl_normal']):.0f}</div>
                    <div style="color: #78909C; font-size: 0.75rem; margin-top: 4px;">Wide: {round_to_tick(da['sl_wide']['price']):.0f}</div>
                </div>
                """, unsafe_allow_html=True)
            with col3:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #1a1f2e 0%, #16192a 100%); border: 1px solid rgba(255,255,255,0.06);
                    border-radius: 14px; padding: 20px; text-align: center; box-shadow: 0 4px 16px rgba(0,0,0,0.25);">
                    <div style="color: #78909C; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">Timing</div>
                    <div style="color: {timing_color}; font-size: 1.5rem; font-weight: 700;">{timing_emoji}</div>
                    <div style="color: {timing_color}; font-size: 0.85rem; font-weight: 600; margin-top: 4px;">{timing_display}</div>
                </div>
                """, unsafe_allow_html=True)
            with col4:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #1a1f2e 0%, #16192a 100%); border: 1px solid rgba(255,255,255,0.06);
                    border-radius: 14px; padding: 20px; text-align: center; box-shadow: 0 4px 16px rgba(0,0,0,0.25);">
                    <div style="color: #78909C; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">Target Profit</div>
                    <div style="color: #66BB6A; font-size: 1.1rem; font-weight: 700; font-family: 'Inter', monospace;">{round_to_tick(da['tp_analysis'][0]['price']):.0f}</div>
                    <div style="color: #78909C; font-size: 0.75rem; margin-top: 4px;">TP2: {round_to_tick(da['tp_analysis'][1]['price']):.0f} | TP3: {round_to_tick(da['tp_analysis'][2]['price']):.0f}</div>
                </div>
                """, unsafe_allow_html=True)

            # ── Action Box (Langkah Selanjutnya) ──
            entry_low = da['entry_zone']['low']
            entry_high = da['entry_zone']['high']
            sl = da['sl_normal']
            tp1 = da['tp_analysis'][0]['price']
            tp2 = da['tp_analysis'][1]['price']
            tp3 = da['tp_analysis'][2]['price']

            if timing_label == "ENTRY_READY":
                action_items = [
                    f"Siap masuk! Entry di zona {round_to_tick(entry_low):.0f} - {round_to_tick(entry_high):.0f}",
                    f"Batas rugi di {round_to_tick(sl):.0f}",
                    f"Target profit: {round_to_tick(tp1):.0f} → {round_to_tick(tp2):.0f} → {round_to_tick(tp3):.0f}",
                ]
                action_color = "#66BB6A"
                action_emoji = "✅"
                action_title = "SIAP MASUK"
            elif "WAIT_PULLBACK" in timing_label:
                if target_price:
                    action_items = [
                        f"Tunggu harga turun ke {round_to_tick(target_price):.0f} dulu",
                        f"Setelah sampai, entry di zona {round_to_tick(target_price):.0f} - {round_to_tick(target_price * 1.02):.0f}",
                        f"Batas rugi di {round_to_tick(sl):.0f}",
                    ]
                else:
                    action_items = [
                        "Tunggu harga turun dulu sebelum masuk",
                        f"Entry di zona {round_to_tick(entry_low):.0f} - {round_to_tick(entry_high):.0f}",
                        f"Batas rugi di {round_to_tick(sl):.0f}",
                    ]
                action_color = "#FFA726"
                action_emoji = "⏳"
                action_title = "TUNGGU PULLBACK"
            elif "WAIT_RETEST" in timing_label:
                if target_price:
                    action_items = [
                        f"Tunggu harga kembali ke {round_to_tick(target_price):.0f}",
                        f"Setelah test ulang, entry di zona {round_to_tick(target_price):.0f} - {round_to_tick(target_price * 1.02):.0f}",
                        f"Batas rugi di {round_to_tick(sl):.0f}",
                    ]
                else:
                    action_items = [
                        "Tunggu harga test ulang level kunci",
                        f"Entry di zona {round_to_tick(entry_low):.0f} - {round_to_tick(entry_high):.0f}",
                        f"Batas rugi di {round_to_tick(sl):.0f}",
                    ]
                action_color = "#FFA726"
                action_emoji = "⏳"
                action_title = "TUNGGU RETEST"
            elif "WAIT_VOLUME" in timing_label:
                action_items = [
                    "Tunggu volume naik dulu sebelum masuk",
                    f"Entry di zona {round_to_tick(entry_low):.0f} - {round_to_tick(entry_high):.0f} setelah volume konfirmasi",
                    f"Batas rugi di {round_to_tick(sl):.0f}",
                ]
                action_color = "#FFA726"
                action_emoji = "⏳"
                action_title = "TUNGGU VOLUME"
            elif "WAIT_PRICE" in timing_label:
                if target_price:
                    action_items = [
                        f"Tunggu harga naik di atas {target_price:.0f}",
                        f"Entry di zona {entry_low:.0f} - {entry_high:.0f} setelah breakout",
                        f"Batas rugi di {sl:.0f}",
                    ]
                else:
                    action_items = [
                        "Tunggu harga bergerak lebih tinggi",
                        f"Entry di zona {entry_low:.0f} - {entry_high:.0f}",
                        f"Batas rugi di {sl:.0f}",
                    ]
                action_color = "#FFA726"
                action_emoji = "⏳"
                action_title = "TUNGGU BREAKOUT"
            else:
                action_items = [
                    "Belum ada sinyal entry yang jelas",
                    "Tunggu konfirmasi lebih lanjut",
                ]
                action_color = "#90A4AE"
                action_emoji = "⏸️"
                action_title = "TUNGGU"

            action_html = "".join(f'<li style="margin-bottom: 6px;">{item}</li>' for item in action_items)
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1a1f2e 0%, #16192a 100%); border: 1px solid {action_color}44;
                border-radius: 14px; padding: 20px; margin: 1rem 0; box-shadow: 0 4px 16px rgba(0,0,0,0.25);">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
                    <span style="font-size: 1.2rem;">{action_emoji}</span>
                    <span style="color: {action_color}; font-size: 1rem; font-weight: 700;">Langkah Selanjutnya</span>
                    <span style="background: {action_color}22; color: {action_color}; padding: 2px 10px; border-radius: 6px;
                        font-size: 0.75rem; font-weight: 600; border: 1px solid {action_color}44;">
                        {action_title}
                    </span>
                </div>
                <ul style="color: #B0BEC5; margin: 0; padding-left: 20px; font-size: 0.9rem; line-height: 1.6;">
                    {action_html}
                </ul>
            </div>
            """, unsafe_allow_html=True)

            st.divider()

        # Compute all analyses first
        patterns, meta = detect_patterns(df_stock)
        mta = multi_timeframe_analysis(ticker)
        vp = volume_profile_analysis(df_stock)
        tl = trendline_analysis(df_stock)
        jkse = cached_jkse()
        rs = risk_scenario_analysis(df_stock, jkse) if jkse is not None else {"beta": None, "scenarios": []}

        # Load fundamental data for this ticker
        fundamental_df = cached_fundamental()
        fund_data = {}
        if ticker in fundamental_df.index:
            fund_data = fundamental_df.loc[ticker].to_dict()

        # ── Interpretation Section ──
        if valid:
            interp = generate_interpretation(full, setup, da, mta, vp, tl, rs, patterns, meta, fund_data)
            st.markdown("""
            <div style="background: linear-gradient(135deg, #1a1f2e 0%, #16192a 100%); border: 1px solid rgba(255,255,255,0.06);
                border-radius: 14px; padding: 12px; margin-bottom: 0.5rem; box-shadow: 0 4px 16px rgba(0,0,0,0.25);">
                <h3 style="color: #ECEFF1; margin: 0 0 8px 0; font-size: 0.95rem;">📊 Analisa Signal</h3>
            """, unsafe_allow_html=True)

            for line in interp.split("\n"):
                if line.startswith("KONDISI HARGA:"):
                    st.markdown(f"**📈 {line}**")
                elif line.startswith("VOLUME:"):
                    st.markdown(f"**📊 {line}**")
                elif line.startswith("POLA:"):
                    st.markdown(f"**🕯️ {line}**")
                elif line.startswith("FUNDAMENTAL:"):
                    st.markdown(f"**💼 {line}**")
                elif line.startswith("RISIKO:"):
                    st.markdown(f"**⚠️ {line}**")
                elif line.startswith("LANGKAH SELANJUTNYA:"):
                    st.markdown(f"**✅ {line}**")
                elif line.startswith("  •"):
                    st.markdown(f"{line}")
                elif line.strip():
                    st.markdown(line)

            st.markdown("</div>", unsafe_allow_html=True)

        st.divider()

        # ── Analysis Tabs ──
        tab_names = ["📈 Chart", "🕯️ Candlestick", "📊 Multi-Timeframe", "📦 Volume Profile", "📐 Trendlines", "⚠️ Risk Scenario"]
        tabs = st.tabs(tab_names)

        with tabs[0]:
            if valid:
                render_plotly_chart(full, da, da['levels'])
            else:
                st.info("No active setup for chart display.")

        with tabs[1]:
            if patterns:
                pat_df = pd.DataFrame(patterns, columns=["Date", "Pattern", "Confidence"])
                st.dataframe(pat_df, use_container_width=True, hide_index=True)

                if meta["bars_since_last"] > 3:
                    st.warning(
                        f"Last pattern: **{patterns[-1][0]}** on **{meta['last_pattern_date']}** "
                        f"({meta['bars_since_last']} trading days ago). "
                        f"The last {meta['bars_since_last']} bars did not form any detectable patterns."
                    )
            else:
                st.info("No significant patterns detected in the last 7 bars.")

        with tabs[2]:
            wk = mta["weekly"]
            if wk.get("trend"):
                st.json(wk)
            else:
                st.warning("Weekly data unavailable.")

            daily_trend = "BULLISH" if last.get('supertrend_bullish', False) else "BEARISH" if last.get('price_below_cloud', False) else "SIDEWAYS"
            st.metric("Daily Trend", daily_trend)
            if wk.get("trend"):
                align = "ALIGNED" if wk["trend"] == daily_trend else "CONFLICT"
                st.metric("Alignment", align)

        with tabs[3]:
            st.metric("Current Zone", vp["current_zone"])
            if vp["hvns"]:
                hv = pd.DataFrame(vp["hvns"])
                st.dataframe(hv, use_container_width=True, hide_index=True)

        with tabs[4]:
            c1, c2 = st.columns(2)
            with c1:
                if tl.get("uptrend"):
                    st.metric("Uptrend", f"Active: {tl['uptrend']['active']}")
                    st.caption(f"slope {tl['uptrend']['slope']}")
                else:
                    st.info("No uptrend detected")
            with c2:
                if tl.get("downtrend"):
                    d = tl["downtrend"]
                    status = "Broken ✓" if d.get("broken") else "Active"
                    st.metric("Downtrend", status)
                    st.caption(f"slope {d['slope']}")
                else:
                    st.info("No downtrend detected")

        with tabs[5]:
            if rs.get("beta"):
                st.metric("Beta vs IHSG", rs["beta"])
                if rs["scenarios"]:
                    sc = pd.DataFrame(rs["scenarios"])
                    st.dataframe(sc, use_container_width=True, hide_index=True)
            else:
                st.warning("Beta: insufficient data")


# ═══════════════════════════════════════════
# PERFORMANCE TAB
# ═══════════════════════════════════════════

def render_performance():
    tab_bt, tab_cal, tab_port, tab_jrn = st.tabs(
        ["📊 Backtest", "🎯 Calibration", "💰 Portfolio", "📋 Journal"]
    )

    with tab_bt:
        render_backtest()

    with tab_cal:
        render_calibration()

    with tab_port:
        render_portfolio()

    with tab_jrn:
        render_journal()


def render_backtest():
    st.subheader("📊 Historical Backtest")

    col1, col2 = st.columns(2)
    with col1:
        mode = st.radio(
            "Backtest Mode",
            ["Quick (~30s)", "Full (~5-10min)"],
            horizontal=True,
            key="bt_mode"
        )
        freq = "5B" if "Quick" in mode else "B"

    with col2:
        st.caption("Quick: samples every 5 trading days")
        st.caption("Full: runs every trading day")

    col1, col2 = st.columns(2)
    start_date = col1.date_input("Start Date", value=datetime.now() - timedelta(days=365), key="bt_start")
    end_date = col2.date_input("End Date", value=datetime.now(), key="bt_end")

    col1, col2, col3 = st.columns(3)
    capital = col1.number_input("Capital (Rp)", value=INITIAL_CAPITAL, step=10_000_000, key="bt_capital")
    pos_size = col2.number_input("Position Size (Rp)", value=POSITION_SIZE, step=1_000_000, key="bt_pos")
    max_pos = col3.number_input("Max Positions", value=MAX_POSITIONS, min_value=1, max_value=20, key="bt_max")

    market_data = st.session_state.get("market_data", {})
    all_tickers = sorted(market_data.keys()) if market_data else TICKERS
    selected_tickers = st.multiselect(
        "Tickers to Backtest",
        options=all_tickers,
        default=[],
        key="bt_tickers",
        help="Leave empty to backtest all tickers"
    )

    if st.button("🚀 Run Backtest", type="primary", key="bt_run"):
        _run_backtest(start_date, end_date, capital, pos_size, max_pos, freq, selected_tickers)


def _run_backtest(start_date, end_date, capital, pos_size, max_pos, freq, tickers=None):
    init_db()
    clear_backtest_data()

    LOOKBACK_DAYS = 300
    if isinstance(start_date, datetime):
        fetch_start = start_date - timedelta(days=LOOKBACK_DAYS)
    else:
        fetch_start = datetime.combine(start_date, datetime.min.time()) - timedelta(days=LOOKBACK_DAYS)
    if isinstance(end_date, datetime):
        fetch_end = end_date
    else:
        fetch_end = datetime.combine(end_date, datetime.min.time())

    with st.spinner(f"Loading data from {fetch_start.date()} to {fetch_end.date()}..."):
        market_data = cached_load_data(
            start_date=fetch_start.strftime("%Y-%m-%d"),
            end_date=fetch_end.strftime("%Y-%m-%d"),
        )

    if not market_data:
        st.warning("No market data loaded.")
        return

    if tickers:
        market_data = {k: v for k, v in market_data.items() if k in tickers}

    signal_dates = pd.bdate_range(start=start_date, end=end_date, freq=freq)
    total_days = len(signal_dates)

    progress = st.progress(0, text="Starting backtest...")

    positions = {}
    cash = capital
    equity_curve = []
    snapshot_dates = []
    trades_log = []

    for i, sig_date in enumerate(signal_dates):
        progress.progress(
            i / total_days,
            text=f"Processing {sig_date.date()} ({i+1}/{total_days})..."
        )

        for ticker, pos in list(positions.items()):
            if ticker not in market_data:
                continue
            df = market_data[ticker]
            future_data = df[df.index > pos["entry_date"]]
            if future_data.empty:
                continue

            today_data = future_data[future_data.index <= sig_date]
            if today_data.empty:
                continue

            last_row = today_data.iloc[-1]
            high = last_row["High"]
            low = last_row["Low"]
            close = last_row["Close"]

            remaining = pos.get("remaining_shares", pos["shares"])
            original = pos.get("original_cost", pos["cost"])
            entry_p = pos["entry_price"]

            ap = load_adaptive_config()
            tp1_pct = ap.get("tp1_pct", 33) / 100.0
            tp2_pct = ap.get("tp2_pct", 33) / 100.0
            tp3_pct = ap.get("tp3_pct", 34) / 100.0

            if pos["sl"] and low <= pos["sl"]:
                shares = remaining
                proceeds = shares * pos["sl"]
                cost_basis = (shares / pos["shares"]) * original
                pnl = proceeds - cost_basis
                cash += proceeds
                trade_data = {
                    "setup": pos.get("setup", "UNKNOWN"),
                    "prediction_id": pos.get("prediction_id"),
                    "ticker": ticker,
                    "entry_date": pos["entry_date"].strftime("%Y-%m-%d"),
                    "entry_price": entry_p,
                    "exit_date": sig_date.strftime("%Y-%m-%d"),
                    "exit_price": round(pos["sl"], 2),
                    "exit_reason": "SL",
                    "return_pct": round((pnl / cost_basis) * 100, 2),
                    "return_abs": round(pnl, 2),
                    "days_held": (sig_date - pos["entry_date"]).days,
                    "hit_tp1": 1 if pos.get("tp1_hit") else 0,
                    "hit_tp2": 1 if pos.get("tp2_hit") else 0,
                    "hit_tp3": 0, "hit_sl": 1,
                    "max_favorable": 0, "max_adverse": 0,
                    "status": "CLOSED",
                }
                trades_log.append(trade_data)
                log_trade_result(trade_data)
                del positions[ticker]
                continue

            if pos.get("tp1") and high >= pos["tp1"] and not pos.get("tp1_hit"):
                pos["tp1_hit"] = True
                pos["sl"] = pos["entry_price"]
                sell_qty = int(pos["shares"] * tp1_pct)
                if sell_qty > 0 and remaining >= sell_qty:
                    proceeds = sell_qty * pos["tp1"]
                    cost_basis = (sell_qty / pos["shares"]) * original
                    pnl = proceeds - cost_basis
                    cash += proceeds
                    pos["remaining_shares"] = remaining - sell_qty
                    trade_data = {
                        "setup": pos.get("setup", "UNKNOWN"),
                        "prediction_id": pos.get("prediction_id"),
                        "ticker": ticker,
                        "entry_date": pos["entry_date"].strftime("%Y-%m-%d"),
                        "entry_price": entry_p,
                        "exit_date": sig_date.strftime("%Y-%m-%d"),
                        "exit_price": round(pos["tp1"], 2),
                        "exit_reason": "TP1",
                        "return_pct": round((pnl / cost_basis) * 100, 2),
                        "return_abs": round(pnl, 2),
                        "days_held": (sig_date - pos["entry_date"]).days,
                        "hit_tp1": 1, "hit_tp2": 0, "hit_tp3": 0, "hit_sl": 0,
                        "max_favorable": 0, "max_adverse": 0,
                        "status": "CLOSED",
                    }
                    trades_log.append(trade_data)
                    log_trade_result(trade_data)

            if pos.get("tp2") and high >= pos["tp2"] and pos.get("tp1_hit") and not pos.get("tp2_hit"):
                pos["tp2_hit"] = True
                pos["sl"] = pos["tp2"]
                remaining = pos.get("remaining_shares", pos["shares"])
                sell_qty = int(pos["shares"] * tp2_pct)
                if sell_qty > 0 and remaining >= sell_qty:
                    proceeds = sell_qty * pos["tp2"]
                    cost_basis = (sell_qty / pos["shares"]) * original
                    pnl = proceeds - cost_basis
                    cash += proceeds
                    pos["remaining_shares"] = remaining - sell_qty
                    trade_data = {
                        "setup": pos.get("setup", "UNKNOWN"),
                        "prediction_id": pos.get("prediction_id"),
                        "ticker": ticker,
                        "entry_date": pos["entry_date"].strftime("%Y-%m-%d"),
                        "entry_price": entry_p,
                        "exit_date": sig_date.strftime("%Y-%m-%d"),
                        "exit_price": round(pos["tp2"], 2),
                        "exit_reason": "TP2",
                        "return_pct": round((pnl / cost_basis) * 100, 2),
                        "return_abs": round(pnl, 2),
                        "days_held": (sig_date - pos["entry_date"]).days,
                        "hit_tp1": 1, "hit_tp2": 1, "hit_tp3": 0, "hit_sl": 0,
                        "max_favorable": 0, "max_adverse": 0,
                        "status": "CLOSED",
                    }
                    trades_log.append(trade_data)
                    log_trade_result(trade_data)

            remaining = pos.get("remaining_shares", pos["shares"])
            if pos.get("tp3") and high >= pos["tp3"] and pos.get("tp2_hit") and remaining > 0:
                proceeds = remaining * pos["tp3"]
                cost_basis = (remaining / pos["shares"]) * original
                pnl = proceeds - cost_basis
                cash += proceeds
                trade_data = {
                    "setup": pos.get("setup", "UNKNOWN"),
                    "prediction_id": pos.get("prediction_id"),
                    "ticker": ticker,
                    "entry_date": pos["entry_date"].strftime("%Y-%m-%d"),
                    "entry_price": entry_p,
                    "exit_date": sig_date.strftime("%Y-%m-%d"),
                    "exit_price": round(pos["tp3"], 2),
                    "exit_reason": "TP3",
                    "return_pct": round((pnl / cost_basis) * 100, 2),
                    "return_abs": round(pnl, 2),
                    "days_held": (sig_date - pos["entry_date"]).days,
                    "hit_tp1": 1, "hit_tp2": 1, "hit_tp3": 1, "hit_sl": 0,
                    "max_favorable": 0, "max_adverse": 0,
                    "status": "CLOSED",
                }
                trades_log.append(trade_data)
                log_trade_result(trade_data)
                del positions[ticker]
                continue

            days_held = (sig_date - pos["entry_date"]).days
            if days_held > MC_HORIZON:
                remaining = pos.get("remaining_shares", pos["shares"])
                original = pos.get("original_cost", pos["cost"])
                entry_p = pos["entry_price"]
                proceeds = remaining * close
                cost_basis = (remaining / pos["shares"]) * original
                pnl = proceeds - cost_basis
                cash += proceeds
                trade_data = {
                    "setup": pos.get("setup", "UNKNOWN"),
                    "prediction_id": pos.get("prediction_id"),
                    "ticker": ticker,
                    "entry_date": pos["entry_date"].strftime("%Y-%m-%d"),
                    "entry_price": entry_p,
                    "exit_date": sig_date.strftime("%Y-%m-%d"),
                    "exit_price": round(close, 2),
                    "exit_reason": "TIMEOUT",
                    "return_pct": round((pnl / cost_basis) * 100, 2),
                    "return_abs": round(pnl, 2),
                    "days_held": days_held,
                    "hit_tp1": 1 if pos.get("tp1_hit") else 0,
                    "hit_tp2": 1 if pos.get("tp2_hit") else 0,
                    "hit_tp3": 0, "hit_sl": 0,
                    "max_favorable": 0, "max_adverse": 0,
                    "status": "CLOSED",
                }
                trades_log.append(trade_data)
                log_trade_result(trade_data)
                del positions[ticker]

        results = run_screening_at_date(market_data, sig_date, None)
        for r in results:
            if r.get("timing") != "ENTRY_READY":
                continue
            ticker = r["ticker"]
            if ticker in positions:
                continue
            if len(positions) >= max_pos:
                break
            if cash < pos_size:
                break

            pred_id = log_prediction(r)

            entry_price = r["price_at_signal"]
            shares = int(pos_size / entry_price)
            if shares <= 0:
                continue

            cost = shares * entry_price
            if cost > cash:
                continue

            cash -= cost
            positions[ticker] = {
                "shares": shares,
                "remaining_shares": shares,
                "original_cost": cost,
                "entry_price": entry_price,
                "cost": cost,
                "entry_date": sig_date,
                "setup": r["setup"],
                "sl": r["stop_loss"],
                "tp1": r.get("tp1"),
                "tp2": r.get("tp2"),
                "tp3": r.get("tp3"),
                "prediction_id": pred_id,
                "tp1_hit": False,
                "tp2_hit": False,
            }

        total_value = cash
        for ticker, pos in positions.items():
            if ticker in market_data:
                df = market_data[ticker]
                recent = df[df.index <= sig_date]
                if not recent.empty:
                    remaining = pos.get("remaining_shares", pos["shares"])
                    total_value += remaining * recent["Close"].iloc[-1]
                else:
                    total_value += pos["cost"]
            else:
                total_value += pos["cost"]

        equity_curve.append(total_value)
        snapshot_dates.append(sig_date)

    for ticker, pos in list(positions.items()):
        if ticker in market_data:
            df = market_data[ticker]
            last_close = df["Close"].iloc[-1]
            remaining = pos.get("remaining_shares", pos["shares"])
            original = pos.get("original_cost", pos["cost"])
            entry_p = pos["entry_price"]
            proceeds = remaining * last_close
            cost_basis = (remaining / pos["shares"]) * original
            pnl = proceeds - cost_basis
            cash += proceeds
            trade_data = {
                "setup": pos.get("setup", "UNKNOWN"),
                "prediction_id": pos.get("prediction_id"),
                "ticker": ticker,
                "entry_date": pos["entry_date"].strftime("%Y-%m-%d"),
                "entry_price": entry_p,
                "exit_date": end_date.strftime("%Y-%m-%d"),
                "exit_price": round(last_close, 2),
                "exit_reason": "END",
                "return_pct": round((pnl / cost_basis) * 100, 2),
                "return_abs": round(pnl, 2),
                "days_held": (end_date - pos["entry_date"].date()).days,
                "hit_tp1": 1 if pos.get("tp1_hit") else 0,
                "hit_tp2": 1 if pos.get("tp2_hit") else 0,
                "hit_tp3": 0, "hit_sl": 0,
                "max_favorable": 0, "max_adverse": 0,
                "status": "CLOSED",
            }
            trades_log.append(trade_data)
            log_trade_result(trade_data)

    progress.progress(1.0, text="Backtest complete!")

    if trades_log:
        report = full_report(trades_log, equity_curve)
        _display_backtest_results(report, equity_curve, snapshot_dates, trades_log, capital)
    else:
        st.warning("No trades generated during backtest period.")


def _display_backtest_results(report, equity_curve, snapshot_dates, trades_log, capital):
    st.divider()

    # ── Results Header ──
    total_ret = (equity_curve[-1] / capital - 1) * 100 if equity_curve else 0
    ret_color = "#66BB6A" if total_ret > 0 else "#EF5350"
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1a1f2e 0%, #16192a 100%); border: 1px solid rgba(255,255,255,0.06);
        border-radius: 16px; padding: 28px; margin-bottom: 1.5rem; box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
        <div style="display: flex; align-items: center; gap: 12px;">
            <h2 style="margin: 0; color: #ECEFF1; font-size: 1.4rem;">📈 Backtest Results</h2>
            <span style="background: {ret_color}22; color: {ret_color}; padding: 6px 14px; border-radius: 8px;
                font-weight: 600; font-size: 0.85rem; border: 1px solid {ret_color}44;">
                Total Return: {total_ret:+.2f}%
            </span>
            <span style="background: rgba(255,255,255,0.05); color: #B0BEC5; padding: 6px 14px; border-radius: 8px;
                font-weight: 500; font-size: 0.85rem; border: 1px solid rgba(255,255,255,0.08);">
                {report.get('total_trades', 0)} trades
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Key Metrics ──
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Win Rate", f"{report.get('win_rate', 0):.1%}")
    col2.metric("Avg Return", f"{report.get('avg_return_pct', 0):+.2f}%")
    col3.metric("Sharpe", f"{report.get('sharpe_ratio', 0):.2f}")
    col4.metric("Max DD", f"{report.get('max_drawdown', 0):.2%}")
    col5.metric("Trades", f"{report.get('total_trades', 0)}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Profit Factor", f"{report.get('profit_factor', 0):.2f}")
    col2.metric("Sortino", f"{report.get('sortino_ratio', 0):.2f}")
    col3.metric("Total Return", f"{total_ret:+.2f}%")
    col4.metric("Calmar", f"{report.get('calmar_ratio', 0):.2f}")

    st.divider()

    # ── Equity Curve ──
    st.subheader("📊 Equity Curve")
    eq_df = pd.DataFrame({
        "Date": snapshot_dates[:len(equity_curve)],
        "Portfolio (Rp Juta)": [v / 1_000_000 for v in equity_curve],
    })

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=eq_df["Date"], y=eq_df["Portfolio (Rp Juta)"],
        mode="lines", name="Portfolio",
        line=dict(color="#42A5F5", width=2.5),
        fill="tozeroy",
        fillcolor="rgba(66, 165, 245, 0.1)",
    ))
    fig.update_layout(
        height=380,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis_title="Value (Rp Juta)",
        xaxis_title="",
        font_color="#B0BEC5", font_family="Inter",
        margin=dict(l=50, r=20, t=20, b=40),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Setup Breakdown ──
    st.subheader("📊 Setup Breakdown")
    sb = report.get("setup_breakdown", {})
    if sb:
        sb_df = pd.DataFrame([
            {"Setup": k, "Trades": v["count"], "Win Rate": v["win_rate"],
             "Avg Return": v["avg_return"], "Profit Factor": v["profit_factor"],
             "Reliable": "✅" if v.get("reliable", False) else "⚠️ <3"}
            for k, v in sb.items()
        ])
        fig = px.bar(
            sb_df, x="Setup", y="Win Rate", color="Setup",
            color_discrete_map=COLOR_MAP, text="Win Rate",
        )
        fig.update_traces(texttemplate="%{text:.1%}", textposition="outside")
        fig.update_layout(
            height=320, showlegend=False,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis_tickformat=".0%",
            font_color="#B0BEC5", font_family="Inter",
            margin=dict(l=50, r=20, t=20, b=40),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Exit Reason Breakdown ──
    er = report.get("exit_reason_breakdown", {})
    if er:
        st.subheader("🚪 Exit Reason Breakdown")
        er_df = pd.DataFrame([
            {"Reason": k, "Count": v["count"], "Avg Return": v["avg_return"], "Avg Days": v["avg_days_held"]}
            for k, v in er.items()
        ])
        total = er_df["Count"].sum()
        er_df["%"] = (er_df["Count"] / total * 100).round(1)

        c1, c2 = st.columns([2, 1])
        with c1:
            st.dataframe(
                er_df[["Reason", "Count", "%", "Avg Return", "Avg Days"]],
                use_container_width=True, hide_index=True,
                column_config={
                    "Avg Return": st.column_config.NumberColumn("Avg Return", format="%.2f%%"),
                    "Avg Days": st.column_config.NumberColumn("Avg Days", format="%.1f"),
                    "%": st.column_config.NumberColumn("%", format="%.1f%%"),
                },
            )
        with c2:
            colors = {"TP1": "#2ecc71", "TP2": "#27ae60", "TP3": "#1e8449", "SL": "#e74c3c", "TIMEOUT": "#f39c12"}
            fig_er = px.pie(er_df, values="Count", names="Reason",
                            color="Reason", color_discrete_map=colors)
            fig_er.update_traces(textinfo="percent+label")
            fig_er.update_layout(
                height=280, showlegend=False,
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=10, b=10),
            )
            st.plotly_chart(fig_er, use_container_width=True)

    st.divider()

    st.subheader("📋 Trade Log")
    trades_df = pd.DataFrame(trades_log)
    if not trades_df.empty:
        st.dataframe(
            trades_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "return_pct": st.column_config.NumberColumn("Return %", format="%.2f"),
                "entry_price": st.column_config.NumberColumn("Entry", format="%.2f"),
                "exit_price": st.column_config.NumberColumn("Exit", format="%.2f"),
            },
        )

        csv = trades_df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Trade Log", csv, "backtest_trades.csv", "text/csv")

    # DYOR Disclaimer
    st.markdown("""
    <div class="dyor-disclaimer">
        ⚠️ Think First. Trade Second. DYOR - Do Your Own Research
    </div>
    """, unsafe_allow_html=True)


def render_calibration():
    st.subheader("🎯 Monte Carlo Calibration")

    init_db()
    trades = get_trade_results()
    predictions = get_all_predictions(filters={"status": "CLOSED"})

    if not trades:
        st.info("No closed trades available. Run a backtest first.")
        return

    pred_map = {p["id"]: p for p in predictions}

    bins_data = {}
    for trade in trades:
        pred_id = trade.get("prediction_id")
        if pred_id not in pred_map:
            continue

        pred = pred_map[pred_id]
        prob_str = pred.get("prob_tp1")
        if prob_str is None:
            continue
        try:
            prob = float(str(prob_str).replace("%", "").strip())
        except (ValueError, TypeError):
            continue

        actual = 1 if trade.get("hit_tp1") else 0
        bin_idx = min(int(prob / 10), 9)
        bin_label = f"{bin_idx*10}-{(bin_idx+1)*10}%"

        if bin_label not in bins_data:
            bins_data[bin_label] = {"predicted": [], "actual": []}
        bins_data[bin_label]["predicted"].append(prob)
        bins_data[bin_label]["actual"].append(actual)

    if not bins_data:
        st.warning("No probability data available for calibration analysis.")
        return

    bins_result = {}
    for label in sorted(bins_data.keys()):
        data = bins_data[label]
        avg_pred = np.mean(data["predicted"])
        actual_rate = np.mean(data["actual"]) * 100
        count = len(data["actual"])
        bins_result[label] = {
            "avg_predicted": round(avg_pred, 2),
            "actual_hit_rate": round(actual_rate, 2),
            "count": count,
            "gap": round(abs(avg_pred - actual_rate), 2),
        }

    col1, col2, col3 = st.columns(3)
    bs = brier_score(trades, predictions)
    ece = expected_calibration_error(bins_result)
    mce = maximum_calibration_error(bins_result)

    col1.metric("Brier Score", f"{bs:.4f}" if bs else "N/A",
                 help="Lower is better. <0.1 = Excellent, <0.2 = Good")
    col2.metric("Calibration Error (ECE)", f"{ece:.2f}%" if ece else "N/A",
                 help="Average gap between predicted and actual")
    col3.metric("Max Calibration Error", f"{mce:.1f}%" if mce else "N/A")

    st.divider()

    st.subheader("Reliability Diagram")

    bin_labels = sorted(bins_data.keys())
    predicted_vals = [bins_result[b]["avg_predicted"] for b in bin_labels]
    actual_vals = [bins_result[b]["actual_hit_rate"] for b in bin_labels]
    counts = [bins_result[b]["count"] for b in bin_labels]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[0, 100], y=[0, 100],
        mode="lines", name="Perfect Calibration",
        line=dict(color="gray", dash="dash", width=1),
    ))
    fig.add_trace(go.Scatter(
        x=predicted_vals, y=actual_vals,
        mode="markers+text", name="Calibration",
        marker=dict(size=[max(8, c * 2) for c in counts], color=counts,
                    colorscale="Viridis", showscale=True, colorbar=dict(title="Count")),
        text=bin_labels, textposition="top center", textfont=dict(size=9),
    ))
    fig.update_layout(
        height=400,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="Predicted Probability (%)",
        yaxis_title="Actual Hit Rate (%)",
        margin=dict(l=50, r=20, t=30, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.subheader("Calibration Bins")
    bins_df = pd.DataFrame([
        {"Bin": k, "Predicted": f"{v['avg_predicted']:.1f}%",
         "Actual": f"{v['actual_hit_rate']:.1f}%", "Gap": f"{v['gap']:.1f}%",
         "Count": v["count"]}
        for k, v in bins_result.items()
    ])
    st.dataframe(bins_df, use_container_width=True, hide_index=True)

    # DYOR Disclaimer
    st.markdown("""
    <div class="dyor-disclaimer">
        ⚠️ Think First. Trade Second. DYOR - Do Your Own Research
    </div>
    """, unsafe_allow_html=True)


def render_portfolio():
    st.subheader("💰 Portfolio Simulation")

    init_db()

    col1, col2 = st.columns(2)
    capital = col1.number_input("Initial Capital (Rp)", value=INITIAL_CAPITAL, step=10_000_000, key="port_capital")
    pos_size = col2.number_input("Position Size (Rp)", value=POSITION_SIZE, step=1_000_000, key="port_pos")

    if st.button("🚀 Run Portfolio Simulation", type="primary", key="port_run"):
        _run_portfolio_simulation(capital, pos_size)


def _run_portfolio_simulation(capital, pos_size):
    market_data = st.session_state.get("market_data")
    if not market_data:
        st.warning("Please run the screener first to load market data.")
        return

    pending = get_all_predictions(filters={"status": "PENDING"})
    if not pending:
        st.info("No pending predictions. Run a backtest first to generate predictions.")
        return

    pending_by_date = {}
    for p in pending:
        date_str = p["screen_date"][:10]
        if date_str not in pending_by_date:
            pending_by_date[date_str] = []
        pending_by_date[date_str].append(p)

    positions = {}
    cash = capital
    equity_curve = []
    snapshot_dates = []
    trades_log = []

    all_dates = sorted(set(p["screen_date"][:10] for p in pending))

    progress = st.progress(0, text="Simulating portfolio...")

    for i, date_str in enumerate(all_dates):
        progress.progress(i / len(all_dates), text=f"Processing {date_str}...")

        sig_date = pd.Timestamp(date_str)

        for ticker in list(positions.keys()):
            if ticker not in market_data:
                continue
            pos = positions[ticker]
            df = market_data[ticker]
            future_data = df[df.index > pos["entry_date"]]
            if future_data.empty:
                continue

            today_data = future_data[future_data.index <= sig_date]
            if today_data.empty:
                continue

            last_row = today_data.iloc[-1]
            high, low, close = last_row["High"], last_row["Low"], last_row["Close"]

            if pos["sl"] and low <= pos["sl"]:
                shares = pos["shares"]
                proceeds = shares * pos["sl"]
                pnl = proceeds - pos["cost"]
                cash += proceeds
                trades_log.append({
                    "ticker": ticker, "setup": pos["setup"],
                    "entry_date": pos["entry_date"].strftime("%Y-%m-%d"),
                    "entry_price": pos["entry_price"],
                    "exit_date": date_str, "exit_price": round(pos["sl"], 2),
                    "exit_reason": "SL",
                    "return_pct": round((pnl / pos["cost"]) * 100, 2),
                    "days_held": (sig_date - pos["entry_date"]).days,
                })
                del positions[ticker]
                continue

            if pos.get("tp1") and high >= pos["tp1"] and not pos.get("tp1_hit"):
                pos["tp1_hit"] = True
                pos["sl"] = pos["entry_price"]

            if pos.get("tp2") and high >= pos["tp2"] and pos.get("tp1_hit") and not pos.get("tp2_hit"):
                pos["tp2_hit"] = True
                pos["sl"] = pos["tp2"]

            if pos.get("tp3") and high >= pos["tp3"] and pos.get("tp2_hit"):
                shares = pos["shares"]
                proceeds = shares * pos["tp3"]
                pnl = proceeds - pos["cost"]
                cash += proceeds
                trades_log.append({
                    "ticker": ticker, "setup": pos["setup"],
                    "entry_date": pos["entry_date"].strftime("%Y-%m-%d"),
                    "entry_price": pos["entry_price"],
                    "exit_date": date_str, "exit_price": round(pos["tp3"], 2),
                    "exit_reason": "TP3",
                    "return_pct": round((pnl / pos["cost"]) * 100, 2),
                    "days_held": (sig_date - pos["entry_date"]).days,
                })
                del positions[ticker]
                continue

            days_held = (sig_date - pos["entry_date"]).days
            if days_held > MC_HORIZON:
                shares = pos["shares"]
                proceeds = shares * close
                pnl = proceeds - pos["cost"]
                cash += proceeds
                trades_log.append({
                    "ticker": ticker, "setup": pos["setup"],
                    "entry_date": pos["entry_date"].strftime("%Y-%m-%d"),
                    "entry_price": pos["entry_price"],
                    "exit_date": date_str, "exit_price": round(close, 2),
                    "exit_reason": "TIMEOUT",
                    "return_pct": round((pnl / pos["cost"]) * 100, 2),
                    "days_held": days_held,
                })
                del positions[ticker]

        for pred in pending_by_date.get(date_str, []):
            ticker = pred["ticker"]
            if ticker in positions:
                continue
            if len(positions) >= MAX_POSITIONS:
                break
            if cash < pos_size:
                break

            entry_price = pred["price_at_signal"]
            shares = int(pos_size / entry_price)
            if shares <= 0:
                continue

            cost = shares * entry_price
            if cost > cash:
                continue

            cash -= cost
            positions[ticker] = {
                "shares": shares,
                "entry_price": entry_price,
                "cost": cost,
                "entry_date": sig_date,
                "setup": pred["setup"],
                "sl": pred.get("stop_loss"),
                "tp1": pred.get("tp1"),
                "tp2": pred.get("tp2"),
                "tp3": pred.get("tp3"),
                "tp1_hit": False,
                "tp2_hit": False,
            }

        total_value = cash
        for ticker, pos in positions.items():
            if ticker in market_data:
                df = market_data[ticker]
                recent = df[df.index <= sig_date]
                if not recent.empty:
                    total_value += pos["shares"] * recent["Close"].iloc[-1]
                else:
                    total_value += pos["cost"]
            else:
                total_value += pos["cost"]

        equity_curve.append(total_value)
        snapshot_dates.append(sig_date)

    progress.progress(1.0, text="Portfolio simulation complete!")

    if trades_log:
        report = full_report(trades_log, equity_curve)
        _display_portfolio_results(report, equity_curve, snapshot_dates, trades_log, capital)
    else:
        st.warning("No trades generated during simulation period.")


def _display_portfolio_results(report, equity_curve, snapshot_dates, trades_log, capital):
    st.divider()
    st.subheader("📈 Portfolio Results")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Win Rate", f"{report.get('win_rate', 0):.1%}")
    col2.metric("Total Return", f"{(equity_curve[-1]/capital - 1)*100:+.2f}%")
    col3.metric("Sharpe", f"{report.get('sharpe_ratio', 0):.2f}")
    col4.metric("Max DD", f"{report.get('max_drawdown', 0):.2%}")
    col5.metric("Trades", f"{report.get('total_trades', 0)}")

    st.divider()

    st.subheader("📊 Equity Curve vs IHSG")

    jkse = cached_jkse()
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=snapshot_dates[:len(equity_curve)],
        y=[v / 1_000_000 for v in equity_curve],
        mode="lines", name="Portfolio",
        line=dict(color="#42A5F5", width=2),
    ))

    if jkse is not None:
        jkse_slice = jkse[jkse.index >= snapshot_dates[0]]
        jkse_slice = jkse_slice[jkse_slice.index <= snapshot_dates[-1]]
        if not jkse_slice.empty:
            jkse_norm = jkse_slice["Close"] / jkse_slice["Close"].iloc[0] * capital
            fig.add_trace(go.Scatter(
                x=jkse_slice.index,
                y=jkse_norm / 1_000_000,
                mode="lines", name="IHSG",
                line=dict(color="#FFA726", width=1.5, dash="dash"),
            ))

    fig.update_layout(
        height=400,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis_title="Value (Rp Juta)",
        xaxis_title="Date",
        margin=dict(l=50, r=20, t=30, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.subheader("📉 Drawdown")
    equity_arr = np.array(equity_curve)
    peaks = np.maximum.accumulate(equity_arr)
    drawdowns = (peaks - equity_arr) / peaks * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=snapshot_dates[:len(drawdowns)],
        y=-drawdowns,
        fill="tozeroy", name="Drawdown",
        line=dict(color="#EF5350", width=1),
    ))
    fig.update_layout(
        height=250,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis_title="Drawdown (%)",
        margin=dict(l=50, r=20, t=30, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    er = report.get("exit_reason_breakdown", {})
    if er:
        st.subheader("🚪 Exit Reason Breakdown")
        er_df = pd.DataFrame([
            {"Reason": k, "Count": v["count"], "Avg Return": v["avg_return"], "Avg Days": v["avg_days_held"]}
            for k, v in er.items()
        ])
        total = er_df["Count"].sum()
        er_df["%"] = (er_df["Count"] / total * 100).round(1)

        c1, c2 = st.columns([2, 1])
        with c1:
            st.dataframe(
                er_df[["Reason", "Count", "%", "Avg Return", "Avg Days"]],
                use_container_width=True, hide_index=True,
                column_config={
                    "Avg Return": st.column_config.NumberColumn("Avg Return", format="%.2f%%"),
                    "Avg Days": st.column_config.NumberColumn("Avg Days", format="%.1f"),
                    "%": st.column_config.NumberColumn("%", format="%.1f%%"),
                },
            )
        with c2:
            colors = {"TP1": "#2ecc71", "TP2": "#27ae60", "TP3": "#1e8449", "SL": "#e74c3c", "TIMEOUT": "#f39c12"}
            fig_er = px.pie(er_df, values="Count", names="Reason",
                            color="Reason", color_discrete_map=colors)
            fig_er.update_traces(textinfo="percent+label")
            fig_er.update_layout(
                height=280, showlegend=False,
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=10, b=10),
            )
            st.plotly_chart(fig_er, use_container_width=True)

    st.divider()

    st.subheader("📋 Trade Log")
    trades_df = pd.DataFrame(trades_log)
    if not trades_df.empty:
        st.dataframe(trades_df, use_container_width=True, hide_index=True)
        csv = trades_df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Trade Log", csv, "portfolio_trades.csv", "text/csv")

    # DYOR Disclaimer
    st.markdown("""
    <div class="dyor-disclaimer">
        ⚠️ Think First. Trade Second. DYOR - Do Your Own Research
    </div>
    """, unsafe_allow_html=True)


def render_journal():
    st.subheader("📋 Performance Journal")

    init_db()
    summary = get_journal_summary()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Predictions", summary["total_predictions"])
    col2.metric("Pending", summary["pending"])
    col3.metric("Active", summary["active"])
    col4.metric("Closed", summary["closed"])

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Trades", summary["total_trades"])
    col2.metric("Open Trades", summary["open_trades"])
    col3.metric("Closed Trades", summary["closed_trades"])

    st.divider()

    tab_pred, tab_trades = st.tabs(["📊 Predictions", "📈 Trade Results"])

    with tab_pred:
        status_filter = st.selectbox("Filter by Status", ["All", "PENDING", "ACTIVE", "CLOSED"], key="jrn_status")
        ticker_filter = st.text_input("Filter by Ticker", key="jrn_ticker")

        filters = {}
        if status_filter != "All":
            filters["status"] = status_filter
        if ticker_filter:
            filters["ticker"] = ticker_filter.upper()

        preds = get_all_predictions(filters if filters else None)

        if preds:
            preds_df = pd.DataFrame(preds)
            display_cols = ["id", "ticker", "setup", "signal", "price_at_signal",
                          "stop_loss", "tp1", "timing", "score", "status", "screen_date"]
            avail = [c for c in display_cols if c in preds_df.columns]
            display_df = preds_df[avail].copy()
            if "screen_date" in display_df.columns:
                display_df["screen_date"] = display_df["screen_date"].apply(safe_screen_date_str)
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("No predictions found.")

    with tab_trades:
        exit_filter = st.selectbox("Filter by Exit Reason", ["All", "TP1", "TP2", "TP3", "SL", "TIMEOUT"], key="jrn_exit")

        filters = {}
        if exit_filter != "All":
            filters["exit_reason"] = exit_filter

        trades = get_trade_results(filters if filters else None)

        if trades:
            trades_df = pd.DataFrame(trades)
            st.dataframe(trades_df, use_container_width=True, hide_index=True)

            if len(trades) > 1:
                report = full_report(trades)
                st.divider()
                st.subheader("Summary")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Win Rate", f"{report.get('win_rate', 0):.1%}")
                col2.metric("Avg Return", f"{report.get('avg_return_pct', 0):+.2f}%")
                col3.metric("Profit Factor", f"{report.get('profit_factor', 0):.2f}")
                col4.metric("Sharpe", f"{report.get('sharpe_ratio', 0):.2f}")

                er = report.get("exit_reason_breakdown", {})
                if er:
                    st.subheader("🚪 Exit Reason Breakdown")
                    er_df = pd.DataFrame([
                        {"Reason": k, "Count": v["count"], "Avg Return": v["avg_return"], "Avg Days": v["avg_days_held"]}
                        for k, v in er.items()
                    ])
                    total = er_df["Count"].sum()
                    er_df["%"] = (er_df["Count"] / total * 100).round(1)

                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.dataframe(
                            er_df[["Reason", "Count", "%", "Avg Return", "Avg Days"]],
                            use_container_width=True, hide_index=True,
                            column_config={
                                "Avg Return": st.column_config.NumberColumn("Avg Return", format="%.2f%%"),
                                "Avg Days": st.column_config.NumberColumn("Avg Days", format="%.1f"),
                                "%": st.column_config.NumberColumn("%", format="%.1f%%"),
                            },
                        )
                    with c2:
                        colors = {"TP1": "#2ecc71", "TP2": "#27ae60", "TP3": "#1e8449", "SL": "#e74c3c", "TIMEOUT": "#f39c12"}
                        fig_er = px.pie(er_df, values="Count", names="Reason",
                                        color="Reason", color_discrete_map=colors)
                        fig_er.update_traces(textinfo="percent+label")
                        fig_er.update_layout(
                            height=280, showlegend=False,
                            template="plotly_dark",
                            paper_bgcolor="rgba(0,0,0,0)",
                            margin=dict(l=20, r=20, t=10, b=10),
                        )
                        st.plotly_chart(fig_er, use_container_width=True)
        else:
            st.info("No trade results found.")

    # DYOR Disclaimer
    st.markdown("""
    <div class="dyor-disclaimer">
        ⚠️ Think First. Trade Second. DYOR - Do Your Own Research
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════

def main():
    render_sidebar()

    if st.session_state.screening_done and st.session_state.screening_df is not None:
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "📋 Results", "🎯 Trade Assistant", "📈 Performance"])
        with tab1:
            render_dashboard()
        with tab2:
            render_results()
        with tab3:
            render_analysis()
        with tab4:
            render_performance()
    else:
        # ── Professional Landing Page ──
        st.markdown("""
        <div style="text-align: center; padding: 2rem 0 1rem;">
            <h1 style="font-size: 3rem; font-weight: 800; background: linear-gradient(135deg, #42A5F5 0%, #26A69A 50%, #66BB6A 100%);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -1px; margin-bottom: 0.5rem;">
                ⚡ SWING SCREENER v2
            </h1>
            <p style="color: #78909C; font-size: 1.15rem; margin-bottom: 2.5rem; font-weight: 400;">
                Professional IDX Stock Screening Tool with AI-Powered Ranking
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Feature cards
        fcol1, fcol2, fcol3 = st.columns(3)
        with fcol1:
            st.markdown("""
            <div style="background: linear-gradient(135deg, #1a1f2e 0%, #16192a 100%); border: 1px solid rgba(255,255,255,0.06);
                border-radius: 14px; padding: 28px; text-align: center; box-shadow: 0 4px 16px rgba(0,0,0,0.25);">
                <div style="font-size: 2.5rem; margin-bottom: 12px;">🎯</div>
                <h3 style="color: #ECEFF1; margin: 0 0 8px 0; font-size: 1.1rem;">9 Setup Types</h3>
                <p style="color: #78909C; margin: 0; font-size: 0.85rem;">PRE_BREAKOUT, VCP, TIGHT_BASE, BULL_FLAG, BREAKOUT & more</p>
            </div>
            """, unsafe_allow_html=True)
        with fcol2:
            st.markdown("""
            <div style="background: linear-gradient(135deg, #1a1f2e 0%, #16192a 100%); border: 1px solid rgba(255,255,255,0.06);
                border-radius: 14px; padding: 28px; text-align: center; box-shadow: 0 4px 16px rgba(0,0,0,0.25);">
                <div style="font-size: 2.5rem; margin-bottom: 12px;">🤖</div>
                <h3 style="color: #ECEFF1; margin: 0 0 8px 0; font-size: 1.1rem;">AI-Powered Ranking</h3>
                <p style="color: #78909C; margin: 0; font-size: 0.85rem;">Reinforcement Learning scoring with Monte Carlo simulation</p>
            </div>
            """, unsafe_allow_html=True)
        with fcol3:
            st.markdown("""
            <div style="background: linear-gradient(135deg, #1a1f2e 0%, #16192a 100%); border: 1px solid rgba(255,255,255,0.06);
                border-radius: 14px; padding: 28px; text-align: center; box-shadow: 0 4px 16px rgba(0,0,0,0.25);">
                <div style="font-size: 2.5rem; margin-bottom: 12px;">📊</div>
                <h3 style="color: #ECEFF1; margin: 0 0 8px 0; font-size: 1.1rem;">Deep Analysis</h3>
                <p style="color: #78909C; margin: 0; font-size: 0.85rem;">Multi-TF, volume profile, trendlines, risk scenarios</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Setup types showcase
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1a1f2e 0%, #16192a 100%); border: 1px solid rgba(255,255,255,0.06);
            border-radius: 14px; padding: 32px; box-shadow: 0 4px 16px rgba(0,0,0,0.25);">
            <h3 style="color: #ECEFF1; text-align: center; margin: 0 0 24px 0;">Setup Types</h3>
            <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 8px;">
                <span style="background: #FFA726; color: #000; padding: 8px 16px; border-radius: 8px; font-weight: 600; font-size: 0.85rem;">PRE_BREAKOUT</span>
                <span style="background: #AB47BC; color: #000; padding: 8px 16px; border-radius: 8px; font-weight: 600; font-size: 0.85rem;">VCP</span>
                <span style="background: #26A69A; color: #000; padding: 8px 16px; border-radius: 8px; font-weight: 600; font-size: 0.85rem;">TIGHT_BASE_BREAKOUT</span>
                <span style="background: #5C6BC0; color: #000; padding: 8px 16px; border-radius: 8px; font-weight: 600; font-size: 0.85rem;">BASE_ON_BASE</span>
                <span style="background: #FF7043; color: #000; padding: 8px 16px; border-radius: 8px; font-weight: 600; font-size: 0.85rem;">BULL_FLAG</span>
                <span style="background: #66BB6A; color: #000; padding: 8px 16px; border-radius: 8px; font-weight: 600; font-size: 0.85rem;">BREAKOUT</span>
                <span style="background: #FFCA28; color: #000; padding: 8px 16px; border-radius: 8px; font-weight: 600; font-size: 0.85rem;">PULLBACK_MA20</span>
                <span style="background: #42A5F5; color: #000; padding: 8px 16px; border-radius: 8px; font-weight: 600; font-size: 0.85rem;">ACCUMULATION</span>
                <span style="background: #EF5350; color: #000; padding: 8px 16px; border-radius: 8px; font-weight: 600; font-size: 0.85rem;">EARLY_REVERSAL</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # DYOR Disclaimer
        st.markdown("""
        <div class="dyor-disclaimer">
            ⚠️ Think First. Trade Second. DYOR - Do Your Own Research
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # CTA
        st.markdown("""
        <div style="text-align: center; padding: 1rem;">
            <p style="color: #90A4AE; font-size: 0.95rem;">👈 Click <strong>Run Screener</strong> in the sidebar to start scanning IDX stocks</p>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
