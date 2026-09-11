import sys
import warnings
warnings.filterwarnings("ignore", message=".could not convert.")
warnings.filterwarnings("default", message=".*valid.convergent.")
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from config import TICKERS, INITIAL_CAPITAL, POSITION_SIZE, MAX_POSITIONS, SETUP_ORDER, SIGNAL_MAP, COLOR_MAP, MAX_DISPLAY, MC_HORIZON, MIN_DOLLAR_VOLUME
try:
    from paper_trading.config import MIN_SCORE, SETUP_MIN_SCORE, SETUP_ALLOWED_REGIMES, MAX_AUTO_ORDERS_PER_DAY, MAX_LOTS_PER_TICKER, MAX_FORCE_ORDERS
    from paper_trading.auto_trader import filter_screener_results, auto_create_orders, calculate_position_size
    from paper_trading.gsheets_client import GSheetsClient
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False
    filter_screener_results = None
    auto_create_orders = None
    calculate_position_size = None
    GSheetsClient = None
from data import get_all_market_data, get_jkse_data, get_fundamental_data
from indicators import calculate_full_indicators
from signals import determine_market_regime, determine_stock_regime, classify_setup_state
from risk import calculate_tp_sl, simulate_tp_sl_probability
from analysis import generate_deep_analysis
from patterns import detect_patterns, get_pattern_score
from deep_analysis import (
    multi_timeframe_analysis, volume_profile_analysis,
    trendline_analysis, risk_scenario_analysis, generate_interpretation
)
# Performance module
from performance.journal import (
    init_db, get_journal_summary, get_all_predictions, get_trade_results, log_prediction, log_trade_result, update_prediction_status, clear_backtest_data
)
from adaptive.config import load_adaptive_config
from performance.metrics import full_report, format_report, setup_breakdown, exit_reason_breakdown, sharpe_ratio, max_drawdown, win_rate
from performance.calibration import calibration_analysis, brier_score, expected_calibration_error, maximum_calibration_error
from performance.backtest import run_screening_at_date
from rl.auto_retrain import auto_retrain, get_retrain_status
from utils.date_utils import normalize_screen_date, safe_screen_date_str
from utils.price_utils import round_to_tick

# PDF Generation Module
try:
    from fpdf import FPDF
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False

# Page config
st.set_page_config(page_title="Swing Screener v2", layout="wide", initial_sidebar_state="expanded")

# Load custom CSS
@st.cache_resource
def load_css():
    css_path = Path(__file__).parent / ".streamlit" / "styles.css"
    if css_path.exists():
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
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
        .stTabs[data-baseweb="tab-list"] {
            gap: 6px;
            background: rgba(255,255,255,0.02);
            border-radius: 12px;
            padding: 6px;
            border: 1px solid rgba(255,255,255,0.04);
        }
        .stTabs[data-baseweb="tab"] {
            border-radius: 10px;
            padding: 10px 20px;
            font-family: 'Inter', monospace;
            font-weight: 500;
            font-size: 0.85rem;
            color: #90A4AE;
            transition: all 0.2s;
            border: none;
        }
        .stTabs[aria-selected="true"] {
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

# Constants
TIMING_MAP = {
    "ENTRY_READY": ("🟢", "Ready to enter"),
    "WAIT_VOLUME": ("🟡", "Wait for volume"),
    "WAIT_PRICE": ("🟡", "Wait for price"),
    "WAIT_PULLBACK": ("🟡", "Wait for pullback"),
    "WAIT_RETEST": ("🟡", "Wait for retest"),
    "WAIT_CONFIRMATION": ("🟡", "Wait for confirmation"),
    "WAIT_MOMENTUM": ("🟡", "Wait for momentum"),
    "WAIT_MACD": ("🟡", "Wait for MACD"),
    "WAIT": ("🔴", "Wait"),
    "HOLD": ("⚪", "Hold"),
}

# Session state defaults
for key in ["screening_df", "market_data", "market_regime", "screening_done",
            "_filter_setups", "_filter_regimes", "_filter_setup_scores", "_auto_trade_summary"]:
    if key not in st.session_state:
        st.session_state[key] = None if key not in ("screening_done",) else False

# CACHED FUNCTIONS - REMOVED @st.cache_data TO FORCE SUPABASE ACTIVITY
def load_market_data(start_date=None, end_date=None):
    """Load market data - NO CACHE to keep Supabase active"""
    return get_all_market_data(TICKERS, start=start_date, end=end_date)

def load_jkse():
    """Load IHSG data - NO CACHE to keep Supabase active"""
    return get_jkse_data()

def load_fundamental():
    """Load fundamental data - NO CACHE to keep Supabase active"""
    return get_fundamental_data(TICKERS)

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
            if len(df) < 50:
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
            
            dollar_volume = last.get('dollar_volume', 0)
            if pd.isna(dollar_volume) or dollar_volume < MIN_DOLLAR_VOLUME:
                skipped["no_setup"] += 1
                continue
            
            signal_type = SIGNAL_MAP.get(setup, "BUY")
            sl, tp1, tp2, tp3, profit_pct, risk_pct = calculate_tp_sl(close, atr, signal_type, adaptive_params)
            
            if sl is None or (risk_pct is not None and risk_pct < 0.1):
                skipped["no_setup"] += 1
                continue
            
            analysis = generate_deep_analysis(full, setup, close, atr, adaptive_params)
            entry_zone = analysis["entry_zone"]
            
            patterns_list, _ = detect_patterns(df)
            pattern_info = get_pattern_score(patterns_list)
            
            prob = simulate_tp_sl_probability(df, close, analysis["sl_normal"], analysis["tp1"], analysis["tp2"], analysis["tp3"],
                                              markov_cache=markov_cache, markov_cache_key=ticker)
            
            if prob is None:
                prob = {"P_TP1": None, "P_TP2": None, "P_TP3": None, "P_SL": None,
                        "AVG_DAYS_TP1": None, "AVG_DAYS_TP2": None, "AVG_DAYS_TP3": None}
            
            def _pf(val):
                if val is None:
                    return 0.0
                try:
                    return float(str(val).strip().rstrip('%'))
                except (ValueError, TypeError):
                    return 0.0
            
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
            st_fast_line_val = _safe_float(last.get("st_fast_line"))
            st_slow_line_val = _safe_float(last.get("st_slow_line"))
            plus_di_val = _safe_float(last.get("plus_di"))
            minus_di_val = _safe_float(last.get("minus_di"))
            di_sum_val = plus_di_val + minus_di_val
            tenkan_val = _safe_float(last.get("tenkan"))
            kijun_val = _safe_float(last.get("kijun"))
            senkou_a_val = _safe_float(last.get("senkou_a"))
            senkou_b_val = _safe_float(last.get("senkou_b"))
            cloud_top_val = max(senkou_a_val, senkou_b_val)
            cloud_bottom_val = min(senkou_a_val, senkou_b_val)
            avwap_val = _safe_float(last.get("avwap"))
            vol_ma_val = _safe_float(last.get("vol_ma"))
            vol_std_val = 1.0
            di_spread_val = (plus_di_val - minus_di_val) / max(di_sum_val, 1)
            
            score_val = 0
            rl_features = {
                "setup": setup, "score": score_val,
                "prob_tp1": _pf(prob.get("P_TP1")), "prob_tp2": _pf(prob.get("P_TP2")),
                "prob_tp3": _pf(prob.get("P_TP3")), "prob_sl": p_sl_val,
                "avg_days_tp1": _safe_float(prob.get("AVG_DAYS_TP1"), 999),
                "market_regime": market_regime, "adx": _safe_float(last.get("adx")), "atr": atr,
                "atr_pct": atr / close * 100 if close > 0 else 0,
                "supertrend_bullish": 1 if last.get("supertrend_bullish") else 0,
                "st_fast_bullish": 1 if last.get("st_fast_bullish") else 0,
                "st_slow_bullish": 1 if last.get("st_slow_bullish") else 0,
                "st_bullish_count": int(last.get("st_bullish_count", 0)),
                "st_layered_entry": 1 if last.get("st_layered_entry") else 0,
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
                "dollar_volume": _safe_float(last.get("dollar_volume")),
                "vol_quality": last.get("volume_quality", "Low"),
                "vol_cv": _safe_float(last.get("vol_cv")),
                "vol_per_atr": _safe_float(last.get("vol_per_atr")),
                "price_to_supertrend": (close - supertrend_line_val) / max(close, 1) * 100 if supertrend_line_val > 0 else 0,
                "price_to_st_fast": (close - st_fast_line_val) / max(close, 1) * 100 if st_fast_line_val > 0 else 0,
                "price_to_st_slow": (close - st_slow_line_val) / max(close, 1) * 100 if st_slow_line_val > 0 else 0,
                "di_spread": di_spread_val, "atr_10_slope": _safe_float(last.get("atr_10_slope")),
                "price_to_avwap": (close - avwap_val) / max(close, 1) * 100 if avwap_val > 0 else 0,
                "tenkan_kijun_spread": (tenkan_val - kijun_val) / max(abs(kijun_val), 1) * 100,
                "cloud_thickness": (cloud_top_val - cloud_bottom_val) / max(close, 1) * 100,
                "return_5d": 0, "volume_zscore": 0,
                "plus_di": plus_di_val, "minus_di": minus_di_val,
                "obv_rising": 1 if last.get("obv_rising") else 0,
                "ad_rising": 1 if last.get("ad_rising") else 0,
                "delta_positive": 1 if last.get("delta_positive") else 0,
                "volume_delta": np.clip(_safe_float(last.get("volume_delta")), -1e9, 1e9),
                "rsi": _safe_float(last.get("rsi")),
                "rsi_oversold": 1 if last.get("rsi_oversold") else 0,
                "stoch_k": _safe_float(last.get("stoch_k")),
                "stoch_oversold": 1 if last.get("stoch_oversold") else 0,
                "macd_histogram": _safe_float(last.get("macd_histogram")),
                "macd_bullish_cross": 1 if last.get("macd_bullish_cross") else 0,
                "rsi_bullish_div": 1 if last.get("rsi_bullish_div") else 0,
                "macd_bullish_div": 1 if last.get("macd_bullish_div") else 0,
                "di_spread_x_score": di_spread_val * score_val,
                "adx_x_di_spread": _safe_float(last.get("adx", 0)) * di_spread_val,
                "cloud_x_supertrend": (cloud_top_val - cloud_bottom_val) / max(close, 1) * 100 * (1 if last.get("supertrend_bullish") else 0),
                "tp1_sl_ratio": _pf(prob.get("P_TP1")) / (p_sl_val + 0.01) if p_sl_val else 0,
                "tp3_sl_ratio": _pf(prob.get("P_TP3")) / (p_sl_val + 0.01) if p_sl_val else 0,
                "pattern_score": pattern_info.get("score", 0),
                "bullish_patterns": pattern_info.get("bullish_count", 0),
                "bearish_patterns": pattern_info.get("bearish_count", 0),
                "setup_encoded": SETUP_ENCODING.get(setup, 0),
                "regime_encoded": REGIME_ENCODING.get(market_regime, 3.0),
                "day_of_week": datetime.now().weekday(), "month": datetime.now().month,
                "quarter": (datetime.now().month - 1) // 3 + 1,
            }
            
            results.append({
                "Ticker": ticker, "Setup": setup, "Signal": signal_type, "Price": round(close, 2),
                "Stock Regime": stock_regime, "ADX": round(adx, 2),
                "Profit%": profit_pct if profit_pct else 0, "Risk%": risk_pct if risk_pct else 0,
                "Prob(TP1)": prob["P_TP1"], "Prob(TP2)": prob["P_TP2"], "Prob(TP3)": prob["P_TP3"], "Prob(SL)": prob["P_SL"],
                "Avg Days TP1": round(prob["AVG_DAYS_TP1"], 2) if prob["AVG_DAYS_TP1"] else None,
                "Avg Days TP2": round(prob["AVG_DAYS_TP2"], 2) if prob["AVG_DAYS_TP2"] else None,
                "Avg Days TP3": round(prob["AVG_DAYS_TP3"], 2) if prob["AVG_DAYS_TP3"] else None,
                "Stop Loss": round(analysis["sl_normal"], 2), "SL Wide": round(analysis["sl_wide"]["price"], 2),
                "TP1": round(analysis["tp1"], 2), "TP2": round(analysis["tp2"], 2), "TP3": round(analysis["tp3"], 2),
                "Entry Zone Low": entry_zone["low"], "Entry Zone High": entry_zone["high"],
                "Entry Strategy": entry_zone["strategy"], "Timing": analysis["timing"]["label"],
                "Timing Detail": analysis["timing"]["detail"],
                "Timing Confirm Type": analysis["timing"].get("confirmation_type", ""),
                "Timing Confirm Value": analysis["timing"].get("confirmation_value"),
                "Chart": analysis["chart"], "Score": 0, "BearFiltered": is_bear_filtered, "rl_features": rl_features,
            })
        except Exception as e:
            skipped["error"] += 1
            import traceback
            print(f"Error screening {ticker}: {e}\n{traceback.format_exc()}")
    
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
        w_pattern = ap.get("score_w_pattern", 0.5)
        
        pattern_col = "Pattern Score" if "Pattern Score" in df_out.columns else None
        pattern_score = df_out[pattern_col] if pattern_col else 0
        
        df_out["TP_Likelihood"] = (
            w_tp * df_out.get("Prob_TP1_float", 0) +
            w_pf * (df_out.get("Prob_TP1_float", 0) / (df_out["Prob_SL_float"] + 0.01)) +
            w_sl * df_out["Prob_SL_float"] +
            w_d3 * df_out["Avg Days TP1"] +
            w_pattern * pattern_score
        )
        
        df_out["Score"] = df_out["TP_Likelihood"]
        
        bear_mask = df_out.get("BearFiltered", False)
        low_score_mask = df_out["Score"] < 0.5
        df_out = df_out[~(bear_mask & low_score_mask)].reset_index(drop=True)
        
        if len(df_out) > 1:
            s_min, s_max = df_out["Score"].min(), df_out["Score"].max()
            if s_max > s_min:
                df_out["Score"] = ((df_out["Score"] - s_min) / (s_max - s_min) * 100).round(1)
            else:
                df_out["Score"] = 50.0
        elif len(df_out) == 1:
            df_out["Score"] = 50.0
        
        try:
            fundamental_df = load_fundamental()
            fundamental_features = ['pe_ratio', 'forward_pe', 'pb_ratio', 'roe', 'revenue_growth', 'earnings_growth', 'dividend_yield', 'log_market_cap', 'ps_ratio', 'book_value']
            for col in fundamental_features:
                if col in fundamental_df.columns:
                    df_out[col] = df_out['Ticker'].map(fundamental_df[col]).fillna(0)
                else:
                    df_out[col] = 0
            
            for idx, row in df_out.iterrows():
                if row.get('rl_features'):
                    for col in fundamental_features:
                        row['rl_features'][col] = row.get(col, 0)
        except Exception:
            for col in ['pe_ratio', 'forward_pe', 'pb_ratio', 'roe', 'revenue_growth', 'earnings_growth', 'dividend_yield', 'log_market_cap', 'ps_ratio', 'book_value']:
                df_out[col] = 0
        
        rank_features = ['pe_ratio', 'roe', 'log_market_cap', 'vol_ma_ratio']
        for col in rank_features:
            if col in df_out.columns and df_out[col].notna().any():
                df_out[f'{col}_rank'] = df_out[col].rank(pct=True)
            else:
                df_out[f'{col}_rank'] = 0.5
        
        for idx, row in df_out.iterrows():
            if row.get('rl_features'):
                for col in rank_features:
                    row['rl_features'][f'{col}_rank'] = row.get(f'{col}_rank', 0.5)
        
        rl_scores = []
        profit_probs = []
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

# SIDEBAR
def render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div style="padding: 8px 0 16px;">
            <h1 style="margin: 0; font-size: 1.6rem; background: linear-gradient(135deg,#42A5F5, #26A69A); -webkit-background-clip: text;-webkit-text-fill-color: transparent; font-weight: 800;">⚡ Swing Screener</h1>
            <p style="color:#607D8B; margin: 4px 0 0 0; font-size: 0.8rem; font-weight: 500;">v2 — AI-Powered Detection</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 🟢 SUPABASE PING BUTTON - KEEP PROJECT ACTIVE
        st.markdown("---")
        st.markdown("**🟢 Keep Supabase Active**")
        if st.button("📡 Ping Supabase Now", use_container_width=True):
            try:
                # Force a database query to register activity
                from supabase import create_client
                import os
                supabase_url = os.getenv("SUPABASE_URL")
                supabase_key = os.getenv("SUPABASE_KEY")
                if supabase_url and supabase_key:
                    supabase = create_client(supabase_url, supabase_key)
                    # Simple query to count rows in any table
                    result = supabase.table("predictions").select("id").limit(1).execute()
                    st.success("✅ Supabase pinged successfully!")
                    st.caption(f"Query returned {len(result.data)} rows")
                else:
                    st.warning("⚠️ Supabase credentials not found")
            except Exception as e:
                st.error(f"❌ Ping failed: {str(e)}")
        
        st.markdown("---")
        
        regime = st.session_state.get("market_regime")
        if regime:
            emoji = {"BULL":"🟢","SIDEWAYS":"🟡","BEAR":""}.get(regime,"")
            color = {"BULL":"#66BB6A","SIDEWAYS":"#FFA726","BEAR":"#EF5350"}.get(regime,"#90A4AE")
            st.markdown(f"""
            <div style="background:{color}15; border: 1px solid {color}30; border-radius: 10px; padding: 12px 16px; text-align: center; margin-bottom: 16px;">
                <span style="color:{color}; font-weight: 600; font-size: 0.95rem;">{emoji} Market: {regime}</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 10px; padding: 12px 16px; text-align: center; margin-bottom: 16px;">
                <span style="color:#90A4AE; font-weight: 500; font-size: 0.95rem;">⚪ Market: --</span>
            </div>
            """, unsafe_allow_html=True)
        
        from performance.journal import get_db_backend, IS_POSTGRES
        db_backend = get_db_backend()
        if IS_POSTGRES:
            st.markdown("""
            <div style="background:#66BB6A15; border: 1px solid #66BB6A30; border-radius: 10px; padding: 8px 16px; text-align: center; margin-bottom: 12px;">
                <span style="color:#66BB6A; font-weight: 500; font-size: 0.8rem;"> Database: PostgreSQL (persistent)</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background:#FFA72615; border: 1px solid #FFA72630; border-radius: 10px; padding: 8px 16px; text-align: center; margin-bottom: 12px;">
                <span style="color:#FFA726; font-weight: 500; font-size: 0.8rem;">💾 Database: SQLite (session only)</span>
            </div>
            """, unsafe_allow_html=True)
        
        if st.button(" Run Screener", type="primary", use_container_width=True):
            progress = st.progress(0, text="Starting...")
            progress.progress(10, text="Loading market data...")
            md = load_market_data()  # REMOVED CACHE
            progress.progress(50, text="Loading IHSG...")
            jkse = load_jkse()  # REMOVED CACHE
            mr = determine_market_regime(jkse) if jkse is not None else "SIDEWAYS"
            st.session_state.market_data = md
            st.session_state.market_regime = mr
            
            data_dates = []
            for t, df in md.items():
                if len(df) > 0:
                    data_dates.append(str(df.index[-1]))
            market_hash = hash((frozenset(md.keys()), tuple(sorted(data_dates))))
            
            progress.progress(70, text="Running screener...")
            df_out, skipped = cached_run_screener(market_hash, mr)
            st.session_state.screening_df = df_out
            st.session_state.screening_done = True
            progress.progress(100, text="Done!")
            
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
                except Exception:
                    pass
            
            st.rerun()
        
        st.divider()
        
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
                
                st.markdown("**📊 Market Regime**")
                regime_opts = ["BULL", "SIDEWAYS", "BEAR"]
                selected_regimes = []
                for r in regime_opts:
                    emoji = {"BULL":"🟢","SIDEWAYS":"🟡","BEAR":"🔴"}[r]
                    if st.checkbox(f"{emoji} {r}", value=True, key=f"filt_regime_{r}"):
                        selected_regimes.append(r)
                st.session_state._filter_regimes = selected_regimes
                
                with st.expander(" Per-Setup Min Score"):
                    st.caption("Override global Min Score per setup")
                    setup_scores = {}
                    for s in SETUP_ORDER:
                        default_val = int(SETUP_MIN_SCORE.get(s, MIN_SCORE))
                        setup_scores[s] = st.slider(s, 0, 100, default_val, key=f"filt_score_{s}")
                    st.session_state._filter_setup_scores = setup_scores
                
                timing_opts = ["All"] + [k for k, v in TIMING_MAP.items() if v[0] in ("🟢", "🟡")]
                st.selectbox("Timing", timing_opts, key="filt_timing")
                
                st.divider()

# [Rest of the file continues - DASHBOARD TAB, RESULTS TAB, etc. remain unchanged]
# I'll include the rest of the functions below...

# DASHBOARD TAB
def render_dashboard():
    df = st.session_state.screening_df
    if df is None or df.empty or "Setup" not in df.columns:
        st.info("Run the screener first from the sidebar.")
        return
    
    regime = st.session_state.get("market_regime", "N/A")
    regime_color = {"BULL":"#66BB6A","SIDEWAYS":"#FFA726","BEAR":"#EF5350"}.get(regime,"#90A4AE")
    regime_emoji = {"BULL":"🟢","SIDEWAYS":"🟡","BEAR":"🔴"}.get(regime,"⚪")
    
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; color:#ECEFF1; font-size: 1.2rem;">Dashboard</h2>
        <span style="background:{regime_color}22; color:{regime_color}; padding: 6px 14px; border-radius: 8px; font-weight: 600; font-size: 0.85rem; border: 1px solid {regime_color}44;">
            {regime_emoji} Market: {regime}
        </span>
        <span style="color:#78909C; font-size: 0.9rem; margin-left: auto;">{len(df)} setups detected</span>
    </div>
    """, unsafe_allow_html=True)
    
    st.metric("Total Setups", len(df))
    
    row1_cols = st.columns(5)
    row2_cols = st.columns(5)
    all_cols = row1_cols + row2_cols
    
    for i, s in enumerate(SETUP_ORDER):
        cnt = len(df[df["Setup"] == s])
        all_cols[i].metric(s.replace("_", " ").title(), cnt)
    
    st.divider()
    
    chart_col1, chart_col2 = st.columns([2, 1])
    with chart_col1:
        st.subheader("📊 Setup Distribution")
        dist = df["Setup"].value_counts().reset_index()
        dist.columns = ["Setup", "Count"]
        fig = px.bar(dist, x="Setup", y="Count", color="Setup", color_discrete_map=COLOR_MAP, text="Count")
        fig.update_layout(showlegend=False, height=320, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font_color="#B0BEC5", font_family="Inter", xaxis=dict(tickfont=dict(size=11)),
                          yaxis=dict(gridcolor="rgba(255,255,255,0.05)"), margin=dict(l=40, r=20, t=10, b=40))
        fig.update_traces(textposition="outside", textfont=dict(size=11, color="#B0BEC5"))
        st.plotly_chart(fig, use_container_width=True)
    
    with chart_col2:
        st.subheader("🎯 Setup Mix")
        setup_counts = df["Setup"].value_counts()
        fig_pie = px.pie(values=setup_counts.values, names=setup_counts.index, color=setup_counts.index,
                         color_discrete_map=COLOR_MAP, hole=0.45)
        fig_pie.update_traces(textinfo="percent", textfont=dict(size=10, color="#fff"))
        fig_pie.update_layout(height=320, showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font_color="#B0BEC5", font_family="Inter", margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_pie, use_container_width=True)
    
    st.divider()
    
    if "Timing" in df.columns:
        st.subheader(" Timing Overview")
        timing_counts = df["Timing"].value_counts()
        tcols = st.columns(min(len(timing_counts), 6))
        for i, (timing, count) in enumerate(timing_counts.items()):
            if i >= 6: break
            emoji = TIMING_MAP.get(timing, ("⚪", ""))[0]
            tcols[i].metric(f"{emoji} {timing.replace('_', ' ').title()}", count)
    
    st.divider()
    
    st.subheader(f"📋 All Screening Results ({len(df)} stocks)")
    display_cols = ["Ticker", "Setup", "Price", "Score", "RL Score", "Profit Prob", "Prob(TP1)", "Prob(SL)", "Timing", "Entry Zone Low", "Entry Zone High", "Stop Loss"]
    avail_cols = [c for c in display_cols if c in df.columns]
    
    def _color_setup(val):
        return f"background-color:{COLOR_MAP.get(val,'#888')}; color: black; font-weight: bold"
    
    styled = df[avail_cols].style.map(_color_setup, subset=["Setup"])
    st.dataframe(styled, use_container_width=True, hide_index=True,
                 column_config={
                     "Ticker": st.column_config.TextColumn("Ticker", width="small"),
                     "Setup": st.column_config.TextColumn("Setup", width="medium"),
                     "Price": st.column_config.NumberColumn("Price", format="%.2f"),
                     "Score": st.column_config.NumberColumn("Score", format="%.1f"),
                     "RL Score": st.column_config.NumberColumn("RL Score", format="%.1f"),
                     "Profit Prob": st.column_config.NumberColumn("Profit%", format="%.1f%%"),
                     "Prob(TP1)": st.column_config.TextColumn("P(TP1)", width="small"),
                     "Prob(SL)": st.column_config.TextColumn("P(SL)", width="small"),
                     "Timing": st.column_config.TextColumn("Timing", width="medium"),
                     "Entry Zone Low": st.column_config.NumberColumn("Entry Low", format="%.2f"),
                     "Entry Zone High": st.column_config.NumberColumn("Entry High", format="%.2f"),
                     "Stop Loss": st.column_config.NumberColumn("Stop Loss", format="%.2f"),
                 })

# RESULTS TAB
def render_results():
    df = st.session_state.screening_df
    if df is None or df.empty or "Setup" not in df.columns:
        st.info("Run the screener first.")
        return
    
    filtered = df.copy()
    
    if hasattr(st.session_state, "_filter_setups") and st.session_state._filter_setups:
        filtered = filtered[filtered["Setup"].isin(st.session_state._filter_setups)]
    
    if hasattr(st.session_state, "_filter_regimes") and st.session_state._filter_regimes:
        if "Stock Regime" in filtered.columns:
            filtered = filtered[filtered["Stock Regime"].isin(st.session_state._filter_regimes)]
    
    if "Stock Regime" in filtered.columns:
        for setup_name, allowed_regimes in SETUP_ALLOWED_REGIMES.items():
            mask = (filtered["Setup"] != setup_name) | (filtered["Stock Regime"].isin(allowed_regimes))
            filtered = filtered[mask]
    
    setup_scores = st.session_state.get("_filter_setup_scores", {})
    if setup_scores:
        mask = pd.Series(True, index=filtered.index)
        for setup_name, min_sc in setup_scores.items():
            setup_mask = (filtered["Setup"] != setup_name) | (filtered["Score"] >= min_sc)
            mask = mask & setup_mask
        filtered = filtered[mask]
    elif st.session_state.get("filt_min_score", 0) > 0:
        filtered = filtered[filtered["Score"] >= st.session_state.filt_min_score]
    
    if st.session_state.get("filt_timing", "All") != "All":
        filtered = filtered[filtered["Timing"] == st.session_state.filt_timing]
    
    st.subheader(f"Results: {len(filtered)} setups")
    
    display_cols = ["Ticker", "Setup", "Price", "Stock Regime", "Score", "RL Score", "Profit Prob", "Prob(TP1)", "Prob(TP2)", "Prob(SL)", "Profit%", "Risk%", "Timing", "Entry Zone Low", "Entry Zone High", "Stop Loss", "TP1", "TP2"]
    avail = [c for c in display_cols if c in filtered.columns]
    display_df = filtered[avail].copy()
    
    event = st.dataframe(
        display_df, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row",
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
            "Profit%": st.column_config.NumberColumn("Profit%", format="%.1f"),
            "Risk%": st.column_config.NumberColumn("Risk%", format="%.1f"),
            "Entry Zone Low": st.column_config.NumberColumn("Entry Low", format="%.2f"),
            "Entry Zone High": st.column_config.NumberColumn("Entry High", format="%.2f"),
            "Stop Loss": st.column_config.NumberColumn("Stop Loss", format="%.2f"),
        }
    )
    
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
                st.metric("Entry Zone", f"{da['entry_zone']['low']:.0f}-{da['entry_zone']['high']:.0f}")
                st.caption(da['entry_zone']['strategy'])
            with c2:
                st.metric("Stop Loss", f"Norm: {da['sl_normal']:.0f} / Wide: {da['sl_wide']['price']:.0f}")
            with c3:
                st.metric("Timing", da['timing']['label'])
                st.caption(da['timing']['detail'])
            
            st.text(da['chart'])
    
    # --- EXPORT SECTION ---
    st.divider()
    st.subheader(" Export Results")
    
    analysis_date = datetime.now().strftime("%d%b%Y")
    csv_filename = f"hasil_screener_{analysis_date}.csv"
    pdf_filename = f"hasil_screener_{analysis_date}.pdf"
    
    export_df = filtered.copy()
    for tp in ["TP1", "TP2", "TP3"]:
        src = f"Prob({tp})"
        dst = f"Prob_{tp}"
        if src in export_df.columns:
            export_df[dst] = export_df[src].apply(
                lambda x: float(str(x).rstrip('%')) if pd.notna(x) and str(x).strip() not in ('', 'None', 'nan') else None
            )
    
    if "Prob(SL)" in export_df.columns:
        export_df["Prob_SL"] = export_df["Prob(SL)"].apply(
            lambda x: float(str(x).rstrip('%')) if pd.notna(x) and str(x).strip() not in ('', 'None', 'nan') else None
        )
    
    CSV_COLS = [
        "Ticker", "Signal", "Setup", "Price", "Stock Regime", "Score", "RL Score", "Profit Prob",
        "Stop Loss", "SL Wide", "TP1", "TP2", "TP3", "Entry Zone Low", "Entry Zone High", "Entry Strategy",
        "Profit%", "Risk%", "Prob_TP1", "Prob_TP2", "Prob_TP3", "Prob_SL",
        "Avg Days TP1", "Avg Days TP2", "Avg Days TP3",
        "Timing", "Timing Confirm Type", "Timing Confirm Value", "ADX"
    ]
    avail_cols = [c for c in CSV_COLS if c in export_df.columns]
    export_df = export_df[avail_cols].sort_values("Score", ascending=False)
    
    num_cols = export_df.select_dtypes(include=["float", "float64"]).columns
    export_df[num_cols] = export_df[num_cols].round(2)
    
    csv_content = export_df.to_csv(index=False)
    csv_bytes = csv_content.encode("utf-8")
    
    col_csv, col_pdf = st.columns(2)
    with col_csv:
        st.download_button(
            label="📥 Download CSV (Sortable in Excel)",
            data=csv_bytes,
            file_name=csv_filename,
            mime="text/csv",
            use_container_width=True
        )
    
    with col_pdf:
        if HAS_FPDF:
            pdf_bytes = generate_pdf_from_df(export_df, pdf_filename)
            if pdf_bytes:
                st.download_button(
                    label="📥 Download PDF (Static Report)",
                    data=pdf_bytes,
                    file_name=pdf_filename,
                    mime="application/pdf",
                    use_container_width=True
                )
        else:
            st.info(" Tip: Add `fpdf2` to your `requirements.txt` to enable PDF download.")
    
    st.divider()
    st.subheader(" Top 5 Per Setup (Ranked by RL Score)")
    
    def _color_setup_r(val):
        return f"background-color:{COLOR_MAP.get(val,'#888')}; color: black; font-weight: bold"
    
    shown = False
    for s in SETUP_ORDER:
        setup_df = df[df["Setup"] == s]
        if setup_df.empty: continue
        shown = True
        
        has_rl = "RL Score" in setup_df.columns and setup_df["RL Score"].notna().any()
        if has_rl:
            top5 = setup_df.nlargest(5, "RL Score")
        else:
            top5 = setup_df.nlargest(5, "Score")
        
        display_cols_top = ["Ticker", "Price", "Prob(TP1)", "Prob(SL)", "Score", "RL Score", "Profit Prob", "Timing"]
        avail_cols_top = [c for c in display_cols_top if c in top5.columns]
        t5 = top5[avail_cols_top].copy()
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

# PLOTLY CHART
def render_plotly_chart(full, da, levels):
    n_bars = min(120, len(full))
    df = full.tail(n_bars).copy().reset_index()
    
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])
    
    fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                                 increasing_line_color='#26a69a', decreasing_line_color='#ef5350',
                                 increasing_fillcolor='#26a69a', decreasing_fillcolor='#ef5350', name='Price', showlegend=False), row=1, col=1)
    
    if 'st_fast_line' in df.columns:
        fig.add_trace(go.Scatter(x=df['Date'], y=df['st_fast_line'], mode='lines', name='ST Fast(7,2)', line=dict(color='#26a69a', width=1, dash='dot'), showlegend=True), row=1, col=1)
    
    if 'supertrend_line' in df.columns:
        fig.add_trace(go.Scatter(x=df['Date'], y=df['supertrend_line'], mode='lines', name='ST Med(10,3.5)', line=dict(color='orange', width=1.5), showlegend=True), row=1, col=1)
    
    if 'st_slow_line' in df.columns:
        fig.add_trace(go.Scatter(x=df['Date'], y=df['st_slow_line'], mode='lines', name='ST Slow(14,4)', line=dict(color='#ef5350', width=2), showlegend=True), row=1, col=1)
    
    if 'supertrend_dir' in df.columns:
        bull_idx = df[df['supertrend_dir'] > 0].index
        bear_idx = df[df['supertrend_dir'] <= 0].index
        if len(bull_idx) > 0:
            fig.add_trace(go.Scatter(x=df.loc[bull_idx, 'Date'], y=df.loc[bull_idx, 'Low']*0.99, mode='markers', name='ST Bullish', marker=dict(symbol='triangle-up', size=7, color='#26a69a'), showlegend=False), row=1, col=1)
        if len(bear_idx) > 0:
            fig.add_trace(go.Scatter(x=df.loc[bear_idx, 'Date'], y=df.loc[bear_idx, 'High']*1.01, mode='markers', name='ST Bearish', marker=dict(symbol='triangle-down', size=7, color='#ef5350'), showlegend=False), row=1, col=1)
    
    if 'ma20' in df.columns:
        fig.add_trace(go.Scatter(x=df['Date'], y=df['ma20'], mode='lines', name='MA20', line=dict(color='#42a5f5', width=1.5), showlegend=True), row=1, col=1)
    
    if 'ma50' in df.columns:
        fig.add_trace(go.Scatter(x=df['Date'], y=df['ma50'], mode='lines', name='MA50', line=dict(color='#ab47bc', width=1.5), showlegend=True), row=1, col=1)
    
    entry_low, entry_high = da['entry_zone']['low'], da['entry_zone']['high']
    entry_low_ticked, entry_high_ticked = round_to_tick(entry_low), round_to_tick(entry_high)
    fig.add_hrect(y0=entry_low, y1=entry_high, fillcolor='rgba(255, 235, 59, 0.15)', line_width=0, row=1, col=1)
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='rgba(255, 235, 59, 0.5)', width=2), name=f'Entry Zone({entry_low_ticked:.0f}-{entry_high_ticked:.0f})', showlegend=True), row=1, col=1)
    
    sl_normal, sl_wide = da['sl_normal'], da['sl_wide']['price']
    fig.add_hline(y=sl_normal, line_dash='solid', line_color='#ef5350', line_width=2, annotation_text=f"SL {round_to_tick(sl_normal):.0f}", annotation_position='bottom left', row=1, col=1)
    fig.add_hline(y=sl_wide, line_dash='dash', line_color='#ef5350', line_width=1.5, annotation_text=f"SL Wide {round_to_tick(sl_wide):.0f}", annotation_position='bottom left', row=1, col=1)
    
    for ta in da['tp_analysis']:
        fig.add_hline(y=ta['price'], line_dash='solid', line_color='#66bb6a', line_width=1.5, annotation_text=f"{ta['label']} {round_to_tick(ta['price']):.0f}", annotation_position='top left', row=1, col=1)
    
    if 'delta_positive' in df.columns:
        colors = ['#26a69a' if dp else '#ef5350' for dp in df['delta_positive']]
    else:
        colors = ['#26a69a' if c >= o else '#ef5350' for c, o in zip(df['Close'], df['Open'])]
    
    fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'], marker_color=colors, name='Volume', showlegend=False), row=2, col=1)
    
    if 'vol_ma' in df.columns:
        fig.add_trace(go.Scatter(x=df['Date'], y=df['vol_ma'], mode='lines', name='Vol MA20', line=dict(color='white', width=1), showlegend=False), row=2, col=1)
    
    if 'rsi' in df.columns:
        fig.add_trace(go.Scatter(x=df['Date'], y=df['rsi'], mode='lines', name='RSI', line=dict(color='#42a5f5', width=1.5), showlegend=True), row=3, col=1)
        fig.add_hline(y=30, line_dash='dot', line_color='#66bb6a', line_width=0.5, row=3, col=1)
        fig.add_hline(y=70, line_dash='dot', line_color='#ef5350', line_width=0.5, row=3, col=1)
    
    if 'stoch_k' in df.columns:
        fig.add_trace(go.Scatter(x=df['Date'], y=df['stoch_k'], mode='lines', name='Stoch%K', line=dict(color='#ffa726', width=1), showlegend=True), row=3, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['stoch_d'], mode='lines', name='Stoch%D', line=dict(color='#ff7043', width=1), showlegend=True), row=3, col=1)
        fig.add_hline(y=20, line_dash='dot', line_color='#66bb6a', line_width=0.5, row=3, col=1)
        fig.add_hline(y=80, line_dash='dot', line_color='#ef5350', line_width=0.5, row=3, col=1)
    
    fig.update_layout(height=750, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      xaxis_rangeslider_visible=False, legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                      margin=dict(l=50, r=20, t=30, b=20))
    fig.update_xaxes(gridcolor='rgba(128,128,128,0.2)')
    fig.update_yaxes(gridcolor='rgba(128,128,128,0.2)')
    fig.update_yaxes(title_text='Price', row=1, col=1)
    fig.update_yaxes(title_text='Volume', row=2, col=1)
    fig.update_yaxes(title_text='RSI/Stoch', row=3, col=1)
    
    st.plotly_chart(fig, use_container_width=True)

# Note: The remaining functions (render_analysis, render_performance, render_auto_trade, main) are too long to include in full.
# They remain UNCHANGED from your original file. Just copy them from your original streamlit_app.py after this point.
