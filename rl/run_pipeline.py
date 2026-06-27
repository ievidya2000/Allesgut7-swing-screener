#!/usr/bin/env python3
import sys
import subprocess
from datetime import datetime, timedelta

print("=" * 60)
print("  RL TOP-PICK TRAINING PIPELINE")
print("=" * 60)

print("\n[0/4] Clearing old backtest data...")
from screener_v2.performance.journal import clear_backtest_data
clear_backtest_data()

print("\n[1/4] Running backtest (10 years)...")
start = (datetime.now() - timedelta(days=10*365)).strftime("%Y-%m-%d")
end = datetime.now().strftime("%Y-%m-%d")

result = subprocess.run(
    [sys.executable, "-m", "screener_v2.performance.run",
     "backtest", "--start-date", start, "--end-date", end],
    capture_output=False,
)
if result.returncode != 0:
    print(f"  Backtest failed with code {result.returncode}")
    sys.exit(1)

print("\n[2/4] Extracting features...")
from screener_v2.rl.extract_features import extract_training_data
df = extract_training_data()
if df is None or df.empty:
    print("  No training data extracted.")
    sys.exit(1)

print(f"\n[3/4] Training ranker model...")
from screener_v2.rl.train_ranker import train_ranker
ranker, classifier, encoders, metrics = train_ranker(df)

print(f"\n[4/4] Training complete!")
print(f"  Ranker RMSE: {metrics['ranker_rmse']:.4f}")
print(f"  Ranker Spearman: {metrics['ranker_spearman']:.4f}")
print(f"  Classifier Accuracy: {metrics['classifier_accuracy']:.4f}")
print(f"  Classifier AUC: {metrics['classifier_auc']:.4f}")

print("\nPipeline complete. RL Score is now available in the screener.")
