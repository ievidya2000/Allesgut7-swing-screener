#!/usr/bin/env python3
"""RL Top-Pick Training Pipeline.

Full pipeline: backtest -> extract features -> train ranker + classifier.
"""
import sys
import argparse
import subprocess
from datetime import datetime, timedelta


def run_pipeline():
    print("=" * 60)
    print("  RL TOP-PICK TRAINING PIPELINE")
    print("=" * 60)

    print("\n[0/4] Clearing old backtest data...")
    from performance.journal import clear_backtest_data
    clear_backtest_data()

    print("\n[1/4] Running backtest (10 years)...")
    start = (datetime.now() - timedelta(days=10*365)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")

    result = subprocess.run(
        [sys.executable, "-m", "performance.run",
         "backtest", "--start-date", start, "--end-date", end],
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"  Backtest failed with code {result.returncode}")
        sys.exit(1)

    print("\n[2/4] Extracting features...")
    from rl.extract_features import extract_training_data
    df = extract_training_data()
    if df is None or df.empty:
        print("  No training data extracted.")
        sys.exit(1)

    print(f"\n[3/4] Training ranker model...")
    from rl.train_ranker import train_ranker
    ranker, classifier, encoders, metrics = train_ranker(df)

    print(f"\n[4/4] Training complete!")
    print(f"  Ranker RMSE: {metrics['ranker_rmse']:.4f}")
    print(f"  Ranker Spearman: {metrics['ranker_spearman']:.4f}")
    print(f"  Classifier Accuracy: {metrics['classifier_accuracy']:.4f}")
    print(f"  Classifier AUC: {metrics['classifier_auc']:.4f}")

    print("\nPipeline complete. RL Score is now available in the screener.")


def cli_main():
    parser = argparse.ArgumentParser(
        prog="python -m rl.run_pipeline",
        description="RL Top-Pick Training Pipeline - Full backtest + model training",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
pipeline steps:
  0/4  Clear old backtest data
  1/4  Run 10-year walk-forward backtest
  2/4  Extract features from trade journal
  3/4  Train ranker + classifier models
  4/4  Save trained models

examples:
  python -m rl.run_pipeline              Run full pipeline
  python -m rl.run_pipeline --help       Show this help
        """
    )
    parser.parse_args()
    run_pipeline()


if __name__ == "__main__":
    cli_main()
