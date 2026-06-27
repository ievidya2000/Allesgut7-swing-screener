import sys
import argparse
from datetime import datetime, timedelta

from screener_v2.performance.journal import init_db, get_all_predictions, get_trade_results, get_journal_summary
from screener_v2.performance.metrics import full_report, format_report
from screener_v2.utils.date_utils import safe_screen_date_str


def cmd_backtest(args):
    from performance.backtest import run_historical_backtest

    start = args.start_date
    end = args.end_date

    if start:
        start = datetime.fromisoformat(start)
    else:
        start = datetime.now() - timedelta(days=365)

    if end:
        end = datetime.fromisoformat(end)
    else:
        end = datetime.now()

    run_historical_backtest(start, end)


def cmd_calibration(args):
    from performance.calibration import print_calibration_report, plot_reliability_diagram

    print_calibration_report()
    if args.plot:
        plot_reliability_diagram(args.plot)


def cmd_portfolio(args):
    from performance.portfolio import simulate_portfolio, plot_equity_curve

    start = args.start_date
    end = args.end_date

    if start:
        start = datetime.fromisoformat(start)
    else:
        start = datetime.now() - timedelta(days=365)

    if end:
        end = datetime.fromisoformat(end)
    else:
        end = datetime.now()

    report, sim = simulate_portfolio(start, end, args.capital)

    if args.plot:
        plot_equity_curve(sim, args.plot)


def cmd_check(args):
    from performance.realtime import run_full_check

    run_full_check()


def cmd_journal(args):
    init_db()

    if args.summary:
        summary = get_journal_summary()
        print(f"\n  Journal Summary:")
        for k, v in summary.items():
            print(f"    {k}: {v}")
        return

    filters = {}
    if args.status:
        filters["status"] = args.status
    if args.ticker:
        filters["ticker"] = args.ticker

    predictions = get_all_predictions(filters if filters else None)

    if not predictions:
        print("  No predictions found")
        return

    print(f"\n  Found {len(predictions)} predictions:\n")
    print(f"  {'ID':>5s} {'Ticker':<10s} {'Setup':<16s} {'Price':>8s} {'Status':<10s} {'Date':<12s}")
    print("  " + "-" * 65)

    for p in predictions[:50]:
        print(
            f"  {p['id']:>5d} {p['ticker']:<10s} {p['setup']:<16s} "
            f"{p['price_at_signal']:>8.2f} {p['status']:<10s} {safe_screen_date_str(p['screen_date']):<12s}"
        )

    if len(predictions) > 50:
        print(f"\n  ... and {len(predictions) - 50} more")


def cmd_trades(args):
    init_db()

    filters = {}
    if args.status:
        filters["status"] = args.status
    if args.ticker:
        filters["ticker"] = args.ticker
    if args.exit_reason:
        filters["exit_reason"] = args.exit_reason

    trades = get_trade_results(filters if filters else None)

    if not trades:
        print("  No trades found")
        return

    print(f"\n  Found {len(trades)} trades:\n")
    print(f"  {'Ticker':<10s} {'Setup':<16s} {'Entry':>8s} {'Exit':>8s} {'Return':>8s} {'Reason':<8s} {'Days':>4s}")
    print("  " + "-" * 70)

    for t in trades[:50]:
        print(
            f"  {t['ticker']:<10s} {t.get('setup', 'N/A'):<16s} "
            f"{t.get('entry_price', 0):>8.2f} {t.get('exit_price', 0):>8.2f} "
            f"{t.get('return_pct', 0):>+7.2f}% {t.get('exit_reason', ''):<8s} "
            f"{t.get('days_held', 0):>4d}"
        )

    if trades:
        report = full_report(trades)
        print(f"\n{format_report(report)}")


def cmd_report(args):
    init_db()

    trades = get_trade_results()
    if not trades:
        print("  No trades available for report")
        return

    report = full_report(trades)
    print(format_report(report))


def cmd_optimize(args):
    from adaptive.optimizer import ParameterOptimizer

    start = args.start_date
    end = args.end_date

    if start:
        start = datetime.fromisoformat(start)
    else:
        start = datetime.now() - timedelta(days=365)

    if end:
        end = datetime.fromisoformat(end)
    else:
        end = datetime.now()

    optimizer = ParameterOptimizer()
    best_config, results = optimizer.optimize(
        start_date=start,
        end_date=end,
        max_combinations=args.max_combos,
    )

    if args.show_top:
        print(f"\n  Top {args.show_top} configurations:")
        top = optimizer.get_top_configs(args.show_top)
        for i, cfg in enumerate(top, 1):
            print(f"  {i}. Sharpe={cfg['sharpe']:.4f} WinRate={cfg['win_rate']:.1%} "
                  f"PF={cfg['profit_factor']:.2f} Return={cfg['total_return']:.2%} "
                  f"Params={cfg['params']}")


def cmd_rolling_optimize(args):
    from adaptive.optimizer import ParameterOptimizer

    optimizer = ParameterOptimizer()

    if args.history:
        optimizer.print_history(args.history_count)
        return

    best_config, window_results, stability = optimizer.rolling_optimize(
        window_months=args.window_months,
        step_months=args.step_months,
        max_combinations=args.max_combos,
    )

    print(f"\n  Optimization complete! Parameters saved to adaptive_config.json")
    print(f"  Run screener to use new parameters.")


def cmd_daily(args):
    from performance.daily_summary import run_daily_summary
    run_daily_summary()


def main():
    parser = argparse.ArgumentParser(
        description="Swing Screener Performance & Adaptive Tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  backtest         Run historical walk-forward backtest
  calibration      Analyze MC probability calibration
  portfolio        Simulate portfolio with position sizing
  check            Check and update open trades (real-time mode)
  journal          View prediction journal
  trades           View trade results
  report           Generate full performance report
  optimize         Optimize indicator parameters (Phase 1)
  rolling-optimize Rolling window parameter optimization (Phase 2)
  daily            Generate daily performance summary
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    p_bt = subparsers.add_parser("backtest", help="Run historical backtest")
    p_bt.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    p_bt.add_argument("--end-date", help="End date (YYYY-MM-DD)")

    p_cal = subparsers.add_parser("calibration", help="MC probability calibration")
    p_cal.add_argument("--plot", nargs="?", const="calibration_plot.png", help="Save calibration plot")

    p_port = subparsers.add_parser("portfolio", help="Portfolio simulation")
    p_port.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    p_port.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    p_port.add_argument("--capital", type=float, default=100_000_000, help="Initial capital (default: 100M)")
    p_port.add_argument("--plot", nargs="?", const="equity_curve.png", help="Save equity curve plot")

    p_check = subparsers.add_parser("check", help="Check open trades")

    p_journal = subparsers.add_parser("journal", help="View prediction journal")
    p_journal.add_argument("--status", choices=["PENDING", "ACTIVE", "CLOSED"], help="Filter by status")
    p_journal.add_argument("--ticker", help="Filter by ticker")
    p_journal.add_argument("--summary", action="store_true", help="Show summary only")

    p_trades = subparsers.add_parser("trades", help="View trade results")
    p_trades.add_argument("--status", choices=["OPEN", "CLOSED"], help="Filter by status")
    p_trades.add_argument("--ticker", help="Filter by ticker")
    p_trades.add_argument("--exit-reason", choices=["TP1", "TP2", "TP3", "SL", "TIMEOUT"], help="Filter by exit reason")

    p_report = subparsers.add_parser("report", help="Full performance report")

    p_opt = subparsers.add_parser("optimize", help="Optimize indicator parameters")
    p_opt.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    p_opt.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    p_opt.add_argument("--max-combos", type=int, default=50, help="Max parameter combinations to test (default: 50)")
    p_opt.add_argument("--show-top", type=int, default=10, help="Show top N results")

    p_roll = subparsers.add_parser("rolling-optimize", help="Rolling window parameter optimization")
    p_roll.add_argument("--window-months", type=int, default=6, help="Optimization window size in months (default: 6)")
    p_roll.add_argument("--step-months", type=int, default=1, help="Step size in months (default: 1)")
    p_roll.add_argument("--max-combos", type=int, default=50, help="Max parameter combinations per window (default: 50)")
    p_roll.add_argument("--history", action="store_true", help="Show optimization history")
    p_roll.add_argument("--history-count", type=int, default=10, help="Number of history entries to show")

    p_daily = subparsers.add_parser("daily", help="Generate daily performance summary")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    commands = {
        "backtest": cmd_backtest,
        "calibration": cmd_calibration,
        "portfolio": cmd_portfolio,
        "check": cmd_check,
        "journal": cmd_journal,
        "trades": cmd_trades,
        "report": cmd_report,
        "optimize": cmd_optimize,
        "rolling-optimize": cmd_rolling_optimize,
        "daily": cmd_daily,
    }

    try:
        commands[args.command](args)
    except Exception as e:
        print(f"\n  Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
