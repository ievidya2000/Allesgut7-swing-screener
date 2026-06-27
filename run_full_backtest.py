import time
import sys
import warnings
warnings.filterwarnings('ignore')

start = time.time()
print(f"Backtest started at {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

from screener_v2.performance.backtest import run_historical_backtest
report = run_historical_backtest(start_date='2016-01-01', end_date='2026-06-25')

elapsed = time.time() - start
print(f"\nBacktest completed at {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
print(f"Total time: {elapsed:.1f}s ({elapsed/60:.1f}min, {elapsed/3600:.1f}hr)", flush=True)
