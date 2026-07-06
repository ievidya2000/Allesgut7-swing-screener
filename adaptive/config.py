import json
import logging
import threading
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "models" / "adaptive_config.json"
HISTORY_PATH = Path(__file__).parent / "models" / "parameter_history.json"

DEFAULT_CONFIG = {
    # Multi-SuperTrend (Layered Entry)
    "st_fast_period": 7,
    "st_fast_multiplier": 2.0,
    "st_med_period": 10,
    "st_med_multiplier": 3.5,
    "st_slow_period": 14,
    "st_slow_multiplier": 4.0,
    "adx_length": 14,
    "adx_threshold": 25,
    "rr1": 1.5,
    "rr2": 2.5,
    "rr3": 3.0,
    "sl_multiplier": 1.5,
    "donchian_period": 20,
    "volume_ma_period": 20,
    "ichimoku_tenkan": 9,
    "ichimoku_kijun": 26,
    "ichimoku_senkou_b": 52,
    "vol_contraction_threshold": 0.8,
    "fresh_signal_bars": 3,
    "score_w_prob_tp": 1.0,
    "score_w_profit_pct": 0.5,
    "score_w_prob_sl": -1.0,
    "score_w_avg_days": -0.3,
    "score_w_pattern": 0.5,
    "tp1_pct": 60,
    "tp2_pct": 25,
    "tp3_pct": 15,
    "rl_auto_retrain": False,
    "rl_min_new_trades": 50,
    # Momentum Oscillators
    "rsi_period": 14,
    "rsi_oversold": 30,
    "rsi_overbought": 70,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "stoch_k": 14,
    "stoch_d": 3,
    "stoch_smooth": 3,
    "stoch_oversold": 20,
    # Elliott Wave
    "elliott_swing_lookback": 5,
    # Entry Zone
    "entry_zone_max_atr": 0.75,
    "entry_zone_min_atr": 0.25,
    "entry_zone_max_pct": 0.04,
    # Volume Quality
    "min_dollar_volume": 500_000_000,
    "vol_per_atr_min": 100_000,
    "max_vol_cv": 1.5,
    # Too Late Filter
    "max_runup": 0.30,
    "max_runup_block": 0.50,
    "max_price_to_ma20": 0.15,
    "max_price_to_avwap": 0.10,
    "stoch_overbought": 80,
}

_config_cache = None
_config_lock = threading.Lock()

# Validation rules: (min_val, max_val, must_be_positive)
_VALIDATION_RULES = {
    # Multi-SuperTrend
    "st_fast_period": (1, 50, True),
    "st_fast_multiplier": (0.1, 10.0, True),
    "st_med_period": (1, 50, True),
    "st_med_multiplier": (0.1, 10.0, True),
    "st_slow_period": (1, 50, True),
    "st_slow_multiplier": (0.1, 10.0, True),
    "adx_length": (1, 100, True),
    "adx_threshold": (1, 100, True),
    "rr1": (0.1, 20.0, True),
    "rr2": (0.1, 20.0, True),
    "rr3": (0.1, 20.0, True),
    "sl_multiplier": (0.1, 10.0, True),
    "donchian_period": (1, 200, True),
    "volume_ma_period": (1, 200, True),
    "ichimoku_tenkan": (1, 100, True),
    "ichimoku_kijun": (1, 100, True),
    "ichimoku_senkou_b": (1, 200, True),
    "vol_contraction_threshold": (0.0, 2.0, False),
    "fresh_signal_bars": (1, 50, True),
    "rsi_period": (1, 100, True),
    "rsi_oversold": (0, 100, False),
    "rsi_overbought": (0, 100, False),
    "macd_fast": (1, 100, True),
    "macd_slow": (1, 100, True),
    "macd_signal": (1, 100, True),
    "stoch_k": (1, 100, True),
    "stoch_d": (1, 100, True),
    "stoch_smooth": (1, 100, True),
    "stoch_oversold": (0, 100, False),
    "entry_zone_max_atr": (0.01, 5.0, True),
    "entry_zone_min_atr": (0.01, 5.0, True),
    "entry_zone_max_pct": (0.001, 0.5, True),
    # Volume Quality
    "min_dollar_volume": (10_000_000, 10_000_000_000, True),
    "vol_per_atr_min": (1_000, 10_000_000, True),
    "max_vol_cv": (0.5, 5.0, True),
    # Too Late Filter
    "max_runup": (0.05, 1.0, True),
    "max_runup_block": (0.10, 2.0, True),
    "max_price_to_ma20": (0.05, 0.50, True),
    "max_price_to_avwap": (0.03, 0.30, True),
    "stoch_overbought": (50, 100, False),
}


def _validate_config(config):
    """Validate config values against rules. Returns cleaned config."""
    cleaned = {}
    for key, value in config.items():
        if key not in DEFAULT_CONFIG:
            continue
        expected_type = type(DEFAULT_CONFIG[key])
        if not isinstance(value, (int, float)):
            logger.warning(f"Config '{key}': expected {expected_type.__name__}, got {type(value).__name__}. Using default.")
            continue
        if key in _VALIDATION_RULES:
            min_val, max_val, must_be_positive = _VALIDATION_RULES[key]
            if must_be_positive and value <= 0:
                logger.warning(f"Config '{key}': must be positive, got {value}. Using default.")
                continue
            if value < min_val or value > max_val:
                logger.warning(f"Config '{key}': {value} out of range [{min_val}, {max_val}]. Using default.")
                continue
        cleaned[key] = value
    return cleaned


def load_adaptive_config():
    global _config_cache
    with _config_lock:
        if _config_cache is not None:
            return _config_cache

        config = DEFAULT_CONFIG.copy()

        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r") as f:
                    saved = json.load(f)
                validated = _validate_config(saved)
                config.update(validated)
            except Exception as e:
                logger.warning(f"Could not load adaptive config: {e}")

        _config_cache = config
        return config


def save_adaptive_config(config):
    global _config_cache
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

    with _config_lock:
        _config_cache = config


def get_param(name, default=None):
    config = load_adaptive_config()
    return config.get(name, default)


def reset_config():
    global _config_cache
    _config_cache = None
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()


def load_parameter_history():
    if HISTORY_PATH.exists():
        try:
            with open(HISTORY_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_to_history(config, metrics=None, window_start=None, window_end=None):
    history = load_parameter_history()

    entry = {
        "timestamp": datetime.now().isoformat(),
        "config": config.copy(),
        "metrics": metrics or {},
        "window": {
            "start": str(window_start) if window_start else None,
            "end": str(window_end) if window_end else None,
        },
    }

    history.append(entry)

    if len(history) > 100:
        history = history[-100:]

    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)

    return entry


def get_latest_history(n=5):
    history = load_parameter_history()
    return history[-n:] if history else []


def has_config_changed(old_config, new_config, threshold=0.01):
    if old_config is None:
        return True

    for key in new_config:
        old_val = old_config.get(key)
        new_val = new_config.get(key)

        if old_val is None:
            return True

        if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
            if abs(new_val - old_val) / max(abs(old_val), 1e-10) > threshold:
                return True
        elif old_val != new_val:
            return True

    return False
