<div align="center">

# ⚡ Swing Screener v2

**Professional IDX Stock Screening Tool with AI-Powered Ranking**

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://swing-screener.streamlit.app)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-4CAF50?style=for-the-badge)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-4CAF50?style=for-the-badge)]()

---

Screening saham IDX berbasis technical analysis dengan **9 setup types**, Monte Carlo simulation, dan reinforcement learning ranking.

[Features](#-features) • [Quick Start](#-quick-start) • [Setup Types](#-setup-types) • [Architecture](#-architecture) • [CLI Commands](#-cli-commands) • [Deployment](#-deployment)

</div>

---

## 🎯 Features

| Feature | Description |
|---------|-------------|
| **9 Setup Types** | PRE_BREAKOUT, VCP, TIGHT_BASE_BREAKOUT, BASE_ON_BASE, BULL_FLAG, BREAKOUT, PULLBACK_MA20, ACCUMULATION, EARLY_REVERSAL |
| **Monte Carlo Simulation** | Probability distribution untuk TP/SL targets dengan 1000+ simulasi |
| **Reinforcement Learning** | AI-powered ranking menggunakan ensemble model (XGBoost + LightGBM + TabNet) |
| **Trade Assistant** | Entry zone, stop loss, take profit, timing signal untuk setiap setup |
| **Deep Analysis** | Multi-timeframe, volume profile, trendlines, risk scenarios |
| **Performance Tracking** | Walk-forward backtest, calibration check, portfolio simulation vs IHSG |
| **Adaptive Learning** | Parameter optimization dengan rolling window untuk adaptasi ke market |
| **Email Notifications** | Alert via email ketika setup baru terdeteksi |

---

## 🚀 Quick Start

### Option 1: Streamlit Cloud (Recommended)

1. Fork repo ini
2. Buka [share.streamlit.io](https://share.streamlit.io)
3. Connect repo → Set main file: `streamlit_app.py`
4. Add secrets di Settings → Secrets (lihat [Deployment](#-deployment))
5. Deploy!

### Option 2: Local Installation

```bash
# Clone repo
git clone https://github.com/Allesgut7/swing-screener.git
cd swing-screener/screener_v2

# Install dependencies
pip install -r requirements.txt

# Run dashboard
streamlit run streamlit_app.py
```

### Option 3: CLI Mode

```bash
# Full screening
python -m screener_v2.main

# Single ticker analysis
python -m screener_v2.main --analyze BBCA.JK
```

---

## 📊 Dashboard Preview

| Dashboard | Trade Assistant | Performance |
|-----------|-----------------|-------------|
| Overview metrics & setup distribution | Entry/SL/TP/Timing signals | Backtest & portfolio simulation |

---

## 🎯 Setup Types

| Setup | Signal | Description |
|-------|--------|-------------|
| `PRE_BREAKOUT` | BUY | Volatility contraction, near resistance, volume rising |
| `VCP` | BUY | Volatility Contraction Pattern — tight bases within bases |
| `TIGHT_BASE_BREAKOUT` | STRONG BUY | Tight base dengan inside bars, ready to break out |
| `BASE_ON_BASE` | BUY | Multiple consolidation levels, breakout-ready |
| `BULL_FLAG` | BUY | Flag pattern — flagpole + descending consolidation |
| `BREAKOUT` | STRONG BUY | Fresh Donchian breakout dengan volume confirmation |
| `PULLBACK_MA20` | BUY | Healthy pullback ke 20-MA support dalam uptrend |
| `ACCUMULATION` | BUY | Smart money accumulation — stealth buying pattern |
| `EARLY_REVERSAL` | BUY | Early signs of trend reversal dari downtrend |

---

## 🏗️ Architecture

```
screener_v2/
├── streamlit_app.py          # Main Streamlit dashboard (4 tabs)
├── config.py                 # Configuration & ticker list (600+ IDX stocks)
├── config_email.py           # Email config (secrets.toml / env vars)
├── data.py                   # Data download & caching (yfinance)
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
│   ├── train_ranker.py       # Training script
│   ├── extract_features.py   # Feature extraction
│   └── models/               # Trained models (.pkl)
│       ├── ensemble_model.pkl
│       ├── ranker_model.pkl
│       ├── classifier_model.pkl
│       └── tabnet_model.pkl
│
├── adaptive/                 # Adaptive Learning module
│   ├── config.py             # Adaptive config management
│   ├── optimizer.py          # Parameter optimization (grid search)
│   └── models/               # Saved adaptive configs (.json)
│
├── utils/                    # Utilities
│   └── date_utils.py         # Date normalization helpers
│
└── tests/                    # Unit tests
    └── test_core.py
```

---

## ⚙️ Configuration

### Risk Management

| Parameter | Default | Description |
|-----------|---------|-------------|
| `INITIAL_CAPITAL` | Rp 100M | Starting capital |
| `POSITION_SIZE` | Rp 10M | Per-entry position size |
| `MAX_POSITIONS` | 12 | Maximum concurrent positions |
| `RISK_PER_TRADE_PCT` | 2% | Maximum risk per trade |
| `SL_MULTIPLIER` | 1.2x ATR | Stop loss distance |
| `RR1 / RR2 / RR3` | 1.5 / 2.5 / 3.0 | Risk-reward ratios for TP1/TP2/TP3 |

### Indicator Parameters

| Indicator | Parameters | Description |
|-----------|-----------|-------------|
| Ichimoku | Tenkan=9, Kijun=26, Senkou B=52 | Trend & support/resistance |
| SuperTrend | ATR(10) × 3.5 | Trend direction |
| Donchian | Period=20 | Breakout channels |
| ADX | Period=14, Threshold=25 | Trend strength |
| Volume MA | Period=20 | Volume analysis |

### Monte Carlo

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MC_N_SIM` | 1000 | Number of simulations |
| `MC_HORIZON` | 20 | Forward test horizon (days) |

---

## 🔧 CLI Commands

### Screening

```bash
# Full screening (all tickers)
python -m screener_v2.main

# Single ticker analysis
python -m screener_v2.main --analyze BBCA.JK
```

### Performance Tools

```bash
# Backtest
python -m screener_v2.performance.run backtest
python -m screener_v2.performance.run backtest --start-date 2024-01-01 --end-date 2025-12-31

# Portfolio simulation
python -m screener_v2.performance.run portfolio --capital 100000000

# Calibration check
python -m screener_v2.performance.run calibration

# View journal
python -m screener_v2.performance.run journal --summary
python -m screener_v2.performance.run journal --status PENDING

# View trade results
python -m screener_v2.performance.run trades --exit-reason TP1

# Full performance report
python -m screener_v2.performance.run report
```

### Adaptive Learning

```bash
# Parameter optimization
python -m screener_v2.performance.run optimize --max-combos 50

# Rolling optimization
python -m screener_v2.performance.run rolling-optimize
python -m screener_v2.performance.run rolling-optimize --history
```

---

## 🚀 Deployment

### Streamlit Cloud

1. **Repository**: Push ke GitHub (private recommended)
2. **Main file**: `streamlit_app.py`
3. **Secrets**: Tambahkan di Streamlit Cloud dashboard (Settings → Secrets):

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

4. **Deploy**: Klik Deploy

### Environment Variables (Alternative)

```bash
export SMTP_USERNAME="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
export FROM_EMAIL="your-email@gmail.com"
export TO_EMAIL="recipient@example.com"
```

### Database

- **Default**: SQLite (`performance_journal.db`) — auto-created, no setup needed
- **Production**: PostgreSQL (Supabase free tier) — set `DATABASE_URL` in secrets

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

### predictions

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

### trade_results

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
| `ModuleNotFoundError: No module named 'screener_v2'` | Run from repo root, not inside `screener_v2/` |
| `yfinance download failed` | Check internet connection; data cached 18h in `cache_yfinance/` |
| `SQLite database is locked` | Close other instances using the database |
| Email not sending | Check SMTP credentials in `secrets.toml` or env vars |
| No setups found | Normal in BEAR market — only EARLY_REVERSAL considered |

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
scikit-learn>=1.2        # ML models (pickle deserialization)
psycopg2-binary>=2.9     # PostgreSQL driver (optional)
scipy>=1.9               # Statistical functions
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with** ❤️ **using Streamlit, yfinance, and Python**

[⬆ Back to top](#-swing-screener-v2)

</div>
