import numpy as np
import pandas as pd
from itertools import product
from datetime import datetime, timedelta
import json
from pathlib import Path

from config import TICKERS, MAX_POSITIONS, INITIAL_CAPITAL, ADX_THRESHOLD
from data import get_all_market_data, get_jkse_data
from signals import determine_market_regime
from adaptive.config import (
    save_adaptive_config, DEFAULT_CONFIG,
    load_adaptive_config, save_to_history, get_latest_history, has_config_changed
)

MODELS_DIR = Path(__file__).parent / "models"
RESULTS_PATH = MODELS_DIR / "optimization_results.json"


class ParameterOptimizer:
    def __init__(self):
        self.param_grid = {
            # Multi-SuperTrend parameters
            "st_fast_multiplier": [1.5, 2.0, 2.5],
            "st_med_multiplier": [3.0, 3.5, 4.0],
            "st_slow_multiplier": [3.5, 4.0, 4.5],
            "adx_threshold": [20, 22, 25, 28],
            "rr1": [1.5, 2.0, 2.5],
            "sl_multiplier": [1.2, 1.5, 2.0],
            "donchian_period": [15, 20, 25],
            "volume_ma_period": [15, 20, 25],
            "rsi_period": [10, 14, 20],
            "rsi_oversold": [25, 30, 35],
            "stoch_k": [10, 14, 20],
            "stoch_oversold": [15, 20, 25],
            "entry_zone_max_atr": [0.5, 0.75, 1.0],
            "entry_zone_max_pct": [0.03, 0.04, 0.05],
            # Too Late Filter parameters
            "max_runup": [0.20, 0.30, 0.40],
            "max_runup_block": [0.40, 0.50, 0.60],
            "max_price_to_ma20": [0.10, 0.15, 0.20],
            # Volume Quality parameters
            "min_dollar_volume": [300_000_000, 500_000_000, 1_000_000_000],
            # Pattern Score weight
            "score_w_pattern": [0.3, 0.5, 0.7],
        }

        self.results = []
        self.best_config = None
        self.best_sharpe = -999

    def _precompute_indicators(self, market_data, params):
        from indicators import calculate_full_indicators

        precomputed = {}
        for ticker, df in market_data.items():
            try:
                if len(df) < 50:
                    continue
                full = calculate_full_indicators(df, custom_params=params)
                precomputed[ticker] = full
            except Exception:
                continue
        return precomputed

    def _scan_from_precomputed(self, precomputed, signal_date, market_regime, params):
        from signals import determine_stock_regime, classify_setup_state
        from risk import calculate_tp_sl

        results = []
        adx_thresh = params.get("adx_threshold", ADX_THRESHOLD)

        for ticker, full in precomputed.items():
            try:
                df_slice = full[full.index <= signal_date]
                if len(df_slice) < 100:
                    continue

                last = df_slice.iloc[-1]
                stock_regime = determine_stock_regime(df_slice)
                setup, is_valid = classify_setup_state(df_slice, stock_regime, params)

                if not is_valid:
                    continue

                if market_regime == "BEAR" and setup != "EARLY_REVERSAL":
                    continue

                close = last["Close"]
                atr = last.get("atr_rm", None)
                if atr is None or pd.isna(atr) or atr / close < 0.001:
                    continue

                sl, tp1, tp2, tp3, profit_pct, risk_pct = calculate_tp_sl(
                    close, atr, "BUY", params
                )
                if sl is None:
                    continue

                results.append({
                    "ticker": ticker,
                    "setup": setup,
                    "price_at_signal": round(close, 2),
                    "stop_loss": round(sl, 2),
                    "tp1": round(tp1, 2) if tp1 else None,
                    "tp2": round(tp2, 2) if tp2 else None,
                    "tp3": round(tp3, 2) if tp3 else None,
                })
            except Exception:
                continue

        return results

    def _run_single_backtest(self, precomputed, market_data, market_regime, signal_dates, params):
        positions = {}
        cash = INITIAL_CAPITAL
        equity_curve = []
        trades_log = []

        for sig_date in signal_dates:
            for ticker, pos in list(positions.items()):
                if ticker not in market_data:
                    continue
                df = market_data[ticker]
                future_data = df[df.index > pos["entry_date"]]
                if future_data.empty:
                    continue

                today_data = future_data[future_data.index <= sig_date]
                if today_data.empty:
                    continue

                last_row = today_data.iloc[-1]
                high, low, close = last_row["High"], last_row["Low"], last_row["Close"]

                if pos["sl"] and low <= pos["sl"]:
                    shares = pos["shares"]
                    proceeds = shares * pos["sl"]
                    pnl = proceeds - pos["cost"]
                    cash += proceeds
                    trades_log.append({
                        "return_pct": (pnl / pos["cost"]) * 100,
                        "exit_reason": "SL",
                    })
                    del positions[ticker]
                    continue

                if pos.get("tp1") and high >= pos["tp1"] and not pos.get("tp1_hit"):
                    pos["tp1_hit"] = True
                    pos["sl"] = pos["entry_price"]

                if pos.get("tp2") and high >= pos["tp2"] and pos.get("tp1_hit") and not pos.get("tp2_hit"):
                    pos["tp2_hit"] = True
                    pos["sl"] = pos["tp2"]

                if pos.get("tp3") and high >= pos["tp3"] and pos.get("tp2_hit"):
                    shares = pos["shares"]
                    proceeds = shares * pos["tp3"]
                    pnl = proceeds - pos["cost"]
                    cash += proceeds
                    trades_log.append({
                        "return_pct": (pnl / pos["cost"]) * 100,
                        "exit_reason": "TP3",
                    })
                    del positions[ticker]
                    continue

                days_held = (sig_date - pos["entry_date"]).days
                if days_held > 35:
                    shares = pos["shares"]
                    proceeds = shares * close
                    pnl = proceeds - pos["cost"]
                    cash += proceeds
                    trades_log.append({
                        "return_pct": (pnl / pos["cost"]) * 100,
                        "exit_reason": "TIMEOUT",
                    })
                    del positions[ticker]

            results = self._scan_from_precomputed(precomputed, sig_date, market_regime, params)
            for r in results:
                ticker = r["ticker"]
                if ticker in positions or len(positions) >= MAX_POSITIONS:
                    continue

                entry_price = r["price_at_signal"]
                if ticker in market_data:
                    df = market_data[ticker]
                    future_data = df[df.index > sig_date]
                    if not future_data.empty:
                        entry_price = future_data["Open"].iloc[0]

                sl = r["stop_loss"]
                risk_per_share = entry_price - sl
                if risk_per_share <= 0:
                    continue

                rr1 = params.get("rr1", 2.5)
                rr2 = params.get("rr2", 2.5)
                rr3 = params.get("rr3", 3.0)
                tp1 = entry_price + (risk_per_share * rr1)
                tp2 = entry_price + (risk_per_share * rr2)
                tp3 = entry_price + (risk_per_share * rr3)

                risk_per_share = entry_price - sl
                if risk_per_share <= 0:
                    continue

                risk_amount = cash * 0.02
                shares = int(risk_amount / risk_per_share)
                if shares <= 0:
                    continue

                cost = shares * entry_price
                if cost > cash:
                    continue

                cash -= cost
                positions[ticker] = {
                    "shares": shares,
                    "entry_price": entry_price,
                    "cost": cost,
                    "entry_date": sig_date,
                    "sl": sl,
                    "tp1": round(tp1, 2),
                    "tp2": round(tp2, 2),
                    "tp3": round(tp3, 2),
                    "tp1_hit": False,
                    "tp2_hit": False,
                }

            total_value = cash
            for ticker, pos in positions.items():
                if ticker in market_data:
                    df = market_data[ticker]
                    recent = df[df.index <= sig_date]
                    if not recent.empty:
                        total_value += pos["shares"] * recent["Close"].iloc[-1]
                    else:
                        total_value += pos["cost"]
                else:
                    total_value += pos["cost"]

            equity_curve.append(total_value)

        for ticker, pos in list(positions.items()):
            if ticker in market_data:
                df = market_data[ticker]
                last_close = df["Close"].iloc[-1]
                shares = pos["shares"]
                proceeds = shares * last_close
                pnl = proceeds - pos["cost"]
                cash += proceeds
                trades_log.append({
                    "return_pct": (pnl / pos["cost"]) * 100,
                    "exit_reason": "END",
                })

        return trades_log, equity_curve

    def _calculate_metrics(self, trades_log, equity_curve, capital=INITIAL_CAPITAL):
        if not trades_log or not equity_curve:
            return {
                "sharpe": 0, "win_rate": 0, "profit_factor": 0,
                "total_return": 0, "max_drawdown": 0, "num_trades": 0,
            }

        returns = [t["return_pct"] / 100 for t in trades_log]
        wins = sum(1 for r in returns if r > 0)
        win_rate = wins / len(returns) if returns else 0

        gross_profit = sum(r for r in returns if r > 0)
        gross_loss = abs(sum(r for r in returns if r < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (
            float("inf") if gross_profit > 0 else 0
        )

        eq = np.array(equity_curve)
        peaks = np.maximum.accumulate(eq)
        drawdowns = (peaks - eq) / peaks
        max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0

        total_return = (equity_curve[-1] / capital - 1) if equity_curve else 0

        if len(equity_curve) > 1:
            eq = np.array(equity_curve, dtype=float)
            daily_returns = np.diff(eq) / eq[:-1]
            excess = daily_returns - 0.05 / 252
            if np.std(excess) > 0:
                sharpe = np.sqrt(252) * np.mean(excess) / np.std(excess)
            else:
                sharpe = 0
        else:
            sharpe = 0

        return {
            "sharpe": round(sharpe, 4),
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 4),
            "total_return": round(total_return, 4),
            "max_drawdown": round(max_dd, 4),
            "num_trades": len(trades_log),
        }

    def optimize(self, market_data=None, start_date=None, end_date=None,
                 max_combinations=50, progress_callback=None):
        MODELS_DIR.mkdir(parents=True, exist_ok=True)

        if end_date is None:
            end_date = datetime.now()
        if start_date is None:
            start_date = end_date - timedelta(days=365)

        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date)

        print(f"\n{'='*60}")
        print(f"  PARAMETER OPTIMIZATION (Fast Mode)")
        print(f"  Period: {start_date.date()} → {end_date.date()}")
        print(f"{'='*60}\n")

        if market_data is None:
            print("[1/4] Loading market data...")
            market_data = get_all_market_data(TICKERS)
            print(f"  Loaded {len(market_data)} tickers")

        jkse_df = get_jkse_data()
        market_regime = determine_market_regime(jkse_df) if jkse_df is not None else "SIDEWAYS"
        print(f"  Market Regime: {market_regime}")

        signal_dates = pd.bdate_range(start=start_date, end=end_date, freq="B")

        param_combos = list(product(*self.param_grid.values()))
        param_names = list(self.param_grid.keys())

        if len(param_combos) > max_combinations:
            indices = np.random.choice(len(param_combos), max_combinations, replace=False)
            param_combos = [param_combos[i] for i in indices]

        total = len(param_combos)
        print(f"\n[2/4] Pre-computing indicators for {total} combinations...")

        precomputed_cache = {}
        for i, combo in enumerate(param_combos):
            params = dict(zip(param_names, combo))
            full_params = DEFAULT_CONFIG.copy()
            full_params.update(params)

            if progress_callback:
                progress_callback(i / total, f"Pre-computing {i+1}/{total}...")
            elif (i + 1) % 5 == 0 or i == 0:
                print(f"  [{i+1}/{total}] Pre-computing indicators...")

            precomputed_cache[combo] = self._precompute_indicators(market_data, full_params)

        print(f"\n[3/4] Running backtests with pre-computed data...")

        self.results = []

        for i, combo in enumerate(param_combos):
            params = dict(zip(param_names, combo))
            full_params = DEFAULT_CONFIG.copy()
            full_params.update(params)

            if progress_callback:
                progress_callback(i / total, f"Backtesting {i+1}/{total}...")

            trades_log, equity_curve = self._run_single_backtest(
                precomputed_cache[combo], market_data, market_regime, signal_dates, full_params
            )

            metrics = self._calculate_metrics(trades_log, equity_curve)
            metrics["params"] = params
            metrics["combo_index"] = i

            self.results.append(metrics)

            if metrics["sharpe"] > self.best_sharpe:
                self.best_sharpe = metrics["sharpe"]
                self.best_config = full_params

            if (i + 1) % 10 == 0:
                print(f"  [{i+1}/{total}] Best Sharpe so far: {self.best_sharpe:.4f}")

        print(f"\n[4/4] Saving results...")
        self._save_results()

        print(f"\n[4/4] Optimization complete!")
        self._print_best()

        return self.best_config, self.results

    def _save_results(self):
        sorted_results = sorted(self.results, key=lambda x: x["sharpe"], reverse=True)

        save_data = {
            "timestamp": datetime.now().isoformat(),
            "best_config": self.best_config,
            "best_sharpe": self.best_sharpe,
            "top_10": sorted_results[:10],
            "total_combinations": len(self.results),
        }

        with open(RESULTS_PATH, "w") as f:
            json.dump(save_data, f, indent=2)

        if self.best_config:
            save_adaptive_config(self.best_config)

    def _print_best(self):
        if not self.best_config:
            print("  No valid results found.")
            return

        print(f"\n{'='*60}")
        print("  BEST PARAMETERS FOUND")
        print(f"{'='*60}\n")

        key_params = [
            "st_fast_multiplier", "st_med_multiplier", "st_slow_multiplier",
            "adx_threshold", "rr1",
            "sl_multiplier", "donchian_period", "volume_ma_period",
            "rsi_period", "rsi_oversold", "stoch_k", "stoch_oversold",
            "entry_zone_max_atr", "entry_zone_max_pct",
        ]

        for param in key_params:
            default_val = DEFAULT_CONFIG.get(param, "N/A")
            best_val = self.best_config.get(param, "N/A")
            changed = " ← CHANGED" if default_val != best_val else ""
            print(f"  {param:<30s} {str(default_val):>8s} → {str(best_val):>8s}{changed}")

        sorted_results = sorted(self.results, key=lambda x: x["sharpe"], reverse=True)
        best_metrics = sorted_results[0] if sorted_results else {}

        print(f"\n  PERFORMANCE IMPROVEMENT:")
        print(f"  {'Metric':<20s} {'Value':>10s}")
        print(f"  {'-'*32}")
        print(f"  {'Sharpe Ratio':<20s} {best_metrics.get('sharpe', 0):>10.4f}")
        print(f"  {'Win Rate':<20s} {best_metrics.get('win_rate', 0):>9.1%}")
        print(f"  {'Profit Factor':<20s} {best_metrics.get('profit_factor', 0):>10.2f}")
        print(f"  {'Total Return':<20s} {best_metrics.get('total_return', 0):>9.2%}")
        print(f"  {'Max Drawdown':<20s} {best_metrics.get('max_drawdown', 0):>9.2%}")
        print(f"  {'Num Trades':<20s} {best_metrics.get('num_trades', 0):>10d}")
        print(f"\n{'='*60}")

    def get_results_df(self):
        if not self.results:
            return pd.DataFrame()

        rows = []
        for r in self.results:
            row = {k: v for k, v in r.items() if k != "params"}
            row.update(r.get("params", {}))
            rows.append(row)

        return pd.DataFrame(rows)

    def get_top_configs(self, n=10):
        sorted_results = sorted(self.results, key=lambda x: x["sharpe"], reverse=True)
        return sorted_results[:n]

    def rolling_optimize(self, market_data=None, window_months=6, step_months=1,
                         max_combinations=50, progress_callback=None):
        MODELS_DIR.mkdir(parents=True, exist_ok=True)

        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)

        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date)

        print(f"\n{'='*60}")
        print(f"  ROLLING PARAMETER OPTIMIZATION")
        print(f"  Full Period: {start_date.date()} → {end_date.date()}")
        print(f"  Window: {window_months} months | Step: {step_months} months")
        print(f"{'='*60}\n")

        if market_data is None:
            print("[1/5] Loading market data...")
            market_data = get_all_market_data(TICKERS)
            print(f"  Loaded {len(market_data)} tickers")

        current_config = load_adaptive_config()
        print(f"\n  Current adaptive config:")
        for key in ["st_fast_multiplier", "st_med_multiplier", "st_slow_multiplier",
                     "adx_threshold", "rr1", "sl_multiplier",
                     "rsi_period", "rsi_oversold", "stoch_k", "stoch_oversold"]:
            print(f"    {key}: {current_config.get(key, 'N/A')}")

        optimization_windows = []
        window_end = end_date
        window_start = end_date - timedelta(days=window_months * 30)

        while window_start >= start_date:
            optimization_windows.append({
                "start": window_start,
                "end": window_end,
            })
            window_end = window_end - timedelta(days=step_months * 30)
            window_start = window_start - timedelta(days=step_months * 30)

        optimization_windows.reverse()

        print(f"\n[2/5] Created {len(optimization_windows)} optimization windows:")
        for i, w in enumerate(optimization_windows):
            print(f"  Window {i+1}: {w['start'].date()} → {w['end'].date()}")

        all_window_results = []
        best_overall_config = current_config.copy()
        best_overall_sharpe = -999

        for i, window in enumerate(optimization_windows):
            print(f"\n[3/5] Optimizing window {i+1}/{len(optimization_windows)}: "
                  f"{window['start'].date()} → {window['end'].date()}")

            self.results = []
            self.best_config = None
            self.best_sharpe = -999

            window_result = self.optimize(
                market_data=market_data,
                start_date=window["start"],
                end_date=window["end"],
                max_combinations=max_combinations,
                progress_callback=progress_callback,
            )

            all_window_results.append({
                "window": window,
                "best_config": self.best_config,
                "best_sharpe": self.best_sharpe,
                "top_configs": self.get_top_configs(5),
            })

            if self.best_config is not None and self.best_sharpe > best_overall_sharpe:
                best_overall_sharpe = self.best_sharpe
                best_overall_config = self.best_config.copy()

            print(f"\n  Window {i+1} Result:")
            print(f"    Best Sharpe: {self.best_sharpe:.4f}")
            print(f"    Best Params: {self.best_config}")

        print(f"\n[4/5] Analyzing parameter stability...")

        param_stability = self._analyze_param_stability(all_window_results)

        print(f"\n  Parameter Stability Analysis:")
        print(f"  {'Parameter':<30s} {'Stability':>10s} {'Avg':>8s} {'Std':>8s}")
        print(f"  {'-'*58}")
        for param, stats in param_stability.items():
            print(f"  {param:<30s} {stats['stability']:>9.1%} "
                  f"{stats['mean']:>8.2f} {stats['std']:>8.2f}")

        print(f"\n[5/5] Finalizing optimization...")

        if has_config_changed(current_config, best_overall_config):
            print(f"\n  Parameters IMPROVED! Updating adaptive config...")
            save_adaptive_config(best_overall_config)

            save_to_history(
                best_overall_config,
                metrics={"sharpe": best_overall_sharpe, "stability": param_stability},
                window_start=start_date,
                window_end=end_date,
            )

            print(f"\n  NEW PARAMETERS APPLIED:")
            for key in ["st_fast_multiplier", "st_med_multiplier", "st_slow_multiplier",
                         "adx_threshold", "rr1", "sl_multiplier",
                         "rsi_period", "rsi_oversold", "stoch_k", "stoch_oversold",
                         "entry_zone_max_atr", "entry_zone_max_pct"]:
                old_val = current_config.get(key)
                new_val = best_overall_config.get(key)
                changed = " ← CHANGED" if old_val != new_val else ""
                print(f"    {key}: {old_val} → {new_val}{changed}")
        else:
            print(f"\n  Parameters STABLE. No changes needed.")
            save_to_history(
                current_config,
                metrics={"sharpe": best_overall_sharpe, "stability": param_stability, "status": "stable"},
                window_start=start_date,
                window_end=end_date,
            )

        self._print_rolling_summary(all_window_results, param_stability)

        return best_overall_config, all_window_results, param_stability

    def _analyze_param_stability(self, all_window_results):
        param_values = {}
        for result in all_window_results:
            if result["best_config"]:
                for param, value in result["best_config"].items():
                    if param in self.param_grid:
                        if param not in param_values:
                            param_values[param] = []
                        param_values[param].append(value)

        stability = {}
        for param, values in param_values.items():
            values_arr = np.array(values)
            mean_val = np.mean(values_arr)
            std_val = np.std(values_arr)
            cv = std_val / mean_val if mean_val != 0 else 0
            stability[param] = {
                "mean": round(float(mean_val), 4),
                "std": round(float(std_val), 4),
                "stability": round(1 - min(cv, 1), 4),
                "values": values,
            }

        return stability

    def _print_rolling_summary(self, all_window_results, param_stability):
        print(f"\n{'='*60}")
        print(f"  ROLLING OPTIMIZATION SUMMARY")
        print(f"{'='*60}\n")

        print(f"  Windows Analyzed: {len(all_window_results)}")
        print(f"\n  Window-by-Window Results:")
        print(f"  {'Window':<8s} {'Period':<25s} {'Sharpe':>8s} {'Best Config'}")
        print(f"  {'-'*75}")

        for i, result in enumerate(all_window_results):
            window = result["window"]
            period = f"{window['start'].date()} → {window['end'].date()}"
            sharpe = result["best_sharpe"]
            config_str = str(result["best_config"])[:40] + "..."
            print(f"  {i+1:<8d} {period:<25s} {sharpe:>8.4f} {config_str}")

        print(f"\n  Parameter Stability (higher = more stable):")
        for param, stats in param_stability.items():
            stability_bar = "█" * int(stats["stability"] * 20)
            print(f"  {param:<30s} {stats['stability']:>5.1%} {stability_bar}")

        most_stable = max(param_stability.items(), key=lambda x: x[1]["stability"])
        least_stable = min(param_stability.items(), key=lambda x: x[1]["stability"])

        print(f"\n  Most Stable:  {most_stable[0]} ({most_stable[1]['stability']:.1%})")
        print(f"  Least Stable: {least_stable[0]} ({least_stable[1]['stability']:.1%})")

        print(f"\n{'='*60}")

    def print_history(self, n=10):
        history = get_latest_history(n)

        if not history:
            print("  No optimization history found.")
            return

        print(f"\n{'='*60}")
        print(f"  OPTIMIZATION HISTORY (Last {len(history)} entries)")
        print(f"{'='*60}\n")

        print(f"  {'Timestamp':<22s} {'Sharpe':>8s} {'Status':<10s} {'Key Changes'}")
        print(f"  {'-'*65}")

        for entry in history:
            timestamp = entry["timestamp"][:19]
            metrics = entry.get("metrics", {})
            sharpe = metrics.get("sharpe", 0)
            status = metrics.get("status", "optimized")
            config = entry.get("config", {})

            changes = []
            for key in ["st_fast_multiplier", "st_med_multiplier", "st_slow_multiplier", "adx_threshold", "rr1"]:
                if key in config:
                    changes.append(f"{key}={config[key]}")
            changes_str = ", ".join(changes[:3])

            print(f"  {timestamp:<22s} {sharpe:>8.4f} {status:<10s} {changes_str}")

        print(f"\n{'='*60}")


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    from datetime import datetime, timedelta

    optimizer = ParameterOptimizer()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    print(f"\n{'='*60}")
    print(f"  ADAPTIVE PARAMETER OPTIMIZER")
    print(f"  Period: {start_date.date()} to {end_date.date()}")
    print(f"  Parameters: {len(optimizer.param_grid)}")
    print(f"{'='*60}\n")

    optimizer.optimize(start_date=start_date, end_date=end_date)
    optimizer.show_results()
