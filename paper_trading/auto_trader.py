"""Auto Trader — converts screener results to Google Sheets bracket orders."""

import math
from datetime import datetime

from paper_trading.config import (
    INITIAL_CAPITAL, RISK_PER_TRADE_PCT, MAX_POSITIONS, MAX_LOTS_PER_TICKER,
    TP1_PCT, TP2_PCT, TP3_PCT,
    MIN_SCORE, SETUP_MIN_SCORE, SETUP_ALLOWED_REGIMES,
    ALLOWED_TIMING, MAX_AUTO_ORDERS_PER_DAY,
    SKIP_IF_ALREADY_OPEN, SKIP_IF_ALREADY_PENDING,
    BUY_FEE, SELL_FEE, SHOW_SKIPPED,
    PENDING_ORDER_MAX_DAYS, EXCLUDED_SETUPS
)
from paper_trading.gsheets_client import GSheetsClient, _safe_float
from utils.price_utils import round_to_tick


def _clean_ticker(ticker):
    """Strip .JK suffix for matching with Google Sheets."""
    return ticker.replace(".JK", "")


def calculate_position_size(entry_price, sl_price, modal, risk_pct):
    """
    Hitung position size berdasarkan risk management.

    Returns:
        int: jumlah lot yang direkomendasikan
    """
    if entry_price <= 0 or sl_price <= 0 or entry_price <= sl_price:
        return 0

    risk_amount = modal * (risk_pct / 100)
    risk_per_share = entry_price - sl_price
    lots = math.floor(risk_amount / (risk_per_share * 100))
    return max(lots, 0)


def recalculate_tp_sl_for_target(original_price, new_entry_price, tp1, tp2, tp3, sl):
    """
    Recalculate TP/SL berdasarkan target entry price (untuk WAIT conditions).
    Jarak risk-reward dari harga asli dipertahankan.

    Args:
        original_price: Harga dari screener (Price field)
        new_entry_price: Target entry price (untuk WAIT conditions)
        tp1, tp2, tp3: Harga TP dari screener (relatif ke original_price)
        sl: Harga SL dari screener (relatif ke original_price)

    Returns:
        tuple: (new_tp1, new_tp2, new_tp3, new_sl)
    """
    if original_price <= 0 or new_entry_price <= 0:
        return tp1, tp2, tp3, sl

    # Hitung risk dan RR ratios dari harga asli
    risk = abs(original_price - sl)
    if risk <= 0:
        return tp1, tp2, tp3, sl

    rr1 = abs(tp1 - original_price) / risk
    rr2 = abs(tp2 - original_price) / risk
    rr3 = abs(tp3 - original_price) / risk

    # Apply ratios ke entry price baru
    new_sl = new_entry_price - risk
    new_tp1 = new_entry_price + risk * rr1
    new_tp2 = new_entry_price + risk * rr2
    new_tp3 = new_entry_price + risk * rr3

    return round_to_tick(new_tp1), round_to_tick(new_tp2), round_to_tick(new_tp3), round_to_tick(new_sl)


def filter_screener_results(results, open_tickers=None, pending_tickers=None,
                             today_orders=0, open_positions=0, max_positions=12):
    """
    Filter screener results berdasarkan auto-trade rules.

    Args:
        results: list of dict (screener results)
        open_tickers: set ticker yang sudah ada trade OPEN
        pending_tickers: set ticker yang sudah ada pending order
        today_orders: jumlah order yang sudah dibuat hari ini
        open_positions: jumlah posisi yang sedang open
        max_positions: maksimal posisi concurrent

    Returns:
        tuple: (to_execute, to_watch, skipped)
            - to_execute: list yang siap di-eksekusi
            - to_watch: list yang perlu di-watchlist (WAIT tanpa target)
            - skipped: list yang di-skip dengan alasan
    """
    if open_tickers is None:
        open_tickers = set()
    if pending_tickers is None:
        pending_tickers = set()

    to_execute = []
    to_watch = []
    skipped = []

    for r in results:
        ticker = r.get("Ticker", "")
        timing = r.get("Timing", "")
        timing_detail = r.get("Timing Detail", "")
        score = _safe_float(r.get("Score", 0))
        confirm_type = r.get("Timing Confirm Type", "")
        confirm_value = r.get("Timing Confirm Value")

        ticker_clean = _clean_ticker(ticker)
        setup = r.get("Setup", "")
        stock_regime = r.get("Stock Regime", "")

        # 0. Check excluded setups
        if setup in EXCLUDED_SETUPS:
            reason = f"setup '{setup}' excluded from auto-trade"
            skipped.append({"Ticker": ticker, "Setup": setup, "Score": score, "Stock Regime": stock_regime, "reason": reason, "Timing": timing, "Force_disabled": True})
            continue

        # 0b. Check per-setup market regime filter
        allowed_regimes = SETUP_ALLOWED_REGIMES.get(setup)
        if allowed_regimes and stock_regime not in allowed_regimes:
            reason = f"setup '{setup}' not allowed in {stock_regime} market"
            skipped.append({"Ticker": ticker, "Setup": setup, "Score": score, "Stock Regime": stock_regime, "reason": reason, "Timing": timing, "Force_disabled": False})
            continue

        # 1. Check timing allowed
        if timing not in ALLOWED_TIMING:
            reason = f"timing '{timing}' not allowed"
            skipped.append({"Ticker": ticker, "Setup": setup, "Score": score, "Stock Regime": stock_regime, "reason": reason, "Timing": timing, "Force_disabled": False})
            continue

        # 2. Check minimum score (per-setup override or global)
        setup_min_score = SETUP_MIN_SCORE.get(setup, MIN_SCORE)
        if score < setup_min_score:
            reason = f"score {score:.2f} < min {setup_min_score} for {setup}"
            skipped.append({"Ticker": ticker, "Setup": setup, "Score": score, "Stock Regime": stock_regime, "reason": reason, "Timing": timing, "Force_disabled": False})
            continue

        # 3. Check if already open
        if SKIP_IF_ALREADY_OPEN and ticker_clean in open_tickers:
            reason = "already has OPEN trade"
            skipped.append({"Ticker": ticker, "Setup": setup, "Score": score, "Stock Regime": stock_regime, "reason": reason, "Timing": timing, "Force_disabled": True})
            continue

        # 4. Check if already pending
        if SKIP_IF_ALREADY_PENDING and ticker_clean in pending_tickers:
            reason = "already has pending order"
            skipped.append({"Ticker": ticker, "Setup": setup, "Score": score, "Stock Regime": stock_regime, "reason": reason, "Timing": timing, "Force_disabled": True})
            continue

        # 5. Check max orders per day
        if today_orders >= MAX_AUTO_ORDERS_PER_DAY:
            reason = f"max {MAX_AUTO_ORDERS_PER_DAY} orders/day reached"
            skipped.append({"Ticker": ticker, "Setup": setup, "Score": score, "Stock Regime": stock_regime, "reason": reason, "Timing": timing, "Force_disabled": False})
            continue

        # 6. Check position limit
        if open_positions + len(to_execute) >= max_positions:
            reason = f"max positions {max_positions} reached"
            skipped.append({"Ticker": ticker, "Setup": setup, "Score": score, "Stock Regime": stock_regime, "reason": reason, "Timing": timing, "Force_disabled": False})
            continue

        # Klasifikasi berdasarkan timing
        if timing == "ENTRY_READY":
            to_execute.append(r)
            today_orders += 1
        elif timing in ("WAIT_PULLBACK", "WAIT_PRICE", "WAIT_RETEST"):
            # Punya target_price → bisa jadi limit order
            target_price = r.get("Timing Confirm Value") or r.get("Entry Zone Low")
            target_val = _safe_float(target_price, 0)
            if target_val > 0:
                to_execute.append(r)
                today_orders += 1
            else:
                to_watch.append(r)
        else:
            # WAIT_MOMENTUM, WAIT_MACD, WAIT_VOLUME, dll → watchlist
            to_watch.append(r)

    return to_execute, to_watch, skipped


def auto_create_orders(results, client=None, dry_run=False, force=False):
    """
    Auto-create bracket orders dari screener results ke Google Sheets.

    Args:
        results: list of dict dari screener (sudah di-filter)
        client: GSheetsClient instance (akan dibuat jika None)
        dry_run: jika True, hanya print tanpa benar-benar create order

    Returns:
        dict dengan summary hasil
    """
    if client is None:
        client = GSheetsClient()
        client.connect()

    # Cancel expired pending orders (older than PENDING_ORDER_MAX_DAYS)
    expired = client.cancel_expired_orders(max_days=PENDING_ORDER_MAX_DAYS)
    if expired:
        print(f"\n  ⏰ Cancelled {len(expired)} expired pending orders (>{PENDING_ORDER_MAX_DAYS} hari)")
        for e in expired:
            print(f"     ❌ {e['id']} | {e['ticker']} | {e['date']}")

    # Ambil data dari Google Sheets (setelah cancel expired)
    modal = client.get_modal()
    open_tickers = client.get_open_tickers() if SKIP_IF_ALREADY_OPEN else set()
    pending_tickers = client.get_pending_tickers() if SKIP_IF_ALREADY_PENDING else set()
    open_positions = client.count_open_positions()
    today_orders = client.count_today_orders_all()

    # Filter results
    if force:
        to_execute = list(results)
        to_watch = []
        skipped = []
    else:
        to_execute, to_watch, skipped = filter_screener_results(
            results,
            open_tickers=open_tickers,
            pending_tickers=pending_tickers,
            today_orders=today_orders,
            open_positions=open_positions,
            max_positions=MAX_POSITIONS,
        )

    # Summary
    summary = {
        "total_scanned": len(results),
        "to_execute": len(to_execute),
        "to_watch": len(to_watch),
        "skipped": len(skipped),
        "orders_created": [],
        "errors": [],
    }

    # Print header
    print(f"\n{'─' * 50}")
    print(f"  AUTO PAPER TRADING")
    print(f"{'─' * 50}")
    print(f"  Modal: Rp {modal:,.0f} | Risk: {RISK_PER_TRADE_PCT}% | Max pos: {MAX_POSITIONS}")
    print(f"  Open positions: {open_positions}/{MAX_POSITIONS}")
    print(f"  Pending orders: {len(pending_tickers)}")
    print(f"  Today orders: {today_orders}/{MAX_AUTO_ORDERS_PER_DAY}")
    print()

    # Process each result
    for r in to_execute:
        ticker = r.get("Ticker", "")
        ticker_clean = _clean_ticker(ticker)
        timing = r.get("Timing", "")
        timing_detail = r.get("Timing Detail", "")
        entry_price = round_to_tick(_safe_float(r.get("Price", 0)))
        sl = _safe_float(r.get("Stop Loss", 0))
        tp1 = _safe_float(r.get("TP1", 0))
        tp2 = _safe_float(r.get("TP2", 0))
        tp3 = _safe_float(r.get("TP3", 0))
        score = _safe_float(r.get("Score", 0))
        setup = r.get("Setup", "")
        signal = r.get("Signal", "")

        # Tentukan entry price berdasarkan timing
        if timing == "ENTRY_READY":
            # Entry di harga saat ini
            target_entry = entry_price
        else:
            # WAIT conditions → entry di target price
            target_price_raw = r.get("Timing Confirm Value") or r.get("Entry Zone Low")
            target_val = _safe_float(target_price_raw, 0)
            if target_val > 0:
                target_entry = round_to_tick(target_val)
            else:
                target_entry = entry_price

        # Recalculate TP/SL jika entry price berubah (WAIT conditions)
        if timing != "ENTRY_READY" and target_entry != entry_price:
            tp1, tp2, tp3, sl = recalculate_tp_sl_for_target(
                entry_price, target_entry, tp1, tp2, tp3, sl
            )

        # Validasi: TP harus > Entry > SL (untuk long position)
        if not (tp1 > target_entry > sl):
            skipped.append({"ticker": ticker, "reason": f"invalid TP/SL after recalc: TP1={tp1}, Entry={target_entry}, SL={sl}", "timing": timing})
            continue
        if not (tp1 < tp2 < tp3):
            skipped.append({"ticker": ticker, "reason": f"TP order invalid: {tp1}/{tp2}/{tp3}", "timing": timing})
            continue

        # Hitung position size
        qty = calculate_position_size(target_entry, sl, modal, RISK_PER_TRADE_PCT)
        qty = min(qty, MAX_LOTS_PER_TICKER)

        if qty <= 0:
            skipped.append({"ticker": ticker, "reason": "position size = 0", "timing": timing})
            continue

        # Build notes
        timing_label = "ENTRY" if timing == "ENTRY_READY" else f"LIMIT@{target_entry:.0f}"
        notes = f"Auto [{timing_label}] {setup} {signal} Score:{score:.2f}"

        # Print detail
        emoji = "✅" if timing == "ENTRY_READY" else "🟡"
        print(f"  {emoji} {timing} — {ticker} ({setup})")
        print(f"     Entry: Rp {target_entry:,.0f} | SL: Rp {sl:,.0f}")
        tp1_qty = round(qty * TP1_PCT / 100)
        tp2_qty = round(qty * TP2_PCT / 100)
        tp3_qty = qty - tp1_qty - tp2_qty

        # Validasi: semua TP qty harus minimal 1 lot
        if tp1_qty < 1 or tp2_qty < 1 or tp3_qty < 1:
            skipped.append({"ticker": ticker, "reason": f"qty terlalu kecil untuk split TP: {qty} lots (TP1={tp1_qty}, TP2={tp2_qty}, TP3={tp3_qty})", "timing": timing})
            continue

        print(f"     TP1: {tp1_qty} lots @ Rp {tp1:,.0f} | TP2: {tp2_qty} lots @ Rp {tp2:,.0f} | TP3: {tp3_qty} lots @ Rp {tp3:,.0f}")
        print(f"     Risk: {RISK_PER_TRADE_PCT}% = Rp {modal * RISK_PER_TRADE_PCT / 100:,.0f} | Qty: {qty} lots")

        if dry_run:
            print(f"     → [DRY RUN] Bracket order not created")
            summary["orders_created"].append({
                "ticker": ticker, "qty": qty, "entry": target_entry,
                "timing": timing, "dry_run": True
            })
            continue

        # Create bracket order di Google Sheets
        try:
            result = client.create_bracket_order(
                ticker=ticker_clean,
                qty=qty,
                entry_price=target_entry,
                tp1_price=tp1,
                tp2_price=tp2,
                tp3_price=tp3,
                sl_price=sl,
                tp1_pct=TP1_PCT,
                tp2_pct=TP2_PCT,
                tp3_pct=TP3_PCT,
                notes=notes,
            )
            print(f"     → Bracket order {result['order_id']} created")
            summary["orders_created"].append({
                "ticker": ticker, "qty": qty, "entry": target_entry,
                "timing": timing, "order_id": result["order_id"]
            })
            open_positions += 1
        except Exception as e:
            print(f"     → ERROR: {e}")
            summary["errors"].append({"ticker": ticker, "error": str(e)})

    # Print watchlist
    if to_watch:
        print(f"\n  {'─' * 40}")
        print(f"  WATCHLIST ({len(to_watch)} — no target price)")
        print(f"  {'─' * 40}")
        for r in to_watch:
            ticker = r.get("Ticker", "")
            timing = r.get("Timing", "")
            detail = r.get("Timing Detail", "")
            print(f"  ⏳ {ticker} — {timing}: {detail}")

    # Print skipped
    if SHOW_SKIPPED and skipped:
        print(f"\n  {'─' * 40}")
        print(f"  SKIPPED ({len(skipped)})")
        print(f"  {'─' * 40}")
        for s in skipped:
            print(f"  ⏭️  {s['ticker']} — {s['reason']}")

    # Print summary
    print(f"\n  {'─' * 40}")
    print(f"  SUMMARY")
    print(f"  {'─' * 40}")
    print(f"  Scanned: {summary['total_scanned']} | Execute: {summary['to_execute']} | Watch: {summary['to_watch']} | Skipped: {len(skipped)}")
    if summary["orders_created"]:
        print(f"  Orders created: {len(summary['orders_created'])}")
    if summary["errors"]:
        print(f"  Errors: {len(summary['errors'])}")
    print()

    summary["skipped"] = len(skipped)
    return summary
