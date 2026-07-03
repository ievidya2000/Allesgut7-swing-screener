"""Entry point for auto paper trading — run screener + create orders."""

import sys
from datetime import datetime

try:
    import requests
except ImportError:
    requests = None

from paper_trading.config import (
    SPREADSHEET_ID, SERVICE_ACCOUNT_FILE,
    INITIAL_CAPITAL, RISK_PER_TRADE_PCT, MAX_POSITIONS,
    TP1_PCT, TP2_PCT, TP3_PCT,
    SKIP_IF_ALREADY_OPEN, SKIP_IF_ALREADY_PENDING,
    ALLOWED_TIMING
)
from paper_trading.gsheets_client import GSheetsClient
from paper_trading.auto_trader import auto_create_orders, filter_screener_results


def run_auto_paper_trading(results, dry_run=False):
    """
    Jalankan auto paper trading dari hasil screener.

    Args:
        results: list of dict dari screener (atau DataFrame)
        dry_run: jika True, hanya print tanpa create order

    Returns:
        dict: summary hasil
    """
    # Validasi config
    if not SPREADSHEET_ID:
        print("\n  ⚠️  SPREADSHEET_ID belum diisi di paper_trading/config.py")
        print("  Buka Google Sheets → copy ID dari URL")
        print("  Contoh: https://docs.google.com/spreadsheets/d/XXXXX/edit")
        print("  SPREADSHEET_ID = \"XXXXX\"")
        return None

    # Convert DataFrame to list of dict jika perlu
    if hasattr(results, 'to_dict'):
        results_list = results.to_dict('records')
    elif isinstance(results, list):
        results_list = results
    else:
        print("  ❌ Format results tidak dikenali")
        return None

    if not results_list:
        print("  ℹ️  Tidak ada hasil screener untuk di-process")
        return None

    # Koneksi ke Google Sheets
    print("\n  📊 Connecting to Google Sheets...")
    try:
        client = GSheetsClient()
        client.connect()
        print(f"  ✅ Connected: {client.spreadsheet.title}")
    except FileNotFoundError:
        print(f"  ❌ Service account file tidak ditemukan: {SERVICE_ACCOUNT_FILE}")
        print("  Download dari Google Cloud Console → simpan sebagai service_account.json")
        return None
    except Exception as e:
        print(f"  ❌ Gagal koneksi ke Google Sheets: {e}")
        return None

    # Print config
    print(f"\n  ⚙️  Config:")
    print(f"     Modal: Rp {INITIAL_CAPITAL:,.0f}")
    print(f"     Risk per trade: {RISK_PER_TRADE_PCT}%")
    print(f"     Max positions: {MAX_POSITIONS}")
    print(f"     Partial exit: {TP1_PCT}/{TP2_PCT}/{TP3_PCT}")
    print(f"     Allowed timing: {', '.join(ALLOWED_TIMING)}")
    print(f"     Skip if open: {SKIP_IF_ALREADY_OPEN}")
    print(f"     Skip if pending: {SKIP_IF_ALREADY_PENDING}")

    # Auto-create orders
    summary = auto_create_orders(results_list, client=client, dry_run=dry_run)

    # Kirim notifikasi jika ada order (skip saat dry_run)
    if not dry_run and summary and summary["orders_created"]:
        try:
            _send_notification(client, summary)
        except Exception as e:
            print(f"  ⚠️  Notifikasi gagal: {e}")

    return summary


def _send_notification(client, summary):
    """Kirim notifikasi via Telegram (jika dikonfigurasi)."""
    if requests is None:
        print("  ⚠️  requests not installed, skip Telegram notification")
        return

    try:
        settings = client.settings
        bot_token = settings.acell("B7").value
        chat_id = settings.acell("B8").value

        if not bot_token or not chat_id:
            return

        orders = summary["orders_created"]
        msg = f"🤖 AUTO PAPER TRADING\n\n"
        msg += f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')} WIB\n"
        msg += f"📊 Orders created: {len(orders)}\n\n"

        for o in orders:
            emoji = "✅" if o.get("timing") == "ENTRY_READY" else "🟡"
            msg += f"{emoji} {o['ticker']} — {o['qty']} lots @ Rp {o['entry']:,.0f}\n"
            if o.get("order_id"):
                msg += f"   Order: {o['order_id']}\n"

        msg += f"\n⚠️ Think First. Trade Second. DYOR"

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            print("  📱 Telegram notification sent")
        else:
            print(f"  ⚠️  Telegram error: {response.status_code}")

    except Exception as e:
        print(f"  ⚠️  Telegram error: {e}")


def main():
    """CLI entry point untuk standalone testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Auto Paper Trading")
    parser.add_argument("--dry-run", action="store_true", help="Simulasi tanpa create order")
    parser.add_argument("--test", action="store_true", help="Test koneksi Google Sheets")
    args = parser.parse_args()

    if args.test:
        print("  🧪 Testing Google Sheets connection...")
        try:
            client = GSheetsClient()
            client.connect()
            print(f"  ✅ Connected: {client.spreadsheet.title}")
            print(f"  📊 Trade Log: {len(client.trade_log.get_all_values())} rows")
            print(f"  📋 Pending: {len(client.pending.get_all_values())} rows")
            print(f"  ⚙️  Modal: Rp {client.get_modal():,.0f}")
            print(f"  📈 Open trades: {client.count_open_positions()}")
            print(f"  📋 Pending orders: {client.count_pending_orders()}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        return

    # Untuk testing, buat dummy results
    print("  ℹ️  Untuk menjalankan auto-trade, gunakan:")
    print("     python main.py --auto-trade")
    print()
    print("  Atau test koneksi:")
    print("     python -m paper_trading.run_auto --test")


if __name__ == "__main__":
    main()
