"""Production inference module with automatic model selection."""

import pickle
import logging
import numpy as np
import pandas as pd
from pathlib import Path

logger = logging.getLogger("production_predictor")

PRODUCTION_DIR = Path(__file__).parent / "models" / "production"
MODEL_DIR = Path(__file__).parent / "models"


class ProductionPredictor:
    def __init__(self):
        self.ensemble = None
        self.scaler = None
        self.ranker = None
        self.classifier = None
        self.encoders = None
        self.dropped_features = []
        self.model_features = None
        self._load_models()

    def _load_models(self):
        for dir_path in [PRODUCTION_DIR, MODEL_DIR]:
            ensemble_path = dir_path / "ensemble_model.pkl"
            if ensemble_path.exists():
                with open(ensemble_path, 'rb') as f:
                    data = pickle.load(f)
                self.ensemble = data
                self.scaler = data.get('scaler')
                logger.info(f"Loaded ensemble from {dir_path}")
                break

        for dir_path in [PRODUCTION_DIR, MODEL_DIR]:
            ranker_path = dir_path / "ranker_model.pkl"
            if ranker_path.exists():
                with open(ranker_path, 'rb') as f:
                    self.ranker = pickle.load(f)
                break

        for dir_path in [PRODUCTION_DIR, MODEL_DIR]:
            classifier_path = dir_path / "classifier_model.pkl"
            if classifier_path.exists():
                with open(classifier_path, 'rb') as f:
                    self.classifier = pickle.load(f)
                break

        for dir_path in [PRODUCTION_DIR, MODEL_DIR]:
            encoders_path = dir_path / "label_encoders.pkl"
            if encoders_path.exists():
                with open(encoders_path, 'rb') as f:
                    self.encoders = pickle.load(f)
                break

        for dir_path in [PRODUCTION_DIR, MODEL_DIR]:
            metrics_path = dir_path / "training_metrics.pkl"
            if metrics_path.exists():
                with open(metrics_path, 'rb') as f:
                    metrics = pickle.load(f)
                self.dropped_features = metrics.get("dropped_features", [])
                break

        if self.ranker and hasattr(self.ranker, "feature_names_in_"):
            self.model_features = list(self.ranker.feature_names_in_)

    def predict(self, features):
        if self.ensemble is None:
            logger.error("No production model loaded")
            return None, None

        try:
            feature_cols = self.model_features if self.model_features else list(features.keys())
            row = [float(features.get(col, 0) or 0) for col in feature_cols]

            X_df = pd.DataFrame([row], columns=feature_cols)
            X_df = X_df.replace([np.inf, -np.inf], 0).fillna(0)

            if self.dropped_features:
                X_df = X_df.drop(columns=[c for c in self.dropped_features if c in X_df.columns], errors='ignore')

            rl_score = float(self.ranker.predict(X_df)[0])

            gbm_prob = float(self.classifier.predict_proba(X_df)[0][1])

            xgb = self.ensemble.get("xgb")
            lgbm = self.ensemble.get("lgbm")
            rf = self.ensemble.get("rf")
            lr = self.ensemble.get("lr")
            weights = self.ensemble.get("weights", [0.05, 0.10, 0.10, 0.60, 0.15])

            xgb_prob = float(xgb.predict_proba(X_df)[0][1]) if xgb else 0
            lgbm_prob = float(lgbm.predict_proba(X_df)[0][1]) if lgbm else 0
            rf_prob = float(rf.predict_proba(X_df)[0][1]) if rf else 0

            X_lr = pd.DataFrame(self.scaler.transform(X_df), columns=X_df.columns)
            lr_prob = float(lr.predict_proba(X_lr)[0][1]) if lr else 0

            profit_prob = (
                weights[0] * gbm_prob +
                weights[1] * xgb_prob +
                weights[2] * lgbm_prob +
                weights[3] * rf_prob +
                weights[4] * lr_prob
            )

            rl_score_normalized = max(0, min(100, rl_score * 5 + 50))

            return rl_score_normalized, profit_prob

        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return None, None


_predictor = None


def get_predictor():
    global _predictor
    if _predictor is None:
        _predictor = ProductionPredictor()
    return _predictor


def predict_production(features):
    predictor = get_predictor()
    return predictor.predict(features)
