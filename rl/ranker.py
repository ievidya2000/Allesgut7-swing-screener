import pickle
import numpy as np
from pathlib import Path

from screener_v2.rl.extract_features import FEATURE_COLUMNS, CATEGORICAL_COLUMNS

MODEL_DIR = Path(__file__).parent / "models"
PRODUCTION_DIR = MODEL_DIR / "production"

_ranker = None
_classifier = None
_encoders = None
_model_features = None
_ensemble = None
_scaler = None
_tabnet = None
_metrics = None
_dropped_features = None


def _load_models():
    global _ranker, _classifier, _encoders, _model_features, _ensemble, _scaler, _tabnet, _metrics, _dropped_features

    if _ranker is not None:
        return True

    # Try production directory first, fallback to main model dir
    for dir_path in [PRODUCTION_DIR, MODEL_DIR]:
        ranker_path = dir_path / "ranker_model.pkl"
        if ranker_path.exists():
            with open(ranker_path, "rb") as f:
                _ranker = pickle.load(f)
            break

    for dir_path in [PRODUCTION_DIR, MODEL_DIR]:
        classifier_path = dir_path / "classifier_model.pkl"
        if classifier_path.exists():
            with open(classifier_path, "rb") as f:
                _classifier = pickle.load(f)
            break

    for dir_path in [PRODUCTION_DIR, MODEL_DIR]:
        encoders_path = dir_path / "label_encoders.pkl"
        if encoders_path.exists():
            with open(encoders_path, "rb") as f:
                _encoders = pickle.load(f)
            break

    for dir_path in [PRODUCTION_DIR, MODEL_DIR]:
        ensemble_path = dir_path / "ensemble_model.pkl"
        if ensemble_path.exists():
            with open(ensemble_path, "rb") as f:
                _ensemble = pickle.load(f)
            break

    for dir_path in [PRODUCTION_DIR, MODEL_DIR]:
        scaler_path = dir_path / "feature_scaler.pkl"
        if scaler_path.exists():
            with open(scaler_path, "rb") as f:
                _scaler = pickle.load(f)
            break

    for dir_path in [PRODUCTION_DIR, MODEL_DIR]:
        tabnet_path = dir_path / "tabnet_model.pkl"
        if tabnet_path.exists():
            try:
                with open(tabnet_path, "rb") as f:
                    _tabnet = pickle.load(f)
            except Exception:
                _tabnet = None
            break

    for dir_path in [PRODUCTION_DIR, MODEL_DIR]:
        metrics_path = dir_path / "training_metrics.pkl"
        if metrics_path.exists():
            with open(metrics_path, "rb") as f:
                _metrics = pickle.load(f)
            _dropped_features = _metrics.get("dropped_features", [])
            break

    if _ranker is None:
        return False

    if hasattr(_ranker, "feature_names_in_"):
        _model_features = list(_ranker.feature_names_in_)
    else:
        _model_features = FEATURE_COLUMNS

    return True


def predict_rl_score(result):
    if not _load_models():
        return None, None

    features = result.get("rl_features", result)
    if not features:
        return None, None

    feature_cols = _model_features if _model_features else FEATURE_COLUMNS
    row = []
    for col in feature_cols:
        val = features.get(col, 0)
        if col in CATEGORICAL_COLUMNS:
            le = _encoders.get(col)
            if le:
                val_str = str(val)
                mapping = le.get("mapping", {})
                val = mapping.get(val_str, 0)
            else:
                val = 0

        if val is None or (isinstance(val, float) and np.isnan(val)):
            val = 0.0
        row.append(float(val))

    try:
        import pandas as pd
        X_df = pd.DataFrame([row], columns=feature_cols)
        X_df = X_df.replace([np.inf, -np.inf], 0).fillna(0)

        if _dropped_features:
            X_df = X_df.drop(columns=[c for c in _dropped_features if c in X_df.columns], errors='ignore')

        rl_score = float(_ranker.predict(X_df)[0])

        if _ensemble is not None and _scaler is not None:
            gbm_prob = float(_classifier.predict_proba(X_df)[0][1])

            xgb = _ensemble.get("xgb")
            lgbm = _ensemble.get("lgbm")
            rf = _ensemble.get("rf")
            lr = _ensemble.get("lr")
            tabnet = _ensemble.get("tabnet")
            scaler = _ensemble.get("scaler", _scaler)
            weights = _ensemble.get("weights", [0.05, 0.10, 0.10, 0.60, 0.15])
            use_tabnet = _ensemble.get("use_tabnet", False)

            xgb_prob = float(xgb.predict_proba(X_df)[0][1]) if xgb is not None else 0
            lgbm_prob = float(lgbm.predict_proba(X_df)[0][1]) if lgbm is not None else 0
            rf_prob = float(rf.predict_proba(X_df)[0][1]) if rf is not None else 0

            X_lr = pd.DataFrame(
                scaler.transform(X_df), columns=X_df.columns
            )
            lr_prob = float(lr.predict_proba(X_lr)[0][1]) if lr is not None else 0

            if use_tabnet and tabnet is not None:
                X_np = X_df.values.astype(np.float32)
                tabnet_prob = float(tabnet.predict_proba(X_np)[0][1])
                profit_prob = (
                    weights[0] * gbm_prob +
                    weights[1] * xgb_prob +
                    weights[2] * lgbm_prob +
                    weights[3] * rf_prob +
                    weights[4] * lr_prob +
                    weights[5] * tabnet_prob
                )
            else:
                profit_prob = (
                    weights[0] * gbm_prob +
                    weights[1] * xgb_prob +
                    weights[2] * lgbm_prob +
                    weights[3] * rf_prob +
                    weights[4] * lr_prob
                )
        else:
            profit_prob = float(_classifier.predict_proba(X_df)[0][1])
    except Exception:
        return None, None

    rl_score_normalized = max(0, min(100, rl_score * 5 + 50))

    return rl_score_normalized, profit_prob


def predict_rl_scores_batch(results):
    """Batch RL scoring - much faster than calling predict_rl_score per ticker."""
    if not _load_models():
        return [(None, None)] * len(results)

    feature_cols = _model_features if _model_features else FEATURE_COLUMNS
    rows = []

    for result in results:
        features = result.get("rl_features", result)
        if not features:
            rows.append([0.0] * len(feature_cols))
            continue

        row = []
        for col in feature_cols:
            val = features.get(col, 0)
            if col in CATEGORICAL_COLUMNS:
                le = _encoders.get(col)
                if le:
                    val_str = str(val)
                    mapping = le.get("mapping", {})
                    val = mapping.get(val_str, 0)
                else:
                    val = 0

            if val is None or (isinstance(val, float) and np.isnan(val)):
                val = 0.0
            row.append(float(val))
        rows.append(row)

    try:
        import pandas as pd
        X_df = pd.DataFrame(rows, columns=feature_cols)
        X_df = X_df.replace([np.inf, -np.inf], 0).fillna(0)

        if _dropped_features:
            X_df = X_df.drop(columns=[c for c in _dropped_features if c in X_df.columns], errors='ignore')

        rl_scores = _ranker.predict(X_df)

        if _ensemble is not None and _scaler is not None:
            gbm_probs = _classifier.predict_proba(X_df)[:, 1]

            xgb = _ensemble.get("xgb")
            lgbm = _ensemble.get("lgbm")
            rf = _ensemble.get("rf")
            lr = _ensemble.get("lr")
            tabnet = _ensemble.get("tabnet")
            scaler = _ensemble.get("scaler", _scaler)
            weights = _ensemble.get("weights", [0.05, 0.10, 0.10, 0.60, 0.15])
            use_tabnet = _ensemble.get("use_tabnet", False)

            xgb_probs = xgb.predict_proba(X_df)[:, 1] if xgb is not None else np.zeros(len(results))
            lgbm_probs = lgbm.predict_proba(X_df)[:, 1] if lgbm is not None else np.zeros(len(results))
            rf_probs = rf.predict_proba(X_df)[:, 1] if rf is not None else np.zeros(len(results))

            X_lr = pd.DataFrame(scaler.transform(X_df), columns=X_df.columns)
            lr_probs = lr.predict_proba(X_lr)[:, 1] if lr is not None else np.zeros(len(results))

            if use_tabnet and tabnet is not None:
                X_np = X_df.values.astype(np.float32)
                tabnet_probs = tabnet.predict_proba(X_np)[:, 1]
                profit_probs = (
                    weights[0] * gbm_probs +
                    weights[1] * xgb_probs +
                    weights[2] * lgbm_probs +
                    weights[3] * rf_probs +
                    weights[4] * lr_probs +
                    weights[5] * tabnet_probs
                )
            else:
                profit_probs = (
                    weights[0] * gbm_probs +
                    weights[1] * xgb_probs +
                    weights[2] * lgbm_probs +
                    weights[3] * rf_probs +
                    weights[4] * lr_probs
                )
        else:
            profit_probs = _classifier.predict_proba(X_df)[:, 1]

        # Normalize scores
        results_list = []
        for i in range(len(results)):
            rl_score_normalized = max(0, min(100, float(rl_scores[i]) * 5 + 50))
            results_list.append((rl_score_normalized, float(profit_probs[i])))
        return results_list
    except Exception:
        return [(None, None)] * len(results)
