"""Auto Paper Trading Configuration."""

from pathlib import Path

# ── Google Sheets ──────────────────────────────────────────────
# Spreadsheet ID dari URL Google Sheets
# Contoh: https://docs.google.com/spreadsheets/d/XXXXX/edit
SPREADSHEET_ID = "1w8vhm-3sfY8fk_TEPoAvr6ujjZnZAPMXV-QxX5baBPE"

# Path ke service account JSON key file
SERVICE_ACCOUNT_FILE = str(Path(__file__).parent / "service_account.json")

# Sheet names (harus cocok dengan Code.gs)
SHEET_TRADE_LOG = "Trade Log"
SHEET_PENDING = "Pending Orders"
SHEET_SETTINGS = "Settings"

# ── Position Sizing ────────────────────────────────────────────
INITIAL_CAPITAL = 100_000_000      # Rp 100 juta
RISK_PER_TRADE_PCT = 2.0           # 2% risk per trade
MAX_POSITIONS = 12                  # Max concurrent positions

# Partial Exit (% qty dijual di setiap TP)
TP1_PCT = 60
TP2_PCT = 25
TP3_PCT = 15

# ── Auto Trade Rules ──────────────────────────────────────────
# Minimum score untuk auto-order (filter noise)
# Berdasarkan backtest: score >= 15 → win rate 52%, avg ret 4.55%, PF 2.15
MIN_SCORE = 15.0

# Per-setup MIN_SCORE override
# Setup yang tidak ada di sini pakai MIN_SCORE global (15.0)
SETUP_MIN_SCORE = {
    "EARLY_REVERSAL": 50.0,   # Effectively excluded (tidak ada data di score 50+)
    "BULL_FLAG": 20.0,        # Hanya score >= 20 yang diizinkan
}

# Market regime filter per setup
# Hanya izinkan setup di market regime tertentu
# Setup yang tidak ada di sini boleh di semua regime
SETUP_ALLOWED_REGIMES = {
    "BULL_FLAG": ["BEAR"],    # BULL_FLAG hanya bagus di BEAR market
}

# Setup yang dikecualikan dari auto-trade
# EARLY_REVERSAL: win rate rendah (18.5%), avg return negatif (-2.71%)
EXCLUDED_SETUPS = ["EARLY_REVERSAL"]

# Timing yang diizinkan untuk auto-trade
# ENTRY_READY → langsung eksekusi
# WAIT_PULLBACK/WAIT_PRICE/WAIT_RETEST → limit order di target price
ALLOWED_TIMING = [
    "ENTRY_READY",
    "WAIT_PULLBACK",
    "WAIT_PRICE",
    "WAIT_RETEST",
]

# Max order baru per hari (mencegah over-trading)
MAX_AUTO_ORDERS_PER_DAY = 5

# Skip ticker yang sudah ada trade OPEN/PARTIAL
SKIP_IF_ALREADY_OPEN = True

# Skip ticker yang sudah ada pending order
SKIP_IF_ALREADY_PENDING = True

# Pending order expiration (hari) — cancel jika belum match
PENDING_ORDER_MAX_DAYS = 2

# ── Fees ───────────────────────────────────────────────────────
BUY_FEE = 0.0015   # 0.15%
SELL_FEE = 0.0025   # 0.25%

# ── Display ────────────────────────────────────────────────────
SHOW_SKIPPED = True
SHOW_SUMMARY = True
