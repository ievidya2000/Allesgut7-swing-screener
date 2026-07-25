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

Sembilan setup saham berbasis rule. Setiap setup memiliki karakteristik utama dan kondisi deteksi.

<div align="center">
  <img src="4-setup-class.png" alt="Setup Classification" width="100%">
</div>

---

### 9 Setup Detektor (Rule-Based)

Setiap bar (candlestick) dievaluasi terhadap 9 setup secara bersamaan. Jika semua kondisi rule terpenuhi → setup aktif dengan skor kepercayaan (0–100).

#### 1. PRE_BREAKOUT

| Kondisi | Threshold |
|---------|-----------|
| Vol contraction | Volume menyusut mendekati resistance |
| Near resistance | Harga mendekati level resistance |
| Volume rising | Volume meningkat |
| SuperTrend | Medium bullish |
| ADX | > 25 (trend kuat) |
| RSI | > 50 (momentum positif) |

Sumber: [Minervini (2013)](https://www.chartmill.com/documentation/trading-and-investing/methodologies/523-SEPA-Explained-Mark-Minervinis-Specific-Entry-Point-Analysis-System), *Trade Like a Stock Market Wizard*

#### 2. VCP (Volatility Contraction Pattern)

| Kondisi | Threshold |
|---------|-----------|
| Vol contract shrinking | Volume menyusut progresif |
| Donchian near min | Harga mendekati Donchian low |
| Higher lows | Low lebih tinggi dari sebelumnya |
| Above MA20 | Harga di atas MA20 |
| ADX | > 20 |
| Momentum ready | Momentum siap breakout |

3–4 progressive contractions (18%→12%→6%). Success rate 65–70% dengan volume confirmation. Sumber: [Minervini Ch. 10](https://traderlion.com/technical-analysis/volatility-contraction-pattern)

#### 3. TIGHT_BASE_BREAKOUT

| Kondisi | Threshold |
|---------|-----------|
| Range | < 5% (sangat rapat) |
| Percentile | 20th (range sempit) |
| Inside bars | ≥ 3 consecutive |
| ADX | < 18 (no trend) |
| Volume | Dry (kering) |
| SuperTrend | Bull |

Tight base dengan consecutive inside bars. Success rate 65–70% dengan volume confirmation.

#### 4. BASE_ON_BASE

| Kondisi | Threshold |
|---------|-----------|
| Stacked tight zones | 2 level konsolidasi bertumpuk |
| Broke first base | Sudah break base pertama |
| Higher base | Base kedua lebih tinggi |
| Volume | Contracting |
| RSI | > 40 |
| MACD | > 0 |

Sumber: [O'Neil (2009)](https://www.investors.com/how-to-invest/investors-corner/panera-bread-is-a-stock-market-leader), CAN SLIM — "one of the first to emerge at a new high"

#### 5. BULL_FLAG

| Kondisi | Threshold |
|---------|-----------|
| Flagpole | > 15% rally |
| Flag | < 12% pullback |
| Duration | 5–15 hari |
| Volume | Declining |
| MA | Above MA20 |
| SuperTrend | Bull |

High-tight bull flag: 85% success rate, +39% avg gain. Standard: 60–70%. Sumber: [Bulkowski](https://www.thepatternsite.com/)

#### 6. BREAKOUT

| Kondisi | Threshold |
|---------|-----------|
| Donchian | Fresh breakout (20-day high) |
| Volume | Expanding |
| SuperTrend | Layered ST bullish |
| ADX | > 25 (trend kuat) |
| MACD | Confirmation (bullish cross) |

Win rate 30–40%, tapi R:R 1:3 to 1:5. Sumber: [Donchian/Turtle Trading (1983)](https://www.quantifiedstrategies.com/turtle-trading-strategy)

#### 7. PULLBACK_MA20

| Kondisi | Threshold |
|---------|-----------|
| Near MA20 | Harga mendekati MA20 |
| MA20 rising | MA20 slope positif |
| MA20 > MA50 | Golden cross zone |
| Bounce | Harga memantul dari MA20 |
| Prior strength | Sebelumnya ada kekuatan |
| Momentum bounce | Momentum memantul |

Healthy retracement to rising 20-MA in established uptrend.

#### 8. ACCUMULATION

| Kondisi | Threshold |
|---------|-----------|
| Tight range | Range sempit |
| ADX | < 22 (no trend) |
| SuperTrend | Bullish |
| Cloud | In cloud (Ichimoku) |
| Accumulation pressure | Tekanan akumulasi |
| Oversold | Kondisi oversold |

Smart-money stealth buying within tight range. Sumber: [Coulling (2014)](https://www.annacoulling.com/a-complete-guide-to-volume-price-analysis-by-anna-coulling/)

#### 9. EARLY_REVERSAL

| Kondisi | Threshold |
|---------|-----------|
| SuperTrend | Fast flip + slow gate |
| Divergence | Bullish divergence |
| Volume | Spike |
| Low | Higher low |

SuperTrend flip / bullish divergence. **Aktif saat BEAR regime** — satu-satunya setup yang aktif di market bear.

---

### Cara Kerja

Setiap bar (candlestick) dievaluasi terhadap 9 setup secara bersamaan. Jika semua kondisi rule terpenuhi → setup aktif dengan skor kepercayaan (0–100).

---

### Candlestick Patterns — 20+ Detektor

Deteksi pola candlestick untuk membaca sentimen pasar jangka pendek. Metodologi dari [Steve Nison (1991)](https://traderlion.com/trading-books/japanese-candlestick-charting-techniques), *Japanese Candlestick Charting Techniques*.

#### Reversal Patterns

| Pattern | Success Rate | Sumber |
|---------|-------------|--------|
| Bullish Engulfing | 73–78% | [Investopedia](https://www.investopedia.com/terms/b/bullishengulfing.asp) |
| Bearish Engulfing | 73–78% | Bearish equivalent |
| Hammer | 65–70% | [Investopedia](https://www.investopedia.com/terms/h/hammer.asp) |
| Shooting Star | 65–70% | Bearish equivalent |
| Morning Star | 70–75% | Multi-candle reversal |
| Evening Star | 70–75% | Bearish equivalent |
| Piercing Line | 60–65% | Single-candle reversal |
| Dark Cloud Cover | 60–65% | Bearish equivalent |
| Bullish Harami | 55–65% | Indecision pattern |
| Bearish Harami | 55–65% | Bearish equivalent |
| Tweezer Top / Bottom | 60–70% | Reversal at extremes |
| Bullish / Bearish Counterattack | 55–60% | Strong reversal |

#### Continuation Patterns

| Pattern | Success Rate | Sumber |
|---------|-------------|--------|
| Three White Soldiers | 80–82% | [ChartMill](https://www.chartmill.com/documentation/technical-analysis/candlestick-patterns/446-three-white-soldiers) |
| Three Black Crows | 75–80% | Bearish equivalent |
| Three Inside Up / Down | 65–70% | Confirmation-based |
| Rising Three Methods | 74–79% | [Bulkowski](https://www.thepatternsite.com/Rising3Methods.html) |
| Falling Three Methods | 74–79% | Bearish equivalent |

#### Gap-Based Patterns

| Pattern | Fill Rate | Sumber |
|---------|-----------|--------|
| Bullish Abandoned Baby | 70–75% | Strong reversal |
| Bearish Abandoned Baby | 70–75% | Bearish equivalent |
| Bullish Kicking | 75–80% | Strongest gap pattern |
| Bearish Kicking | 75–80% | Bearish equivalent |
| On-Neck Pattern | 50–65% | Continuation downtrend |
| In-Neck Pattern | 50–65% | Continuation downtrend |
| Thrusting Pattern | 50–65% | Continuation downtrend |

#### Doji Variations

| Pattern | Reliability | Sumber |
|---------|-------------|--------|
| Doji | ~49% (alone) | [Investopedia](https://www.investopedia.com/ask/answers/112814/how-do-traders-interpret-dragonfly-doji-pattern.asp) |
| Dragonfly Doji | 57–65% at extremes | Bullish reversal — "T" shape |
| Gravestone Doji | Higher at resistance | Bearish reversal — inverted "T" |
| Long-Legged Doji | Context-dependent | Extreme indecision |

#### Single Bar Patterns

| Pattern | Signal |
|---------|--------|
| Bullish Marubozu | Strong bullish (no shadow) |
| Bearish Marubozu | Strong bearish (no shadow) |
| Spinning Top | Indecision |
| Hanging Man | Bearish reversal |
| Inverted Hammer | Bullish reversal |

#### Scoring Patterns

```
Skor Pola = Σ(bullish_conf) − Σ(bearish_conf × 0.7)
```

→ **BIAS: BULLISH / BEARISH / NEUTRAL** — digabungkan dengan indikator, probabilitas, dan model untuk keputusan akhir.

---

### Catatan

- Setup classification fokus pada **struktur harga, volume, dan momentum jangka menengah**
- Candlestick patterns menangkap **sinyal reversal / continuation jangka pendek**
- Skor dan bias digabungkan dengan indikator, probabilitas, dan model untuk keputusan akhir
- Rule-based bersifat konsisten, transparan, dan tidak bergantung pada data historis untuk training

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

### Price & Trend Indicators

| # | Indicator | Parameters | Formula / Concept | Source |
|---|-----------|------------|-------------------|--------|
| 1 | **Ichimoku Cloud** | Tenkan=9, Kijun=26, Senkou=52 | Tenkan-sen = (Highest High + Lowest Low) / 2 over 9 periods; Kijun-sen over 26 periods; Senkou Span A = (Tenkan + Kijun) / 2 plotted 26 periods ahead; Senkou Span B = Highest High / Lowest Low over 52 periods. Cloud top/bottom = support/resistance zones. Price above cloud = bullish. | [Investopedia](https://www.investopedia.com/terms/i/ichimoku-cloud.asp) — Goichi Hosoda, 1930s–1960s |
| 2 | **SuperTrend Multi-Instance** | Fast(7/2.0), Medium(10/3.5), Slow(14/4.0) | 3 instance paralel berbasis ATR. Layered entry: slow = gate, fast = trigger. Upper Band = (High + Low)/2 + (Multiplier × ATR); Lower Band = (High + Low)/2 − (Multiplier × ATR). SuperTrend flips when price closes on opposite side. | [Investopedia](https://www.investopedia.com/supertrend-indicator-7976167) — Based on Wilder's ATR |
| 3 | **Donchian Channel** | Period=20 | Upper Band = Highest High over N periods; Lower Band = Lowest Low over N periods; Middle Band = (Upper + Lower) / 2. Foundation of Richard Donchian's Turtle Trading System (1983). Breakout above upper band = buy signal. | [Investopedia](https://www.investopedia.com/terms/d/donchianchannels.asp) — Richard Donchian |
| 4 | **AVWAP (Anchored VWAP)** | lookback=5 | Anchored di swing low (bullish) atau swing high (bearish). VWAP = Σ(Price × Volume) / Σ(Volume). Forward-filled dari anchor point. | [StockCharts](https://school.stockcharts.com/doku.php?id=technical_indicators:on_balance_volume_obv) |
| 5 | **ADX + DI** | Wilder's smoothing (RMA), length=14 | +DM = High − Previous High; −DM = Previous Low − Low; +DI = 100 × Smoothed(+DM) / ATR; −DI = 100 × Smoothed(−DM) / ATR; ADX = Smoothed(DX). ADX > 25 = strong trend; < 20 = no trend. +DI/−DI spread determines direction. | [StockCharts](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-directional-index-adx) — Wilder (1978) |
| 6 | **RSI** | period=14 | RS = Average Gain / Average Loss; RSI = 100 − (100 / (1 + RS)). RMA-based smoothing (Wilder). Overbought > 70, Oversold < 30. | [Investopedia](https://www.investopedia.com/terms/r/rsi.asp) — Wilder (1978) |
| 7 | **MACD** | EMA 12/26, signal 9 | MACD Line = 12-period EMA − 26-period EMA; Signal Line = 9-period EMA of MACD; Histogram = MACD − Signal. Bullish/bearish cross generates entry signals. | [Investopedia](https://www.investopedia.com/terms/m/macd.asp) — Gerald Appel, 1970s |
| 8 | **Stochastic** | %K fast(14), smoothing(3), %D(3) | %K = (Close − Lowest Low) / (Highest High − Lowest Low) × 100; %D = 3-period SMA of %K. Oversold < 20, Overbought > 80. %D divergence = valid signal. | [Investopedia](https://www.investopedia.com/terms/s/stochasticoscillator.asp) — George Lane, 1950s |

---

### Volatility & Volume Indicators

| # | Indicator | Parameters | Formula / Concept | Source |
|---|-----------|------------|-------------------|--------|
| 1 | **Bollinger Bands** | MA20 ± 2σ, width = 4σ/MA20 | Middle Band = 20-period SMA; Upper/Lower = Middle ± 2 × Standard Deviation. ~95% of price within bands. %b = (Price − Lower) / (Upper − Lower); BandWidth = (Upper − Lower) / Middle. Squeeze = low volatility before breakout. | [BollingerBands.com](https://www.bollingerbands.com/bollinger-bands) — John Bollinger, CFA |
| 2 | **Elliott Wave** | Swing detection lookback=5, wave position modulo 5 | 5 impulse waves (1-2-3-4-5) + 3 corrective waves (A-B-C). Corrective A-B-C classifier. Fibonacci ratios (38.2%, 50%, 61.8%) define wave relationships. | [Investopedia](https://www.investopedia.com/articles/technical/111401.asp) — R.N. Elliott (1938); Frost & Prechter (1978) |
| 3 | **Fibonacci Retracement** | Level: 23.6, 38.2, 50, 61.8, 78.6 | Retracement Level = Pivot High − (Retracement % × Price Range). Key levels dari swing range. 61.8% (golden ratio) dan 38.2% paling banyak diawasi. Extensions: 127.2%, 161.8%. | [Investopedia](https://www.investopedia.com/terms/f/fibonacciretracement.asp) |
| 4 | **OBV (On-Balance Volume)** | — | Cumulative: +Volume on up days, −Volume on down days. Joe Granville (1963). OBV divergence dari price = sinyal perubahan. | [Investopedia](https://www.investopedia.com/terms/o/onbalancevolume.asp) — Granville (1963) |
| 5 | **A/D Line** | — | Accumulation/Distribution: CLV-weighted cumulative volume. CLV = ((Close − Low) − (High − Close)) / (High − Low). Measures institutional buying/selling pressure. | [StockCharts](https://school.stockcharts.com/doku.php?id=technical_indicators:on_balance_volume_obv) |
| 6 | **Volume Delta** | — | Buy Vol = Vol × (Close − Low) / (High − Low); Sell Vol = Vol × (High − Close) / (High − Low). Estimates order flow imbalance between buyers and sellers. | Volume Price Analysis methodology ([Anna Coulling](https://www.annacoulling.com/a-complete-guide-to-volume-price-analysis-by-anna-coulling/)) |
| 7 | **Divergence Detection** | Bandingkan 2 halves dari 20 bar | Bullish: price lower low + indicator higher low. Bearish: price higher high + indicator lower high. Applied to RSI & MACD histogram. | [Investopedia](https://www.investopedia.com/terms/r/rsi.asp) |

---

### Filters & Market Condition

| # | Filter | Threshold / Formula | Purpose | Source |
|---|--------|---------------------|---------|--------|
| 1 | **Volatility Contraction** | ATR(10) / ATR(50) < 0.8 | Mendeteksi VCP setup sebelum breakout. Mengukur penyusutan volatilitas relatif. | [Minervini (2013)](https://www.chartmill.com/documentation/trading-and-investing/methodologies/523-SEPA-Explained-Mark-Minervinis-Specific-Entry-Point-Analysis-System) |
| 2 | **Moving Averages** | MA20, MA50, MA20 slope (diff 5 hari), MA20 > MA50 | Trend direction & strength. MA20 slope positif = uptrend. MA20 > MA50 = golden cross zone. | Standard TA ([Investopedia](https://www.investopedia.com/terms/m/movingaverage.asp)) |
| 3 | **Price Extension Filters** | Price/MA20 ratio, Price/AVWAP ratio, Run-up dari low 50 hari | Overextension warning. Harga terlalu jauh dari rata-rata = potensi pullback. | [Investopedia](https://www.investopedia.com/terms/f/fibonacciretracement.asp) |
| 4 | **Momentum Exhaustion** | RSI > 70 AND Stoch %K > 80 | Overbought conditions. Dua oscillator konfirmasi = momentum melemah. | [Wilder (1978)](https://www.investopedia.com/terms/r/rsi.asp) |
| 5 | **Inside Bars + Consecutive** | High ≤ prev high AND Low ≥ prev low → group by streak | Consolidation detection. Streak ≥ 3 = tight consolidation sebelum breakout. | [Nison (1991)](https://traderlion.com/trading-books/japanese-candlestick-charting-techniques) |
| 6 | **Volume Quality** | Dollar volume, Vol/ATR, Coefficient of Variation (CV) 20d | Liquidity & conviction filter. High CV = volume tidak konsisten = kurang reliable. | [Coulling (2014)](https://www.annacoulling.com/a-complete-guide-to-volume-price-analysis-by-anna-coulling/) |

---

**Catatan**: Semua indikator dihitung secara deterministik berdasarkan data OHLCV. Indikator digunakan sebagai fitur, filter, dan sinyal pendukung pada tahapan analisis dan scoring.

---

## 📊 Statistical & Probabilistic Models

<div align="center">
  <img src="2-Stats-prob-models.png" alt="Statistical & Probabilistic Models" width="100%">
</div>

Model statistik dan probabilistik untuk estimasi peluang, simulasi, dan penilaian komposit. Dikembangkan oleh James Hamilton (1989) — paper seminal *"A New Approach to the Economic Analysis of Nonstationary Time Series"* ([JSTOR](https://www.jstor.org/stable/1912559)).

---

### Markov Regime-Switching (2-Regime)

Model 2 regime (Bull & Bear) dengan transisi probabilistik. Metode: Markov Regression (2 regime), Trend: constant (c), Switching variance: True.

**Transition Matrix P:**

```
S₀ (Regime 0) Bull  ←→  S₁ (Regime 1) Bear
         P₀₀                P₁₁
         P₀₁                P₁₀
```

P(Sₜ = sₜ | Sₜ₋₁ = sₜ₋₁) = [[P₀₀, P₁₀], [P₀₁, P₁₁]]

**Parameter Output:**

| Parameter | Deskripsi |
|-----------|-----------|
| μ₀ | Mean return Regime 0 (Bull) |
| μ₁ | Mean return Regime 1 (Bear) |
| σ₀ | Std dev Regime 0 |
| σ₁ | Std dev Regime 1 |
| P | Matriks transisi 2×2 |

**Fallback**: Normal(μ, σ) jika gagal konvergensi. Deteksi regime memungkinkan sistem mengaktifkan setup hanya pada kondisi pasar yang sesuai (misal: hanya `EARLY_REVERSAL` saat BEAR).

---

### Monte Carlo Simulation

Simulasi **1,000 paths** untuk estimasi probabilitas TP/SL. Metode: Vectorized simulation. Horizon: 20 hari.

**Generasi harga:**

```
Pₜ = P₀ × exp(Σ rᵢ)    untuk i = 1..horizon
```

**Output per ticker:**

| Target | Hit Rate Formula |
|--------|-----------------|
| TP1 | Hit count / 1000 |
| TP2 | Hit count / 1000 |
| TP3 | Hit count / 1000 |
| SL | Hit count / 1000 |

Cache parameter Markov per ticker untuk efisiensi komputasi. Sumber: [Glasserman (2003)](https://link.springer.com/book/10.1007/978-0-387-21617-1), *Monte Carlo Methods in Financial Engineering*.

---

### Composite Scoring

Skor komposit dihitung dengan kombinasi berbobat:

```
Score = w_tp × P(TP) + w_pf × P(TP) / (P(SL) + 0.01) + w_sl × P(SL) + w_days × AvgDays + w_pattern × PatternScore
```

| Komponen | Simbol | Deskripsi |
|----------|--------|-----------|
| P(TP) | Take Profit | Probabilitas target tercapai (TP1/TP2/TP3) |
| P(SL) | Stop Loss | Probabilitas stop loss |
| P(TP)/P(SL) | Profit Factor | Rasio profit terhadap risiko |
| AvgDays | Holding Period | Rata-rata hari mencapai target |
| PatternScore | Candlestick | Skor pola candlestick |

Bobot (w) disesuaikan berdasarkan optimasi. Semua komponen digabungkan dan dinormalisasi.

**Normalization**: Min-Max Scaling ke skala **0–100**.

```
x' = (x − min(x)) / (max(x) − min(x)) × 100
```

---

### Probability Calibration

Kalibrasi probabilitas untuk memastikan prediksi selaras dengan outcome aktual.

#### Brier Score

Mengukur rata-rata kuadrat error probabilitas.

```
BS = (1/N) × Σ(fₜ − oₜ)²
```

dimana fₜ = forecast probability, oₜ = actual outcome (0 atau 1). Score 0 = sempurna, 1 = terburuk. Sumber: [Brier (1950)](https://doi.org/10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2), *Monthly Weather Review*.

#### ECE (Expected Calibration Error)

Rata-rata selisih absolut antara probabilitas prediksi dan frekuensi aktual per bin.

```
ECE = Σ(n_b / N) × |acc(b) − conf(b)|
```

dimana B = jumlah bin, n_b = jumlah sampel di bin b, acc(b) = akurasi di bin b, conf(b) = rata-rata confidence di bin b. Sumber: [Naeini et al. (2015)](https://arxiv.org/abs/2405.15709), AAAI.

#### MCE (Max Calibration Error)

Kesalahan kalibrasi maksimum di antara semua bin.

```
MCE = max_b |acc(b) − conf(b)|
```

Sumber: [Niculescu-Mizil & Caruana (2005)](https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf), ICML.

#### Reliability Diagram

Visualisasi kesesuaian antara probabilitas prediksi dan frekuensi aktual. Plot: avg_pred(b) vs acc(b) untuk setiap bin. Perfect calibration = titik-titik pada diagonal 45°. Points di bawah diagonal = overconfidence; di atas = underconfidence. Sumber: [Scikit-learn](https://scikit-learn.org/stable/auto_examples/calibration/plot_calibration_curve.html).

---

**Catatan**: Model statistik & probabilistik digunakan untuk mengestimasi distribusi hasil trading, menghitung probabilitas target/stop loss, dan menghasilkan skor komposit yang telah dikalibrasi untuk pengambilan keputusan.

---

## 🤖 Machine Learning Pipeline

<div align="center">
  <img src="3-ml-ensemble.png" alt="Machine Learning Ensemble" width="100%">
</div>

Model ensemble untuk memprediksi probabilitas profit dan meranking setup saham. Menggunakan 60+ fitur, training pipeline dengan walk-forward validation, dan auto-retrain mechanism.

---

### 3.1 Ensemble Classifier — Model & Peran

| Model | Bobot | Peran | Import | Sumber |
|-------|-------|-------|--------|--------|
| **HistGradientBoosting** | **5%** | Classifier (profit prob) | `from sklearn.ensemble import HistGradientBoostingClassifier` | [Scikit-learn Docs](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html) — histogram-based, native NaN support |
| **XGBoost** | **10%** | Classifier | `from xgboost import XGBClassifier` | [Chen & Guestrin (2016)](https://arxiv.org/abs/1603.02754), KDD — scalable tree boosting dengan L1/L2 regularization |
| **LightGBM** | **10%** | Classifier | `from lightgbm import LGBMClassifier` | [Ke et al. (2017)](https://papers.nips.cc/paper/6907-lightgbm-a-highly-efficient-gradient-boosting-decision-tree), NeurIPS — GOSS + EFB |
| **RandomForest** | **60%** | Classifier (**model utama**) | Bobot tertinggi — model utama ensemble | [Breiman (2001)](https://link.springer.com/article/10.1023/A:1010933404324) — bagging + feature subsampling |
| **LogisticRegression** | **15%** | Classifier (baseline) | Input via StandardScaler (berbeda preprocessing) | [Cox (1958)](https://doi.org/10.1111/j.2517-6161.1958.tb00292.x) — logit model |
| **TabNet** | **20%** | Classifier (deep learning) | PyTorch-based tabular transformer. 3 konfigurasi preset. Dinonaktifkan jika gagal load. | [Arik & Pfister (2021)](https://arxiv.org/abs/1908.07442), AAAI |

**Prediksi akhir (probabilitas profit)** = Rata-rata berbobot dari seluruh model classifier.

> Jika TabNet tidak tersedia → bobot TabNet didistribusikan ulang secara proporsional ke model lain.

---

### 3.2 Training Pipeline

| Tahap | Deskripsi | Referensi |
|-------|-----------|-----------|
| **1. Data Preparation** | Sumber: Trade Journal (historis). 60+ fitur teknikal, volume, setup, regime, fundamental, dan interaksi fitur. | [Singh & Khushi (2021)](https://arxiv.org/pdf/2103.09106) |
| **2. Multicollinearity Removal** | Hilangkan fitur dengan korelasi tinggi. Threshold optimal via grid search (0.7–0.95). | [Nti et al. (2020)](https://link.springer.com/article/10.1186/s40537-020-00299-5) |
| **3. Model Training & Tuning** | Optuna hyperparameter tuning. TimeSeriesSplit (walk-forward validation). | [Akiba et al. (2019)](https://arxiv.org/abs/1907.10902), KDD |
| **4. Model Evaluation** | Metric: ROC-AUC, PR-AUC, Log Loss, Brier Score. Pilih parameter terbaik berdasarkan performa validasi. | [Lopez de Prado (2018)](https://www.oreilly.com/library/view/advances-in-financial/9781119482086/c07.xhtml) |
| **5. Auto-Retrain & Deploy** | Jika data baru ≥ threshold → bandingkan model baru vs produksi → deploy jika performa lebih baik. | [Nti et al. (2020)](https://link.springer.com/article/10.1186/s40537-020-00299-5) |

---

### 3.3 Fitur Utama (60+ Features)

| Kategori | Contoh Fitur | Source |
|----------|-------------|--------|
| **Teknikal & Momentum** | ADX, RSI, Stochastic, MACD, MA, SuperTrend, Donchian, Bollinger, Ichimoku, ATR, dll. | [Investopedia](https://www.investopedia.com/terms/r/rsi.asp) |
| **Volume & Likuiditas** | OBV, A/D Line, Volume Delta, Dollar Volume, Vol/ATR, Volume CV, Volume Selling Ratio, dll. | [Granville (1963)](https://www.investopedia.com/terms/o/onbalancevolume.asp) |
| **Setup & Pattern** | 9 setup detector (rule-based), 20+ candlestick pattern, pattern score, inside bar streak, dll. | [Nison (1991)](https://traderlion.com/trading-books/japanese-candlestick-charting-techniques) |
| **Regime & Probabilitas** | Markov regime (encoded), Prob TP/SL, Monte Carlo hit rate, days to target, dll. | [Hamilton (1989)](https://www.jstor.org/stable/1912559) |
| **Fundamental** | PE, PB, ROE, Market Cap, EPS Growth, Debt to Equity, dll. | [Fama & French (2015)](https://doi.org/10.1016/j.jfineco.2014.10.010) |
| **Interaksi Fitur** | di_spread_x_score, cloud_x_supertrend, price_to_avwap_x_volume, dll. | Feature interaction engineering |

---

### 3.4 Alur Training Ensemble

```
Trade Journal     Ekstraksi Fitur     Multicollinearity     TimeSeriesSplit     Train Ensemble     Evaluasi Model     Deploy Model
(Historis)         (60+ features)      Removal               (Walk-Forward       + Optuna Tuning    (Validasi)         (Produksi)
                                       (correlation filter)   Validation)              │                    │
                                                                                        │                    │
                                                                                        └──── Auto-Retrain ──┘
                                                                                       (jika data baru ≥ threshold)
```

Flowchart mengikuti urutan visual pada gambar: **Trade Journal → Ekstraksi Fitur (60+) → Multicollinearity Removal (correlation filter) → TimeSeriesSplit (Walk-Forward Validation) → Train Ensemble + Optuna Tuning → Evaluasi Model (Validasi) → Deploy Model (Produksi)**. Auto-Retrain loop: jika data baru ≥ threshold, pipeline berjalan ulang.

---

### 3.5 Ranker Model (Regressor)

Model regresi menghasilkan raw score untuk meranking setup terbaik.

| Model | Output |
|-------|--------|
| **HGB / XGB / LGBM Regressor** | `raw score → max(0, min(100, score × 5 + 50))` |

**Formula**: Raw score dari model regresi dikonversi ke skala 0–100: `score × 5 + 50`, dibatasi antara 0 dan 100. Setup dengan skor tertinggi di-ranking sebagai kandidat terbaik.

---

**Catatan**:
- Label klasifikasi: **1** = TP tercapai dalam N hari, **0** = tidak
- Label regresi: return aktual (%) hingga exit
- Semua model dievaluasi secara walk-forward untuk menghindari look-ahead bias
- Ensemble meningkatkan robustness dan mengurangi risiko overfitting satu model
- Bobot dapat disesuaikan berdasarkan performa rolling terbaru

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
