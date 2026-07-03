# 📖 Panduan Lengkap Swing Screener v2

**Panduan penggunaan, pemahaman, dan strategi untuk Swing Screener IDX**

---

## Daftar Isi

1. [Apa Itu Swing Screener?](#apa-itu-swing-screener)
2. [Siapa yang Cocok Menggunakan?](#siapa-yang-cocok-menggunakan)
3. [Cara Kerja Sistem](#cara-kerja-sistem)
4. [Memahami 9 Setup Types](#memahami-9-setup-types)
5. [Menggunakan CLI](#menggunakan-cli)
6. [Menggunakan Dashboard Streamlit](#menggunakan-dashboard-streamlit)
7. [Membaca Hasil Screening](#membaca-hasil-screening)
8. [Monte Carlo & Probabilities](#monte-carlo--probabilities)
9. [RL Score & AI Ranking](#rl-score--ai-ranking)
10. [Risk Management](#risk-management)
11. [Market Regime](#market-regime)
12. [Adaptive Learning](#adaptive-learning)
13. [Performance Tracking](#performance-tracking)
14. [Email Notifications](#email-notifications)
15. [Contoh Workflow Harian](#contoh-workflow-harian)
16. [FAQ & Tips](#faq--tips)
17. [Glossary](#glossary)

---

## Apa Itu Swing Screener?

Swing Screener adalah tool screening saham IDX (Bursa Efek Indonesia) yang dirancang khusus untuk **swing trading** — strategi trading dengan holding period 2-20 hari.

Tool ini melakukan scanning terhadap **600+ saham IDX** setiap hari untuk mendeteksi 9 pola teknikal yang memiliki probabilitas tinggi untuk menghasilkan profit. Setiap setup yang terdeteksi dilengkapi dengan:

- **Entry zone** — harga masuk yang optimal
- **Stop loss** — batas kerugian otomatis
- **Take profit (TP1/TP2/TP3)** — target profit bertingkat
- **Monte Carlo probability** — probabilitas mencapai TP/SL
- **RL Score** — ranking AI berdasarkan ensemble model
- **Timing signal** — apakah saatnya masuk atau tunggu

### Alur Data

```
Yahoo Finance API → 600+ saham IDX → Technical Indicators → Setup Detection
→ TP/SL Calculation → Monte Carlo Simulation → RL Ranking → Output
```

---

## Siapa yang Cocok Menggunakan?

| Trader | Kegunaan |
|--------|----------|
| **Swing Trader** | Screening harian untuk mencari setup entry 2-20 hari |
| **Position Trader** | Filter saham untuk holding period lebih lama |
| **Technical Analyst** | Analisis teknikal otomatis dengan 50+ indikator |
| **Quantitative Trader** | Backtest, calibration, portfolio simulation |
| **Pemula** | Belajar membaca chart dan memahami setup teknikal |

### Tidak Cocok Untuk

- **Day trader** (holding < 1 hari) — screener ini dirancang untuk swing
- **Fundamental-only investor** — fokus utama adalah analisis teknikal
- **Scalper** — timeframe terlalu pendek untuk sistem ini

---

## Cara Kerja Sistem

### Pipeline Screening (3 Tahap)

#### Tahap 1: Market Regime Detection

Sistem pertama-tama menganalisis indeks IHSG (^JKSE) untuk menentukan kondisi market:

```
Data IHSG → Ichimoku Cloud + SuperTrend + ADX → Market Regime
```

| Regime | Kondisi | Dampak ke Screening |
|--------|---------|---------------------|
| **BULL** | IHSG di atas Ichimoku Cloud, SuperTrend bullish, ADX > 25 | Semua 9 setup aktif |
| **SIDEWAYS** | IHSG di sekitar Cloud, SuperTrend netral | Semua setup aktif, skor lebih konservatif |
| **BEAR** | IHSG di bawah Cloud, SuperTrend bearish | Hanya EARLY_REVERSAL yang aktif |

#### Tahap 2: Data Download & Caching

```
yfinance API → Download 1 tahun data OHLCV → Cache ke Parquet (18 jam validity)
```

- Data di-download per batch (lebih cepat)
- Jika batch gagal, fallback ke download satu per satu
- Cache mencegah download berulang dalam hari yang sama

#### Tahap 3: Scanning Setiap Saham

Untuk setiap ticker, sistem melakukan:

```
1. Hitung 50+ technical indicators (Ichimoku, SuperTrend, Donchian, ADX, RSI, MACD, dll)
2. Tentukan stock regime (BULL/SIDEWAYS/BEAR)
3. Deteksi candlestick patterns
4. Classify setup type (9 kemungkinan)
5. Hitung entry zone, SL, TP1/TP2/TP3
6. Jalankan Monte Carlo simulation (1000x)
7. Hitung RL score (jika model tersedia)
8. Assign composite score
```

Output akhir berupa list saham yang memenuhi kriteria, diurutkan berdasarkan score.

---

## Memahami 9 Setup Types

Setiap setup memiliki karakteristik dan kondisi yang berbeda. Berikut penjelasan mendalam:

### 1. PRE_BREAKOUT — BUY

**Konsep**: Saham sedang membangun momentum untuk breakout, tapi belum tembus resistance.

**Kondisi Deteksi**:
- Volatility contraction (ATR menyempit)
- Harga mendekati resistance (Donchian upper)
- Volume mulai naik
- SuperTrend bullish
- ADX > 25 (trend kuat)
- RSI > 50

**Kapan Entry**: Ketika harga masuk ke entry zone (antara Donchian mid dan upper).

**Contoh Skema**:
```
Resistance ─────────── [████████████████] ← Donchian Upper
                        Entry Zone
Donchian Mid ───────── [                ]
                        Harga saat ini →
Support ──────────────────────────────────
```

---

### 2. VCP (Volatility Contraction Pattern) — BUY

**Konsep**: Pola Mark Minervini di mana saham membentuk beberapa base yang semakin sempit (contraction).

**Kondisi Deteksi**:
- Donchian width menyempit secara progresif
- Multiple contractions (minimal 2)
- Pullback semakin dangkal di setiap contraction
- Volume menurun di setiap contraction

**Kapan Entry**: Saat contraction terakhir sudah sangat sempit dan siap breakout.

**Visual**:
```
Contraction 1: [████████████████████]  (lebar)
Contraction 2:    [████████████]       (lebih sempit)
Contraction 3:       [█████]           (paling sempit → entry)
```

---

### 3. TIGHT_BASE_BREAKOUT — STRONG BUY

**Konsep**: Base yang sangat sempit (< 5% range) dengan inside bars beruntun, siap meledak.

**Kondisi Deteksi**:
- Price range < 5% dalam periode tertentu
- Inside bars ≥ 3 berturut-turut
- ADX rendah (market tidak trending)
- Volume kering (di bawah rata-rata)

**Kapan Entry**: Ketika harga mulai keluar dari tight base dengan volume.

**Signal**: STRONG BUY (sinyal paling kuat).

---

### 4. BASE_ON_BASE — BUY

**Konsep**: Saham membentuk dua base/konsolidasi yang bertumpuk, base kedua lebih tinggi.

**Kondisi Deteksi**:
- Dua periode konsolidasi terdeteksi
- Base kedua di atas base pertama
- Volume menurun selama pembentukan base

**Kapan Entry**: Saat harga mulai keluar dari base kedua.

---

### 5. BULL_FLAG — BUY

**Konsep**: Pola flag — kenaikan tajam (flagpole) diikuti konsolidasi menurun (flag).

**Kondisi Deteksi**:
- Flagpole > 15% kenaikan
- Flag < 12% retracement
- Volume menurun selama flag
- Harga mendekati MA20

**Kapan Entry**: Saat harga bounce dari MA20 di dalam flag.

**Visual**:
```
                    /|  ← Flagpole
                   / |
                  /  |  ← Flag (konsolidasi menurun)
                 /   |___________
                /    |           |  ← Entry di sini
               /     |           |
```

---

### 6. BREAKOUT — STRONG BUY

**Konsep**: Fresh breakout dari Donchian channel dengan volume confirmation.

**Kondisi Deteksi**:
- Harga menembus Donchian upper (20-period high)
- Volume expanding (di atas MA20)
- MACD confirmation (histogram positif)

**Kapan Entry**: Segera setelah breakout terkonfirmasi.

**Signal**: STRONG BUY.

---

### 7. PULLBACK_MA20 — BUY

**Konsep**: Saham dalam uptrend mengalami pullback sehat ke MA20.

**Kondisi Deteksi**:
- Harga mendekati MA20 (support dinamis)
- MA20 sedang naik
- MA20 > MA50 (trend bullish)
- RSI/MACD oversold tapi mulai recovery

**Kapan Entry**: Saat harga bounce dari MA20.

---

### 8. ACCUMULATION — BUY

**Konsep**: Smart money sedang akumulasi — harga sideways tapi tekanan beli meningkat.

**Kondisi Deteksi**:
- Tight price range
- ADX rendah (tidak trending)
- Volume pressure positif (OBV/A-D Line/Volume Delta naik)
- RSI oversold atau netral

**Kapan Entry**: Saat harga masih di support dan volume mulai meningkat.

---

### 9. EARLY_REVERSAL — BUY

**Konsep**: Tanda-tanda awal pembalikan trend dari downtrend ke uptrend.

**Kondisi Deteksi**:
- SuperTrend flip dari bearish ke bullish
- ATAU RSI/MACD bullish divergence terdeteksi
- Volume spike
- Higher low terbentuk
- Harga masih di bawah Ichimoku Cloud

**Kapan Entry**: Setelah konfirmasi divergence atau SuperTrend flip.

**Catatan**: Setup ini satu-satunya yang aktif saat market BEAR.

---

## Menggunakan CLI

### Full Screening

```bash
cd screener_v2
python -m main
```

**Output**:
- Scanning 600+ saham (butuh waktu 10-30 menit tergantung koneksi)
- Hasil ditampilkan di console dalam format table
- File CSV dihasilkan: `hasil_screener_v2.csv`

### Single Ticker Analysis

```bash
python -m main --analyze BBCA.JK
```

**Output**:
- Analisis mendalam untuk satu saham
- Termasuk entry zone, SL, TP, timing, Monte Carlo probabilities
- Deep analysis: multi-timeframe, volume profile, trendlines

### Performance Tools

```bash
# Backtest — test strategi di periode historis
python -m performance.run backtest
python -m performance.run backtest --start-date 2024-01-01 --end-date 2025-12-31

# Portfolio simulation — simulasi portfolio vs IHSG
python -m performance.run portfolio --capital 100000000

# Calibration check — cek akurasi probabilitas Monte Carlo
python -m performance.run calibration

# View journal — lihat log prediksi
python -m performance.run journal --summary
python -m performance.run journal --status PENDING

# View trade results — lihat hasil trade
python -m performance.run trades --exit-reason TP1

# Full performance report — laporan lengkap
python -m performance.run report
```

### Adaptive Learning

```bash
# Parameter optimization — cari parameter terbaik
python -m performance.run optimize --max-combos 50

# Rolling optimization — optimasi berdasarkan window bergulir
python -m performance.run rolling-optimize
python -m performance.run rolling-optimize --history
```

### RL Pipeline

```bash
# Full RL training pipeline
python -m rl.run_pipeline

# Auto-retrain jika ada data baru yang cukup
python -m rl.auto_retrain
```

---

## Menggunakan Dashboard Streamlit

### Menjalankan Dashboard

```bash
cd screener_v2
streamlit run streamlit_app.py
```

Buka browser di `http://localhost:8501`

### Tab 1: Dashboard

**Fungsi**: Overview dan metrics utama.

| Elemen | Penjelasan |
|--------|------------|
| Metrics cards | Jumlah setups, rata-rata score, market regime |
| Setup Distribution Chart | Bar chart dan pie chart distribusi setup types |
| Timing Overview | Berapa saham yang ENTRY_READY vs WAIT |
| Full Results Table | Semua hasil screening dengan sorting dan filtering |

**Tips**:
- Klik header kolom untuk sorting
- Gunakan filter sidebar untuk filter berdasarkan setup type
- Download CSV untuk analisis lebih lanjut

---

### Tab 2: Results

**Fungsi**: Deep dive ke hasil screening.

| Fitur | Penjelasan |
|-------|------------|
| Filter sidebar | Filter berdasarkan setup, signal, timing, score range |
| Detail panel | Klik baris untuk melihat detail lengkap |
| Top 5 per Setup | Ranking terbaik per setup type |
| CSV download | Export hasil ke CSV |

---

### Tab 3: Deep Analysis

**Fungsi**: Analisis mendalam per ticker.

| Fitur | Penjelasan |
|-------|------------|
| Candlestick chart | Interaktif dengan Plotly (zoom, pan, hover) |
| Indicators overlay | SuperTrend, MA20, MA50, entry zone, SL/TP lines |
| Volume + RSI/Stochastic | Sub-chart di bawah harga |
| Trade assistant card | Entry zone, SL, TP, timing, risk/reward ratio |
| Interpretation | Analisis text lengkap (trend, volume, momentum, fundamental) |

**Cara Menggunakan**:
1. Ketik ticker di search box (contoh: `BBCA.JK`)
2. Klik "Analyze"
3. Scroll ke bawah untuk melihat chart dan analisis

---

### Tab 4: Performance

**Fungsi**: Tracking performa dan backtesting.

| Fitur | Penjelasan |
|-------|------------|
| Backtest results | Walk-forward backtest di periode historis |
| Calibration check | Seberapa akurat probabilitas Monte Carlo |
| Portfolio simulation | Simulasi portfolio vs benchmark IHSG |
| Win rate, Sharpe, Sortino | Metrics performa utama |

---

## Membaca Hasil Screening

Setiap baris hasil screening berisi informasi berikut:

### Kolom Utama

| Kolom | Penjelasan | Contoh |
|-------|------------|--------|
| **Ticker** | Kode saham | `BBCA.JK` |
| **Setup** | Tipe setup yang terdeteksi | `BREAKOUT` |
| **Signal** | Kekuatan sinyal | `STRONG BUY` |
| **Price** | Harga saat sinyal | `9500` |
| **Entry Zone** | Range harga masuk optimal | `9400 - 9550` |
| **Stop Loss** | Batas kerugian | `9100` |
| **TP1 / TP2 / TP3** | Target profit bertingkat | `10000 / 10500 / 11000` |
| **Timing** | Status kesiapan entry | `ENTRY_READY` |
| **Score** | Skor komposit (0-100) | `78.5` |
| **RL Score** | Skor AI (0-100) | `82.3` |
| **P(TP1)** | Probabilitas capai TP1 | `72%` |
| **P(SL)** | Probabilitas kena SL | `18%` |

### Memahami Timing

| Timing | Arti | Action |
|--------|------|--------|
| `ENTRY_READY` | Saatnya masuk sekarang | Eksekusi entry |
| `WAIT_VOLUME` | Tunggu volume naik | Monitor, masuk saat volume spike |
| `WAIT_PRICE` | Tunggu harga turun ke entry zone | Set alert di harga target |
| `WAIT_PULLBACK` | Tunggu pullback ke support | Sabar, jangan FOMO |
| `WAIT_RETEST` | Tunggu retest breakout level | Masuk saat retest berhasil |
| `WAIT_MOMENTUM` | Tunggu momentum konfirmasi | Monitor RSI/MACD |
| `WAIT_CONFIRMATION` | Tunggu konfirmasi candle | Tunggu candle hijau berikutnya |
| `HOLD` | Sudah di posisi | Jangan tambah posisi |

### Memahami Score

Score adalah gabungan dari beberapa faktor:

```
Score = Technical Score + Monte Carlo Score + Pattern Score + RL Score
```

| Range | Interpretasi |
|-------|--------------|
| 80-100 | Setup sangat kuat — priority untuk entry |
| 60-79 | Setup bagus — layak dipertimbangkan |
| 40-59 | Setup moderat — butuh konfirmasi tambahan |
| < 40 | Setup lemah — hindari atau tunggu |

---

## Monte Carlo & Probabilities

### Apa itu Monte Carlo?

Monte Carlo simulation menjalankan **1000 simulasi** pergerakan harga selama **20 hari ke depan** berdasarkan model statistik (Markov Regime-Switching). Hasilnya berupa probabilitas:

| Output | Penjelasan |
|--------|------------|
| **P(TP1)** | Peluang harga mencapai TP1 dalam 20 hari |
| **P(TP2)** | Peluang harga mencapai TP2 dalam 20 hari |
| **P(TP3)** | Peluang harga mencapai TP3 dalam 20 hari |
| **P(SL)** | Peluang harga menyentuh stop loss dalam 20 hari |
| **Avg Days TP1** | Rata-rata hari untuk mencapai TP1 |
| **Avg Days SL** | Rata-rata hari untuk menyentuh SL |

### Cara Membaca Probabilitas

**Contoh**:
```
P(TP1) = 72%   → Dari 1000 simulasi, 720 simulasi harga mencapai TP1
P(TP2) = 55%   → 550 simulasi mencapai TP2
P(TP3) = 38%   → 380 simulasi mencapai TP3
P(SL)  = 18%   → 180 simulasi harga menyentuh SL
```

**Interpretasi**:
- Jika P(TP1) > 60% dan P(SL) < 25% → **Setup bagus**
- Jika P(TP1) > P(SL) secara signifikan → **Risk/reward menguntungkan**
- Jika Avg Days TP1 = 5 hari → Ekspektasi profit dalam 1 minggu

### Markov Regime-Switching Model

Monte Carlo menggunakan model Markov 2-regime:
- **Regime 1 (Bull)**: Return rata-rata positif, volatilitas rendah
- **Regime 2 (Bear)**: Return rata-rata negatif, volatilitas tinggi

Model ini lebih realistis karena menangkap fakta bahwa saham memiliki periode uptrend dan downtend yang berbeda.

---

## RL Score & AI Ranking

### Apa itu RL Score?

RL Score adalah ranking 0-100 yang dihasilkan oleh **ensemble model** machine learning:

| Model | Bobot | Fungsi |
|-------|-------|--------|
| HistGradientBoosting | 5% | Baseline model |
| XGBoost | 10% | Gradient boosting |
| LightGBM | 10% | Fast gradient boosting |
| RandomForest | 60% | Robust ensemble (bobot utama) |
| LogisticRegression | 15% | Linear baseline |
| TabNet | Optional | Deep learning tabular |

### Features yang Digunakan (60+)

Model dilatih dengan 60+ fitur:

- **Technical**: RSI, MACD, ADX, Stochastic, Bollinger Band width, volume ratio
- **Monte Carlo**: P(TP1), P(TP2), P(TP3), P(SL), avg days
- **Fundamental**: PE ratio, PB ratio, ROE, revenue growth, dividend yield, market cap
- **Interaction**: RSI × volume, ADX × trend, price × MA ratio
- **Cross-sectional**: Rank di antara semua saham (volume rank, momentum rank, dll)
- **Temporal**: Hari dalam minggu, bulan, efek Januari

### Interpretasi

| RL Score | Interpretasi |
|----------|--------------|
| 80-100 | Sangat menurut AI — high conviction trade |
| 60-79 | Bagus — layak dipertimbangkan |
| 40-59 | Netral — butuh analisis manual lebih lanjut |
| < 40 | Lemah — AI tidak merekomendasikan |

### Auto-Retrain

Model secara otomatis melakukan retraining ketika:
- Ada cukup data trade baru yang sudah closed (dengan outcome profit/loss)
- Performa model menurun (AUC turun)

Model disimpan dengan versioning, sehingga bisa di-rollback jika versi baru lebih buruk.

---

## Risk Management

### Position Sizing

Parameter default:
- **Initial Capital**: Rp 100.000.000 (100 juta)
- **Position Size**: Rp 10.000.000 (10 juta per entry)
- **Max Positions**: 12 posisi bersamaan
- **Risk Per Trade**: 2% dari modal (Rp 2 juta)

### Stop Loss Calculation

```
Stop Loss = Harga Entry - (ATR 14 × 1.5)
```

- ATR (Average True Range) mengukur volatilitas saham
- Multiplier 1.5x memberikan ruang untuk normal price fluctuation
- Jika ATR = 200 dan harga = 10.000, maka SL = 10.000 - 300 = 9.700

### Take Profit Levels

```
Risk = Harga Entry - Stop Loss
TP1 = Harga Entry + (Risk × 1.5)   → Risk/Reward 1:1.5
TP2 = Harga Entry + (Risk × 2.5)   → Risk/Reward 1:2.5
TP3 = Harga Entry + (Risk × 3.0)   → Risk/Reward 1:3.0
```

### Partial Exit Strategy

Sistem menggunakan strategi **partial exit**:

| Target | % Saham Dijual | Alasan |
|--------|---------------|--------|
| TP1 | 60% | Lock in profit mayoritas |
| TP2 | 25% | Ride the momentum |
| TP3 | 15% | Maximum profit capture |

**Contoh**:
- Entry 1000 saham di harga 10.000
- TP1 tersentuh (10.750) → jual 600 saham (60%)
- TP2 tersentuh (11.500) → jual 250 saham (25%)
- TP3 tersentuh (12.250) → jual 150 saham (15%)

### Risk/Reward Ratio

Setiap setup harus memiliki **minimum risk/reward 1:1.5** untuk TP1. Artinya:
- Jika risk (jarak ke SL) = 300 point
- Maka target profit minimal = 450 point (300 × 1.5)

---

## Market Regime

### Apa itu Market Regime?

Market regime adalah kondisi keseluruhan pasar (IHSG) yang mempengaruhi semua saham.

### Deteksi Regime

Sistem menggunakan 3 indikator untuk menentukan regime:

| Indikator | Bull | Sideways | Bear |
|-----------|------|----------|------|
| **Ichimoku** | IHSG > Cloud | IHSG ≈ Cloud | IHSG < Cloud |
| **SuperTrend** | Bullish | Netral | Bearish |
| **ADX** | > 25 (trending) | < 20 (ranging) | N/A |

### Dampak ke Screening

| Regime | Setup Aktif | Strategi |
|--------|------------|----------|
| **BULL** | Semua 9 setup | Agresif — banyak peluang |
| **SIDEWAYS** | Semua 9 setup (skor dikurangi) | Selektif — pilih yang terbaik |
| **BEAR** | Hanya EARLY_REVERSAL | Defensive — tunggu reversal |

### Kenapa Penting?

- Di market BEAR, 8 dari 9 setup dimatikan karena probabilitas success rendah
- Hanya EARLY_REVERSAL yang aktif untuk mencari saham yang mulai berbalik arah
- Ini melindungi dari false signal di market turun

---

## Adaptive Learning

### Apa itu Adaptive Learning?

Adaptive Learning adalah sistem yang secara otomatis mengoptimasi parameter screening berdasarkan data historis.

### Parameter yang Dioptimasi

| Parameter | Default | Range Optimasi |
|-----------|---------|----------------|
| SuperTrend Multiplier | 3.5 | 2.0 - 4.0 |
| ADX Threshold | 25 | 15 - 35 |
| RR1 (Risk/Reward TP1) | 1.5 | 1.5 - 2.5 |
| SL Multiplier | 1.5 | 1.0 - 2.0 |

### Cara Kerja

1. **Grid Search**: Sistem mencoba semua kombinasi parameter
2. **Walk-Forward Test**: Setiap kombinasi di-test di periode historis
3. **Scoring**: Kombinasi di-score berdasarkan win rate, profit factor, Sharpe ratio
4. **Selection**: Parameter terbaik disimpan ke `adaptive_config.json`
5. **Auto-Load**: Saat screening, sistem otomatis memuat parameter adaptif

### Rolling Window

Parameter bisa berubah seiring waktu karena market berubah. Rolling optimization:
- Menggunakan data 6 bulan terakhir
- Re-optimasi setiap minggu/bulan
- Parameter history tersimpan untuk tracking

---

## Performance Tracking

### Journal

Setiap prediksi dan trade result dicatat di database (SQLite/PostgreSQL).

**Tabel predictions**:
- Ticker, setup, signal, price, SL, TP1/TP2/TP3
- Entry zone, timing, score, RL score
- Monte Carlo probabilities
- Market regime, screen date
- Status: PENDING → ACTIVE → CLOSED

**Tabel trade_results**:
- Entry/exit date dan price
- Exit reason (TP1/TP2/TP3/SL/TIMEOUT)
- Return % dan absolute
- Days held

### Metrics

| Metrik | Rumus | Target Bagus |
|--------|-------|-------------|
| **Win Rate** | Profit trades / Total trades | > 50% |
| **Profit Factor** | Gross profit / Gross loss | > 1.5 |
| **Sharpe Ratio** | (Return - Risk-free) / StdDev | > 1.0 |
| **Sortino Ratio** | (Return - Risk-free) / Downside StdDev | > 1.5 |
| **Max Drawdown** | Largest peak-to-trough | < 20% |
| **Calmar Ratio** | Annual return / Max drawdown | > 1.0 |

### Calibration

Calibration mengecek apakah probabilitas Monte Carlo akurat:

- **Brier Score**: Semakin rendah semakin bagus (< 0.2 bagus, < 0.1 excellent)
- **Expected Calibration Error (ECE)**: Rata-rata selisih antara predicted probability dan actual frequency
- **Maximum Calibration Error (MCE)**: Selisih terbesar

**Contoh**: Jika P(TP1) = 70% untuk 100 saham, maka sekitar 70 saham seharusnya benar-benar mencapai TP1.

### Portfolio Simulation

Simulasi portfolio dengan aturan:
- Entry sesuai sinyal screening
- Exit sesuai TP1 (60%), TP2 (25%), TP3 (15%) atau SL
- Dibandingkan dengan benchmark IHSG

---

## Email Notifications

### Setup Email

1. **Buat Gmail App Password**:
   - Buka Google Account → Security → 2-Step Verification
   - App Passwords → Generate new → Select "Mail"

2. **Konfigurasi** (pilih salah satu):

**Option A: Streamlit Secrets** (untuk deployment):
```toml
# .streamlit/secrets.toml
[smtp]
server = "smtp.gmail.com"
port = 587
username = "your-email@gmail.com"
password = "your-app-password"
from_email = "your-email@gmail.com"
to_email = "recipient@example.com"
```

**Option B: Environment Variables**:
```bash
export SMTP_USERNAME="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
export FROM_EMAIL="your-email@gmail.com"
export TO_EMAIL="recipient@example.com"
```

**Option C: email_config.json**:
```json
{
    "server": "smtp.gmail.com",
    "port": 587,
    "username": "your-email@gmail.com",
    "password": "your-app-password",
    "from_email": "your-email@gmail.com",
    "to_email": "recipient@example.com"
}
```

### Konten Email

Email harian berisi:
- **Today's Activity**: Prediksi baru, trade closed, win rate, avg return
- **Recent 7 Days**: Performa 7 hari terakhir
- **Overall Status**: Total prediksi, pending/active/closed, profit factor
- **Closed Trades Table**: Detail trade yang sudah closed hari ini

### Cron Job (Otomatis)

Untuk menjalankan email otomatis setiap hari:

```bash
# Edit crontab
crontab -e

# Tambahkan (contoh: jam 5 sore setiap hari)
0 17 * * * cd /path/to/screener_v2 && bash run_daily_summary.sh
```

---

## Contoh Workflow Harian

### Pagi Hari (Sebelum Market Buka)

```
1. Buka Streamlit dashboard → Tab Dashboard
2. Cek Market Regime → Apakah BULL/SIDEWAYS/BEAR?
3. Jika BEAR → Hanya perhatikan EARLY_REVERSAL
4. Jika BULL → Scan semua setup yang tersedia
5. Sort berdasarkan Score atau RL Score
6. Catat top 3-5 saham yang ENTRY_READY
```

### Saat Market Buka

```
1. Buka Tab Deep Analysis
2. Analisis saham yang sudah dicatat:
   - Cek chart candlestick + indikator
   - Baca interpretation text
   - Perhatikan entry zone dan timing
3. Jika timing = ENTRY_READY dan harga di entry zone:
   - Hitung position size berdasarkan risk management
   - Set stop loss di level yang ditentukan
   - Entry dengan limit order di entry zone
```

### Setelah Entry

```
1. Set price alert di broker untuk:
   - Stop loss level
   - TP1 level (untuk jual 60%)
   - TP2 level (untuk jual 25%)
   - TP3 level (untuk jual 15%)
2. Monitor via Tab Results → filter status ACTIVE
3. Jangan panik jika harga turun ke SL — itu risk management
```

### Sore Hari (Setelah Market Tutup)

```
1. Jalankan screening lagi (jika belum otomatis):
   python -m main
2. Cek email untuk daily summary
3. Review trade yang sudah closed
4. Update journal (otomatis via sistem)
5. Siapkan watchlist untuk besok
```

### Mingguan

```
1. Cek Performance Tab → Backtest results
2. Review calibration → Apakah Monte Carlo akurat?
3. Cek adaptive learning → Apakah parameter perlu diupdate?
4. Review trade journal → Pattern dari winning vs losing trades
```

---

## FAQ & Tips

### Q: Berapa lama screening berlangsung?

**A**: Full screening 600+ saham membutuhkan **10-30 menit** tergantung koneksi internet dan kecepatan server. Data di-cache selama 8 jam jadi screening kedua di hari yang sama jauh lebih cepat.

### Q: Kenapa tidak ada setup yang ditemukan?

**A**: Beberapa kemungkinan:
1. **Market BEAR** → Hanya EARLY_REVERSAL yang aktif
2. **Tidak ada kondisi yang terpenuhi** → Normal, tidak setiap hari ada setup
3. **Data belum ter-download** → Cek koneksi internet dan cache

### Q: Apakah screener ini 100% akurat?

**A**: Tidak ada sistem yang 100% akurat. Screener ini memberikan **probabilitas**, bukan kepastian. Selalu gunakan risk management (stop loss) dan jangan invest lebih dari yang bisa ditanggung.

### Q: Berapa modal minimum yang dibutuhkan?

**A**: Dengan position size Rp 10 juta dan max 12 posisi, modal minimum ideal adalah **Rp 120 juta**. Namun, Anda bisa menyesuaikan parameter di `config.py`:
- Kurangi `POSITION_SIZE` untuk modal lebih kecil
- Kurangi `MAX_POSITIONS`

### Q: Apakah bisa digunakan untuk saham selain IDX?

**A**: Secara teknis bisa, tapi:
- Daftar ticker perlu diubah di `config.py`
- Tick size rules di `price_utils.py` perlu disesuaikan
- Fundamental data mungkin tidak tersedia
- Model RL dilatih khusus untuk IDX

### Q: Bagaimana cara menambahkan saham baru ke screening?

**A**: Edit `config.py`, tambahkan ticker ke list `TICKERS`:
```python
TICKERS = [
    "BBCA.JK", "BBRI.JK", ...,
    "NEWSTOCK.JK",  # Tambah di sini
]
```

### Tips

1. **Jangan FOMO**: Jika timing bukan ENTRY_READY, tunggu. Sabar adalah kunci.
2. **Selalu gunakan stop loss**: Jangan pernah trading tanpa SL.
3. **Diversifikasi**: Jangan taruh semua modal di 1 saham. Max 12 posisi.
4. **Review berkala**: Cek performance metrics mingguan untuk tahu apakah strategi bekerja.
5. **Jangan override sistem**: Jika sistem bilang SL di 9700, jangan geser ke 9500 karena "sayang".
6. **Start kecil**: Mulai dengan position size kecil sampai paham cara kerja sistem.
7. **Belajar dari losing trades**: Cek journal untuk melihat pattern dari trade yang gagal.

---

## Glossary

| Istilah | Penjelasan |
|---------|------------|
| **ADX** | Average Directional Index — mengukur kekuatan trend (0-100) |
| **ATR** | Average True Range — mengukur volatilitas harga |
| **AVWAP** | Anchored Volume Weighted Average Price |
| **Base** | Periode konsolidasi harga (sideways) |
| **Bollinger Bands** | Indikator volatilitas berbasis standard deviation |
| **Breakout** | Harga menembus level resistance/support |
| **Bull/Bear** | Market naik (bull) atau turun (bear) |
| **Candlestick** | Representasi grafik harga (open, high, low, close) |
| **Divergence** | Perbedaan arah antara harga dan indikator |
| **Donchian Channel** | Channel berbasis highest high dan lowest low |
| **Drawdown** | Penurunan dari puncak ke lembah portfolio |
| **Entry Zone** | Range harga optimal untuk masuk posisi |
| **Fibonacci** | Rasio matematika untuk support/resistance |
| **Flag Pattern** | Pola konsolidasi setelah kenaikan tajam |
| **HVN** | High Volume Node — zona dengan volume perdagangan tinggi |
| **Ichimoku Cloud** | Indikator trend Jepang (Tenkan, Kijun, Senkou) |
| **IHSG** | Indeks Harga Saham Gabungan — benchmark IDX |
| **Inside Bar** | Candle yang range-nya di dalam candle sebelumnya |
| **MACD** | Moving Average Convergence Divergence |
| **Markov Model** | Model statistik dengan state transitions |
| **MA20/MA50** | Moving Average 20/50 hari |
| **Monte Carlo** | Simulasi probabilistik menggunakan random sampling |
| **OBV** | On-Balance Volume — indikator akumulasi/distribusi |
| **Partial Exit** | Strategi jual sebagian di beberapa level profit |
| **Pullback** | Penurunan sementara dalam uptrend |
| **Regime** | Kondisi market (bull/sideways/bear) |
| **Resistance** | Level harga di mana tekanan jual meningkat |
| **RL** | Reinforcement Learning |
| **Risk/Reward** | Rasio antara potensi kerugian dan keuntungan |
| **RSI** | Relative Strength Index — indikator momentum (0-100) |
| **Score** | Skor komposit untuk ranking setup |
| **SL** | Stop Loss — batas kerugian otomatis |
| **Stochastic** | Indikator momentum oscillator |
| **SuperTrend** | Indikator trend berbasis ATR |
| **Support** | Level harga di mana tekanan beli meningkat |
| **Swing Trading** | Strategi trading dengan holding 2-20 hari |
| **TP1/TP2/TP3** | Take Profit level 1/2/3 |
| **VCP** | Volatility Contraction Pattern (Mark Minervini) |
| **Volume Delta** | Selisih antara volume beli dan jual |
| **Walk-Forward** | Backtesting dengan rolling window |

---

<div align="center">

**Selamat menggunakan Swing Screener v2!**

Jika ada pertanyaan atau feedback, buka issue di repository.

[⬆ Kembali ke atas](#-panduan-lengkap-swing-screener-v2)

</div>
