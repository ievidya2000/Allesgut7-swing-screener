"""Auto Paper Trading module — screener to Google Sheets integration."""

from paper_trading.auto_trader import auto_create_orders, filter_screener_results
from paper_trading.run_auto import run_auto_paper_trading
from paper_trading.gsheets_client import GSheetsClient

__all__ = [
    "auto_create_orders",
    "filter_screener_results",
    "run_auto_paper_trading",
    "GSheetsClient",
]
