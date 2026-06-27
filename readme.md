# Swing Screener v2 — Documentation

## Overview

Sistem screening saham IDX (Indonesia Stock Exchange) berbasis technical analysis dengan 4 setup types: PRE_BREAKOUT, BREAKOUT, ACCUMULATION, EARLY_REVERSAL. Dilengkapi dengan performance measurement system untuk mengukur akurasi prediksi.

## Architecture

```
screener_v2/
├── indicators.py      # Pure functions: Ichimoku, SuperTrend, Donchian, ADX, ATR, etc.
├── signals.py         # Pure functions: setup detection & signal classification
├── analysis.py        # Pure functions: entry zones, TP/SL, key levels, timing
├── patterns.py        # Pure functions: candlestick pattern detection
├── risk.py            # Pure functions: TP/SL calculation, Monte Carlo simulation
├── deep_analysis.py   # Multi-TF, volume profile, trendlines, risk scenarios
├── data.py            # Data download, caching, normalization (yfinance)
├── config.py          # All configuration constants
├── output.py          # Console output formatting
├── main.py            # Main screener (live mode) + CLI entry point
├── streamlit_app.py   # Streamlit web dashboard
│
├── performance/       # Performance measurement module
│   ├── __init__.py    # Module exports
│   ├── journal.py     # SQLite database layer (predictions + trade results)
│   ├── metrics.py     # Shared metric calculations (Sharpe, Sortino, etc.)
│   ├── backtest.py    # Walk-forward historical backtesting
│   ├── calibration.py # Monte Carlo probability calibration
│   ├── portfolio.py   # Portfolio simulation + benchmark vs IHSG
│   ├── realtime.py    # Real-time monitoring (auto-check trades)
│   └── run.py         # CLI entry point for performance tools
│
└── adaptive/          # Adaptive Learning Module (Phase 1 + 2)
    ├── __init__.py    # Module exports
    ├── config.py      # Adaptive config management + parameter history
    ├── optimizer.py   # Parameter optimization + rolling window optimization
    └── models/        # Saved models and configs
        ├── adaptive_config.json      # Best parameters found
        ├── optimization_results.json # All optimization results
        └── parameter_history.json    # Rolling optimization history
```

## Setup

### 1. Install Dependencies

```bash
pip install yfinance pandas numpy matplotlib plotly seaborn statsmodels psycopg2-binary
```

### 2. Database (SQLite - Default)

SQLite is used by default. The database file `performance_journal.db` is created automatically on first run. No setup required.

### 3. PostgreSQL (Optional)

If you prefer PostgreSQL:

```bash
# Install PostgreSQL driver (already done above)
pip install psycopg2-binary

# Create database and user (requires sudo access)
sudo -u postgres psql
CREATE USER swing_user WITH PASSWORD 'swing_pass';
CREATE DATABASE swing_screener OWNER swing_user;
GRANT ALL PRIVILEGES ON DATABASE swing_screener TO swing_user;
\q
```

Then update `config.py` to use PostgreSQL:

```python
# In config.py, add:
DB_BACKEND = "postgresql"  # or "sqlite" (default)
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "swing_screener"
DB_USER = "swing_user"
DB_PASSWORD = "swing_pass"
```

## Screener Commands

### Run Full Screener (Interactive)

```bash
# From project root
python -m screener_v2.main

# Or with explicit path
cd /home/chalderaaa/swing-screener
python -m screener_v2.main
```

This will:
1. Determine market regime (IHSG)
2. Scan all tickers for setups
3. Calculate Monte Carlo probabilities
4. Display detailed analysis boxes
5. Save results to `hasil_screener_v2.csv`
6. Log predictions to performance journal
7. Check open trades and update status

### Analyze Single Ticker

```bash
python -m screener_v2.main --analyze BBCA.JK
```

### Run Streamlit Dashboard

```bash
streamlit run streamlit_app.py
```

#### Streamlit Tabs

| Tab | Description |
|-----|-------------|
| 📊 Dashboard | Overview metrics + setup distribution chart |
| 📋 Results | Filterable results table + detail analysis |
| 🔬 Deep Analysis | Per-ticker analysis (chart, patterns, multi-TF, etc.) |
| 📈 Performance | Backtest, Calibration, Portfolio, Journal |

#### Performance Tab Features

- **Backtest**: Run historical walk-forward backtest (Quick ~30s or Full ~5-10min)
- **Calibration**: Monte Carlo probability calibration + reliability diagram
- **Portfolio**: Portfolio simulation vs IHSG benchmark
- **Journal**: View all predictions and trade results

## Performance Measurement Commands

### Backtest Historical Performance

```bash
# Full backtest (1 year)
python -m screener_v2.performance.run backtest

# Custom date range
python -m screener_v2.performance.run backtest --start-date 2025-01-01 --end-date 2025-12-31
```

### Parameter Optimization (Phase 1 - Adaptive Learning)

Run grid search to find optimal indicator parameters:

```bash
# Quick optimization (50 combinations)
python -m screener_v2.performance.run optimize

# Full optimization (all 1620 combinations)
python -m screener_v2.performance.run optimize --max-combos 1620

# Custom date range
python -m screener_v2.performance.run optimize --start-date 2025-01-01 --end-date 2025-12-31

# Show top 20 results
python -m screener_v2.performance.run optimize --show-top 20
```

**Parameters being optimized:**

| Parameter | Values Tested |
|-----------|--------------|
| `supertrend_multiplier` | 2.0, 2.5, 3.0, 3.5, 4.0 |
| `adx_threshold` | 15, 18, 20, 25 |
| `rr1` | 1.5, 2.0, 2.5 |
| `sl_multiplier` | 1.2, 1.5, 2.0 |
| `donchian_period` | 15, 20, 25 |
| `volume_ma_period` | 15, 20, 25 |

**Output:**
- `screener_v2/adaptive/models/adaptive_config.json` — Best parameters found
- `screener_v2/adaptive/models/optimization_results.json` — All results

**After optimization, parameters are automatically used by:**
- `python -m screener_v2.main` (live screening)
- `python -m screener_v2.performance.run backtest` (backtesting)

### Rolling Parameter Optimization (Phase 2 - Adaptive Learning)

Re-optimizes parameters periodically using rolling windows. Detects when market conditions change and parameters need updating.

```bash
# Default: 6-month window, step 1 month, 50 combos per window
python -m screener_v2.performance.run rolling-optimize

# Custom window size (3 months)
python -m screener_v2.performance.run rolling-optimize --window-months 3

# Custom step size (re-optimize every 2 weeks)
python -m screener_v2.performance.run rolling-optimize --step-months 0.5

# More combos per window (slower but more thorough)
python -m screener_v2.performance.run rolling-optimize --max-combos 100

# View optimization history
python -m screener_v2.performance.run rolling-optimize --history
python -m screener_v2.performance.run rolling-optimize --history --history-count 20
```

**How it works:**
1. Creates rolling windows (e.g., 6-month periods)
2. Runs grid search optimization on each window
3. Analyzes parameter stability across windows
4. Updates `adaptive_config.json` if better parameters found
5. Saves history to `parameter_history.json`

**Parameter Stability Analysis:**
- Higher stability = parameter works well across different market periods
- Lower stability = parameter is sensitive to market conditions
- Most/least stable parameters are highlighted in output

**Output:**
- `screener_v2/adaptive/models/adaptive_config.json` — Updated best parameters
- `screener_v2/adaptive/models/parameter_history.json` — Optimization history with timestamps and metrics

### Monte Carlo Calibration

```bash
# Print calibration report
python -m screener_v2.performance.run calibration

# Save calibration plot
python -m screener_v2.performance.run calibration --plot calibration_plot.png
```

### Portfolio Simulation

```bash
# Default: Rp 100 juta capital
python -m screener_v2.performance.run portfolio

# Custom capital
python -m screener_v2.performance.run portfolio --capital 500000000

# With equity curve plot
python -m screener_v2.performance.run portfolio --plot equity_curve.png

# Custom date range
python -m screener_v2.performance.run portfolio --start-date 2025-06-01 --end-date 2026-06-01
```

### Check Open Trades (Real-Time Mode)

```bash
python -m screener_v2.performance.run check
```

### View Prediction Journal

```bash
# All predictions
python -m screener_v2.performance.run journal

# Summary only
python -m screener_v2.performance.run journal --summary

# Filter by status
python -m screener_v2.performance.run journal --status PENDING
python -m screener_v2.performance.run journal --status ACTIVE

# Filter by ticker
python -m screener_v2.performance.run journal --ticker BBCA.JK
```

### View Trade Results

```bash
# All trades
python -m screener_v2.performance.run trades

# Filter by exit reason
python -m screener_v2.performance.run trades --exit-reason TP1
python -m screener_v2.performance.run trades --exit-reason SL

# Filter by ticker
python -m screener_v2.performance.run trades --ticker BBCA.JK
```

### Full Performance Report

```bash
python -m screener_v2.performance.run report
```

## Configuration

### Position Sizing (config.py)

```python
# Performance / Position Sizing
INITIAL_CAPITAL = 100_000_000     # Rp 100 juta
RISK_PER_TRADE_PCT = 2.0          # 2% risk per trade
POSITION_SIZE = 10_000_000        # Rp 10 juta per entry
MAX_POSITIONS = 12                # Max concurrent positions
BENCHMARK_TICKER = "^JKSE"
```

### Risk Management

| Parameter | Value | Description |
|-----------|-------|-------------|
| `SL_MULTIPLIER` | 1.5 | Stop loss = entry - 1.5 × ATR |
| `RR1` | 1.5 | TP1 = entry + 1.5 × risk |
| `RR2` | 2.5 | TP2 = entry + 2.5 × risk |
| `RR3` | 4.0 | TP3 = entry + 4.0 × risk |
| `MC_N_SIM` | 1000 | Monte Carlo simulations |
| `MC_HORIZON` | 20 | Forward test horizon (days) |

### Indicator Parameters

| Indicator | Parameters |
|-----------|-----------|
| Ichimoku | Tenkan=9, Kijun=26, Senkou B=52 |
| Donchian | Period=20 |
| SuperTrend | ATR(10) × 3.0 |
| ADX | Period=14, Threshold=18 |
| Volume MA | Period=20 |

## Output Files

| File | Description |
|------|-------------|
| `hasil_screener_v2.csv` | Latest screener results |
| `performance_journal.db` | SQLite database (predictions + trades) |
| `calibration_plot.png` | MC probability calibration chart |
| `equity_curve.png` | Portfolio equity curve chart |
| `screener_v2/adaptive/models/adaptive_config.json` | Optimized indicator parameters |
| `screener_v2/adaptive/models/optimization_results.json` | Grid search results |
| `screener_v2/adaptive/models/parameter_history.json` | Rolling optimization history |

## Performance Metrics Explained

### Win Rate
Percentage of trades that are profitable.

### Profit Factor
Gross profits / Gross losses. > 1.0 is profitable.

### Sharpe Ratio
Risk-adjusted return. > 1.0 is good, > 2.0 is excellent.

### Sortino Ratio
Like Sharpe but only penalizes downside volatility. > 1.5 is good.

### Max Drawdown
Largest peak-to-trough decline. Lower is better.

### Calmar Ratio
Annualized return / Max drawdown. > 2.0 is excellent.

### Brier Score
Calibration accuracy of probability predictions. < 0.1 is excellent.

### Expected Calibration Error (ECE)
Average gap between predicted and actual probabilities. Lower is better.

## Workflow

### Daily Workflow

1. **Run Screener** — Generates signals + logs to journal
   ```bash
   python -m screener_v2.main
   ```

2. **Check Previous Trades** — Auto-updates on next run
   ```bash
   python -m screener_v2.performance.run check
   ```

3. **View Journal** — See pending/active/closed trades
   ```bash
   python -m screener_v2.performance.run journal --summary
   ```

### Weekly/Monthly Workflow

1. **Full Performance Report**
   ```bash
   python -m screener_v2.performance.run report
   ```

2. **Calibration Check** — Are MC probabilities accurate?
   ```bash
   python -m screener_v2.performance.run calibration --plot
   ```

3. **Portfolio Simulation** — Track portfolio vs IHSG
   ```bash
   python -m screener_v2.performance.run portfolio --plot
   ```

### Periodic Workflow

1. **Full Backtest** — Re-run historical validation
   ```bash
   python -m screener_v2.performance.run backtest
   ```

2. **Rolling Optimization** — Re-optimize parameters monthly
   ```bash
   # Run monthly to adapt to market changes
   python -m screener_v2.performance.run rolling-optimize

   # Check optimization history
   python -m screener_v2.performance.run rolling-optimize --history
   ```

## Database Schema

### predictions Table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| ticker | TEXT | Stock ticker |
| setup | TEXT | Setup type (PRE_BREAKOUT, etc.) |
| signal | TEXT | Signal type (BUY, STRONG BUY) |
| price_at_signal | REAL | Price when signal was generated |
| stop_loss | REAL | Stop loss price |
| tp1, tp2, tp3 | REAL | Take profit targets |
| entry_zone_low/high | REAL | Entry zone range |
| timing | TEXT | Timing status (ENTRY_READY, etc.) |
| score | REAL | Composite score |
| prob_tp1, prob_tp2, prob_tp3 | TEXT | MC probabilities |
| market_regime | TEXT | Market regime (BULL, BEAR, SIDEWAYS) |
| screen_date | TIMESTAMP | When signal was generated |
| status | TEXT | PENDING, ACTIVE, CLOSED |

### trade_results Table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| prediction_id | INTEGER | Reference to predictions |
| ticker | TEXT | Stock ticker |
| entry_date | TIMESTAMP | Trade entry date |
| entry_price | REAL | Entry price |
| exit_date | TIMESTAMP | Trade exit date |
| exit_price | REAL | Exit price |
| exit_reason | TEXT | TP1, TP2, TP3, SL, TIMEOUT |
| return_pct | REAL | Return percentage |
| return_abs | REAL | Return in Rupiah |
| days_held | INTEGER | Days trade was held |
| hit_tp1/tp2/tp3/sl | INTEGER | Binary flags (0/1) |
| max_favorable | REAL | Maximum favorable excursion |
| max_adverse | REAL | Maximum adverse excursion |

## Troubleshooting

### "No module named screener_v2"
Make sure you're in the project root:
```bash
cd /home/chalderaaa/swing-screener
python -m screener_v2.main
```

### "Database not initialized"
Run any performance command to auto-initialize:
```bash
python -m screener_v2.performance.run journal --summary
```

### "yfinance download failed"
Check internet connection. Data is cached for 18 hours in `cache_yfinance/`.

### "No setups found"
Normal in BEAR market regime — only EARLY_REVERSAL setups are considered.

## Dependencies

```
yfinance          # Yahoo Finance data
pandas            # Data manipulation
numpy             # Numerical computation
matplotlib        # Chart generation
plotly            # Interactive charts (Streamlit)
seaborn           # Statistical visualization
statsmodels       # Markov regime-switching model
psycopg2-binary   # PostgreSQL driver (optional)
```
