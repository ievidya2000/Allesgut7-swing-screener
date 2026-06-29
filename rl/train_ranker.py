import pandas as pd
import numpy as np
import pickle
import warnings
from pathlib import Path
from datetime import datetime

from sklearn.ensemble import (
    HistGradientBoostingRegressor,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit
from scipy.stats import spearmanr
from sklearn.metrics import (
    mean_squared_error, accuracy_score, roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

from xgboost import XGBRegressor, XGBClassifier
from lightgbm import LGBMRegressor, LGBMClassifier

import optuna

from rl.extract_features import FEATURE_COLUMNS, CATEGORICAL_COLUMNS
from rl.tabnet_config import TABNET_CONFIGS
from utils.date_utils import normalize_screen_date

warnings.filterwarnings("ignore", category=UserWarning)
optuna.logging.set_verbosity(optuna.logging.WARNING)

MODEL_DIR = Path(__file__).parent / "models"
MODEL_DIR.mkdir(exist_ok=True)

RANKER_PATH = MODEL_DIR / "ranker_model.pkl"
CLASSIFIER_PATH = MODEL_DIR / "classifier_model.pkl"
ENCODERS_PATH = MODEL_DIR / "label_encoders.pkl"
METRICS_PATH = MODEL_DIR / "training_metrics.pkl"
ENSEMBLE_PATH = MODEL_DIR / "ensemble_model.pkl"
SCALER_PATH = MODEL_DIR / "feature_scaler.pkl"
TABNET_PATH = MODEL_DIR / "tabnet_model.pkl"

MIN_TRAIN_SAMPLES = 100


def load_training_data(path="screener_v2/rl/training_data.parquet"):
    df = pd.read_parquet(path)
    if "screen_date" in df.columns:
        df["screen_date"] = df["screen_date"].apply(normalize_screen_date)
        df = df.dropna(subset=["screen_date"]).reset_index(drop=True)
    print(f"Loaded {len(df)} samples from {path}")
    return df


def remove_multicollinearity(X, threshold=0.85):
    corr_matrix = X.corr().abs()
    upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
    to_drop = [column for column in upper.columns if any(upper[column] > threshold)]
    if to_drop:
        print(f"  Removing {len(to_drop)} correlated features (threshold={threshold}): {to_drop}")
    X_filtered = X.drop(columns=to_drop, errors='ignore')
    return X_filtered, to_drop


def find_best_threshold(X_train, y_train, X_test, y_test, thresholds):
    """Find best correlation threshold using full ensemble."""
    print(f"  Testing {len(thresholds)} thresholds...")
    
    results = {}
    for threshold in thresholds:
        X_train_filtered, dropped = remove_multicollinearity(X_train.copy(), threshold=threshold)
        X_test_filtered = X_test.drop(columns=dropped, errors='ignore')
        
        n_features = X_train_filtered.shape[1]
        
        scaler = StandardScaler()
        X_train_scaled = pd.DataFrame(
            scaler.fit_transform(X_train_filtered), columns=X_train_filtered.columns, index=X_train_filtered.index
        )
        X_test_scaled = pd.DataFrame(
            scaler.transform(X_test_filtered), columns=X_test_filtered.columns, index=X_test_filtered.index
        )
        
        pos_count = (y_train == 1).sum()
        neg_count = (y_train == 0).sum()
        
        hgb = HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.05, max_depth=4,
            min_samples_leaf=30, random_state=42, class_weight='balanced'
        )
        hgb.fit(X_train_filtered, y_train)
        hgb_prob = hgb.predict_proba(X_test_filtered)[:, 1]
        
        xgb = XGBClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=4,
            min_child_weight=30, reg_lambda=1.0, subsample=0.8,
            colsample_bytree=0.8, scale_pos_weight=neg_count/max(pos_count,1),
            random_state=42, n_jobs=-1, verbosity=0, eval_metric='auc'
        )
        xgb.fit(X_train_filtered, y_train)
        xgb_prob = xgb.predict_proba(X_test_filtered)[:, 1]
        
        lgbm = LGBMClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=4,
            min_child_samples=30, reg_lambda=1.0, subsample=0.8,
            colsample_bytree=0.8, class_weight='balanced',
            random_state=42, n_jobs=-1, verbose=-1
        )
        lgbm.fit(X_train_filtered, y_train)
        lgbm_prob = lgbm.predict_proba(X_test_filtered)[:, 1]
        
        rf = RandomForestClassifier(
            n_estimators=200, max_depth=4, min_samples_leaf=10,
            class_weight='balanced', random_state=42, n_jobs=-1
        )
        rf.fit(X_train_filtered, y_train)
        rf_prob = rf.predict_proba(X_test_filtered)[:, 1]
        
        lr = LogisticRegression(C=1.0, class_weight='balanced', max_iter=1000, random_state=42)
        lr.fit(X_train_scaled, y_train)
        lr_prob = lr.predict_proba(X_test_scaled)[:, 1]
        
        ensemble_prob = 0.05 * hgb_prob + 0.10 * xgb_prob + 0.10 * lgbm_prob + 0.60 * rf_prob + 0.15 * lr_prob
        ensemble_auc = roc_auc_score(y_test, ensemble_prob)
        
        results[threshold] = {
            'auc': ensemble_auc,
            'n_features': n_features,
            'dropped': dropped,
        }
        print(f"    Threshold {threshold:.2f}: AUC={ensemble_auc:.4f}, Features={n_features}, Dropped={len(dropped)}")
    
    best_threshold = max(results.items(), key=lambda x: x[1]['auc'])
    return best_threshold[0], results


def prepare_features(df, encoders=None, fit=False):
    feature_cols = [c for c in FEATURE_COLUMNS if c in df.columns]
    X = df[feature_cols].copy()

    if encoders is None:
        encoders = {}

    for col in CATEGORICAL_COLUMNS:
        if col in X.columns:
            if fit:
                mapping = {}
                global_mean = X[col].mode()[0] if len(X[col].mode()) > 0 else "UNKNOWN"
                for cat in X[col].unique():
                    mask = X[col] == cat
                    mapping[cat] = mask.sum()
                encoders[col] = {"mapping": mapping, "global": global_mean, "type": "count"}
                X[col] = X[col].map(mapping).fillna(0)
            else:
                info = encoders.get(col, {})
                mapping = info.get("mapping", {})
                X[col] = X[col].map(mapping).fillna(0)

    X = X.fillna(0)
    X = X.replace([np.inf, -np.inf], 0)
    # Clip extreme values to prevent XGBoost errors
    numeric_cols = X.select_dtypes(include=[np.number]).columns
    X[numeric_cols] = X[numeric_cols].clip(-1e10, 1e10)

    return X, encoders


def objective_ranker(trial, X_train, y_train):
    model_type = trial.suggest_categorical("model", ["hgb", "xgb", "lgbm"])

    if model_type == "hgb":
        params = {
            "max_iter": trial.suggest_int("max_iter", 100, 400),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "max_depth": trial.suggest_int("max_depth", 2, 5),
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 10, 50),
            "l2_regularization": trial.suggest_float("l2_regularization", 0, 1.0),
            "max_bins": 127,
            "random_state": 42,
        }
        model = HistGradientBoostingRegressor(**params)
    elif model_type == "xgb":
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 400),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "max_depth": trial.suggest_int("max_depth", 2, 5),
            "min_child_weight": trial.suggest_int("min_child_weight", 10, 50),
            "reg_lambda": trial.suggest_float("reg_lambda", 0, 1.0),
            "subsample": trial.suggest_float("subsample", 0.7, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.7, 1.0),
            "random_state": 42,
            "n_jobs": -1,
            "verbosity": 0,
        }
        model = XGBRegressor(**params)
    else:
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 400),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "max_depth": trial.suggest_int("max_depth", 2, 5),
            "min_child_samples": trial.suggest_int("min_child_samples", 10, 50),
            "reg_lambda": trial.suggest_float("reg_lambda", 0, 1.0),
            "subsample": trial.suggest_float("subsample", 0.7, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.7, 1.0),
            "random_state": 42,
            "n_jobs": -1,
            "verbose": -1,
        }
        model = LGBMRegressor(**params)

    tscv = TimeSeriesSplit(n_splits=5, gap=10)
    scores = []
    for train_idx, val_idx in tscv.split(X_train):
        Xt, Xv = X_train.iloc[train_idx], X_train.iloc[val_idx]
        yt, yv = y_train[train_idx], y_train[val_idx]
        model.fit(Xt, yt)
        pred = model.predict(Xv)
        try:
            corr, _ = spearmanr(yv, pred)
            scores.append(corr if not np.isnan(corr) else 0)
        except Exception:
            scores.append(0)
    return np.mean(scores)


def objective_classifier(trial, X_train, y_train):
    model_type = trial.suggest_categorical("model", ["hgb", "xgb", "lgbm"])

    if model_type == "hgb":
        params = {
            "max_iter": trial.suggest_int("max_iter", 100, 400),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "max_depth": trial.suggest_int("max_depth", 2, 5),
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 10, 50),
            "l2_regularization": trial.suggest_float("l2_regularization", 0, 1.0),
            "max_bins": 127,
            "random_state": 42,
            "class_weight": "balanced",
        }
        model = HistGradientBoostingClassifier(**params)
    elif model_type == "xgb":
        pos_count = (y_train == 1).sum()
        neg_count = (y_train == 0).sum()
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 400),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "max_depth": trial.suggest_int("max_depth", 2, 5),
            "min_child_weight": trial.suggest_int("min_child_weight", 10, 50),
            "reg_lambda": trial.suggest_float("reg_lambda", 0, 1.0),
            "subsample": trial.suggest_float("subsample", 0.7, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.7, 1.0),
            "scale_pos_weight": neg_count / max(pos_count, 1),
            "random_state": 42,
            "n_jobs": -1,
            "verbosity": 0,
            "eval_metric": "auc",
        }
        model = XGBClassifier(**params)
    else:
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 400),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "max_depth": trial.suggest_int("max_depth", 2, 5),
            "min_child_samples": trial.suggest_int("min_child_samples", 10, 50),
            "reg_lambda": trial.suggest_float("reg_lambda", 0, 1.0),
            "subsample": trial.suggest_float("subsample", 0.7, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.7, 1.0),
            "random_state": 42,
            "n_jobs": -1,
            "verbose": -1,
            "class_weight": "balanced",
        }
        model = LGBMClassifier(**params)

    tscv = TimeSeriesSplit(n_splits=5, gap=10)
    scores = []
    for train_idx, val_idx in tscv.split(X_train):
        Xt, Xv = X_train.iloc[train_idx], X_train.iloc[val_idx]
        yt, yv = y_train[train_idx], y_train[val_idx]
        model.fit(Xt, yt)
        try:
            prob = model.predict_proba(Xv)[:, 1]
            auc = roc_auc_score(yv, prob)
            scores.append(auc)
        except Exception:
            scores.append(0.5)
    return np.mean(scores)


def train_tabnet(X_train, y_train, X_test, y_test, n_epochs=50, config_name="baseline"):
    import torch
    from pytorch_tabnet.tab_model import TabNetClassifier

    print(f"\n  Training TabNet (config: {config_name})...")

    params = TABNET_CONFIGS.get(config_name, TABNET_CONFIGS["baseline"]).copy()

    X_train_np = X_train.values.astype(np.float32)
    y_train_np = y_train.astype(np.int64)
    X_test_np = X_test.values.astype(np.float32)
    y_test_np = y_test.astype(np.int64)

    model = TabNetClassifier(
        **params,
        scheduler_fn=torch.optim.lr_scheduler.StepLR,
        verbose=0,
    )

    model.fit(
        X_train_np, y_train_np,
        eval_set=[(X_test_np, y_test_np)],
        eval_name=['test'],
        eval_metric=['auc'],
        max_epochs=n_epochs,
        patience=5,
        batch_size=2048,
        virtual_batch_size=256,
    )

    train_prob = model.predict_proba(X_train_np)[:, 1]
    test_prob = model.predict_proba(X_test_np)[:, 1]

    train_auc = roc_auc_score(y_train_np, train_prob)
    test_auc = roc_auc_score(y_test_np, test_prob)

    print(f"  TabNet ({config_name}) Train AUC: {train_auc:.4f}")
    print(f"  TabNet ({config_name}) Test AUC: {test_auc:.4f}")

    return model, test_prob


def train_ranker(df, n_trials=15):
    print("\n=== Training RL Model (Phase 2: Threshold Search + TabNet + Ensemble) ===\n")

    if len(df) < MIN_TRAIN_SAMPLES:
        raise ValueError(f"Not enough data: {len(df)} samples (need >= {MIN_TRAIN_SAMPLES})")

    df_sorted = df.sort_values("screen_date").reset_index(drop=True)
    split_idx = int(len(df_sorted) * 0.8)
    train_df = df_sorted.iloc[:split_idx]
    test_df = df_sorted.iloc[split_idx:]

    print(f"Train: {len(train_df)} samples, Test: {len(test_df)} samples")
    print(f"Train profit ratio: {train_df['label_profit'].mean():.1%}")
    print(f"Test profit ratio: {test_df['label_profit'].mean():.1%}")

    X_train_full, encoders = prepare_features(train_df, fit=True)
    X_test_full, _ = prepare_features(test_df, encoders=encoders, fit=False)

    y_train_cls = train_df["label_profit"].values
    y_test_cls = test_df["label_profit"].values

    print(f"\n[0/7] Removing multicollinearity (threshold=0.90)...")
    best_threshold = 0.90
    X_train, dropped_features = remove_multicollinearity(X_train_full.copy(), threshold=best_threshold)
    X_test = X_test_full.drop(columns=dropped_features, errors='ignore')
    print(f"  Final features: {X_train.shape[1]}")

    y_train_reg = train_df["label_return"].values
    y_test_reg = test_df["label_return"].values

    scaler = StandardScaler()
    X_train_scaled = pd.DataFrame(
        scaler.fit_transform(X_train), columns=X_train.columns, index=X_train.index
    )
    X_test_scaled = pd.DataFrame(
        scaler.transform(X_test), columns=X_test.columns, index=X_test.index
    )

    print(f"\n[1/7] Optuna tuning ranker ({n_trials} trials, models: HGB/XGB/LGBM)...")
    study_ranker = optuna.create_study(direction="maximize")
    study_ranker.optimize(
        lambda trial: objective_ranker(trial, X_train, y_train_reg),
        n_trials=n_trials,
        show_progress_bar=True,
    )
    best_ranker_params = study_ranker.best_params.copy()
    best_ranker_model_type = best_ranker_params.pop("model")
    print(f"  Best model: {best_ranker_model_type}")
    print(f"  Best Spearman CV: {study_ranker.best_value:.4f}")

    print(f"\n[2/7] Training final ranker ({best_ranker_model_type})...")
    if best_ranker_model_type == "hgb":
        best_ranker_params["max_bins"] = 127
        best_ranker_params["random_state"] = 42
        ranker = HistGradientBoostingRegressor(**best_ranker_params)
    elif best_ranker_model_type == "xgb":
        best_ranker_params["random_state"] = 42
        best_ranker_params["n_jobs"] = -1
        best_ranker_params["verbosity"] = 0
        ranker = XGBRegressor(**best_ranker_params)
    else:
        best_ranker_params["random_state"] = 42
        best_ranker_params["n_jobs"] = -1
        best_ranker_params["verbose"] = -1
        ranker = LGBMRegressor(**best_ranker_params)

    ranker.fit(X_train, y_train_reg)

    y_pred_reg = ranker.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test_reg, y_pred_reg))
    spearman_corr, _ = spearmanr(y_test_reg, y_pred_reg)
    print(f"  Test RMSE: {rmse:.4f}")
    print(f"  Test Spearman: {spearman_corr:.4f}")

    print(f"\n[3/7] Optuna tuning classifier ({n_trials} trials, models: HGB/XGB/LGBM)...")
    study_cls = optuna.create_study(direction="maximize")
    study_cls.optimize(
        lambda trial: objective_classifier(trial, X_train, y_train_cls),
        n_trials=n_trials,
        show_progress_bar=True,
    )
    best_cls_params = study_cls.best_params.copy()
    best_cls_model_type = best_cls_params.pop("model")
    print(f"  Best model: {best_cls_model_type}")
    print(f"  Best AUC CV: {study_cls.best_value:.4f}")

    print(f"\n[4/7] Training final classifier ({best_cls_model_type})...")
    if best_cls_model_type == "hgb":
        best_cls_params["max_bins"] = 127
        best_cls_params["random_state"] = 42
        best_cls_params["class_weight"] = "balanced"
        classifier = HistGradientBoostingClassifier(**best_cls_params)
    elif best_cls_model_type == "xgb":
        best_cls_params["random_state"] = 42
        best_cls_params["n_jobs"] = -1
        best_cls_params["verbosity"] = 0
        best_cls_params["eval_metric"] = "auc"
        pos_count = (y_train_cls == 1).sum()
        neg_count = (y_train_cls == 0).sum()
        best_cls_params["scale_pos_weight"] = neg_count / max(pos_count, 1)
        classifier = XGBClassifier(**best_cls_params)
    else:
        best_cls_params["random_state"] = 42
        best_cls_params["n_jobs"] = -1
        best_cls_params["verbose"] = -1
        best_cls_params["class_weight"] = "balanced"
        classifier = LGBMClassifier(**best_cls_params)

    classifier.fit(X_train, y_train_cls)

    y_prob_cls = classifier.predict_proba(X_test)[:, 1]
    y_pred_cls = classifier.predict(X_test)
    accuracy = accuracy_score(y_test_cls, y_pred_cls)
    try:
        auc = roc_auc_score(y_test_cls, y_prob_cls)
    except ValueError:
        auc = 0.0
    print(f"  Classifier Accuracy: {accuracy:.4f}")
    print(f"  Classifier AUC: {auc:.4f}")

    print(f"\n[5/7] Building ensemble (BestModel + XGB + LGBM + RF + LR)...")
    pos_count = (y_train_cls == 1).sum()
    neg_count = (y_train_cls == 0).sum()

    xgb_ens = XGBClassifier(
        n_estimators=300, learning_rate=0.05, max_depth=4,
        min_child_weight=30, reg_lambda=1.0, subsample=0.8,
        colsample_bytree=0.8, scale_pos_weight=neg_count/max(pos_count,1),
        random_state=42, n_jobs=-1, verbosity=0, eval_metric='auc'
    )
    xgb_ens.fit(X_train, y_train_cls)
    xgb_ens_prob = xgb_ens.predict_proba(X_test)[:, 1]

    lgbm_ens = LGBMClassifier(
        n_estimators=300, learning_rate=0.05, max_depth=4,
        min_child_samples=30, reg_lambda=1.0, subsample=0.8,
        colsample_bytree=0.8, class_weight='balanced',
        random_state=42, n_jobs=-1, verbose=-1
    )
    lgbm_ens.fit(X_train, y_train_cls)
    lgbm_ens_prob = lgbm_ens.predict_proba(X_test)[:, 1]

    rf = RandomForestClassifier(
        n_estimators=300, max_depth=4, min_samples_leaf=10,
        class_weight="balanced", random_state=42, n_jobs=-1,
    )
    rf.fit(X_train, y_train_cls)
    rf_prob = rf.predict_proba(X_test)[:, 1]

    lr = LogisticRegression(
        C=1.0, class_weight="balanced", max_iter=1000, random_state=42,
    )
    lr.fit(X_train_scaled, y_train_cls)
    lr_prob = lr.predict_proba(X_test_scaled)[:, 1]

    gbm_prob = y_prob_cls
    ensemble_prob = (
        0.05 * gbm_prob +
        0.10 * xgb_ens_prob +
        0.10 * lgbm_ens_prob +
        0.60 * rf_prob +
        0.15 * lr_prob
    )
    ensemble_pred = (ensemble_prob >= 0.5).astype(int)
    ensemble_accuracy = accuracy_score(y_test_cls, ensemble_pred)
    try:
        ensemble_auc = roc_auc_score(y_test_cls, ensemble_prob)
    except ValueError:
        ensemble_auc = 0.0
    print(f"  Ensemble Accuracy: {ensemble_accuracy:.4f}")
    print(f"  Ensemble AUC: {ensemble_auc:.4f}")

    print(f"\n[6/7] Training TabNet (3 configs, 50 epochs each)...")
    tabnet_results = {}
    for config_name in TABNET_CONFIGS.keys():
        tabnet_model, tabnet_prob = train_tabnet(
            X_train, y_train_cls, X_test, y_test_cls,
            n_epochs=50, config_name=config_name
        )
        tabnet_auc = roc_auc_score(y_test_cls, tabnet_prob)
        tabnet_results[config_name] = {
            "model": tabnet_model,
            "prob": tabnet_prob,
            "auc": tabnet_auc,
        }

    best_tabnet_config = max(tabnet_results.items(), key=lambda x: x[1]["auc"])
    best_tabnet_name = best_tabnet_config[0]
    best_tabnet_auc = best_tabnet_config[1]["auc"]
    best_tabnet_prob = best_tabnet_config[1]["prob"]
    best_tabnet_model = best_tabnet_config[1]["model"]

    print(f"\n  Best TabNet config: {best_tabnet_name} (AUC: {best_tabnet_auc:.4f})")

    print(f"\n[7/7] Creating ensemble with TabNet...")
    ensemble_with_tabnet_prob = (
        0.05 * gbm_prob +
        0.10 * xgb_ens_prob +
        0.10 * lgbm_ens_prob +
        0.45 * rf_prob +
        0.10 * lr_prob +
        0.20 * best_tabnet_prob
    )
    ensemble_with_tabnet_auc = roc_auc_score(y_test_cls, ensemble_with_tabnet_prob)

    print(f"  Ensemble (without TabNet): {ensemble_auc:.4f}")
    print(f"  Ensemble (with TabNet): {ensemble_with_tabnet_auc:.4f}")

    if ensemble_with_tabnet_auc >= ensemble_auc:
        print(f"  ✓ Using ensemble with TabNet (+{ensemble_with_tabnet_auc - ensemble_auc:.4f})")
        final_ensemble_prob = ensemble_with_tabnet_prob
        final_ensemble_auc = ensemble_with_tabnet_auc
        use_tabnet = True
        ensemble_weights = [0.05, 0.10, 0.10, 0.45, 0.10, 0.20]
    else:
        print(f"  ✓ Using ensemble without TabNet (+{ensemble_auc - ensemble_with_tabnet_auc:.4f})")
        final_ensemble_prob = ensemble_prob
        final_ensemble_auc = ensemble_auc
        use_tabnet = False
        ensemble_weights = [0.05, 0.10, 0.10, 0.60, 0.15]

    final_ensemble_pred = (final_ensemble_prob >= 0.5).astype(int)
    final_ensemble_accuracy = accuracy_score(y_test_cls, final_ensemble_pred)

    if hasattr(classifier, 'feature_importances_') and classifier.feature_importances_.sum() > 0:
        feature_importance = pd.Series(
            classifier.feature_importances_,
            index=X_train.columns,
        ).sort_values(ascending=False)
    else:
        feature_importance = pd.Series(
            rf.feature_importances_,
            index=X_train.columns,
        ).sort_values(ascending=False)
    print("\nTop 10 Feature Importances:")
    for feat, imp in feature_importance.head(10).items():
        print(f"  {feat}: {imp:.4f}")

    with open(RANKER_PATH, "wb") as f:
        pickle.dump(ranker, f)
    with open(CLASSIFIER_PATH, "wb") as f:
        pickle.dump(classifier, f)
    with open(ENCODERS_PATH, "wb") as f:
        pickle.dump(encoders, f)
    with open(ENSEMBLE_PATH, "wb") as f:
        pickle.dump({
            "xgb": xgb_ens, "lgbm": lgbm_ens,
            "rf": rf, "lr": lr, "scaler": scaler,
            "tabnet": best_tabnet_model if use_tabnet else None,
            "weights": ensemble_weights,
            "use_tabnet": use_tabnet,
        }, f)
    with open(SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)
    with open(TABNET_PATH, "wb") as f:
        pickle.dump(best_tabnet_model, f)

    metrics = {
        "timestamp": datetime.now().isoformat(),
        "train_size": len(train_df),
        "test_size": len(test_df),
        "best_threshold": float(best_threshold),
        "ranker_model_type": best_ranker_model_type,
        "classifier_model_type": best_cls_model_type,
        "ranker_rmse": float(rmse),
        "ranker_spearman": float(spearman_corr),
        "classifier_accuracy": float(accuracy),
        "classifier_auc": float(auc),
        "ensemble_auc_without_tabnet": float(ensemble_auc),
        "ensemble_auc_with_tabnet": float(ensemble_with_tabnet_auc),
        "final_ensemble_auc": float(final_ensemble_auc),
        "final_ensemble_accuracy": float(final_ensemble_accuracy),
        "tabnet_results": {k: v["auc"] for k, v in tabnet_results.items()},
        "best_tabnet_config": best_tabnet_name,
        "best_tabnet_auc": float(best_tabnet_auc),
        "use_tabnet": use_tabnet,
        "n_features": X_train.shape[1],
        "dropped_features": dropped_features,
        "ranker_params": {**best_ranker_params, "model_type": best_ranker_model_type},
        "classifier_params": {**best_cls_params, "model_type": best_cls_model_type},
        "feature_importance": feature_importance.to_dict(),
    }
    with open(METRICS_PATH, "wb") as f:
        pickle.dump(metrics, f)

    from rl.model_versioning import (
        should_replace_model, save_version, deploy_to_production, log_deployment
    )

    should_replace, reason = should_replace_model(final_ensemble_auc, improvement_threshold=0.05)

    print(f"\n=== DEPLOYMENT DECISION ===")
    print(f"New AUC: {final_ensemble_auc:.4f}")
    print(f"Decision: {'REPLACE' if should_replace else 'KEEP OLD'}")
    print(f"Reason: {reason}")

    if should_replace:
        version_info = save_version(
            auc=final_ensemble_auc,
            features=X_train.shape[1],
            threshold=best_threshold,
            model_files={
                "ensemble_model.pkl": ENSEMBLE_PATH,
                "ranker_model.pkl": RANKER_PATH,
                "classifier_model.pkl": CLASSIFIER_PATH,
                "feature_scaler.pkl": SCALER_PATH,
                "label_encoders.pkl": ENCODERS_PATH,
                "training_metrics.pkl": METRICS_PATH,
            }
        )
        print(f"Saved as version {version_info['version']}")

        deploy_to_production()
        print("Deployed to production!")

        log_deployment(version_info, "deploy", reason)
    else:
        print("Keeping old production model")
        log_deployment({"version": 0, "auc": final_ensemble_auc}, "skip", reason)

    print(f"\nAll models saved to {MODEL_DIR}")
    print(f"  Best threshold: {best_threshold:.2f}")
    print(f"  Final Ensemble AUC: {final_ensemble_auc:.4f}")
    print(f"  Use TabNet: {use_tabnet}")
    return ranker, classifier, encoders, metrics
