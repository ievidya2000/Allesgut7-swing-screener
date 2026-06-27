import numpy as np
import pandas as pd
from collections import defaultdict


def win_rate(trades):
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.get("return_pct", 0) > 0)
    return wins / len(trades)


def avg_return(trades):
    if not trades:
        return 0.0
    returns = [t.get("return_pct", 0) for t in trades]
    return np.mean(returns)


def avg_win(trades):
    wins = [t.get("return_pct", 0) for t in trades if t.get("return_pct", 0) > 0]
    return np.mean(wins) if wins else 0.0


def avg_loss(trades):
    losses = [t.get("return_pct", 0) for t in trades if t.get("return_pct", 0) <= 0]
    return np.mean(losses) if losses else 0.0


def profit_factor(trades):
    gross_profit = sum(t.get("return_pct", 0) for t in trades if t.get("return_pct", 0) > 0)
    gross_loss = abs(sum(t.get("return_pct", 0) for t in trades if t.get("return_pct", 0) < 0))
    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def sharpe_ratio(returns, risk_free_rate=0.05, periods_per_year=252):
    if not returns or len(returns) < 2:
        return 0.0
    returns_arr = np.array(returns)
    excess_returns = returns_arr - risk_free_rate / periods_per_year
    std = np.std(excess_returns, ddof=1)
    if std == 0:
        return 0.0
    return np.sqrt(periods_per_year) * np.mean(excess_returns) / std


def sortino_ratio(returns, risk_free_rate=0.05, periods_per_year=252):
    if not returns or len(returns) < 2:
        return 0.0
    returns_arr = np.array(returns)
    excess_returns = returns_arr - risk_free_rate / periods_per_year
    downside = excess_returns[excess_returns < 0]
    if len(downside) == 0 or np.std(downside, ddof=1) == 0:
        return 0.0
    return np.sqrt(periods_per_year) * np.mean(excess_returns) / np.std(downside, ddof=1)


def max_drawdown(equity_curve):
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    curve = np.array(equity_curve)
    peak = np.maximum.accumulate(curve)
    drawdown = (peak - curve) / peak
    return float(np.max(drawdown)) if len(drawdown) > 0 else 0.0


def max_drawdown_abs(equity_curve):
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    curve = np.array(equity_curve)
    peak = np.maximum.accumulate(curve)
    dd = peak - curve
    return float(np.max(dd))


def calmar_ratio(returns, equity_curve, periods_per_year=252):
    if not returns or not equity_curve:
        return 0.0
    total_return = (equity_curve[-1] / equity_curve[0]) - 1
    n_periods = len(returns)
    if n_periods == 0:
        return 0.0
    annual_return = (1 + total_return) ** (periods_per_year / n_periods) - 1
    mdd = max_drawdown(equity_curve)
    if mdd == 0:
        return 0.0
    return annual_return / mdd


def win_loss_ratio(trades):
    wins = sum(1 for t in trades if t.get("return_pct", 0) > 0)
    losses = sum(1 for t in trades if t.get("return_pct", 0) <= 0)
    if losses == 0:
        return float('inf') if wins > 0 else 0.0
    return wins / losses


def setup_breakdown(trades, min_sample=3):
    breakdown = defaultdict(list)
    for t in trades:
        breakdown[t.get("setup", "UNKNOWN")].append(t)

    result = {}
    for setup, setup_trades in breakdown.items():
        count = len(setup_trades)
        result[setup] = {
            "count": count,
            "win_rate": win_rate(setup_trades),
            "avg_return": avg_return(setup_trades),
            "profit_factor": profit_factor(setup_trades),
            "avg_win": avg_win(setup_trades),
            "avg_loss": avg_loss(setup_trades),
            "reliable": count >= min_sample,
        }
    return result


def timing_breakdown(trades):
    breakdown = defaultdict(list)
    for t in trades:
        breakdown[t.get("timing", "UNKNOWN")].append(t)

    result = {}
    for timing, timing_trades in breakdown.items():
        result[timing] = {
            "count": len(timing_trades),
            "win_rate": win_rate(timing_trades),
            "avg_return": avg_return(timing_trades),
            "profit_factor": profit_factor(timing_trades),
        }
    return result


def exit_reason_breakdown(trades):
    breakdown = defaultdict(list)
    for t in trades:
        breakdown[t.get("exit_reason", "UNKNOWN")].append(t)

    result = {}
    for reason, reason_trades in breakdown.items():
        result[reason] = {
            "count": len(reason_trades),
            "avg_return": avg_return(reason_trades),
            "avg_days_held": np.mean([t.get("days_held", 0) for t in reason_trades]),
        }
    return result


def full_report(trades, equity_curve=None, benchmark_curve=None):
    if not trades:
        return {"error": "No trades to analyze"}

    returns = [t.get("return_pct", 0) / 100 for t in trades]

    report = {
        "total_trades": len(trades),
        "win_rate": win_rate(trades),
        "avg_return_pct": avg_return(trades),
        "avg_win_pct": avg_win(trades),
        "avg_loss_pct": avg_loss(trades),
        "profit_factor": profit_factor(trades),
        "win_loss_ratio": win_loss_ratio(trades),
        "sharpe_ratio": sharpe_ratio(returns),
        "sortino_ratio": sortino_ratio(returns),
    }

    if equity_curve:
        report["max_drawdown"] = max_drawdown(equity_curve)
        report["max_drawdown_abs"] = max_drawdown_abs(equity_curve)
        report["calmar_ratio"] = calmar_ratio(returns, equity_curve)
        report["total_return_pct"] = (equity_curve[-1] / equity_curve[0] - 1) * 100

    if benchmark_curve and equity_curve:
        bench_return = (benchmark_curve[-1] / benchmark_curve[0] - 1) * 100
        port_return = (equity_curve[-1] / equity_curve[0] - 1) * 100
        report["benchmark_return_pct"] = bench_return
        report["alpha"] = port_return - bench_return

    report["setup_breakdown"] = setup_breakdown(trades)
    report["timing_breakdown"] = timing_breakdown(trades)
    report["exit_reason_breakdown"] = exit_reason_breakdown(trades)

    return report


def format_report(report):
    lines = []
    lines.append("=" * 60)
    lines.append("  PERFORMANCE REPORT")
    lines.append("=" * 60)
    lines.append("")

    lines.append(f"  Total Trades     : {report.get('total_trades', 0)}")
    lines.append(f"  Win Rate         : {report.get('win_rate', 0):.1%}")
    lines.append(f"  Avg Return       : {report.get('avg_return_pct', 0):+.2f}%")
    lines.append(f"  Avg Win          : {report.get('avg_win_pct', 0):+.2f}%")
    lines.append(f"  Avg Loss         : {report.get('avg_loss_pct', 0):.2f}%")
    lines.append(f"  Profit Factor    : {report.get('profit_factor', 0):.2f}")
    lines.append(f"  Win/Loss Ratio   : {report.get('win_loss_ratio', 0):.2f}")
    lines.append("")

    lines.append("  RISK-ADJUSTED:")
    lines.append(f"  Sharpe Ratio     : {report.get('sharpe_ratio', 0):.2f}")
    lines.append(f"  Sortino Ratio    : {report.get('sortino_ratio', 0):.2f}")

    if "max_drawdown" in report:
        lines.append(f"  Max Drawdown     : {report['max_drawdown']:.2%}")
        lines.append(f"  Max DD (abs)     : Rp {report.get('max_drawdown_abs', 0):,.0f}")
        lines.append(f"  Calmar Ratio     : {report.get('calmar_ratio', 0):.2f}")
        lines.append(f"  Total Return     : {report.get('total_return_pct', 0):+.2f}%")

    if "benchmark_return_pct" in report:
        lines.append("")
        lines.append(f"  vs IHSG          : {report.get('benchmark_return_pct', 0):+.2f}%")
        lines.append(f"  Alpha            : {report.get('alpha', 0):+.2f}%")

    lines.append("")

    if report.get("setup_breakdown"):
        lines.append("  BY SETUP:")
        lines.append("  " + "-" * 62)
        lines.append(f"  {'Setup':<16s} {'Trades':>6s} {'WinRate':>8s} {'AvgRet':>8s} {'PF':>6s} {'OK':>4s}")
        lines.append("  " + "-" * 62)
        for setup, stats in report["setup_breakdown"].items():
            reliable = "✓" if stats.get("reliable", False) else "⚠"
            lines.append(
                f"  {setup:<16s} {stats['count']:>6d} "
                f"{stats['win_rate']:>7.1%} {stats['avg_return']:>+7.2f}% "
                f"{stats['profit_factor']:>5.2f} {reliable:>4s}"
            )
        lines.append("  " + "-" * 62)

    if report.get("timing_breakdown"):
        lines.append("")
        lines.append("  BY TIMING:")
        lines.append("  " + "-" * 48)
        lines.append(f"  {'Timing':<20s} {'Trades':>6s} {'WinRate':>8s} {'AvgRet':>8s}")
        lines.append("  " + "-" * 48)
        for timing, stats in report["timing_breakdown"].items():
            lines.append(
                f"  {timing:<20s} {stats['count']:>6d} "
                f"{stats['win_rate']:>7.1%} {stats['avg_return']:>+7.2f}%"
            )
        lines.append("  " + "-" * 48)

    if report.get("exit_reason_breakdown"):
        lines.append("")
        lines.append("  BY EXIT REASON:")
        lines.append("  " + "-" * 52)
        lines.append(f"  {'Reason':<12s} {'Count':>6s} {'AvgRet':>8s} {'AvgDays':>8s}")
        lines.append("  " + "-" * 52)
        for reason, stats in report["exit_reason_breakdown"].items():
            lines.append(
                f"  {reason:<12s} {stats['count']:>6d} "
                f"{stats['avg_return']:>+7.2f}% {stats['avg_days_held']:>7.1f}"
            )
        lines.append("  " + "-" * 52)

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)
