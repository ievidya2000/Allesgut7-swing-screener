<div align="center">

# ⚡ Swing Screener v2

**AI-Powered Technical Screening for IDX Equities (600+ Stocks)**

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://swing-screener.streamlit.app)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-4CAF50?style=for-the-badge)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-4CAF50?style=for-the-badge)]()
[![Code style](https://img.shields.io/badge/Code%20Style-PEP8-0052CC?style=for-the-badge)]()

---

Automated technical screening for 600+ Indonesia Stock Exchange (IDX) equities. Detects **9 chart setups**, runs **Monte Carlo simulations**, and ranks candidates with an **ensemble reinforcement learning model**.

[Features](#-features) • [Quick Start](#-quick-start) • [Setup Types](#-setup-types) • [Architecture](#-architecture) • [CLI](#-cli-commands) • [Configuration](#-configuration) • [Performance](#-performance-metrics) • [Deployment](#-deployment) • [Guide](guide.md)

</div>

---

## 🎯 Features

| Feature | Description |
|---------|-------------|
| **9 Setup Types** | PRE_BREAKOUT, VCP, TIGHT_BASE_BREAKOUT, BASE_ON_BASE, BULL_FLAG, BREAKOUT, PULLBACK_MA20, ACCUMULATION, EARLY_REVERSAL |
| **Monte Carlo Simulation** | 1,000+ Markov regime-switching simulations per ticker for TP/SL probability estimation |
| **Reinforcement Learning** | Ensemble ranking model (XGBoost + LightGBM + TabNet) trained on 60+ features |
| **Trade Assistant** | Entry zone, stop loss, take profit levels, and timing signals per setup |
| **Auto Paper Trading** | Google Sheets integration with bracket orders, gap detection, and Telegram alerts |
| **Deep Analysis** | Multi-timeframe charts, volume profile, trendlines, and risk scenarios |
| **Performance Tracking** | Walk-forward backtest, Monte Carlo calibration, and portfolio simulation vs IHSG |
| **Adaptive Learning** | Rolling-window parameter optimization that adapts to changing market conditions |
| **Email Notifications** | Automated alerts when new setups are detected |

---

## 🚀 Quick Start

### Streamlit Cloud (Recommended)

1. Fork the repository
2. Open [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo — set main file to `streamlit_app.py`
4. Add secrets in Settings → Secrets (see [Deployment](#-deployment))
5. Deploy

### Local Installation

```bash
git clone https://github.com/Allesgut7/swing-screener.git
cd swing-screener/screener_v2
pip install -r requirements.txt
streamlit run streamlit_app.py
```

### CLI Mode

```bash
# Full screening (all 600+ tickers)
python -m main

# Single ticker deep analysis
python -m main --analyze BBCA.JK
```

---

## 📊 Dashboard Preview

| Tab | Purpose |
|-----|---------|
| **Dashboard** | Overview metrics, setup distribution charts, filterable results table |
| **Results** | Deep-dive with per-setup rankings, detail panels, CSV export |
| **Deep Analysis** | Interactive Plotly candlestick charts with indicator overlays, volume profile, trendlines |
| **Performance** | Backtest results, calibration checks, portfolio simulation vs IHSG |
| **Auto Trade** | Bracket-order preview, force-execute controls, live status dashboard |

---

## 🎯 Setup Types

| Setup | Signal | Description |
|-------|--------|-------------|
| `PRE_BREAKOUT` | BUY | Volatility contraction near resistance with rising volume |
| `VCP` | BUY | Volatility Contraction Pattern — progressively tighter bases (Minervini) |
| `TIGHT_BASE_BREAKOUT` | STRONG BUY | Tight base with consecutive inside bars, ready to expand |
| `BASE_ON_BASE` | BUY | Two stacked consolidation levels, each higher than the last |
| `BULL_FLAG` | BUY | Flagpole rally followed by descending consolidation |
| `BREAKOUT` | STRONG BUY | Fresh Donchian breakout with volume confirmation |
| `PULLBACK_MA20` | BUY | Healthy retracement to rising 20-MA in an uptrend |
| `ACCUMULATION` | BUY | Smart-money accumulation — stealth buying within tight range |
| `EARLY_REVERSAL` | BUY | Early trend-reversal signals (SuperTrend flip / bullish divergence) |

**Note**: During BEAR market regime, only `EARLY_REVERSAL` setups are active.

<div align="center">
  <img src="4-setup-class.png" alt="Setup Classification" width="100%">
</div>

---

## 🏗️ Architecture

```
screener_v2/
├── streamlit_app.py          # Main Streamlit dashboard (5 tabs)
├── config.py                 # Configuration & ticker list (600+ IDX stocks)
├── config_email.py           # Email config (secrets.toml / env vars)
├── data.py                   # Data download & caching (yfinance, incremental cache)
├── indicators.py             # Technical indicators (Ichimoku, SuperTrend, Donchian, ADX)
├── signals.py                # Setup detection & signal classification
├── analysis.py               # Entry zone, TP/SL, key levels, timing
├── patterns.py               # Candlestick pattern detection
├── risk.py                   # Risk management & Monte Carlo simulation
├── deep_analysis.py          # Multi-TF, volume profile, trendlines, risk scenarios
├── notifications.py          # Email notification system
├── main.py                   # CLI entry point
├── requirements.txt          # Python dependencies
│
├── paper_trading/            # Auto Paper Trading module
│   ├── auto_trader.py        # Filter results, create bracket orders
│   ├── gsheets_client.py     # Google Sheets API client
│   ├── config.py             # Paper trading config (MAX_LOTS, GAP_TOLERANCE, etc.)
│   ├── Code.gs               # Google Apps Script (gap detection, proximity alert)
│   ├── run_auto.py           # CLI entry point for auto-trading
│   └── service_account.json  # Google Cloud service account key
│
├── performance/              # Performance measurement module
│   ├── journal.py            # SQLite/PostgreSQL journal (predictions + trades)
│   ├── metrics.py            # Sharpe, Sortino, win rate, profit factor
│   ├── backtest.py           # Walk-forward historical backtesting
│   ├── calibration.py        # Monte Carlo probability calibration
│   ├── portfolio.py          # Portfolio simulation vs IHSG benchmark
│   ├── realtime.py           # Real-time trade monitoring
│   └── daily_summary.py      # Daily performance summary
│
├── rl/                       # Reinforcement Learning module
│   ├── ranker.py             # RL scoring/ranking (inference)
│   ├── auto_retrain.py       # Auto-retrain pipeline
│   ├── train_ranker.py       # Training script (Optuna + ensemble)
│   ├── extract_features.py   # Feature extraction (60+ features)
│   ├── generate_augmented.py # Data augmentation for training
│   ├── run_pipeline.py       # Full RL pipeline runner
│   ├── production_predictor.py # Production prediction wrapper
│   ├── model_versioning.py   # Model versioning & rollback
│   ├── tabnet_config.py      # TabNet hyperparameter configs
│   └── models/               # Trained models (.pkl)
│       ├── ensemble_model.pkl
│       ├── ranker_model.pkl
│       ├── classifier_model.pkl
│       ├── tabnet_model.pkl
│       ├── feature_scaler.pkl
│       ├── label_encoders.pkl
│       └── model_version.json
│
├── adaptive/                 # Adaptive Learning module
│   ├── config.py             # Adaptive config management
│   ├── optimizer.py          # Parameter optimization (grid search)
│   └── models/               # Saved adaptive configs (.json)
│
├── utils/                    # Utilities
│   ├── date_utils.py         # Date normalization helpers
│   └── price_utils.py        # IDX tick size rounding
│
└── tests/                    # Unit tests
    └── test_core.py
```

### Data Pipeline

```
Yahoo Finance API → 600+ IDX tickers → 50+ technical indicators → Setup detection
→ Entry zone / SL / TP calculation → Monte Carlo simulation (1000x) → RL ranking → Output
```

---

## 📈 Technical Indicators

<div align="center">
  <img src="1-tech-indicator.png" alt="Technical Indicators" width="100%">
</div>

Indikator teknikal deterministik untuk analisis harga, volume, momentum, volatilitas, dan struktur pasar. Semua indikator dihitung dari data OHLCV dan digunakan sebagai fitur, filter, serta sinyal pendukung.

---

## 📊 Statistical & Probabilistic Models

<div align="center">
  <img src="2-Stats-prob-models.png" alt="Statistical & Probabilistic Models" width="100%">
</div>

Model statistik dan probabilistik untuk estimasi peluang, simulasi, dan penilaian komposit. Meliputi Markov regime-switching, Monte Carlo simulation, composite scoring, dan probability calibration.

---

## 🤖 Machine Learning Pipeline

<div align="center">
  <img src="3-ml-ensemble.png" alt="Machine Learning Ensemble" width="100%">
</div>

Model ensemble untuk memprediksi probabilitas profit dan meranking setup saham. Menggunakan 60+ fitur, training pipeline dengan walk-forward validation, dan auto-retrain mechanism.

---

## ⚙️ Configuration

### Risk Management

| Parameter | Default | Description |
|-----------|---------|-------------|
| `INITIAL_CAPITAL` | Rp 100,000,000 | Starting capital |
| `POSITION_SIZE` | Rp 10,000,000 | Per-entry position size |
| `MAX_POSITIONS` | 12 | Maximum concurrent positions |
| `RISK_PER_TRADE_PCT` | 2% | Maximum risk per trade |
| `SL_MULTIPLIER` | 1.5 × ATR | Stop loss distance |
| `RR1 / RR2 / RR3` | 1.5 / 2.5 / 3.0 | Risk-reward ratios for TP1/TP2/TP3 |
| `TP1_PCT / TP2_PCT / TP3_PCT` | 60% / 25% / 15% | Partial exit allocation at each TP |

### Indicator Parameters

| Indicator | Parameters | Description |
|-----------|------------|-------------|
| Ichimoku | Tenkan=9, Kijun=26, Senkou B=52 | Trend direction & support/resistance |
| SuperTrend | ATR(10) × 3.5 | Trend-following filter |
| Donchian | Period=20 | Breakout channel |
| ADX | Period=14, Threshold=25 | Trend strength |
| Volume MA | Period=20 | Volume baseline |

### Monte Carlo

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MC_N_SIM` | 1,000 | Number of simulations |
| `MC_HORIZON` | 20 | Forward-test horizon (days) |

### Auto Paper Trading

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAX_LOTS_PER_TICKER` | 100 | Maximum lots per order |
| `GAP_TOLERANCE_PCT` | 2.0% | Max price gap for execution (Code.gs sync) |
| `MAX_AUTO_ORDERS_PER_DAY` | 7 | Max new orders per day |
| `MAX_FORCE_ORDERS` | 13 | Extra force-execute orders (max total: 20) |
| `PENDING_ORDER_MAX_DAYS` | 2 | Pending order expiry (days) |
| `BUY_FEE / SELL_FEE` | 0.15% / 0.25% | IDX trading fees |

### Cache

| Parameter | Default | Description |
|-----------|---------|-------------|
| `CACHE_MAX_AGE_HOURS` | 2 | Cache validity before incremental refresh |

---

## 🔧 CLI Commands

### Screening

```bash
# Full screening (all tickers)
python -m main

# Single ticker analysis
python -m main --analyze BBCA.JK

# Auto-trade (paper)
python -m main --auto-trade

# Auto-trade (dry-run)
python -m main --auto-trade --dry-run
```

### Performance Tools

```bash
# Walk-forward backtest
python -m performance.run backtest
python -m performance.run backtest --start-date 2024-01-01 --end-date 2025-12-31

# Portfolio simulation vs IHSG
python -m performance.run portfolio --capital 100000000

# Monte Carlo calibration check
python -m performance.run calibration

# Prediction journal
python -m performance.run journal --summary
python -m performance.run journal --status PENDING

# Trade results
python -m performance.run trades --exit-reason TP1

# Full performance report
python -m performance.run report
```

### Adaptive Learning

```bash
# Parameter optimization
python -m performance.run optimize --max-combos 50

# Rolling-window optimization
python -m performance.run rolling-optimize
python -m performance.run rolling-optimize --history
```

### Reinforcement Learning

```bash
# Full RL training pipeline
python -m rl.run_pipeline

# Auto-retrain (skips if insufficient new data)
python -m rl.auto_retrain

# Force retrain
python -m rl.auto_retrain --force

# Check retrain status
python -m rl.auto_retrain --status
```

---

## 🚀 Deployment

### Streamlit Cloud

1. **Repository**: Push to GitHub (private recommended)
2. **Main file**: `streamlit_app.py`
3. **Secrets**: Add via Streamlit Cloud dashboard (Settings → Secrets):

```toml
[smtp]
server = "smtp.gmail.com"
port = 587
username = "your-email@gmail.com"
password = "your-app-password"
from_email = "your-email@gmail.com"
to_email = "recipient@example.com"

[database]
url = "postgresql://user:password@host:5432/dbname"
```

4. **Deploy**: Click Deploy

### Environment Variables (Alternative)

```bash
export SMTP_USERNAME="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
export FROM_EMAIL="your-email@gmail.com"
export TO_EMAIL="recipient@example.com"
```

### Database

- **Default**: SQLite (`performance_journal.db`) — auto-created, zero setup
- **Production**: PostgreSQL (Supabase free tier) — set `DATABASE_URL` in secrets

### Google Sheets

1. Create a Google Cloud Service Account at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable Google Sheets API and Google Drive API
3. Download JSON key → save as `paper_trading/service_account.json`
4. Create a new Google Sheet → share with the service account email (Editor access)
5. Copy `paper_trading/Code.gs` into the Apps Script editor (Extensions → Apps Script)
6. Run `setupSheets()` to create the sheet structure
7. Set Bot Token and Chat ID in the Settings sheet (cells B7, B8)

### Telegram

1. Open Telegram → search for @BotFather
2. Send `/newbot` and follow the instructions
3. Save the Bot Token
4. Send a message to your bot (e.g., `/start`)
5. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser
6. Locate `"chat":{"id": XXXXXXX}` — that is your Chat ID
7. Enter the Token (B7) and Chat ID (B8) in the Settings sheet
8. Run `testTelegram()` in Apps Script to verify

---

## 📊 Performance Metrics

| Metric | Good | Excellent | Description |
|--------|------|-----------|-------------|
| Win Rate | > 50% | > 60% | Percentage of profitable trades |
| Profit Factor | > 1.5 | > 2.0 | Gross profit / Gross loss |
| Sharpe Ratio | > 1.0 | > 2.0 | Risk-adjusted return |
| Sortino Ratio | > 1.5 | > 2.5 | Downside risk-adjusted return |
| Max Drawdown | < 20% | < 10% | Largest peak-to-trough decline |
| Calmar Ratio | > 1.0 | > 2.0 | Return / Max drawdown |
| Brier Score | < 0.2 | < 0.1 | Probability calibration accuracy |
| ECE | < 0.1 | < 0.05 | Expected calibration error |

---

## 📝 Database Schema

### `predictions`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `ticker` | TEXT | Stock ticker (e.g., BBCA.JK) |
| `setup` | TEXT | Setup type |
| `signal` | TEXT | BUY / STRONG BUY |
| `price_at_signal` | REAL | Price when signal generated |
| `stop_loss` | REAL | Stop loss level |
| `tp1 / tp2 / tp3` | REAL | Take profit targets |
| `entry_zone_low / high` | REAL | Entry zone range |
| `timing` | TEXT | ENTRY_READY / WAIT_* / HOLD |
| `score` | REAL | Composite score |
| `rl_score` | REAL | RL ranking score |
| `prob_tp1 / tp2 / tp3` | TEXT | Monte Carlo probabilities |
| `market_regime` | TEXT | BULL / SIDEWAYS / BEAR |
| `screen_date` | TIMESTAMP | Signal generation time |
| `status` | TEXT | PENDING / ACTIVE / CLOSED |

### `trade_results`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `prediction_id` | INTEGER | FK → predictions |
| `ticker` | TEXT | Stock ticker |
| `entry_date` | TIMESTAMP | Trade entry date |
| `entry_price` | REAL | Entry price |
| `exit_date` | TIMESTAMP | Trade exit date |
| `exit_price` | REAL | Exit price |
| `exit_reason` | TEXT | TP1 / TP2 / TP3 / SL / TIMEOUT |
| `return_pct` | REAL | Return percentage |
| `return_abs` | REAL | Return in Rupiah |
| `days_held` | INTEGER | Days in trade |
| `hit_tp1 / tp2 / tp3 / sl` | INTEGER | Binary flags (0/1) |

---

## 🔍 Troubleshooting

| Error | Solution |
|-------|----------|
| `ModuleNotFoundError` | Run from the `screener_v2/` directory; ensure `__init__.py` exists |
| `yfinance download failed` | Check internet connection; data is cached for 2h in `cache_yfinance/` |
| SQLite database is locked | Close other processes using the database |
| Email not sending | Verify SMTP credentials in `secrets.toml` or environment variables |
| No setups found | Expected in BEAR market — only `EARLY_REVERSAL` setups are considered |
| `gspread not installed` | Run `pip install gspread google-auth` |
| `service_account.json not found` | Place the file in the `paper_trading/` directory |
| Telegram `Unauthorized` error | Regenerate the bot token from @BotFather |
| Today Orders shows wrong count | Orders are counted by BUY rows only; CANCELLED rows are excluded |
| Orders auto-cancelled | Gap detection: price exceeds entry + 2% (runs 09:00–09:15 WIB) |
| Proximity alert spam | Alerts are sent once per order, reset when price moves away from target |

---

## 📦 Dependencies

```
numpy>=1.21              # Numerical computation
pandas>=1.3              # Data manipulation
matplotlib>=3.5          # Chart generation
plotly>=5.0              # Interactive charts (Streamlit)
streamlit>=1.20          # Web dashboard
yfinance>=0.2.0          # Yahoo Finance data
statsmodels>=0.13        # Markov regime-switching model
scikit-learn>=1.2        # ML models
scipy>=1.9               # Statistical functions
xgboost>=1.7             # XGBoost (RL ensemble)
lightgbm>=3.3            # LightGBM (RL ensemble)
pytorch-tabnet>=4.0      # TabNet (RL ensemble)
optuna>=3.0              # Hyperparameter tuning
psycopg2-binary>=2.9     # PostgreSQL driver (optional)
beautifulsoup4>=4.10     # Web scraping utilities
requests>=2.28           # HTTP client
psutil>=5.9              # System resource monitoring
gspread>=5.0             # Google Sheets API
google-auth>=2.0         # Google authentication
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with** [Streamlit](https://streamlit.io), [yfinance](https://github.com/ranaroussi/yfinance), and [Python](https://python.org)

[⬆ Back to top](#-swing-screener-v2)

</div>
