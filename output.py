W = 76


def sep(char="-"):
    return char * W


def print_header(text):
    print()
    print(sep("="))
    print(f"  {text}")
    print(sep("="))


def print_subheader(text):
    print()
    print(sep("─"))
    print(f"  {text}")
    print(sep("─"))


def print_analysis_box(ticker, setup, stock_regime, market_regime, price,
                       entry_zone, sl_normal, sl_wide, tp_analysis,
                       timing, chart, score, adx, profit_pct, risk_pct,
                       prob_tp1, prob_tp2, prob_sl):
    print(sep("━"))
    print(f"  {ticker:<12s} | {setup:<16s} | Score: {score:<8.1f} | ADX: {adx:.1f}")
    print(f"  Price: {price:<10.2f} | Regime: {stock_regime:<8s} | IHSG: {market_regime}")
    print(sep("─"))

    # Entry Zone
    print(f"  Entry Zone   : {entry_zone['low']} - {entry_zone['high']}  ({entry_zone['strategy']})")
    print(f"  Confluence   : {entry_zone['strength']} level(s)")

    # SL
    print(f"  SL Normal     : {sl_normal}")
    print(f"  SL Wide       : {sl_wide['price']}  ({sl_wide['logic']})")

    # TP
    for ta in tp_analysis:
        print(f"  {ta['label']:<14s}: {ta['price']:<10.2f}  {ta['note']}")

    # Probabilities
    print(f"  Probabilities : TP1 {prob_tp1:<6s} | TP2 {prob_tp2:<6s} | SL {prob_sl:<6s}")

    # Risk/Reward
    print(f"  Risk/Reward   : {risk_pct:<5.2f}% risk | {profit_pct:<5.2f}% profit (TP1)")

    # Timing
    print(f"  Timing        : {timing['label']}")
    print(f"  Detail        : {timing['detail']}")

    # Chart
    print(sep("─"))
    print(f"  ── ENTRY ANALYSIS ──")
    print()
    print(chart)

    print(sep("━"))
    print()


def print_banner():
    print()
    print(sep("="))
    print("  SWING SCREENER v2 — Deep Analysis")
    print(sep("="))


def print_summary(market_regime, total_scanned, total_setups, skipped):
    print()
    print(f"  Market Regime (IHSG) : {market_regime}")
    print(f"  Stocks Scanned       : {total_scanned}")
    print(f"  Setups Found         : {total_setups}")
    print(f"  Skipped              : {skipped}")
    print(sep("="))
    print()
