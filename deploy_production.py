"""Deploy current model to production with logging."""

import sys
import pickle
from pathlib import Path

from screener_v2.rl.model_versioning import (
    get_current_version, deploy_to_production, save_version,
    log_deployment, list_versions, rollback_to_version, get_deployment_log
)

MODEL_DIR = Path(__file__).parent / "rl" / "models"


def main():
    print("=== PRODUCTION DEPLOYMENT ===")

    current = get_current_version()
    print(f"Current version: {current['version']}")
    print(f"Current AUC: {current['auc']:.4f}")

    metrics_path = MODEL_DIR / "training_metrics.pkl"
    if metrics_path.exists():
        with open(metrics_path, 'rb') as f:
            metrics = pickle.load(f)

        new_auc = metrics.get('final_ensemble_auc', 0.0)
        print(f"New AUC: {new_auc:.4f}")

        deploy_to_production()

        version_info = save_version(
            auc=new_auc,
            features=metrics.get('n_features', 0),
            threshold=metrics.get('best_threshold', 0.9),
            model_files={
                "ensemble_model.pkl": MODEL_DIR / "ensemble_model.pkl",
                "ranker_model.pkl": MODEL_DIR / "ranker_model.pkl",
                "classifier_model.pkl": MODEL_DIR / "classifier_model.pkl",
                "feature_scaler.pkl": MODEL_DIR / "feature_scaler.pkl",
                "label_encoders.pkl": MODEL_DIR / "label_encoders.pkl",
                "training_metrics.pkl": MODEL_DIR / "training_metrics.pkl",
            }
        )

        log_deployment(version_info, "deploy", "Manual deployment")

        print(f"\nDeployed as version {version_info['version']}")
        print(f"AUC: {version_info['auc']:.4f}")
        print(f"Path: {version_info['path']}")
    else:
        print("No training metrics found")


def rollback():
    versions = list_versions()
    if len(versions) < 2:
        print("No previous version to rollback to")
        return

    prev_version = versions[-2]['version']
    print(f"Rolling back to version {prev_version}...")

    if rollback_to_version(prev_version):
        print(f"Rollback successful to version {prev_version}")
    else:
        print("Rollback failed")


def show_versions():
    versions = list_versions()
    if not versions:
        print("No versions found")
        return

    print("\n=== VERSION HISTORY ===")
    for v in versions:
        print(f"  v{v['version']}: AUC={v['auc']:.4f}")


def show_log():
    log = get_deployment_log()
    if not log:
        print("No deployment log found")
        return

    print("\n=== DEPLOYMENT LOG ===")
    for entry in log[-10:]:
        print(f"  {entry['timestamp']} | {entry['action']} | v{entry.get('version')} | AUC={entry.get('auc', 0):.4f} | {entry.get('reason', '')}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "rollback":
            rollback()
        elif cmd == "versions":
            show_versions()
        elif cmd == "log":
            show_log()
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python deploy_production.py [rollback|versions|log]")
    else:
        main()
