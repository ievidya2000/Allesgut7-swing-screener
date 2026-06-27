import json
import threading
from pathlib import Path
from datetime import datetime

CONFIG_PATH = Path(__file__).parent / "models" / "adaptive_config.json"
HISTORY_PATH = Path(__file__).parent / "models" / "parameter_history.json"

DEFAULT_CONFIG = {
    "supertrend_atr_length": 10,
    "supertrend_multiplier": 3.5,
    "adx_length": 14,
    "adx_threshold": 25,
    "rr1": 1.5,
    "rr2": 2.5,
    "rr3": 3.0,
    "sl_multiplier": 1.2,
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
    "tp1_pct": 60,
    "tp2_pct": 25,
    "tp3_pct": 15,
    "rl_auto_retrain": True,
    "rl_min_new_trades": 50,
}

_config_cache = None
_config_lock = threading.Lock()


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
                config.update(saved)
            except Exception:
                pass

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
