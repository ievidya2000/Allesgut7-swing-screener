import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime, timedelta

from screener_v2.config import INITIAL_CAPITAL, POSITION_SIZE, MAX_POSITIONS, MC_HORIZON
from screener_v2.performance.journal import (
    init_db, get_pending_predictions, get_active_predictions,
    update_prediction_status, log_portfolio_snapshot, get_portfolio_snapshots
)
from screener_v2.performance.metrics import (
    sharpe_ratio, sortino_ratio, max_drawdown, max_drawdown_abs,
    calmar_ratio, format_report, full_report
)
from screener_v2.data import get_jkse_data
from screener_v2.utils.date_utils import normalize_screen_date, safe_screen_date_str


class PortfolioSimulator:
    def __init__(self, initial_capital=None):
        self.initial_capital = initial_capital or INITIAL_CAPITAL
        self.cash = self.initial_capital
        self.positions = {}
        self.equity_curve = []
        self.benchmark_curve = []
        self.trades_log = []
        self.snapshot_dates = []

    def open_position(self, ticker, entry_price, position_size, sl, tp1, tp2, tp3, signal_date, setup):
        if ticker in self.positions:
            return False
        if len(self.positions) >= MAX_POSITIONS:
            return False
        if self.cash < position_size:
            return False

        shares = int(position_size / entry_price)
        if shares <= 0:
            return False

        actual_cost = shares * entry_price
        self.cash -= actual_cost

        self.positions[ticker] = {
            "shares": shares,
            "entry_price": entry_price,
            "cost": actual_cost,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "entry_date": signal_date,
            "setup": setup,
            "max_price": entry_price,
            "tp1_hit": False,
            "tp2_hit": False,
        }
        return True

    def check_exit(self, ticker, current_date, current_high, current_low, current_close):
        if ticker not in self.positions:
            return None

        pos = self.positions[ticker]

        if current_high > pos["max_price"]:
            pos["max_price"] = current_high

        if pos["sl"] and current_low <= pos["sl"]:
            return self._close_position(ticker, pos["sl"], current_date, "SL")

        if pos.get("tp1") and current_high >= pos["tp1"] and not pos.get("tp1_hit"):
            pos["tp1_hit"] = True
            pos["sl"] = pos["entry_price"]

        if pos.get("tp2") and current_high >= pos["tp2"] and pos.get("tp1_hit") and not pos.get("tp2_hit"):
            pos["tp2_hit"] = True
            pos["sl"] = pos["tp2"]

        if pos.get("tp3") and current_high >= pos["tp3"] and pos.get("tp2_hit"):
            return self._close_position(ticker, pos["tp3"], current_date, "TP3")

        days_held = (current_date - pd.Timestamp(pos["entry_date"])).days
        if days_held > MC_HORIZON:
            return self._close_position(ticker, current_close, current_date, "TIMEOUT")

        return None

    def _close_position(self, ticker, exit_price, exit_date, reason):
        pos = self.positions.pop(ticker)
        proceeds = pos["shares"] * exit_price
        self.cash += proceeds

        pnl = proceeds - pos["cost"]
        pnl_pct = (pnl / pos["cost"]) * 100

        trade = {
            "ticker": ticker,
            "setup": pos["setup"],
            "entry_date": pos["entry_date"],
            "entry_price": pos["entry_price"],
            "exit_date": str(exit_date.date()) if hasattr(exit_date, "date") else str(exit_date),
            "exit_price": round(exit_price, 2),
            "exit_reason": reason,
            "return_pct": round(pnl_pct, 2),
            "return_abs": round(pnl, 2),
            "days_held": (exit_date - pd.Timestamp(pos["entry_date"])).days,
            "shares": pos["shares"],
        }
        self.trades_log.append(trade)
        return trade

    def get_total_value(self, market_data, current_date):
        positions_value = 0
        for ticker, pos in self.positions.items():
            if ticker in market_data:
                df = market_data[ticker]
                df_after = df[df.index <= current_date]
                if not df_after.empty:
                    current_price = df_after["Close"].iloc[-1]
                    positions_value += pos["shares"] * current_price
                else:
                    positions_value += pos["cost"]
            else:
                positions_value += pos["cost"]

        return self.cash + positions_value

    def take_snapshot(self, current_date, market_data, ihsg_data=None):
        total_value = self.get_total_value(market_data, current_date)
        positions_value = total_value - self.cash

        ihsg_value = None
        if ihsg_data is not None:
            ihsg_slice = ihsg_data[ihsg_data.index <= current_date]
            if not ihsg_slice.empty:
                ihsg_value = ihsg_slice["Close"].iloc[-1]

        snapshot = {
            "snapshot_date": current_date.isoformat(),
            "cash": round(self.cash, 2),
            "positions_value": round(positions_value, 2),
            "total_value": round(total_value, 2),
            "num_positions": len(self.positions),
            "ihsg_value": ihsg_value,
        }

        self.equity_curve.append(total_value)
        self.snapshot_dates.append(current_date)

        if ihsg_value is not None:
            self.benchmark_curve.append(ihsg_value)

        log_portfolio_snapshot(snapshot)
        return snapshot


def simulate_portfolio(start_date=None, end_date=None, initial_capital=None):
    init_db()

    if end_date is None:
        end_date = datetime.now()
    if start_date is None:
        start_date = end_date - timedelta(days=365)

    if isinstance(start_date, str):
        start_date = datetime.fromisoformat(start_date)
    if isinstance(end_date, str):
        end_date = datetime.fromisoformat(end_date)

    print(f"\n{'='*60}")
    print(f"  PORTFOLIO SIMULATION: {start_date.date()} → {end_date.date()}")
    print(f"  Initial Capital: Rp {initial_capital or INITIAL_CAPITAL:,.0f}")
    print(f"{'='*60}\n")

    from screener_v2.data import get_all_market_data
    from screener_v2.config import TICKERS

    print("[1/3] Loading market data...")
    market_data = get_all_market_data(TICKERS)
    ihsg_data = get_jkse_data()
    print(f"  Loaded {len(market_data)} tickers")

    sim = PortfolioSimulator(initial_capital)
    pending = get_pending_predictions()

    pending_by_date = {}
    for p in pending:
        date_str = safe_screen_date_str(p["screen_date"])
        if date_str not in pending_by_date:
            pending_by_date[date_str] = []
        pending_by_date[date_str].append(p)

    trading_days = pd.bdate_range(start=start_date, end=end_date, freq="B")

    print(f"\n[2/3] Simulating {len(trading_days)} trading days...")
    for i, day in enumerate(trading_days):
        if i % 50 == 0:
            print(f"  Day {day.date()} ({i+1}/{len(trading_days)})...")

        day_str = day.date().isoformat()

        tickers_to_check = list(sim.positions.keys())
        for ticker in tickers_to_check:
            if ticker in market_data:
                df = market_data[ticker]
                day_data = df[df.index == day]
                if not day_data.empty:
                    row = day_data.iloc[0]
                    trade = sim.check_exit(
                        ticker, day,
                        row["High"], row["Low"], row["Close"]
                    )
                    if trade:
                        print(f"    CLOSED {trade['ticker']}: {trade['exit_reason']} "
                              f"({trade['return_pct']:+.2f}%)")

        if day_str in pending_by_date and len(sim.positions) < MAX_POSITIONS:
            for pred in pending_by_date[day_str]:
                if pred["ticker"] in sim.positions:
                    continue
                if len(sim.positions) >= MAX_POSITIONS:
                    break
                if sim.cash < POSITION_SIZE:
                    break

                success = sim.open_position(
                    pred["ticker"], pred["price_at_signal"],
                    POSITION_SIZE, pred["stop_loss"],
                    pred.get("tp1"), pred.get("tp2"), pred.get("tp3"),
                    day_str, pred["setup"]
                )
                if success:
                    update_prediction_status(pred["id"], "ACTIVE")

        if i % 5 == 0:
            sim.take_snapshot(day, market_data, ihsg_data)

    for ticker in list(sim.positions.keys()):
        last_date = trading_days[-1]
        if ticker in market_data:
            df = market_data[ticker]
            day_data = df[df.index <= last_date]
            if not day_data.empty:
                row = day_data.iloc[-1]
                sim.check_exit(ticker, last_date, row["High"], row["Low"], row["Close"])

    sim.take_snapshot(trading_days[-1], market_data, ihsg_data)

    print(f"\n[3/3] Generating report...")
    report = full_report(sim.trades_log, sim.equity_curve, sim.benchmark_curve)
    print(format_report(report))

    return report, sim


def plot_equity_curve(sim, save_path=None):
    if not sim.equity_curve:
        print("  No equity curve data")
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [3, 1]})

    dates = sim.snapshot_dates[:len(sim.equity_curve)]
    equity = np.array(sim.equity_curve)

    ax1.plot(dates, equity / 1_000_000, "b-", linewidth=1.5, label="Portfolio")
    ax1.set_ylabel("Portfolio Value (Rp Juta)")
    ax1.set_title("Portfolio Equity Curve")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    peaks = np.maximum.accumulate(equity)
    drawdowns = (peaks - equity) / peaks * 100
    ax2.fill_between(dates, 0, -drawdowns, color="red", alpha=0.3)
    ax2.set_ylabel("Drawdown (%)")
    ax2.set_xlabel("Date")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path is None:
        save_path = Path(__file__).parent.parent / "equity_curve.png"

    plt.savefig(str(save_path), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Equity curve saved: {save_path}")
    return str(save_path)
