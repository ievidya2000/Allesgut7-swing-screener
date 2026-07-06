"""Google Sheets client for Paper Trading integration."""

import gspread
import uuid
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

from paper_trading.config import (
    SPREADSHEET_ID, SERVICE_ACCOUNT_FILE,
    SHEET_TRADE_LOG, SHEET_PENDING, SHEET_SETTINGS,
    BUY_FEE, SELL_FEE, PENDING_ORDER_MAX_DAYS
)
from utils.price_utils import round_to_tick


def _safe_float(val, default=0.0):
    """Parse float dari format Indonesia (429,4 / 1.429,4) atau standar (429.4)."""
    if not val:
        return default
    s = str(val).strip()
    if not s:
        return default
    try:
        # Cek apakah koma adalah desimal separator (diikuti 1-2 digit di akhir)
        # atau ribuan separator (diikuti 3 digit)
        if "," in s:
            # Temukan posisi koma terakhir dari belakang
            last_comma = s.rfind(",")
            after_comma = s[last_comma + 1:]
            before_comma = s[:last_comma]
            if len(after_comma) <= 2:
                # Koma = desimal separator (format Indonesia: 429,4 atau 1.429,4)
                # Hapus titik ribuan, ganti koma desimal dengan titik
                s = before_comma.replace(".", "") + "." + after_comma
            else:
                # Koma = ribuan separator (format US: 1,429.4)
                s = s.replace(",", "")
        return float(s)
    except (ValueError, TypeError):
        return default


# Column indices for Trade Log (0-indexed)
COL_ID = 0
COL_DATE = 1
COL_TICKER = 2
COL_QTY = 3
COL_ENTRY = 4
COL_ENTRY_FEE = 5
COL_ENTRY_TOTAL = 6
COL_EXIT_DATE = 7
COL_EXIT_PRICE = 8
COL_EXIT_FEE = 9
COL_EXIT_TOTAL = 10
COL_PNL_RP = 11
COL_PNL_PCT = 12
COL_STATUS = 13
COL_REMAINING = 14
COL_STRATEGY = 15
COL_NOTES = 16

# Column indices for Pending Orders (0-indexed)
PCOL_ID = 0
PCOL_DATE = 1
PCOL_TICKER = 2
PCOL_TYPE = 3
PCOL_QTY = 4
PCOL_TARGET = 5
PCOL_CURRENT = 6
PCOL_CHANGE = 7
PCOL_STATUS = 8
PCOL_PARENT = 9
PCOL_TP_PCT = 10
PCOL_NOTES = 11


class GSheetsClient:
    """Client untuk koneksi ke Google Sheets Paper Trading."""

    def __init__(self, spreadsheet_id=None, service_account_file=None):
        self.spreadsheet_id = spreadsheet_id or SPREADSHEET_ID
        self.service_account_file = service_account_file or SERVICE_ACCOUNT_FILE
        self.gc = None
        self.spreadsheet = None
        self._trade_log = None
        self._pending = None
        self._settings = None

    def connect(self):
        """Koneksi ke Google Sheets."""
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        try:
            import streamlit as st
            if hasattr(st, 'secrets') and 'google_service_account' in st.secrets:
                creds = Credentials.from_service_account_info(
                    dict(st.secrets["google_service_account"]), scopes=scopes
                )
            else:
                creds = Credentials.from_service_account_file(
                    self.service_account_file, scopes=scopes
                )
        except Exception:
            creds = Credentials.from_service_account_file(
                self.service_account_file, scopes=scopes
            )
        self.gc = gspread.authorize(creds)
        self.spreadsheet = self.gc.open_by_key(self.spreadsheet_id)
        return self

    def _get_sheet(self, name):
        """Get worksheet by name."""
        return self.spreadsheet.worksheet(name)

    @property
    def trade_log(self):
        if self._trade_log is None:
            self._trade_log = self._get_sheet(SHEET_TRADE_LOG)
        return self._trade_log

    @property
    def pending(self):
        if self._pending is None:
            self._pending = self._get_sheet(SHEET_PENDING)
        return self._pending

    @property
    def settings(self):
        if self._settings is None:
            self._settings = self._get_sheet(SHEET_SETTINGS)
        return self._settings

    def get_modal(self):
        """Ambil modal dari Settings sheet."""
        try:
            return _safe_float(self.settings.acell("B4").value, 100_000_000)
        except Exception:
            return 100_000_000

    def get_open_trades(self):
        """Ambil semua trade yang status OPEN atau PARTIAL."""
        data = self.trade_log.get_all_values()
        trades = []
        for i, row in enumerate(data[1:], start=2):  # skip header
            if len(row) > COL_STATUS and row[COL_STATUS] in ("OPEN", "PARTIAL"):
                trades.append({
                    "row": i,
                    "id": row[COL_ID],
                    "date": row[COL_DATE],
                    "ticker": row[COL_TICKER],
                    "qty": int(row[COL_QTY]) if row[COL_QTY] else 0,
                    "entry_price": _safe_float(row[COL_ENTRY]),
                    "remaining": int(row[COL_REMAINING]) if row[COL_REMAINING] else 0,
                    "status": row[COL_STATUS],
                    "notes": row[COL_NOTES] if len(row) > COL_NOTES else "",
                })
        return trades

    def get_pending_orders(self):
        """Ambil semua pending order."""
        data = self.pending.get_all_values()
        orders = []
        for i, row in enumerate(data[1:], start=2):  # skip header
            if len(row) > PCOL_STATUS and row[PCOL_STATUS] == "PENDING":
                orders.append({
                    "row": i,
                    "id": row[PCOL_ID],
                    "date": row[PCOL_DATE] if len(row) > PCOL_DATE else "",
                    "ticker": row[PCOL_TICKER],
                    "type": row[PCOL_TYPE],
                    "qty": int(row[PCOL_QTY]) if row[PCOL_QTY] else 0,
                    "target_price": _safe_float(row[PCOL_TARGET]),
                    "parent_id": row[PCOL_PARENT] if len(row) > PCOL_PARENT else "",
                    "notes": row[PCOL_NOTES] if len(row) > PCOL_NOTES else "",
                })
        return orders

    def get_open_tickers(self):
        """Ambil set ticker yang sudah ada trade OPEN/PARTIAL."""
        trades = self.get_open_trades()
        return {t["ticker"] for t in trades}

    def get_pending_tickers(self):
        """Ambil set ticker yang sudah ada pending order."""
        orders = self.get_pending_orders()
        return {o["ticker"] for o in orders}

    def count_today_orders(self):
        """Hitung jumlah pending order yang dibuat hari ini."""
        today = datetime.now().strftime("%Y-%m-%d")
        orders = self.get_pending_orders()
        count = 0
        for order in orders:
            date_str = order.get("date", "")
            if date_str.startswith(today):
                count += 1
        return count

    def count_today_orders_all(self):
        """Hitung bracket order yang dibuat hari ini (hanya BUY yang belum CANCELLED)."""
        today = datetime.now().strftime("%Y-%m-%d")
        data = self.pending.get_all_values()
        count = 0
        for row in data[1:]:
            if len(row) > PCOL_DATE and len(row) > PCOL_TYPE and len(row) > PCOL_STATUS:
                date_str = row[PCOL_DATE]
                order_type = row[PCOL_TYPE]
                status = row[PCOL_STATUS]
                if date_str.startswith(today) and order_type == 'BUY' and status != 'CANCELLED':
                    count += 1
        return count

    def get_next_trade_id(self):
        """Generate unique trade ID using timestamp + short UUID."""
        now = datetime.now()
        short_id = uuid.uuid4().hex[:4].upper()
        return f"T{now.strftime('%m%d%H%M')}_{short_id}"

    def get_next_order_id(self):
        """Generate unique order ID using timestamp + short UUID."""
        now = datetime.now()
        short_id = uuid.uuid4().hex[:4].upper()
        return f"P{now.strftime('%m%d%H%M')}_{short_id}"

    def _apply_bracket_colors(self, start_row):
        """Apply row colors matching Code.gs convention.
        BUY = green (#E6F4EA), SELL = red (#FCE8E6), STOPLOSS = yellow (#FDD663)
        """
        GREEN = {'backgroundColor': {'red': 0.90, 'green': 0.96, 'blue': 0.92}}
        RED = {'backgroundColor': {'red': 0.99, 'green': 0.91, 'blue': 0.90}}
        YELLOW = {'backgroundColor': {'red': 0.99, 'green': 0.84, 'blue': 0.39}}

        self.pending.format(f'A{start_row}:L{start_row}', GREEN)
        for i in range(1, 4):
            self.pending.format(f'A{start_row + i}:L{start_row + i}', RED)
        self.pending.format(f'A{start_row + 4}:L{start_row + 4}', YELLOW)

    def create_bracket_order(self, ticker, qty, entry_price, tp1_price, tp2_price,
                              tp3_price, sl_price, tp1_pct=60, tp2_pct=25, tp3_pct=15,
                              notes=""):
        """
        Buat bracket order di Google Sheets.
        1 BUY entry + 3 SELL (TP1/TP2/TP3) + 1 STOPLOSS

        Args:
            ticker: Ticker saham (tanpa .JK)
            qty: Total quantity (lot)
            entry_price: Harga entry (BUY)
            tp1_price, tp2_price, tp3_price: Harga take profit
            sl_price: Harga stop loss
            tp1_pct, tp2_pct, tp3_pct: Persentase qty untuk setiap TP
            notes: Catatan tambahan

        Returns:
            dict dengan order_id dan detail
        """
        # Defensive: pastikan semua harga tick-compliant
        entry_price = round_to_tick(entry_price)
        tp1_price = round_to_tick(tp1_price)
        tp2_price = round_to_tick(tp2_price)
        tp3_price = round_to_tick(tp3_price)
        sl_price = round_to_tick(sl_price)

        now = datetime.now()
        parent_id = self.get_next_order_id()

        # Hitung qty per TP
        tp1_qty = round(qty * tp1_pct / 100)
        tp2_qty = round(qty * tp2_pct / 100)
        tp3_qty = qty - tp1_qty - tp2_qty

        # Ambil harga saat ini (untuk display)
        current_price = entry_price  # Akan di-update oleh autoCheck

        # Generate unique IDs untuk setiap child order
        tp1_id = self.get_next_order_id()
        tp2_id = self.get_next_order_id()
        tp3_id = self.get_next_order_id()
        sl_id = self.get_next_order_id()

        # Buat rows untuk pending orders
        rows = []

        # 1. BUY entry
        rows.append([
            parent_id, now.strftime("%Y-%m-%d %H:%M:%S"), ticker, "BUY",
            qty, entry_price, current_price,
            "0.00", "PENDING", "", "", notes
        ])

        # 2. SELL TP1
        rows.append([
            tp1_id, now.strftime("%Y-%m-%d %H:%M:%S"), ticker, "SELL",
            tp1_qty, tp1_price, current_price,
            "0.00", "PENDING", parent_id, f"{tp1_pct}%", notes
        ])

        # 3. SELL TP2
        rows.append([
            tp2_id, now.strftime("%Y-%m-%d %H:%M:%S"), ticker, "SELL",
            tp2_qty, tp2_price, current_price,
            "0.00", "PENDING", parent_id, f"{tp2_pct}%", notes
        ])

        # 4. SELL TP3
        rows.append([
            tp3_id, now.strftime("%Y-%m-%d %H:%M:%S"), ticker, "SELL",
            tp3_qty, tp3_price, current_price,
            "0.00", "PENDING", parent_id, f"{tp3_pct}%", notes
        ])

        # 5. STOPLOSS
        rows.append([
            sl_id, now.strftime("%Y-%m-%d %H:%M:%S"), ticker, "STOPLOSS",
            qty, sl_price, current_price,
            "0.00", "PENDING", parent_id, "100%", notes
        ])

        # Append semua rows ke Pending Orders sheet (batch call)
        self.pending.append_rows(rows, value_input_option="USER_ENTERED")

        # Apply row colors (matching Code.gs convention)
        last_row = len(self.pending.get_all_values())
        self._apply_bracket_colors(last_row - 4)

        return {
            "order_id": parent_id,
            "ticker": ticker,
            "qty": qty,
            "entry_price": entry_price,
            "tp1": {"id": tp1_id, "price": tp1_price, "qty": tp1_qty},
            "tp2": {"id": tp2_id, "price": tp2_price, "qty": tp2_qty},
            "tp3": {"id": tp3_id, "price": tp3_price, "qty": tp3_qty},
            "sl": {"id": sl_id, "price": sl_price},
        }

    def count_open_positions(self):
        """Hitung jumlah posisi yang sedang OPEN/PARTIAL."""
        return len(self.get_open_trades())

    def count_pending_orders(self):
        """Hitung jumlah pending orders."""
        return len(self.get_pending_orders())

    def cancel_pending_by_parent(self, parent_id):
        """
        Cancel semua pending order dengan parent_id yang sama.
        Mirip logic di Code.gs:cancelPendingByParent().

        Args:
            parent_id: ID parent order (contoh: P012)

        Returns:
            list of cancelled order IDs
        """
        cancelled = []
        data = self.pending.get_all_values()

        for i, row in enumerate(data[1:], start=2):
            if len(row) > PCOL_STATUS and len(row) > PCOL_PARENT:
                # Cancel parent order atau child order dengan parent_id yang sama
                is_parent = row[PCOL_ID] == parent_id and row[PCOL_STATUS] == "PENDING"
                is_child = row[PCOL_PARENT] == parent_id and row[PCOL_STATUS] == "PENDING"

                if is_parent or is_child:
                    self.pending.update_cell(i, PCOL_STATUS + 1, "CANCELLED")
                    cancelled.append(row[PCOL_ID])

        return cancelled

    def cancel_expired_orders(self, max_days=None):
        """
        Cancel pending order yang sudah expired (lebih dari max_days hari).

        Args:
            max_days: Maksimal hari sebelum order di-cancel (default: dari config)

        Returns:
            list of dicts dengan info order yang di-cancel
        """
        if max_days is None:
            max_days = PENDING_ORDER_MAX_DAYS

        expired = []
        now = datetime.now()
        cutoff = now - timedelta(days=max_days)

        orders = self.get_pending_orders()
        parent_ids_to_cancel = set()

        for order in orders:
            date_str = order.get("date", "")
            if not date_str:
                continue

            try:
                # Parse date (format: "2026-06-30 09:15:00" atau "2026-06-30")
                order_date = datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    order_date = datetime.strptime(date_str[:10], "%Y-%m-%d")
                except ValueError:
                    continue

            # Cek apakah order sudah expired
            if order_date < cutoff:
                parent_id = order.get("parent_id")
                if not parent_id:
                    # Ini parent order sendiri (BUY entry), gunakan ID sendiri
                    parent_id = order["id"]
                parent_ids_to_cancel.add(parent_id)
                expired.append(order)

        # Cancel semua order (parent + children) untuk setiap parent_id
        all_cancelled = []
        for parent_id in parent_ids_to_cancel:
            cancelled = self.cancel_pending_by_parent(parent_id)
            all_cancelled.extend(cancelled)

        # Return info lengkap (deduplicated by parent_id)
        result = []
        seen_ids = set()
        for order in expired:
            oid = order["id"]
            if oid not in seen_ids:
                seen_ids.add(oid)
                result.append({
                    "id": order["id"],
                    "ticker": order["ticker"],
                    "date": order["date"],
                    "type": order["type"],
                    "target_price": order["target_price"],
                    "parent_id": order.get("parent_id", ""),
                })

        return result
