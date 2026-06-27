"""Daily performance summary generator."""

import json
import csv
import logging
from datetime import datetime, timedelta
from pathlib import Path

from screener_v2.performance.journal import (
    init_db, get_all_predictions, get_trade_results, get_journal_summary
)
from screener_v2.performance.realtime import run_full_check
from screener_v2.performance.metrics import (
    win_rate, avg_return, profit_factor
)

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

DAILY_LOG = LOG_DIR / "daily_summary.json"
DAILY_REPORT = LOG_DIR / "daily_report.txt"
DAILY_CSV = LOG_DIR / "daily_report.csv"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "daily_summary.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("daily_summary")


def get_today_summary():
    init_db()

    today = datetime.now().strftime("%Y-%m-%d")

    all_preds = get_all_predictions()
    today_preds = [p for p in all_preds if p.get("screen_date", "").startswith(today)]

    all_trades = get_trade_results(filters={"status": "CLOSED"})
    today_trades = [t for t in all_trades if t.get("exit_date", "").startswith(today)]

    summary = get_journal_summary()

    today_win_rate = win_rate(today_trades) if today_trades else 0
    today_avg_return = avg_return(today_trades) if today_trades else 0

    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    recent_trades = [t for t in all_trades if t.get("exit_date", "") >= week_ago]
    recent_win_rate = win_rate(recent_trades) if recent_trades else 0
    recent_avg_return = avg_return(recent_trades) if recent_trades else 0

    overall_win_rate = win_rate(all_trades) if all_trades else 0
    overall_avg_return = avg_return(all_trades) if all_trades else 0
    overall_pf = profit_factor(all_trades) if all_trades else 0

    return {
        "date": today,
        "timestamp": datetime.now().isoformat(),

        "today_predictions": len(today_preds),
        "today_trades_closed": len(today_trades),
        "today_win_rate": today_win_rate,
        "today_avg_return": today_avg_return,

        "recent_trades": len(recent_trades),
        "recent_win_rate": recent_win_rate,
        "recent_avg_return": recent_avg_return,

        "total_predictions": summary["total_predictions"],
        "pending": summary["pending"],
        "active": summary["active"],
        "closed": summary["closed"],
        "total_trades": summary["total_trades"],
        "overall_win_rate": overall_win_rate,
        "overall_avg_return": overall_avg_return,
        "overall_profit_factor": overall_pf,

        "today_trade_details": [
            {
                "ticker": t.get("ticker"),
                "setup": t.get("setup"),
                "return_pct": t.get("return_pct"),
                "exit_reason": t.get("exit_reason"),
                "days_held": t.get("days_held"),
            }
            for t in today_trades
        ],
    }


def format_daily_summary(summary):
    lines = []
    lines.append("=" * 60)
    lines.append(f"  DAILY PERFORMANCE SUMMARY - {summary['date']}")
    lines.append("=" * 60)
    lines.append("")

    lines.append("  TODAY'S ACTIVITY:")
    lines.append(f"  ├─ New Predictions : {summary['today_predictions']}")
    lines.append(f"  ├─ Trades Closed   : {summary['today_trades_closed']}")
    lines.append(f"  ├─ Win Rate        : {summary['today_win_rate']:.1%}")
    lines.append(f"  └─ Avg Return      : {summary['today_avg_return']:+.2f}%")
    lines.append("")

    lines.append("  RECENT PERFORMANCE (7 days):")
    lines.append(f"  ├─ Trades          : {summary['recent_trades']}")
    lines.append(f"  ├─ Win Rate        : {summary['recent_win_rate']:.1%}")
    lines.append(f"  └─ Avg Return      : {summary['recent_avg_return']:+.2f}%")
    lines.append("")

    lines.append("  OVERALL STATUS:")
    lines.append(f"  ├─ Total Predictions : {summary['total_predictions']}")
    lines.append(f"  │  ├─ Pending        : {summary['pending']}")
    lines.append(f"  │  ├─ Active         : {summary['active']}")
    lines.append(f"  │  └─ Closed         : {summary['closed']}")
    lines.append(f"  ├─ Total Trades      : {summary['total_trades']}")
    lines.append(f"  ├─ Win Rate          : {summary['overall_win_rate']:.1%}")
    lines.append(f"  ├─ Avg Return        : {summary['overall_avg_return']:+.2f}%")
    lines.append(f"  └─ Profit Factor     : {summary['overall_profit_factor']:.2f}")
    lines.append("")

    if summary['today_trade_details']:
        lines.append("  TODAY'S CLOSED TRADES:")
        lines.append(f"  {'Ticker':<10s} {'Setup':<16s} {'Return':>8s} {'Reason':<8s} {'Days':>4s}")
        lines.append("  " + "-" * 50)
        for t in summary['today_trade_details']:
            lines.append(
                f"  {t['ticker']:<10s} {t.get('setup', 'N/A'):<16s} "
                f"{t.get('return_pct', 0):>+7.2f}% {t.get('exit_reason', ''):<8s} "
                f"{t.get('days_held', 0):>4d}"
            )
    else:
        lines.append("  No trades closed today.")

    lines.append("")
    lines.append("=" * 60)
    lines.append("  ⚠️  Think First. Trade Second. DYOR - Do Your Own Research")
    lines.append("=" * 60)

    return "\n".join(lines)


def save_daily_summary(summary):
    history = []
    if DAILY_LOG.exists():
        try:
            with open(DAILY_LOG, 'r') as f:
                history = json.load(f)
        except Exception:
            history = []

    history.append(summary)

    if len(history) > 90:
        history = history[-90:]

    with open(DAILY_LOG, 'w') as f:
        json.dump(history, f, indent=2)

    report = format_daily_summary(summary)
    with open(DAILY_REPORT, 'w') as f:
        f.write(report)

    logger.info(f"Daily summary saved for {summary['date']}")


def export_summary_to_csv(summary, filepath):
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)

        writer.writerow(["Daily Performance Summary", summary['date']])
        writer.writerow([])

        writer.writerow(["Metric", "Value"])
        writer.writerow(["Date", summary['date']])
        writer.writerow(["Today Predictions", summary['today_predictions']])
        writer.writerow(["Today Trades Closed", summary['today_trades_closed']])
        writer.writerow(["Today Win Rate", f"{summary['today_win_rate']:.1%}"])
        writer.writerow(["Today Avg Return", f"{summary['today_avg_return']:+.2f}%"])
        writer.writerow([])
        writer.writerow(["Recent Trades (7d)", summary['recent_trades']])
        writer.writerow(["Recent Win Rate", f"{summary['recent_win_rate']:.1%}"])
        writer.writerow(["Recent Avg Return", f"{summary['recent_avg_return']:+.2f}%"])
        writer.writerow([])
        writer.writerow(["Total Predictions", summary['total_predictions']])
        writer.writerow(["Pending", summary['pending']])
        writer.writerow(["Active", summary['active']])
        writer.writerow(["Closed", summary['closed']])
        writer.writerow(["Total Trades", summary['total_trades']])
        writer.writerow(["Overall Win Rate", f"{summary['overall_win_rate']:.1%}"])
        writer.writerow(["Overall Avg Return", f"{summary['overall_avg_return']:+.2f}%"])
        writer.writerow(["Overall Profit Factor", f"{summary['overall_profit_factor']:.2f}"])
        writer.writerow([])

        if summary['today_trade_details']:
            writer.writerow(["Today's Closed Trades"])
            writer.writerow(["Ticker", "Setup", "Return %", "Exit Reason", "Days Held"])
            for t in summary['today_trade_details']:
                writer.writerow([
                    t['ticker'],
                    t.get('setup', 'N/A'),
                    f"{t.get('return_pct', 0):+.2f}",
                    t.get('exit_reason', ''),
                    t.get('days_held', 0),
                ])

    logger.info(f"CSV exported to {filepath}")


def export_history_to_csv(history, filepath):
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)

        writer.writerow([
            "Date", "Today Predictions", "Today Trades Closed",
            "Today Win Rate", "Today Avg Return",
            "Recent Trades", "Recent Win Rate", "Recent Avg Return",
            "Total Predictions", "Pending", "Active", "Closed",
            "Total Trades", "Overall Win Rate", "Overall Avg Return",
            "Overall Profit Factor"
        ])

        for s in history:
            writer.writerow([
                s['date'],
                s['today_predictions'],
                s['today_trades_closed'],
                f"{s['today_win_rate']:.4f}",
                f"{s['today_avg_return']:.4f}",
                s['recent_trades'],
                f"{s['recent_win_rate']:.4f}",
                f"{s['recent_avg_return']:.4f}",
                s['total_predictions'],
                s['pending'],
                s['active'],
                s['closed'],
                s['total_trades'],
                f"{s['overall_win_rate']:.4f}",
                f"{s['overall_avg_return']:.4f}",
                f"{s['overall_profit_factor']:.4f}",
            ])

    logger.info(f"History CSV exported to {filepath}")


def check_and_archive():
    if not DAILY_LOG.exists():
        return None, None

    with open(DAILY_LOG, 'r') as f:
        history = json.load(f)

    if len(history) < 90:
        return None, None

    archive_data = history[:90]
    remaining = history[90:]

    archive_date = datetime.now().strftime("%Y%m%d")
    archive_path = LOG_DIR / f"archive_{archive_date}.json"
    csv_path = LOG_DIR / f"archive_{archive_date}.csv"

    with open(archive_path, 'w') as f:
        json.dump(archive_data, f, indent=2)

    export_history_to_csv(archive_data, csv_path)

    with open(DAILY_LOG, 'w') as f:
        json.dump(remaining, f, indent=2)

    logger.info(f"Archived {len(archive_data)} days to {archive_path}")

    return str(archive_path), str(csv_path)


def run_daily_summary():
    from notifications import send_daily_summary_email, send_archive_email

    logger.info("Starting daily performance summary...")

    logger.info("Checking open trades...")
    run_full_check()

    logger.info("Generating summary...")
    summary = get_today_summary()
    save_daily_summary(summary)

    export_summary_to_csv(summary, DAILY_CSV)

    report = format_daily_summary(summary)
    print(report)

    logger.info("Sending email notification...")
    send_daily_summary_email(summary, report, attachments=[str(DAILY_CSV)])

    archive_path, csv_path = check_and_archive()
    if archive_path:
        logger.info("Sending archive email...")
        period = f"Last 90 days ending {summary['date']}"
        send_archive_email(archive_path, csv_path, period)

    logger.info("Daily summary complete.")
    return summary
