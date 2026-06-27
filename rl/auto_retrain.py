import json
import shutil
from pathlib import Path
from datetime import datetime

from screener_v2.performance.journal import _get_conn, init_db
from screener_v2.rl.extract_features import extract_training_data
from screener_v2.rl.train_ranker import train_ranker

MODEL_DIR = Path(__file__).parent / "models"
MODEL_BACKUP_DIR = MODEL_DIR / "backup"
METRICS_HISTORY_PATH = MODEL_DIR / "metrics_history.json"
RETRAIN_LOG_PATH = MODEL_DIR / "retrain_log.json"

MODEL_FILES = ["ranker_model.pkl", "classifier_model.pkl", "label_encoders.pkl"]


def backup_models():
    MODEL_BACKUP_DIR.mkdir(exist_ok=True)
    for name in MODEL_FILES:
        src = MODEL_DIR / name
        dst = MODEL_BACKUP_DIR / name
        if src.exists():
            shutil.copy2(src, dst)


def restore_models():
    for name in MODEL_FILES:
        src = MODEL_BACKUP_DIR / name
        dst = MODEL_DIR / name
        if src.exists():
            shutil.copy2(src, dst)
    cleanup_backup()


def cleanup_backup():
    if MODEL_BACKUP_DIR.exists():
        shutil.rmtree(MODEL_BACKUP_DIR)


def load_metrics_history():
    if METRICS_HISTORY_PATH.exists():
        try:
            with open(METRICS_HISTORY_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_metrics_history(history):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(METRICS_HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)


def append_metrics(metrics):
    history = load_metrics_history()
    history.append(metrics)
    if len(history) > 50:
        history = history[-50:]
    save_metrics_history(history)
    return history


def get_new_trade_count():
    init_db()
    conn = _get_conn()

    row = conn.execute("""
        SELECT COUNT(*) as cnt FROM trade_results
        WHERE status = 'CLOSED'
    """).fetchone()
    total_closed = row["cnt"] if row else 0

    row2 = conn.execute("""
        SELECT COUNT(*) as cnt FROM trade_results
        WHERE status = 'CLOSED'
    """).fetchone()

    return total_closed


def get_last_retrain_info():
    if RETRAIN_LOG_PATH.exists():
        try:
            with open(RETRAIN_LOG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_retrain_trades": 0, "last_retrain_time": None}


def save_retrain_info(info):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(RETRAIN_LOG_PATH, "w") as f:
        json.dump(info, f, indent=2)


def load_old_metrics():
    if not METRICS_HISTORY_PATH.exists():
        return None
    try:
        with open(METRICS_HISTORY_PATH, "r") as f:
            history = json.load(f)
        if history:
            return history[-1]
    except Exception:
        pass
    return None


def should_retrain(min_new_trades=50):
    last_info = get_last_retrain_info()
    last_count = last_info.get("last_retrain_trades", 0)

    current_count = get_new_trade_count()
    new_since_retrain = current_count - last_count

    return new_since_retrain >= min_new_trades, new_since_retrain, current_count


def compare_metrics(old_metrics, new_metrics):
    if old_metrics is None:
        return True, "First training run"

    old_auc = old_metrics.get("classifier_auc", 0)
    new_auc = new_metrics.get("classifier_auc", 0)

    old_acc = old_metrics.get("classifier_accuracy", 0)
    new_acc = new_metrics.get("classifier_accuracy", 0)

    old_spearman = old_metrics.get("ranker_spearman", 0)
    new_spearman = new_metrics.get("ranker_spearman", 0)

    auc_change = new_auc - old_auc
    acc_change = new_acc - old_acc
    spearman_change = new_spearman - old_spearman

    should_deploy = auc_change > -0.02

    reasons = []
    if auc_change > 0.01:
        reasons.append(f"AUC improved: {old_auc:.3f} → {new_auc:.3f}")
    elif auc_change < -0.01:
        reasons.append(f"AUC declined: {old_auc:.3f} → {new_auc:.3f}")

    if acc_change > 0.01:
        reasons.append(f"Accuracy improved: {old_acc:.3f} → {new_acc:.3f}")

    if spearman_change > 0.05:
        reasons.append(f"Ranking improved: {old_spearman:.3f} → {new_spearman:.3f}")

    if not reasons:
        reasons.append(f"Metrics stable (AUC {old_auc:.3f} → {new_auc:.3f})")

    return should_deploy, "; ".join(reasons)


def auto_retrain(min_new_trades=50, force=False):
    result = {
        "retrained": False,
        "deployed": False,
        "reason": "",
        "metrics": None,
    }

    should, new_count, total = should_retrain(min_new_trades)

    if not should and not force:
        result["reason"] = f"Only {new_count} new trades since last retrain (need {min_new_trades})"
        return result

    print(f"\n{'='*60}")
    print(f"  AUTO-RETRAIN: {new_count} new trades (total: {total})")
    print(f"{'='*60}\n")

    old_metrics = load_old_metrics()

    print("[1/4] Extracting features...")
    df = extract_training_data()
    if df is None or df.empty:
        result["reason"] = "No training data available"
        return result

    print(f"\n[2/4] Training new model...")
    backup_models()
    ranker, classifier, encoders, new_metrics = train_ranker(df)

    print(f"\n[3/4] Comparing with old model...")
    should_deploy, reason = compare_metrics(old_metrics, new_metrics)

    new_metrics["total_trades"] = total
    new_metrics["new_trades"] = new_count
    new_metrics["comparison"] = reason
    append_metrics(new_metrics)

    if should_deploy:
        print(f"\n[4/4] Deploying new model ✓")
        cleanup_backup()
        result["deployed"] = True
        result["reason"] = reason
    else:
        print(f"\n[4/4] Restoring old model (new model not better)")
        restore_models()
        result["reason"] = reason

    result["retrained"] = True
    result["metrics"] = {
        "new_auc": new_metrics.get("classifier_auc", 0),
        "new_accuracy": new_metrics.get("classifier_accuracy", 0),
        "new_spearman": new_metrics.get("ranker_spearman", 0),
    }

    save_retrain_info({
        "last_retrain_trades": total,
        "last_retrain_time": datetime.now().isoformat(),
        "deployed": should_deploy,
        "reason": reason,
    })

    print(f"\nResult: {'DEPLOYED' if should_deploy else 'KEPT OLD'} | {reason}")
    return result


def get_retrain_status():
    last_info = get_last_retrain_info()
    total = get_new_trade_count()
    last_count = last_info.get("last_retrain_trades", 0)
    new_since = total - last_count

    history = load_metrics_history()
    latest_metrics = history[-1] if history else None

    return {
        "total_trades": total,
        "trades_since_retrain": new_since,
        "last_retrain_time": last_info.get("last_retrain_time"),
        "last_deployed": last_info.get("deployed"),
        "last_reason": last_info.get("reason"),
        "latest_metrics": latest_metrics,
        "history_count": len(history),
    }
