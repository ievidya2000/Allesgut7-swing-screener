"""Model versioning and deployment system with logging."""

import pickle
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime

LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "model_deployment.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("model_versioning")

MODEL_DIR = Path(__file__).parent / "models"
VERSIONS_DIR = MODEL_DIR / "versions"
VERSIONS_DIR.mkdir(exist_ok=True)

PRODUCTION_DIR = MODEL_DIR / "production"
PRODUCTION_DIR.mkdir(exist_ok=True)

VERSION_FILE = MODEL_DIR / "model_version.json"
DEPLOYMENT_LOG = MODEL_DIR / "deployment_log.json"

MODEL_FILES = [
    "ensemble_model.pkl",
    "ranker_model.pkl",
    "classifier_model.pkl",
    "feature_scaler.pkl",
    "label_encoders.pkl",
    "training_metrics.pkl",
]


def get_current_version():
    if VERSION_FILE.exists():
        with open(VERSION_FILE, 'r') as f:
            return json.load(f)
    return {"version": 0, "auc": 0.0, "timestamp": None, "path": None}


def get_deployment_log():
    if DEPLOYMENT_LOG.exists():
        with open(DEPLOYMENT_LOG, 'r') as f:
            return json.load(f)
    return []


def log_deployment(version_info, action, reason):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "version": version_info.get("version"),
        "auc": version_info.get("auc"),
        "reason": reason,
    }

    log = get_deployment_log()
    log.append(log_entry)

    with open(DEPLOYMENT_LOG, 'w') as f:
        json.dump(log, f, indent=2)

    logger.info(f"Deployment {action}: v{version_info.get('version')} (AUC={version_info.get('auc'):.4f}) - {reason}")


def save_version(auc, features, threshold, model_files):
    current = get_current_version()
    new_version = current["version"] + 1

    version_dir = VERSIONS_DIR / f"v{new_version}"
    version_dir.mkdir(exist_ok=True)

    for file_name, file_path in model_files.items():
        dest = version_dir / file_name
        if file_path.exists():
            shutil.copy2(file_path, dest)

    version_info = {
        "version": new_version,
        "auc": auc,
        "features": features,
        "threshold": threshold,
        "timestamp": datetime.now().isoformat(),
        "path": str(version_dir),
    }

    with open(VERSION_FILE, 'w') as f:
        json.dump(version_info, f, indent=2)

    logger.info(f"Saved version {new_version} with AUC={auc:.4f}")

    return version_info


def should_replace_model(new_auc, improvement_threshold=0.05):
    current = get_current_version()
    old_auc = current["auc"]

    if old_auc == 0:
        return True, "No previous model exists"

    required_auc = old_auc * (1 + improvement_threshold)

    if new_auc >= required_auc:
        return True, f"New AUC {new_auc:.4f} >= {required_auc:.4f} ({improvement_threshold*100}% improvement)"
    else:
        return False, f"New AUC {new_auc:.4f} < {required_auc:.4f} (need {improvement_threshold*100}% improvement)"


def deploy_to_production():
    for file_name in MODEL_FILES:
        src = MODEL_DIR / file_name
        dst = PRODUCTION_DIR / file_name
        if src.exists():
            shutil.copy2(src, dst)

    logger.info(f"Deployed to production: {PRODUCTION_DIR}")


def rollback_to_version(version_number):
    version_dir = VERSIONS_DIR / f"v{version_number}"

    if not version_dir.exists():
        logger.error(f"Version {version_number} not found")
        return False

    for file_name in MODEL_FILES:
        src = version_dir / file_name
        dst = PRODUCTION_DIR / file_name
        if src.exists():
            shutil.copy2(src, dst)

    version_file = version_dir / "training_metrics.pkl"
    if version_file.exists():
        with open(version_file, 'rb') as f:
            metrics = pickle.load(f)

        version_info = {
            "version": version_number,
            "auc": metrics.get("final_ensemble_auc", 0.0),
            "timestamp": datetime.now().isoformat(),
            "path": str(version_dir),
            "rollback": True,
        }

        with open(VERSION_FILE, 'w') as f:
            json.dump(version_info, f, indent=2)

    logger.info(f"Rolled back to version {version_number}")
    return True


def load_production_model():
    ensemble_path = PRODUCTION_DIR / "ensemble_model.pkl"

    if not ensemble_path.exists():
        ensemble_path = MODEL_DIR / "ensemble_model.pkl"

    if ensemble_path.exists():
        with open(ensemble_path, 'rb') as f:
            return pickle.load(f)
    return None


def list_versions():
    versions = []
    for version_dir in sorted(VERSIONS_DIR.iterdir()):
        if version_dir.is_dir() and version_dir.name.startswith("v"):
            version_num = int(version_dir.name[1:])
            metrics_file = version_dir / "training_metrics.pkl"
            if metrics_file.exists():
                with open(metrics_file, 'rb') as f:
                    metrics = pickle.load(f)
                versions.append({
                    "version": version_num,
                    "auc": metrics.get("final_ensemble_auc", 0.0),
                    "path": str(version_dir),
                })
    return versions
