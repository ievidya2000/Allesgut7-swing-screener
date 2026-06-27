import pandas as pd
from datetime import datetime, timedelta

from screener_v2.performance.journal import (
    init_db, get_pending_predictions, get_active_predictions,
    get_all_predictions, update_prediction_status,
    log_prediction, log_trade_result, get_journal_summary
)
from screener_v2.performance.backtest import check_tp_sl_hit
from screener_v2.performance.calibration import print_calibration_report
from screener_v2.performance.metrics import full_report, format_report
from screener_v2.utils.date_utils import normalize_screen_date


def log_new_predictions(results, market_regime):
    init_db()

    count = 0
    for r in results:
        data = {
            "ticker": r.get("Ticker"),
            "setup": r.get("Setup"),
            "signal": r.get("Signal"),
            "price_at_signal": r.get("Price"),
            "stop_loss": r.get("Stop Loss"),
            "tp1": r.get("TP1"),
            "tp2": r.get("TP2"),
            "tp3": r.get("TP3"),
            "entry_zone_low": r.get("Entry Zone Low"),
            "entry_zone_high": r.get("Entry Zone High"),
            "entry_strategy": r.get("Entry Strategy"),
            "timing": r.get("Timing"),
            "score": r.get("Score"),
            "prob_tp1": r.get("Prob(TP1)"),
            "prob_tp2": r.get("Prob(TP2)"),
            "prob_tp3": r.get("Prob(TP3)"),
            "prob_sl": r.get("Prob(SL)"),
            "avg_days_tp1": r.get("Avg Days TP1"),
            "avg_days_tp2": r.get("Avg Days TP2"),
            "avg_days_tp3": r.get("Avg Days TP3"),
            "market_regime": market_regime,
            "stock_regime": r.get("Stock Regime"),
            "adx": r.get("ADX"),
            "atr": r.get("ATR"),
            "screen_date": datetime.now(),
        }
        log_prediction(data)
        count += 1

    return count


def check_open_trades(market_data=None):
    init_db()

    pending = get_pending_predictions()
    active = get_active_predictions()

    if not pending and not active:
        return {"updated": 0, "closed": 0, "still_pending": 0, "still_active": 0}

    updated = 0
    closed = 0

    if market_data is None:
        from data import get_all_market_data
        from config import TICKERS
        market_data = get_all_market_data(TICKERS)

    for pred in pending:
        ticker = pred["ticker"]
        signal_date = normalize_screen_date(pred["screen_date"])

        days_since = (datetime.now() - signal_date.to_pydatetime()).days
        if days_since > 1:
            update_prediction_status(pred["id"], "ACTIVE")
            updated += 1

    active = get_active_predictions()
    for pred in active:
        ticker = pred["ticker"]
        if ticker not in market_data:
            continue

        signal_date = normalize_screen_date(pred["screen_date"])
        df = market_data[ticker]
        future_data = df[df.index > signal_date]

        if future_data.empty:
            continue

        result = check_tp_sl_hit(
            future_data,
            pred["price_at_signal"],
            pred.get("tp1"), pred.get("tp2"), pred.get("tp3"),
            pred.get("stop_loss")
        )

        if result:
            exit_date = (signal_date + timedelta(days=result["days_held"])).isoformat()
            trade_data = {
                "prediction_id": pred["id"],
                "ticker": ticker,
                "entry_date": signal_date.isoformat(),
                "entry_price": pred["price_at_signal"],
                "exit_date": exit_date,
                "exit_price": result["exit_price"],
                "exit_reason": result["exit_reason"],
                "return_pct": result["return_pct"],
                "return_abs": result["return_abs"],
                "days_held": result["days_held"],
                "hit_tp1": int(result["hit_tp1"]),
                "hit_tp2": int(result["hit_tp2"]),
                "hit_tp3": int(result["hit_tp3"]),
                "hit_sl": int(result["hit_sl"]),
                "max_favorable": result["max_favorable"],
                "max_adverse": result["max_adverse"],
                "status": "CLOSED",
            }
            log_trade_result(trade_data)
            update_prediction_status(pred["id"], "CLOSED")
            closed += 1

    return {
        "updated": updated,
        "closed": closed,
        "still_pending": len(get_pending_predictions()),
        "still_active": len(get_active_predictions()),
    }


def auto_close_expired(max_days=20):
    init_db()

    active = get_active_predictions()
    closed_count = 0

    for pred in active:
        signal_date = normalize_screen_date(pred["screen_date"])
        days_since = (datetime.now() - signal_date.to_pydatetime()).days

        if days_since > max_days:
            trade_data = {
                "prediction_id": pred["id"],
                "ticker": pred["ticker"],
                "entry_date": signal_date.isoformat(),
                "entry_price": pred["price_at_signal"],
                "exit_date": datetime.now().isoformat(),
                "exit_price": pred["price_at_signal"],
                "exit_reason": "TIMEOUT",
                "return_pct": 0,
                "return_abs": 0,
                "days_held": days_since,
                "hit_tp1": 0, "hit_tp2": 0, "hit_tp3": 0, "hit_sl": 0,
                "max_favorable": 0, "max_adverse": 0,
                "status": "CLOSED",
            }
            log_trade_result(trade_data)
            update_prediction_status(pred["id"], "CLOSED")
            closed_count += 1

    return closed_count


def print_performance_summary():
    init_db()
    summary = get_journal_summary()

    print(f"\n  {'─'*40}")
    print(f"  PERFORMANCE JOURNAL")
    print(f"  {'─'*40}")
    print(f"  Total Predictions : {summary['total_predictions']}")
    print(f"  ├─ Pending        : {summary['pending']}")
    print(f"  ├─ Active         : {summary['active']}")
    print(f"  └─ Closed         : {summary['closed']}")
    print(f"  Total Trades      : {summary['total_trades']}")
    print(f"  ├─ Open           : {summary['open_trades']}")
    print(f"  └─ Closed         : {summary['closed_trades']}")
    print(f"  {'─'*40}")

    if (summary["closed_trades"] or 0) > 0:
        from screener_v2.performance.journal import get_trade_results
        trades = get_trade_results(filters={"status": "CLOSED"})
        if trades:
            report = full_report(trades)
            print(f"\n  Win Rate    : {report['win_rate']:.1%}")
            print(f"  Avg Return  : {report['avg_return_pct']:+.2f}%")
            print(f"  Profit Factor: {report['profit_factor']:.2f}")
    print()


def run_full_check(market_data=None):
    init_db()

    print("\n  Checking open trades...")
    result = check_open_trades(market_data)
    print(f"  Updated: {result['updated']}, Closed: {result['closed']}")

    print("  Auto-closing expired trades...")
    expired = auto_close_expired()
    print(f"  Expired: {expired}")

    print_performance_summary()

    return result
